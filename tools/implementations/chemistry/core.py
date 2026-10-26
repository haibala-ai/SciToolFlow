"""Shared parsing and conformer policies for the Chemical tools.

These helpers never infer scientific equivalence from a fingerprint or silently
normalize salts, protonation, stereochemistry, or a caller's atom inventory.
"""

import hashlib
import io
import math


def molecule(smiles, hydrogen_policy="as_parsed"):
    from rdkit import Chem

    if not isinstance(smiles, str) or not smiles.strip() or len(smiles) > 10000:
        raise ValueError("smiles must be a nonempty string of at most 10000 characters")
    if hydrogen_policy not in {"as_parsed", "explicit", "remove"}:
        raise ValueError("hydrogen_policy must be as_parsed, explicit, or remove")
    # Disallow the SMILES reader's optional trailing name rather than accidentally
    # accepting a second argument or a malformed record as molecule metadata.
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.removeHs = hydrogen_policy == "remove"
    mol = Chem.MolFromSmiles(smiles.strip(), params)
    if mol is None or not 0 < mol.GetNumAtoms() <= 500:
        raise ValueError("SMILES must encode a valid nonempty molecule of at most 500 parsed atoms")
    if hydrogen_policy == "explicit":
        mol = Chem.AddHs(mol)
    if mol.GetNumAtoms() > 1000:
        raise ValueError("Expanded molecule exceeds 1000 atoms")
    return mol


def conformer(smiles, seed=42, optimization="none", hydrogen_policy="explicit"):
    from rdkit.Chem import AllChem

    if type(seed) is not int or not -1 <= seed <= 2147483647:
        raise ValueError("seed must be -1 (random) or an integer in [0,2147483647]")
    if optimization not in {"none", "mmff", "uff"}:
        raise ValueError("optimization must be none, mmff, or uff")
    mol = molecule(smiles, hydrogen_policy)
    from rdkit import Chem
    if len(Chem.GetMolFrags(mol)) != 1:
        raise ValueError("Generated conformers require one connected molecular graph; no relative placement of disconnected components is inferred")
    options = AllChem.ETKDGv3()
    options.randomSeed = seed
    if AllChem.EmbedMolecule(mol, options) != 0:
        raise ValueError("RDKit ETKDGv3 could not generate a conformer")
    if optimization == "mmff":
        if not AllChem.MMFFHasAllMoleculeParams(mol):
            raise ValueError("MMFF parameters are unavailable for this molecule")
        status = AllChem.MMFFOptimizeMolecule(mol, maxIters=2000)
    elif optimization == "uff":
        if not AllChem.UFFHasAllMoleculeParams(mol):
            raise ValueError("UFF parameters are unavailable for this molecule")
        status = AllChem.UFFOptimizeMolecule(mol, maxIters=2000)
    else:
        status = 0
    if status != 0:
        raise ValueError(f"{optimization.upper()} optimization did not converge (status {status})")
    return mol


def finite(value):
    """Convert numeric library results to complete, finite JSON values."""
    if isinstance(value, (list, tuple)):
        return [finite(v) for v in value]
    if hasattr(value, "tolist"):
        return finite(value.tolist())
    if type(value) is int:
        return value
    if isinstance(value, (int, float)) or hasattr(value, "__float__"):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Scientific computation returned a nonfinite value")
        return result
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    # Boost.Python RDKit vectors are sequence-like without numpy's tolist().
    try:
        return [finite(v) for v in value]
    except TypeError as exc:
        raise TypeError("Unsupported scientific result type: " + type(value).__name__) from exc


def source_bytes(source, extensions=None):
    from tools.implementations.general.research_data import _public_source_path

    path = _public_source_path(source)
    if extensions and path.suffix.lower() not in extensions:
        raise ValueError("Source must use one of: " + ", ".join(sorted(extensions)))
    raw = path.read_bytes()
    if not raw or len(raw) > 25 * 1024 * 1024:
        raise ValueError("Source must be nonempty and at most 25 MiB")
    return path, raw, hashlib.sha256(raw).hexdigest()


def coordinate_inventory(source, source_format, record_index=0,
                         hydrogen_policy="as_parsed", atom_scope="all"):
    """Read source coordinates without embedding, alignment or optimization."""
    import numpy as np
    from rdkit import Chem

    if source_format not in {"sdf", "pdb"}:
        raise ValueError("source_format must be sdf or pdb")
    if type(record_index) is not int or record_index < 0:
        raise ValueError("record_index must be a nonnegative integer")
    if atom_scope != "all":
        raise ValueError("Only atom_scope=all is supported; select a source explicitly for other scopes")
    if hydrogen_policy not in {"as_parsed", "remove"}:
        raise ValueError("Coordinate sources support as_parsed or remove; no coordinates are invented for missing H")
    path, raw, sha = source_bytes(source, {".sdf"} if source_format == "sdf" else {".pdb"})
    if source_format == "pdb":
        import MDAnalysis as mda

        if hydrogen_policy != "as_parsed":
            raise ValueError("PDB uses the exact MDAnalysis parsed inventory; hydrogen_policy must be as_parsed")
        universe = mda.Universe(io.StringIO(raw.decode("ascii")), format="PDB")
        if record_index >= len(universe.trajectory):
            raise ValueError("record_index exceeds the PDB model/frame count")
        universe.trajectory[record_index]
        coords = universe.atoms.positions.astype(float)
        # Counting does not depend on guessed elements, so preserve names instead.
        symbols = list(universe.atoms.names)
        reader = "MDAnalysis PDB all topology atoms, including water and hetero atoms"
        mol = None
    else:
        supplier = Chem.ForwardSDMolSupplier(io.BytesIO(raw), removeHs=hydrogen_policy == "remove")
        mol = None
        found = False
        for index, candidate in enumerate(supplier):
            if index == record_index:
                mol, found = candidate, True
                break
        if not found:
            raise ValueError("record_index exceeds the SDF record count")
        if mol is None or mol.GetNumConformers() == 0:
            raise ValueError("Selected SDF record is invalid or lacks coordinates")
        coords = mol.GetConformer().GetPositions()
        symbols = [a.GetSymbol() for a in mol.GetAtoms()]
        reader = "RDKit SDF selected record"
    if len(coords) == 0 or len(coords) > 100000 or not np.isfinite(coords).all():
        raise ValueError("Selected source has empty, oversized or nonfinite coordinates")
    return mol, coords, {"source": str(path), "source_sha256": sha,
                        "source_format": source_format, "record_index": record_index,
                        "hydrogen_policy": hydrogen_policy, "atom_scope": atom_scope,
                        "atom_count": len(coords), "reader": reader, "coordinate_unit": "angstrom",
                        "atom_labels": symbols}


def molecular_centroid(source: str, source_format: str = "sdf", record_index: int = 0,
                       hydrogen_policy: str = "as_parsed", atom_scope: str = "all") -> dict:
    """Return the unweighted arithmetic centroid of an uploaded SDF record or PDB model.

    PDB uses every MDAnalysis topology atom, including water, hetero atoms and
    explicit hydrogen; model/frame is selected by zero-based record_index. SDF
    retains explicit H unless remove is requested. No missing atoms, generated
    conformer, mass weighting or coordinate alignment is applied.
    """
    _, coords, provenance = coordinate_inventory(source, source_format, record_index,
                                                 hydrogen_policy, atom_scope)
    return {"centroid": finite(coords.mean(axis=0)), "definition": "unweighted atom-coordinate arithmetic mean",
            "provenance": provenance}


def count_molecular_atoms(source: str, source_format: str = "smiles", record_index: int = 0,
                         hydrogen_policy: str = "as_parsed", atom_scope: str = "all",
                         count_kind: str = "all") -> dict:
    """Count a declared atom inventory: all, heavy (Z>1), or hetero (Z not 1/6).

    SMILES as_parsed retains explicitly encoded H and does not add implicit H;
    explicit expands implicit H, remove removes removable H. SDF uses the stated
    reader H policy. PDB supports only all/as_parsed/all scope and counts every
    MDAnalysis topology atom; no element guessing or hydrogen completion.
    """
    if count_kind not in {"all", "heavy", "hetero"}:
        raise ValueError("count_kind must be all, heavy, or hetero")
    if type(record_index) is not int or record_index < 0:
        raise ValueError("record_index must be a nonnegative integer")
    if source_format == "smiles":
        if record_index != 0 or atom_scope != "all":
            raise ValueError("SMILES supports record_index=0 and atom_scope=all")
        mol = molecule(source, hydrogen_policy)
        provenance = {"source_format": "smiles", "hydrogen_policy": hydrogen_policy,
                      "atom_scope": atom_scope, "record_index": 0, "atom_count": mol.GetNumAtoms()}
    else:
        mol, _, provenance = coordinate_inventory(source, source_format, record_index,
                                                   hydrogen_policy, atom_scope)
        if mol is None:
            if count_kind != "all":
                raise ValueError("PDB supports count_kind=all; element-dependent filters are not guessed")
            return {"count": provenance["atom_count"], "count_kind": count_kind, "provenance": provenance}
    count = sum(count_kind == "all" or (a.GetAtomicNum() > 1 if count_kind == "heavy"
                                        else a.GetAtomicNum() not in {1, 6}) for a in mol.GetAtoms())
    return {"count": int(count), "count_kind": count_kind, "provenance": provenance}


def transform_smiles_csv(csv_file, columns, transform, suffix, invalid_policy="error"):
    """Shared streaming adapter; cache exact input strings within this one batch only."""
    import csv
    import json
    import uuid
    from tools.implementations.general.research_data import _task_artifacts_root

    if not isinstance(columns, list) or not 1 <= len(columns) <= 16 or any(not isinstance(c, str) or not c for c in columns) or len(set(columns)) != len(columns):
        raise ValueError("columns must contain 1-16 unique nonempty names")
    if invalid_policy not in {"error", "record"}:
        raise ValueError("invalid_policy must be error or record")
    path, raw, sha = source_bytes(csv_file, {".csv"})
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames
    added = [c + suffix for c in columns]
    if not fields or len(set(fields)) != len(fields) or any(c not in fields for c in columns):
        raise ValueError("CSV must have unique headers and contain every requested column")
    if set(fields) & set(added + ["source_row_index"]):
        raise ValueError("Output columns would overwrite existing CSV fields")
    output = _task_artifacts_root() / ("chemical_rows_" + uuid.uuid4().hex + ".csv")
    cache, errors, count = {}, [], 0
    try:
        with output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["source_row_index"] + fields + added)
            writer.writeheader()
            for index, row in enumerate(reader):
                if index >= 10000 or (index + 1) * len(columns) > 10000:
                    raise ValueError("CSV is limited to 10000 transformed cells and 10000 rows")
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"Malformed CSV width at data row {index}")
                for column in columns:
                    smiles = row[column]
                    if smiles not in cache:
                        try:
                            cache[smiles] = (json.dumps(transform(smiles), separators=(",", ":"), allow_nan=False), None)
                        except (ValueError, RuntimeError) as exc:
                            cache[smiles] = ("null", str(exc))
                    value, error = cache[smiles]
                    if error:
                        if invalid_policy == "error":
                            raise ValueError(f"Invalid record at data row {index}, column {column}: {error}")
                        errors.append({"row_index": index, "column": column, "error": error})
                    row[column + suffix] = value
                row["source_row_index"] = index
                writer.writerow(row)
                count += 1
                if stream.tell() > 128 * 1024 * 1024:
                    raise ValueError("Generated CSV exceeds the 128 MiB output limit")
        if not count:
            raise ValueError("CSV has no data rows")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {"artifact": str(output), "row_count": count, "columns": columns,
            "errors": errors, "invalid_policy": invalid_policy,
            "source": str(path), "source_sha256": sha,
            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "operation_counts": {"input_cells": count * len(columns), "unique_molecule_calculations": len(cache)}}
