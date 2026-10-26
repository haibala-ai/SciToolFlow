"""Focused molecular inspection and shape primitives with explicit policies."""

from .core import molecule, conformer, finite, coordinate_inventory


def descriptor_value(smiles, backend, geometry=False, hydrogen_policy="remove",
                     seed=42, optimization="none"):
    """Internal typed adapter; registered wrappers select a fixed scientific descriptor."""
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdMolDescriptors
    mol = conformer(smiles, seed, optimization, hydrogen_policy) if geometry else molecule(smiles, hydrogen_policy)
    if backend == "CalcNumRotatableBonds":
        result = rdMolDescriptors.CalcNumRotatableBonds(mol, rdMolDescriptors.NumRotatableBondsOptions.Strict)
    else:
        result = getattr(rdMolDescriptors, backend)(mol)
    undefined = []
    if backend == "CalcGETAWAY":
        import math
        values = []
        for i, value in enumerate(result):
            if not math.isfinite(float(value)):
                undefined.append(i)
                values.append(None)
            else:
                values.append(float(value))
        result = values
    response = {"descriptor": backend, "value": finite(result), "canonical_smiles": Chem.MolToSmiles(mol),
            "status": "partially_undefined" if undefined else "complete",
            "undefined_component_indices": undefined,
            "undefined_policy": "GETAWAY nonfinite components are explicit null, never zero-imputed; other nonfinite results fail",
            "hydrogen_policy": hydrogen_policy, "rdkit_version": rdBase.rdkitVersion,
            "unit": {"CalcExactMolWt": "Da", "CalcPMI1": "Da*angstrom^2", "CalcPMI2": "Da*angstrom^2",
                     "CalcPMI3": "Da*angstrom^2", "CalcRadiusOfGyration": "angstrom",
                     "CalcTPSA": "angstrom^2", "CalcLabuteASA": "angstrom^2", "CalcEEMcharges": "elementary_charge",
                     "CalcInertialShapeFactor": "1/(Da*angstrom^2)",
                     "CalcCoulombMat": "RDKit Z/distance-in-angstrom descriptor convention; not an energy"}.get(backend, "descriptor-specific; see named RDKit definition"),
            "conformer": ({"method": "ETKDGv3", "seed": seed, "optimization": optimization,
                            "coordinate_unit": "angstrom"} if geometry else None)}
    if backend == "CalcCrippenDescriptors":
        response["component_labels"] = ["Wildman-Crippen logP", "Wildman-Crippen molar refractivity"]
    if backend == "BCUT2D":
        response["component_labels"] = ["mass_high", "mass_low", "Gasteiger_charge_high", "Gasteiger_charge_low",
                                        "Crippen_logP_high", "Crippen_logP_low", "Crippen_MR_high", "Crippen_MR_low"]
    if backend in {"CalcEEMcharges", "CalcCoulombMat"}:
        response["atom_inventory"] = [{"atom_index": a.GetIdx(), "element": a.GetSymbol(), "atomic_number": a.GetAtomicNum()}
                                      for a in mol.GetAtoms()]
    if backend == "CalcCoulombMat":
        response["matrix_axes"] = "backend-defined randomized Coulomb matrices; atom-axis correspondence is not verified"
    return response


def normalized_principal_moments(smiles: str, seed: int = 42,
                                 optimization: str = "none",
                                 hydrogen_policy: str = "explicit") -> dict:
    """Return dimensionless NPR1=I1/I3 and NPR2=I2/I3 for one declared conformer.

    ETKDGv3 uses seed42 by default; seed=-1 requests random embedding. optimization
    is none, mmff or uff (2000 iteration cap; missing parameters/nonconvergence
    fail). H policy is explicit/as_parsed/remove. These are shape ratios, not
    partial charges or raw principal moments. No ensemble/solution-state claim.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdMolDescriptors
    mol = conformer(smiles, seed, optimization, hydrogen_policy)
    return {"npr1": finite(rdMolDescriptors.CalcNPR1(mol)),
            "npr2": finite(rdMolDescriptors.CalcNPR2(mol)),
            "unit": "dimensionless", "canonical_smiles": Chem.MolToSmiles(mol),
            "conformer": {"method": "ETKDGv3", "seed": seed, "optimization": optimization,
                          "hydrogen_policy": hydrogen_policy}, "rdkit_version": rdBase.rdkitVersion}


def formal_charges(smiles: str) -> dict:
    """Return total and indexed per-atom integer formal charges of the parsed graph.

    Explicit H are retained, implicit H are not expanded. No partial-charge model,
    protonation adjustment, neutralization or oxidation-state inference is used.
    """
    from rdkit import Chem, rdBase
    mol = molecule(smiles)
    atoms = [{"atom_index": a.GetIdx(), "element": a.GetSymbol(),
              "formal_charge": a.GetFormalCharge()} for a in mol.GetAtoms()]
    return {"total_formal_charge": sum(a["formal_charge"] for a in atoms), "atoms": atoms,
            "canonical_smiles": Chem.MolToSmiles(mol), "rdkit_version": rdBase.rdkitVersion}


def estate_analysis(smiles: str) -> dict:
    """Return atomic EState types/indices and per-type counts/index sums together.

    This is the RDKit EState model on a hydrogen-suppressed parsed graph. Atom
    indices refer to that graph. VSA/EState surface bins are a different descriptor
    and are not substituted here. All values are complete, unrounded JSON numbers.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem.EState import EStateIndices, Fingerprinter
    from rdkit.Chem.EState.AtomTypes import TypeAtoms
    mol = molecule(smiles, "remove")
    types = TypeAtoms(mol)
    counts, sums = Fingerprinter.FingerprintMol(mol)
    # FingerprintMol computes and caches these same indices on this unchanged mol.
    indices = EStateIndices(mol, force=False)
    return {"atoms": [{"atom_index": i, "types": list(t or []), "type_status": "matched" if t else "unmatched",
                        "estate_index": finite(indices[i])}
                       for i, t in enumerate(types)],
            "type_counts": [int(x) for x in counts], "type_index_sums": finite(sums),
            "canonical_smiles": Chem.MolToSmiles(mol), "rdkit_version": rdBase.rdkitVersion}


def inspect_tautomer_query(smiles: str) -> dict:
    """Inspect a single RDKit TautomerQuery: structures, mutable indices and template bits.

    Enumerates the TautomerQuery backend's tautomer set, not a pH/solvent or dominant
    species model. Atom/bond indices refer to the input hydrogen-suppressed graph.
    Template fingerprint is for query screening and differs from the target
    screening fingerprint. Complete bit indices are returned, not an object repr.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdTautomerQuery
    mol = molecule(smiles, "remove")
    query = rdTautomerQuery.TautomerQuery(mol)
    fp = query.PatternFingerprintTemplate()
    return {"template_smiles": Chem.MolToSmiles(query.GetTemplateMolecule()),
            "tautomers": [Chem.MolToSmiles(m) for m in query.GetTautomers()],
            "modified_atom_indices": [int(i) for i in query.GetModifiedAtoms()],
            "modified_bond_indices": [int(i) for i in query.GetModifiedBonds()],
            "template_fingerprint": {"length": fp.GetNumBits(), "on_bits": list(fp.GetOnBits())},
            "rdkit_version": rdBase.rdkitVersion}


def substructure_query(smiles: str, query: str, query_format: str = "smarts",
                       use_chirality: bool = True, max_matches: int = 100,
                       tautomer_aware: bool = False) -> dict:
    """Return boolean and explicit unique atom matches for ordinary or tautomer-aware matching.

    Separate target/query parameters preserve disconnected SMILES. query_format is
    smarts or smiles. tautomer_aware=true requires query_format=smiles and uses
    RDKit TautomerQuery; false uses ordinary graph matching. Chirality is explicit.
    max_matches is 1-1000; one extra match detects truncation. No assay claim.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdTautomerQuery
    target = molecule(smiles, "remove")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("query must be a nonempty string of at most 2000 characters")
    if query_format not in {"smarts", "smiles"}:
        raise ValueError("query_format must be smarts or smiles")
    if type(use_chirality) is not bool or type(tautomer_aware) is not bool:
        raise ValueError("use_chirality and tautomer_aware must be boolean")
    if type(max_matches) is not int or not 1 <= max_matches <= 1000:
        raise ValueError("max_matches must be in [1,1000]")
    if tautomer_aware and query_format != "smiles":
        raise ValueError("Tautomer-aware matching requires query_format=smiles")
    pattern = Chem.MolFromSmarts(query) if query_format == "smarts" else molecule(query, "remove")
    if pattern is None or pattern.GetNumAtoms() == 0:
        raise ValueError("Query cannot be parsed in declared query_format")
    if tautomer_aware:
        params = Chem.SubstructMatchParameters()
        params.uniquify = True
        params.useChirality = use_chirality
        params.maxMatches = max_matches + 1
        matches = rdTautomerQuery.TautomerQuery(pattern).GetSubstructMatches(target, params)
    else:
        matches = target.GetSubstructMatches(pattern, uniquify=True,
                                             useChirality=use_chirality, maxMatches=max_matches + 1)
    return {"matched": bool(matches), "matches": [list(m) for m in matches[:max_matches]],
            "reported_match_count": min(len(matches), max_matches), "truncated": len(matches) > max_matches,
            "target_canonical_smiles": Chem.MolToSmiles(target), "query": query,
            "query_format": query_format, "use_chirality": use_chirality,
            "tautomer_aware": tautomer_aware, "rdkit_version": rdBase.rdkitVersion}


def molecular_key(smiles: str) -> dict:
    """Compute one RDKit MolKey result and return its key, stereo code and error state.

    Avalon generates a 2D CTAB; MolKey.GetKeyForCTAB supplies both fields. MolKey
    is a distinct algorithm from standard InChIKey. Backend failure/error status is
    not converted into a successful empty key.
    """
    from rdkit.Chem.MolKey import MolKey
    from rdkit.Avalon.pyAvalonTools import Generate2DCoords
    from rdkit import Chem, rdBase
    mol = molecule(smiles, "remove")
    result = MolKey.GetKeyForCTAB(Generate2DCoords(Chem.MolToSmiles(mol), True))
    if result.error or not result.mol_key:
        raise ValueError("MolKey construction failed with error code " + str(result.error))
    return {"mol_key": result.mol_key, "stereo_code": result.stereo_code,
            "error_code": int(result.error), "rdkit_version": rdBase.rdkitVersion}


def inspect_selfies(selfies: str) -> dict:
    """Return SELFIES tokens and semantic symbol count, with explicit syntax validation.

    A literal dot is retained as a disconnected-component token by split_selfies;
    symbol_count follows the installed len_selfies, including dot separators.
    Decoding validates the input, but no canonical molecular identity is inferred.
    """
    import selfies as sf
    if not isinstance(selfies, str) or not selfies or len(selfies) > 20000:
        raise ValueError("selfies must be a nonempty string of at most 20000 characters")
    decoded = sf.decoder(selfies)
    if not decoded:
        raise ValueError("SELFIES decodes to an empty structure")
    molecule(decoded)
    tokens = list(sf.split_selfies(selfies))
    return {"tokens": tokens, "symbol_count": sf.len_selfies(selfies),
            "token_count_including_separators": len(tokens), "decoded_smiles": decoded}


def rdkit_capabilities() -> dict:
    """Report RDKit version and process-wide tautomer serialization/stereo flags.

    This is a capability/configuration query; it accepts no molecule and does not
    report a molecular property. Flags are read without modification.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdTautomerQuery
    return {"rdkit_version": rdBase.rdkitVersion,
            "tautomer_query_serializable": bool(rdTautomerQuery.TautomerQueryCanSerialize()),
            "allow_nontetrahedral_chirality": bool(Chem.GetAllowNontetrahedralChirality()),
            "use_legacy_stereo_perception": bool(Chem.GetUseLegacyStereoPerception())}


def atom_pair_codes(smiles: str, atom_indices: list[int] | None = None,
                     include_chirality: bool = True) -> dict:
    """Return indexed atom-pair atom codes and decoded fields for selected or all atoms.

    Codes use RDKit GetAtomPairAtomCode; include_chirality changes their integers.
    Zero-based indices refer to the hydrogen-suppressed parsed graph. This is an
    atom code, not the code for a pair at an inferred molecular distance.
    """
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.AtomPairs.Utils import ExplainAtomCode
    mol = molecule(smiles, "remove")
    if type(include_chirality) is not bool:
        raise ValueError("include_chirality must be boolean")
    if atom_indices is None:
        atom_indices = list(range(mol.GetNumAtoms()))
    if not isinstance(atom_indices, list) or not atom_indices or any(type(i) is not int or not 0 <= i < mol.GetNumAtoms() for i in atom_indices) or len(set(atom_indices)) != len(atom_indices):
        raise ValueError("atom_indices must be null or unique valid atom indices")
    rows = []
    for i in atom_indices:
        code = rdMolDescriptors.GetAtomPairAtomCode(mol.GetAtomWithIdx(i), includeChirality=include_chirality)
        rows.append({"atom_index": i, "code": int(code),
                     "decoded": list(ExplainAtomCode(code, includeChirality=include_chirality))})
    return {"atoms": rows, "include_chirality": include_chirality}


def compare_molecular_shapes(source: str | list[str], source_format: str = "smiles", seed: int = 42,
                              optimization: str = "none", hydrogen_policy: str = "explicit",
                              conformer_policy: str = "generate") -> dict:
    """Compare 2-100 conformers by typed USRCAT/GetUSRScore, with declared geometry policy.

    source_format=smiles takes a list; sdf takes an uploaded SDF path. generate
    builds ETKDGv3 conformers with seed/optimization/H policy for both input forms.
    preserve is SDF-only, requires as_parsed H and no optimization, and uses the
    supplied coordinates unchanged. Every invalid record is an error; no silent
    filtering/re-embedding. Returns a symmetric USRCAT similarity matrix and
    explicit index mapping. Fingerprint/Tanimoto comparisons are a separate API.
    """
    import io
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdMolDescriptors
    from .core import source_bytes
    if source_format not in {"smiles", "sdf"} or conformer_policy not in {"generate", "preserve"}:
        raise ValueError("source_format must be smiles/sdf; conformer_policy must be generate/preserve")
    provenance = None
    generated = 0
    cache = {}
    def generate(smiles):
        nonlocal generated
        if seed != -1 and smiles in cache:
            return cache[smiles]
        mol = conformer(smiles, seed, optimization, hydrogen_policy)
        generated += 1
        if seed != -1:
            cache[smiles] = mol
        return mol
    if source_format == "smiles":
        if conformer_policy != "generate" or not isinstance(source, list) or not 2 <= len(source) <= 100:
            raise ValueError("SMILES source must be a list of 2-100 strings with conformer_policy=generate")
        smiles = source
        mols = [generate(s) for s in smiles]
    else:
        path, raw, sha = source_bytes(source, {".sdf"})
        originals = list(Chem.ForwardSDMolSupplier(io.BytesIO(raw), removeHs=False))
        if not 2 <= len(originals) <= 100 or any(m is None for m in originals):
            raise ValueError("SDF must contain 2-100 valid records")
        smiles = [Chem.MolToSmiles(Chem.RemoveHs(m)) for m in originals]
        if conformer_policy == "preserve":
            if hydrogen_policy != "as_parsed" or optimization != "none":
                raise ValueError("preserve requires hydrogen_policy=as_parsed and optimization=none")
            if any(m.GetNumConformers() == 0 for m in originals):
                raise ValueError("An SDF record lacks coordinates")
            mols = originals
        else:
            mols = [generate(s) for s in smiles]
        provenance = {"source": str(path), "source_sha256": sha}
    descriptor_cache = {}
    descriptors = []
    for mol in mols:
        if id(mol) not in descriptor_cache:
            descriptor_cache[id(mol)] = rdMolDescriptors.GetUSRCAT(mol)
        descriptors.append(descriptor_cache[id(mol)])
    matrix = [[0.0] * len(descriptors) for _ in descriptors]
    comparisons = 0
    for i, a in enumerate(descriptors):
        for j in range(i, len(descriptors)):
            matrix[i][j] = matrix[j][i] = finite(rdMolDescriptors.GetUSRScore(a, descriptors[j]))
            comparisons += 1
    return {"similarity_matrix": matrix, "method": "USRCAT/GetUSRScore", "records": [
                {"index": i, "canonical_smiles": s, "atom_count": mols[i].GetNumAtoms()}
                for i, s in enumerate(smiles)],
            "conformer_policy": conformer_policy, "hydrogen_policy": hydrogen_policy,
            "seed": seed if conformer_policy == "generate" else None,
            "optimization": optimization, "provenance": provenance, "rdkit_version": rdBase.rdkitVersion,
            "operation_counts": {"generated_conformers": generated, "descriptor_calculations": len(descriptor_cache),
                                 "symmetric_pair_scores": comparisons}}
