"""One explicit peptide-sequence to molecular-graph construction primitive."""


def peptide_to_smiles(protein: str) -> dict:
    """Construct canonical isomeric SMILES for an unmodified linear L-peptide.

    Input1..2000 canonical single-letter residues; whitespace removed and
    uppercase. RDKit MolFromFASTA(flavor=0) supplies L-amino-acid templates,
    ordinary peptide bonds, free N/C termini and its template protonation.
    No pH-state assignment, terminal capping, PTM, disulfide/cyclization,
    missing residue or 3D coordinate inference. Glycine is achiral. Return the
    molecular representation and construction metadata only; formula, average
    mass and other molecular descriptors use the Chemical primitives on the
    returned complete SMILES. Invalid/ambiguous/modified input fails explicitly.
    """
    from rdkit import Chem, rdBase
    from tools.implementations.biology.sequence_primitives import canonical_sequence

    sequence = canonical_sequence(protein, maximum=2000)
    molecule = Chem.MolFromFASTA(sequence, sanitize=True, flavor=0)
    if molecule is None:
        raise ValueError("RDKit could not construct the canonical linear peptide")
    smiles = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
    if not smiles or Chem.MolFromSmiles(smiles) is None:
        raise RuntimeError("RDKit did not return a valid molecular representation")
    return {"smiles": smiles, "sequence_length": len(sequence),
            "method": "RDKit MolFromFASTA(flavor=0), canonical isomeric MolToSmiles",
            "rdkit_version": rdBase.rdkitVersion,
            "construction": "linear unmodified L-amino-acid templates; free N/C termini; no disulfide or cyclization",
            "protonation": "RDKit template graph; no requested-pH state assignment",
            "coordinates_generated": False}
