"""One declared fingerprint kernel, with comparison and file adapters."""

import csv
import hashlib
import io
import json
import math
import uuid
from functools import lru_cache

from .core import molecule, source_bytes, finite


DEFAULTS = {
    "morgan": {"radius": 2, "bits": 2048, "chirality": False, "features": False},
    "rdkit": {"bits": 2048, "min_path": 1, "max_path": 7, "bits_per_hash": 2,
              "use_hs": True, "target_density": 0.0, "min_size": 128},
    "atom_pair": {"representation": "counts", "chirality": False, "min_length": 1, "max_length": 30},
    "torsion": {"target_size": 4, "chirality": False},
    "maccs": {}, "avalon": {"bits": 512},
    "pharm2d": {"feature_definition_file": None}, "mhfp": {"permutations": 2048, "seed": 42},
    "secfp": {"bits": 2048}, "tautomer_target": {"bits": 2048},
}


def _options(algorithm, options):
    if algorithm not in DEFAULTS:
        raise ValueError("algorithm must be one of: " + ", ".join(DEFAULTS))
    if options is not None and not isinstance(options, dict):
        raise ValueError("options must be null or an object")
    unknown = set(options or {}) - set(DEFAULTS[algorithm])
    if unknown:
        raise ValueError("Unsupported options for " + algorithm + ": " + ", ".join(sorted(unknown)))
    result = {**DEFAULTS[algorithm], **(options or {})}
    for key, value in result.items():
        default = DEFAULTS[algorithm][key]
        if type(default) is bool and type(value) is not bool:
            raise ValueError(key + " must be boolean")
        if type(default) is int and (type(value) is not int or value < 0):
            raise ValueError(key + " must be a nonnegative integer")
        if type(default) is str and not isinstance(value, str):
            raise ValueError(key + " must be a string")
    for key in ["bits", "permutations"]:
        if key in result and not 64 <= result[key] <= 65536:
            raise ValueError(key + " must be in [64,65536]")
    if "radius" in result and not 0 <= result["radius"] <= 5:
        raise ValueError("radius must be in [0,5]")
    if "seed" in result and result["seed"] > 4294967295:
        raise ValueError("seed must fit an unsigned 32-bit integer")
    if algorithm == "rdkit":
        if not 1 <= result["min_path"] <= result["max_path"] <= 12:
            raise ValueError("Path bounds must satisfy 1 <= min_path <= max_path <= 12")
        if not 1 <= result["bits_per_hash"] <= 8:
            raise ValueError("bits_per_hash must be in [1,8]")
        if type(result["target_density"]) not in {int, float} or not 0 <= result["target_density"] <= 1:
            raise ValueError("target_density must be a finite number in [0,1]")
        if not 1 <= result["min_size"] <= result["bits"]:
            raise ValueError("min_size must be between 1 and bits")
    if algorithm == "atom_pair":
        if result["representation"] not in {"counts", "presence"}:
            raise ValueError("representation must be counts or presence")
        if not 1 <= result["min_length"] <= result["max_length"] <= 30:
            raise ValueError("Atom-pair length bounds must satisfy 1 <= min_length <= max_length <= 30")
    if algorithm == "torsion" and not 2 <= result["target_size"] <= 8:
        raise ValueError("target_size must be in [2,8]")
    if algorithm == "pharm2d" and result["feature_definition_file"] is not None and not isinstance(result["feature_definition_file"], str):
        raise ValueError("feature_definition_file must be null or an uploaded .fdef path")
    return result


@lru_cache(maxsize=8)
def _pharm_signature(definition):
    from rdkit.Chem import ChemicalFeatures
    from rdkit.Chem.Pharm2D import SigFactory
    factory = ChemicalFeatures.BuildFeatureFactoryFromString(definition)
    signature = SigFactory.SigFactory(factory, trianglePruneBins=False)
    signature.SetBins([(2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 100)])
    signature.Init()
    return signature


def _fingerprint(smiles, algorithm="morgan", options=None):
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors, rdMHFPFingerprint, rdTautomerQuery

    settings = _options(algorithm, options)
    mol = molecule(smiles, "remove")
    if algorithm == "morgan":
        fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(
            mol, settings["radius"], nBits=settings["bits"],
            useChirality=settings["chirality"], useFeatures=settings["features"])
    elif algorithm == "rdkit":
        fp = Chem.RDKFingerprint(mol, minPath=settings["min_path"], maxPath=settings["max_path"],
                                 fpSize=settings["bits"], nBitsPerHash=settings["bits_per_hash"],
                                 useHs=settings["use_hs"], tgtDensity=settings["target_density"],
                                 minSize=settings["min_size"])
    elif algorithm == "atom_pair":
        fp = rdMolDescriptors.GetAtomPairFingerprint(mol, minLength=settings["min_length"],
                maxLength=settings["max_length"], includeChirality=settings["chirality"])
        if settings["representation"] == "presence":
            from rdkit import DataStructs
            result = DataStructs.SparseBitVect(fp.GetLength())
            for index in fp.GetNonzeroElements():
                result.SetBit(index)
            fp = result
    elif algorithm == "torsion":
        fp = rdMolDescriptors.GetTopologicalTorsionFingerprint(
            mol, targetSize=settings["target_size"], includeChirality=settings["chirality"])
    elif algorithm == "maccs":
        fp = rdMolDescriptors.GetMACCSKeysFingerprint(mol)
    elif algorithm == "avalon":
        from rdkit.Avalon.pyAvalonTools import GetAvalonFP
        fp = GetAvalonFP(mol, nBits=settings["bits"])
    elif algorithm == "pharm2d":
        from rdkit import RDConfig
        from rdkit.Chem.Pharm2D import Generate
        from pathlib import Path
        if settings["feature_definition_file"] is None:
            definition = (Path(RDConfig.RDDataDir) / "BaseFeatures.fdef").read_text()
        else:
            _, raw, _ = source_bytes(settings["feature_definition_file"], {".fdef"})
            definition = raw.decode("utf-8")
        signature = _pharm_signature(definition)
        fp = Generate.Gen2DFingerprint(mol, signature)
    elif algorithm == "mhfp":
        fp = list(rdMHFPFingerprint.MHFPEncoder(settings["permutations"], settings["seed"]).EncodeMol(mol))
    elif algorithm == "secfp":
        fp = rdMHFPFingerprint.MHFPEncoder().EncodeSECFPMol(mol, length=settings["bits"])
    else:
        fp = rdTautomerQuery.PatternFingerprintTautomerTarget(mol, settings["bits"])
    return fp, settings, Chem.MolToSmiles(mol)


def _serialize(fp):
    if isinstance(fp, list):
        return {"representation": "minhash", "values": [int(x) for x in fp], "length": len(fp)}
    if hasattr(fp, "GetNonzeroElements"):
        return {"representation": "sparse_counts", "length": int(fp.GetLength()),
                "counts": {str(k): int(v) for k, v in sorted(fp.GetNonzeroElements().items())}}
    return {"representation": "bits", "length": int(fp.GetNumBits()),
            "on_bits": [int(x) for x in fp.GetOnBits()]}


def molecular_fingerprint(smiles: str | None = None, algorithm: str = "morgan",
                          options: dict | None = None, csv_file: str | None = None,
                          columns: list[str] | None = None, invalid_policy: str = "error") -> dict:
    """Calculate molecular fingerprints from exactly one SMILES or explicit CSV source.

    Algorithms: morgan, rdkit (path), atom_pair, torsion, maccs, avalon,
    pharm2d, mhfp, secfp, tautomer_target. options accepts only algorithm-specific
    keys, rejecting irrelevant settings. Morgan defaults radius2/2048 bits;
    rdkit defaults 2048 bits/path1-7/2 bits per hash/use_hs true/no density folding.
    atom_pair defaults un-hashed counts; presence must be explicit. Outputs use
    full sparse indices/counts or minhash values, never abbreviated NumPy text.
    No salt/tautomer/stereo normalization is applied; removable H are suppressed.

    Supply exactly one of smiles or csv_file. CSV requires 1-16 named SMILES
    columns; source fields, zero-based row identity, SHA256 provenance and full
    JSON fingerprint cells are preserved in a new streamed artifact. Exact
    repeated SMILES are computed once per CSV call. invalid_policy=error fails
    and removes a partial artifact; record writes null and indexed errors for
    invalid cells. Limits are 10000 transformed cells, 25 MiB input and128 MiB
    output. Inline mode rejects columns and nondefault invalid_policy. No model
    training, feature selection, response selection or scientific workflow is run.
    """
    if (smiles is None) == (csv_file is None):
        raise ValueError("Supply exactly one of smiles or csv_file")
    if csv_file is not None:
        result = _fingerprint_csv(csv_file, columns, algorithm, options, invalid_policy)
        return {"input_mode": "csv", **result}
    if columns is not None or invalid_policy != "error":
        raise ValueError("columns and nondefault invalid_policy apply only to csv_file input")
    from rdkit import rdBase
    fp, settings, canonical = _fingerprint(smiles, algorithm, options)
    return {"input_mode": "inline", "algorithm": algorithm, "settings": settings, "canonical_smiles": canonical,
            "fingerprint": _serialize(fp), "rdkit_version": rdBase.rdkitVersion}


def compare_molecular_fingerprints(smiles_list: list[str], algorithm: str = "morgan",
                                  options: dict | None = None, metric: str = "tanimoto",
                                  distance: bool = False) -> dict:
    """Return an explicit symmetric pairwise fingerprint similarity/distance matrix.

    Input is 2-100 SMILES records, kept separately so disconnected molecules are
    never split on dots. Supported bit/count algorithms: morgan, rdkit, atom_pair,
    torsion, maccs, avalon, pharm2d, secfp, tautomer_target; minhash MHFP is excluded.
    metric is tanimoto or dice; count vectors use RDKit's count-vector definition.
    distance=true returns 1-score. Score1 is reported normally and does not prove
    structural identity. Index labels preserve every supplied record.
    """
    from rdkit import DataStructs, rdBase
    if not isinstance(smiles_list, list) or not 2 <= len(smiles_list) <= 100:
        raise ValueError("smiles_list must contain 2-100 SMILES strings")
    if algorithm == "mhfp":
        raise ValueError("MHFP minhash needs a declared minhash comparison, not bit/count Tanimoto or Dice")
    if metric not in {"tanimoto", "dice"} or type(distance) is not bool:
        raise ValueError("metric must be tanimoto/dice; distance must be boolean")
    if any(not isinstance(s, str) for s in smiles_list):
        raise ValueError("Every smiles_list entry must be a SMILES string")
    cache = {}
    parsed = []
    for s in smiles_list:
        if s not in cache:
            cache[s] = _fingerprint(s, algorithm, options)
        parsed.append(cache[s])
    fun = DataStructs.TanimotoSimilarity if metric == "tanimoto" else DataStructs.DiceSimilarity
    matrix = [[0.0] * len(parsed) for _ in parsed]
    score_count = 0
    for i, (a, _, _) in enumerate(parsed):
        for j in range(i, len(parsed)):
            b = parsed[j][0]
            score = float(fun(a, b))
            score_count += 1
            if not math.isfinite(score):
                raise ValueError("Fingerprint comparison returned a nonfinite score")
            matrix[i][j] = matrix[j][i] = 1 - score if distance else score
    return {"matrix": matrix, "quantity": "distance" if distance else "similarity",
            "metric": metric, "algorithm": algorithm, "settings": parsed[0][1],
            "records": [{"index": i, "smiles": s, "canonical_smiles": parsed[i][2]}
                        for i, s in enumerate(smiles_list)], "rdkit_version": rdBase.rdkitVersion,
            "operation_counts": {"records": len(parsed), "fingerprint_calculations": len(cache),
                                 "symmetric_pair_scores": score_count}}


def _fingerprint_csv(csv_file, columns, algorithm="morgan", options=None, invalid_policy="error"):
    """Private CSV transport for the same MolecularFingerprint calculation.

    Keep every source field and stable source_row_index. Full fingerprints are
    JSON in new columns; no training or hidden first-three-column convention.
    Invalid records fail unless invalid_policy=record requests indexed errors.
    Exact repeated SMILES are computed once per batch. Limits: 10000 transformed
    cells, 16 columns, 25 MiB input and 128 MiB output; no silent truncation.
    """
    from .core import transform_smiles_csv
    settings = _options(algorithm, options)
    result = transform_smiles_csv(csv_file, columns, lambda s: molecular_fingerprint(s, algorithm, settings)["fingerprint"], "_fingerprint", invalid_policy)
    result.update(algorithm=algorithm, settings=settings, capability_role="file adapter over MolecularFingerprint")
    return result


def fingerprint_csv(csv_file: str, columns: list[str], algorithm: str = "morgan", options: dict | None = None, invalid_policy: str = "error") -> dict:
    """Retired transport-only public name; use MolecularFingerprint(csv_file=...)."""
    raise NotImplementedError("FingerprintCSV retired; use MolecularFingerprint(csv_file=csv_file, columns=columns, algorithm=algorithm, options=options, invalid_policy=invalid_policy), with smiles omitted")


def cluster_molecular_fingerprints(smiles_list: list[str], algorithm: str = "morgan",
                                  options: dict | None = None, threshold: float = 0.35,
                                  method: str = "butina") -> dict:
    """Cluster 2-100 molecules from declared Tanimoto distances.

    method=butina uses an RDKit Butina distance threshold; average uses SciPy
    average-linkage and a distance cut. Ward is not applied to arbitrary Tanimoto
    dissimilarities. Return actual cluster membership and record indices.
    """
    if type(threshold) not in {int, float} or not 0 <= threshold <= 1:
        raise ValueError("threshold must be a finite distance in [0,1]")
    if method not in {"butina", "average"}:
        raise ValueError("method must be butina or average")
    comparison = compare_molecular_fingerprints(smiles_list, algorithm, options, "tanimoto", True)
    matrix = comparison["matrix"]
    if method == "butina":
        from rdkit.ML.Cluster import Butina
        condensed = [matrix[i][j] for i in range(len(matrix)) for j in range(i)]
        clusters = [list(c) for c in Butina.ClusterData(condensed, len(matrix), threshold, isDistData=True)]
    else:
        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform
        labels = fcluster(linkage(squareform(matrix, checks=True), method="average"), threshold, criterion="distance")
        clusters = [[i for i, label in enumerate(labels) if label == k] for k in sorted(set(labels))]
    return {"clusters": clusters, "cluster_count": len(clusters), "method": method,
            "distance_threshold": float(threshold), "fingerprint": algorithm,
            "settings": comparison["settings"], "records": comparison["records"]}
