"""Explicit local replacements for basic calculations and missing KG implementations."""

from scitoolflow.paths import local_root, artifacts_root
import json
from pathlib import Path
import uuid


def _dna_weight(sequence, double_stranded=False, circular=False):
    from Bio.SeqUtils import molecular_weight

    sequence = "".join(sequence.split()).upper()
    if not sequence or set(sequence) - set("ACGT"):
        raise ValueError(
            "DNA molecular weight requires a non-empty, unambiguous A/C/G/T sequence"
        )
    value = molecular_weight(
        sequence, seq_type="DNA", double_stranded=double_stranded, circular=circular
    )
    return json.dumps(
        {
            "sequence": sequence,
            "molecular_weight": value,
            "units": "g/mol",
            "mass_type": "average",
            "double_stranded": double_stranded,
            "circular": circular,
            "implementation": "Bio.SeqUtils.molecular_weight",
        }
    )


def single_linear_dna_weight(sequence: str):
    """Compute average single-stranded linear DNA molecular weight, in g/mol."""
    return _dna_weight(sequence)


def single_circular_dna_weight(sequence: str):
    """Compute average single-stranded circular DNA molecular weight, in g/mol."""
    return _dna_weight(sequence, circular=True)


def double_linear_dna_weight(sequence: str):
    """Compute average double-stranded linear DNA molecular weight, in g/mol."""
    return _dna_weight(sequence, double_stranded=True)


def double_circular_dna_weight(sequence: str):
    """Compute average double-stranded circular DNA molecular weight, in g/mol."""
    return _dna_weight(sequence, double_stranded=True, circular=True)


def nucleic_acid_gc(sequence: str, window_size: int = 0, base_type: str = "DNA"):
    """Return GC percent and optional sliding windows; positions are 1-based inclusive."""
    sequence = "".join(sequence.split()).upper()
    base_type = base_type.upper()
    if base_type not in ["DNA", "RNA"]:
        raise ValueError("base_type must be DNA or RNA")
    alphabet = "ACGT" if base_type == "DNA" else "ACGU"
    if not sequence or set(sequence) - set(alphabet):
        raise ValueError(
            "GC calculation requires unambiguous bases for the requested nucleic acid type"
        )
    if not 0 <= window_size <= len(sequence):
        raise ValueError("window_size must be between zero and sequence length")

    def percent(text):
        return 100 * (text.count("G") + text.count("C")) / len(text)

    windows = (
        [
            {
                "start": index + 1,
                "end": index + window_size,
                "gc_percent": percent(sequence[index : index + window_size]),
            }
            for index in range(len(sequence) - window_size + 1)
        ]
        if window_size
        else []
    )
    return json.dumps(
        {
            "sequence": sequence,
            "base_type": base_type,
            "gc_percent": percent(sequence),
            "windows": windows,
        }
    )


def _peptide(sequence):
    sequence = "".join(sequence.split()).upper()
    if not sequence or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
        raise ValueError(
            "Expected an unmodified peptide with the 20 canonical amino acids"
        )
    return sequence


def peptide_weight(sequence: str):
    """Average molecular weight of an unmodified linear peptide with free termini, g/mol."""
    from Bio.SeqUtils import molecular_weight

    sequence = _peptide(sequence)
    return json.dumps(
        {
            "sequence": sequence,
            "molecular_weight": molecular_weight(sequence, seq_type="protein"),
            "units": "g/mol",
            "mass_type": "average",
            "implementation": "Bio.SeqUtils.molecular_weight",
        }
    )


def peptide_formula(sequence: str):
    """Molecular formula for an unmodified linear peptide with free termini, using RDKit."""
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    sequence = _peptide(sequence)
    molecule = Chem.MolFromFASTA(sequence)
    if molecule is None:
        raise ValueError("RDKit could not construct the peptide")
    return json.dumps(
        {
            "sequence": sequence,
            "formula": rdMolDescriptors.CalcMolFormula(molecule),
            "implementation": "RDKit MolFromFASTA",
        }
    )


def _embedded_molecule(smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None or not molecule.GetNumAtoms():
        raise ValueError("Expected valid, non-empty SMILES")
    molecule = Chem.AddHs(molecule)
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 42
    if AllChem.EmbedMolecule(molecule, parameters) != 0:
        raise ValueError("RDKit 3D embedding failed")
    if AllChem.MMFFHasAllMoleculeParams(molecule):
        status = AllChem.MMFFOptimizeMolecule(molecule, maxIters=1000)
        method = "ETKDGv3 + MMFF94"
    elif AllChem.UFFHasAllMoleculeParams(molecule):
        status = AllChem.UFFOptimizeMolecule(molecule, maxIters=1000)
        method = "ETKDGv3 + UFF"
    else:
        raise ValueError("No supported RDKit force field parameters for this molecule")
    if status != 0:
        raise ValueError("Force field optimization did not converge")
    return molecule, method


def coords_from_smiles(smiles: str):
    """Return one optimized RDKit 3D conformer, including explicit hydrogen atoms, in angstroms."""
    molecule, method = _embedded_molecule(smiles)
    coordinates = molecule.GetConformer().GetPositions().tolist()
    return json.dumps(
        {
            "smiles": smiles,
            "method": method,
            "coordinate_units": "angstrom",
            "atoms": [atom.GetSymbol() for atom in molecule.GetAtoms()],
            "coordinates": coordinates,
        }
    )


def smiles_to_pdb(smiles: str):
    """Save a predicted ETKDGv3/force-field molecular conformer as a local PDB file."""
    from rdkit import Chem

    molecule, method = _embedded_molecule(smiles)
    directory = artifacts_root()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("molecule_" + uuid.uuid4().hex + ".pdb")
    Chem.MolToPDBFile(molecule, str(path))
    return json.dumps(
        {
            "smiles": smiles,
            "method": method,
            "pdb_path": str(path),
            "atoms": molecule.GetNumAtoms(),
        }
    )


def local_pairwise_alignment(sequence: str):
    """True local pairwise alignment with explicit generic scores; differs from the old global needle request."""
    from Bio.Align import PairwiseAligner
    import re

    parts = [part.upper() for part in re.split(r"[^A-Za-z]+", sequence.strip()) if part]
    if len(parts) != 2:
        raise ValueError(
            "Require two sequences separated by '.', '|', ',' or whitespace"
        )
    first, second = parts
    if not first or not second or not first.isalpha() or not second.isalpha():
        raise ValueError("Require two non-empty sequences separated by '.'")
    if max(len(first), len(second)) > 10000:
        raise ValueError("Local alignment is limited to 10000 residues per sequence")
    scoring = {
        "match_score": 2.0,
        "mismatch_score": -1.0,
        "open_gap_score": -2.0,
        "extend_gap_score": -0.5,
    }
    aligner = PairwiseAligner(mode="local", **scoring)
    alignments = aligner.align(first, second)
    alignment = next(iter(alignments), None)
    return json.dumps(
        {
            "implementation": "Bio.Align.PairwiseAligner",
            "mode": "local",
            "algorithm": aligner.algorithm,
            "scoring": scoring,
            "score": alignment.score if alignment is not None else 0.0,
            "coordinates_are": "0-based half-open",
            "coordinates": (
                alignment.coordinates.tolist() if alignment is not None else []
            ),
            "alignment": str(alignment) if alignment is not None else "",
        }
    )


def aligned_sequence_similarity(sequence_group: str):
    """Pairwise percent identity/similarity for pre-aligned sequences; explicit user residue groups define similarity."""
    sequences_text, groups_text = sequence_group.split(":", 1)
    sequences = ["".join(part.split()).upper() for part in sequences_text.split(".")]
    groups = [set(group.upper()) for group in groups_text.split(",") if group]
    if (
        not 2 <= len(sequences) <= 100
        or len({len(sequence) for sequence in sequences}) != 1
    ):
        raise ValueError("Require 2-100 aligned sequences of equal length")
    if (
        not sequences[0]
        or len(sequences[0]) > 20000
        or any(set(seq) - set("ABCDEFGHIJKLMNOPQRSTUVWXYZ-") for seq in sequences)
    ):
        raise ValueError(
            "Require aligned amino acid/base letters and '-' gaps, length 1-20000"
        )
    pairs = []
    for i, first in enumerate(sequences):
        for j in range(i + 1, len(sequences)):
            positions = [
                (a, b) for a, b in zip(first, sequences[j]) if (a, b) != ("-", "-")
            ]
            denominator = len(positions)
            if not denominator:
                raise ValueError("A pair contains only double-gap columns")
            identical = sum(a == b for a, b in positions)
            similar = sum(
                a != "-"
                and b != "-"
                and (a == b or any(a in group and b in group for group in groups))
                for a, b in positions
            )
            pairs.append(
                {
                    "sequence_indices": [i + 1, j + 1],
                    "compared_columns": denominator,
                    "identity_percent": 100 * identical / denominator,
                    "similarity_percent": 100 * similar / denominator,
                }
            )
    return json.dumps(
        {
            "implementation": "local aligned-column counting",
            "residue_groups": ["".join(sorted(g)) for g in groups],
            "gap_policy": "exclude double-gap columns; single gaps count as nonmatches",
            "pairs": pairs,
        }
    )
