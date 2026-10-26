"""Explicit local replacements for basic calculations and missing KG implementations."""

from src.utils.paths import local_root, artifacts_root
import json
from pathlib import Path
import uuid


def _dna_weight(sequence, double_stranded=False, circular=False):
    from Bio.SeqUtils import molecular_weight
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    if type(double_stranded) is not bool or type(circular) is not bool:
        raise ValueError("double_stranded and circular must be strict booleans")
    sequence = canonical_sequence(sequence, "DNA")
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


def dna_molecular_weight(sequence: str, double_stranded: bool = False, circular: bool = False):
    """Average DNA molar mass with explicit strand and end-group topology assumptions.

    Canonical unambiguous DNA only, 1..100000 bases; whitespace removed and
    uppercase. Biopython average molecular weights, not monoisotopic masses.
    For double-stranded DNA the complementary strand is included. Circularity
    changes terminal-water accounting. No ligation, purity or modification
    inference. Invalid symbols or non-Boolean flags raise ValueError.
    """
    return _dna_weight(sequence, double_stranded, circular)


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
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    if not isinstance(base_type, str):
        raise ValueError("base_type must be DNA or RNA")
    base_type = base_type.upper()
    if base_type not in ["DNA", "RNA"]:
        raise ValueError("base_type must be DNA or RNA")
    sequence = canonical_sequence(sequence, base_type)
    if type(window_size) is not int or not 0 <= window_size <= len(sequence):
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
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    return canonical_sequence(sequence)


def peptide_weight(sequence: str):
    """Retired sequence-only wrapper of average molecular mass."""
    raise NotImplementedError("PeptideWeightCalculator retired; use ConvertingPeptide2SMILES then SMILESToWeight. RDKit atomic weights differ from the old Biopython residue table; no digitwise equivalence is claimed")


def peptide_formula(sequence: str):
    """Retired input adapter of the shared RDKit molecular-formula kernel."""
    raise NotImplementedError("PeptideFormulaCalculator retired; use ConvertingPeptide2SMILES then GetMolFormula on its complete SMILES")


def _embedded_molecule(smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    if not isinstance(smiles, str) or not smiles.strip() or len(smiles) > 100000:
        raise ValueError("Require a nonempty SMILES string of at most100000characters")
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None or not molecule.GetNumAtoms():
        raise ValueError("Expected valid, non-empty SMILES")
    if len(Chem.GetMolFrags(molecule)) != 1:
        raise ValueError("Conformer generation requires one connected molecule; disconnected components have no defined relative placement")
    molecule = Chem.AddHs(molecule)
    if molecule.GetNumAtoms() > 1000:
        raise ValueError("Conformer generation supports at most1000atoms including hydrogens")
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


def generate_molecular_conformer(smiles: str, output_format: str = "coordinates"):
    """Generate one seed42 ETKDGv3 conformer, optimized by MMFF94 or UFF.

    Require one connected molecule; disconnected components have no defined
    relative placement. output_format is coordinates, pdb or both. Explicit H atoms are included;
    coordinates are angstroms. This is a predicted conformer, not a unique
    solution, binding pose or experimentally determined structure. Unsupported
    force fields, embedding failure or nonconvergence raise errors. PDB output
    writes only a new task artifact and may round coordinate precision.
    """
    if output_format not in {"coordinates", "pdb", "both"}:
        raise ValueError("output_format must be coordinates, pdb or both")
    from rdkit import Chem
    import numpy as np
    molecule, method = _embedded_molecule(smiles)
    coordinates = molecule.GetConformer().GetPositions()
    if not np.isfinite(coordinates).all():
        raise RuntimeError("Conformer contains nonfinite coordinates")
    result = {"smiles": smiles, "method": method, "random_seed": 42,
              "coordinate_units": "angstrom", "atom_count": molecule.GetNumAtoms(),
              "hydrogen_policy": "explicit hydrogens added by RDKit",
              "experimental_structure": False}
    if output_format in {"coordinates", "both"}:
        result.update(atoms=[atom.GetSymbol() for atom in molecule.GetAtoms()],
                      coordinates=coordinates.tolist())
    if output_format in {"pdb", "both"}:
        directory = artifacts_root()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ("conformer_" + uuid.uuid4().hex + ".pdb")
        Chem.MolToPDBFile(molecule, str(path))
        result["pdb_path"] = str(path)
    return json.dumps(result, allow_nan=False)


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
    if not isinstance(sequence_group, str) or len(sequence_group) > 2100000:
        raise ValueError("Require a bounded aligned sequence text string")
    text = sequence_group.strip()
    groups = []
    if text.startswith(">"):
        from Bio import SeqIO
        from io import StringIO

        sequences = [str(record.seq).upper() for record in SeqIO.parse(StringIO(text), "fasta")]
    elif text.startswith(("!!AA_MULTIPLE_ALIGNMENT", "!!NA_MULTIPLE_ALIGNMENT", "PileUp")):
        from Bio import AlignIO
        from io import StringIO

        sequences = [str(record.seq).upper() for record in AlignIO.read(StringIO(text), "msf")]
    else:
        if ":" not in text:
            raise ValueError(
                "Use aligned FASTA, GCG/MSF, or legacy SEQUENCE1.SEQUENCE2:GROUP1,GROUP2; "
                "an empty legacy group suffix is allowed"
            )
        sequences_text, groups_text = text.split(":", 1)
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
