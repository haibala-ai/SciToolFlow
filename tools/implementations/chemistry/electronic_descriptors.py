"""Declared electronic-descriptor bundle and its CSV adapter; no model training."""

from .core import molecule, finite, transform_smiles_csv


NAMES = ["MaxEStateIndex", "MinAbsEStateIndex", "MinEStateIndex", "qed", "NumValenceElectrons",
         "NumRadicalElectrons", "MaxPartialCharge", "MinPartialCharge", "MaxAbsPartialCharge",
         "MinAbsPartialCharge", "MolLogP", "MolMR"]


def electronic_descriptors(smiles: str | None = None, descriptors: list[str] | None = None,
                           csv_file: str | None = None, columns: list[str] | None = None,
                           invalid_policy: str = "error") -> dict:
    """Compute selected RDKit electronic features from exactly one SMILES or CSV source.

    Supply exactly one of smiles or csv_file; CSV requires explicit SMILES
    columns. Both transports use the same named descriptors and scientific
    settings. CSV preserves source fields, zero-based row identity, selected
    names, SHA256 provenance and indexed invalid-cell errors in a new streamed
    artifact. Repeated exact SMILES are computed once per call. Invalid cells
    fail by default; invalid_policy=record writes null with an indexed error.
    Limits:10000 transformed cells,16 columns,25 MiB input,128 MiB output.
    Inline input rejects columns and nondefault invalid_policy. No imputation,
    training, response selection or scientific workflow is performed.

    Default names: MaxEStateIndex, MinAbsEStateIndex, MinEStateIndex, qed,
    NumValenceElectrons, NumRadicalElectrons, MaxPartialCharge, MinPartialCharge,
    MaxAbsPartialCharge, MinAbsPartialCharge, MolLogP and MolMR. descriptors may
    select a unique nonempty subset. One parsed hydrogen-suppressed molecule
    shares EState extrema, Wildman-Crippen logP/MR and one12-iteration Gasteiger
    charge assignment; missing parameters and nonfinite values fail.
    MinAbsPartialCharge follows RDKit's named descriptor: the smaller absolute
    signed minimum/maximum charge, not the minimum over every atom. QED is a
    model-defined composite, not measured drug-likeness. These features do not
    estimate experimental charge, activity or partition measurements.
    """
    if (smiles is None) == (csv_file is None):
        raise ValueError("Supply exactly one of smiles or csv_file")
    if csv_file is not None:
        result = _electronic_descriptors_csv(csv_file, columns, descriptors, invalid_policy)
        return {"input_mode": "csv", **result}
    if columns is not None or invalid_policy != "error":
        raise ValueError("columns and nondefault invalid_policy apply only to csv_file input")
    return {"input_mode": "inline", **_electronic_descriptors_inline(smiles, descriptors)}


def _electronic_descriptors_inline(smiles, descriptors=None):
    """Compute selected RDKit electronic/QED/Crippen features on one parsed molecule.

    Default is the 12-feature historical electrical-CSV bundle; descriptors may
    select unique names from NAMES. Atomic EState extrema share one EState call,
    Crippen logP/MR share one call, and partial-charge extrema share one 12-iteration
    Gasteiger assignment (missing parameters/nonfinite values fail). QED is a
    model-defined composite score, not an experimental drug-likeness result.
    MinAbsPartialCharge follows the named RDKit descriptor: the smaller absolute
    value of the signed minimum/maximum charges, not the minimum over all atoms.
    This is a declared composition of scientific descriptors, not another method
    for the same Crippen/EState quantities.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdMolDescriptors, rdPartialCharges, Descriptors, QED
    from rdkit.Chem.EState import EStateIndices
    names = NAMES if descriptors is None else descriptors
    if not isinstance(names, list) or not names or len(set(names)) != len(names) or any(n not in NAMES for n in names):
        raise ValueError("descriptors must be a unique nonempty list from: " + ", ".join(NAMES))
    mol = molecule(smiles, "remove")
    values, counts = {}, {"molecule_parses": 1, "estate_calculations": 0, "crippen_calculations": 0, "gasteiger_assignments": 0}
    if any(n in names for n in NAMES[:3]):
        indices = list(EStateIndices(mol))
        values.update(MaxEStateIndex=max(indices), MinAbsEStateIndex=min(abs(x) for x in indices), MinEStateIndex=min(indices))
        counts["estate_calculations"] = 1
    if any(n in names for n in ["MolLogP", "MolMR"]):
        logp, mr = rdMolDescriptors.CalcCrippenDescriptors(mol)
        values.update(MolLogP=logp, MolMR=mr)
        counts["crippen_calculations"] = 1
    if any("PartialCharge" in n for n in names):
        rdPartialCharges.ComputeGasteigerCharges(mol, nIter=12, throwOnParamFailure=True)
        charges = [a.GetDoubleProp("_GasteigerCharge") for a in mol.GetAtoms()]
        minimum, maximum = min(charges), max(charges)
        values.update(MaxPartialCharge=maximum, MinPartialCharge=minimum,
                      MaxAbsPartialCharge=max(abs(minimum), abs(maximum)),
                      MinAbsPartialCharge=min(abs(minimum), abs(maximum)))
        counts["gasteiger_assignments"] = 1
    if "qed" in names:
        values["qed"] = QED.qed(mol)
    if "NumValenceElectrons" in names:
        values["NumValenceElectrons"] = Descriptors.NumValenceElectrons(mol)
    if "NumRadicalElectrons" in names:
        values["NumRadicalElectrons"] = Descriptors.NumRadicalElectrons(mol)
    return {"descriptors": {name: finite(values[name]) for name in names},
            "canonical_smiles": Chem.MolToSmiles(mol), "hydrogen_policy": "remove",
            "gasteiger_iterations": 12 if counts["gasteiger_assignments"] else None,
            "operation_counts": counts, "rdkit_version": rdBase.rdkitVersion}


def _electronic_descriptors_csv(csv_file, columns, descriptors=None, invalid_policy="error"):
    """Private CSV transport over the single electronic descriptor kernel.

    Preserve all source columns, stable source_row_index, selected feature names,
    source/output SHA256 and per-cell errors when record policy is requested.
    Invalid records fail by default. Repeated exact SMILES are computed once per
    batch; rows are streamed to a unique task-local artifact, with no training or
    response selection. Limits: 10000 transformed cells and 128 MiB output.
    """
    selected = list(NAMES) if descriptors is None else descriptors
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected) or any(x not in NAMES for x in selected):
        raise ValueError("Unknown, empty or repeated descriptor names")
    result = transform_smiles_csv(csv_file, columns, lambda s: _electronic_descriptors_inline(s, selected)["descriptors"],
                                  "_electronic_descriptors", invalid_policy)
    result["descriptor_names"] = selected
    result["capability_role"] = "file adapter over MolecularElectronicDescriptors"
    return result


def electronic_descriptors_csv(csv_file: str, columns: list[str],
                                descriptors: list[str] | None = None,
                                invalid_policy: str = "error") -> dict:
    """Retired transport-only name; use MolecularElectronicDescriptors(csv_file=...)."""
    raise NotImplementedError("ElectronicDescriptorsCSV retired; use MolecularElectronicDescriptors(csv_file=csv_file, columns=columns, descriptors=descriptors, invalid_policy=invalid_policy), with smiles omitted")
