"""Explicit local contracts for five KG tools absent from the upstream implementation."""
from scitoolflow.paths import local_root, artifacts_root
import json
from pathlib import Path
import random
import uuid

ROOT = local_root()
AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"

# Common names a caller may reasonably use, mapped to the ExPASy rule that implements them.
ENZYME_ALIASES = {
    "trypsin": "trypsin",
    "trypsin/p": "trypsin",
    "trypsinp": "trypsin",
    "chymotrypsin": "chymotrypsin high specificity",
    "chymotrypsin high specificity": "chymotrypsin high specificity",
    "chymotrypsin low specificity": "chymotrypsin low specificity",
    "lys-c": "lys-c",
    "lysc": "lys-c",
    "lys-n": "lys-n",
    "lysn": "lys-n",
    "arg-c": "arg-c",
    "argc": "arg-c",
    "asp-n": "asp-n",
    "aspn": "asp-n",
    "glu-c": "glutamyl endopeptidase",
    "gluc": "glutamyl endopeptidase",
    "glutamyl endopeptidase": "glutamyl endopeptidase",
    "pepsin": "pepsina",
    "pepsina": "pepsina",
    "thermolysin": "thermolysin",
    "cnbr": "cnbr",
    "cyanogen bromide": "cnbr",
    "formic acid": "formic acid",
    "hydroxylamine": "hydroxylamine",
    "iodosobenzoate": "iodosobenzoate",
    "proline endopeptidase": "proline endopeptidase",
    "staphylococcal protease": "staphylococcal protease",
    "v8 protease": "staphylococcal protease",
    "no cleavage": "no cleavage",
    "unspecific cleavage": "unspecific cleavage",
}


def resolve_enzyme(enzyme, rules):
    """Accept the common enzyme names as well as the exact ExPASy rule keys."""
    key = str(enzyme).strip()
    if key in rules:
        return key
    alias = ENZYME_ALIASES.get(key.lower())
    if alias and alias in rules:
        return alias
    raise ValueError("Unsupported enzyme '%s'. Use one of: %s"
                     % (enzyme, ", ".join(sorted(set(ENZYME_ALIASES) & set(rules))))) 


def _sequence(sequence):
    value = "".join(str(sequence).split()).upper()
    # A translated protein may carry a terminal stop symbol; it is not a residue.
    value = value.rstrip("*")
    if not value or len(value) > 10000 or set(value) - set(AMINO_ACIDS):
        raise ValueError("Require 1..10000 canonical amino acids; no ambiguous or modified residues; "
                         "a trailing stop symbol is accepted and ignored")
    return value


def generate_random_sequence(length: int = None, sequence: str = "", seed: int = 42):
    """Uniform independent canonical amino acids, specified length or template length; seeded, no biological design claim."""
    if length is None:
        length = len(_sequence(sequence))
    elif sequence:
        raise ValueError("Specify length or a sequence template, not both")
    if not 1 <= length <= 10000:
        raise ValueError("Require integer length 1..10000")
    rng = random.Random(seed)
    result = "".join(rng.choice(AMINO_ACIDS) for _ in range(length))
    return json.dumps({"sequence": result, "length": length, "seed": seed,
                       "method": "uniform independent sampling of 20 canonical amino acids"})


def _digest(sequence, enzyme, missed_cleavages):
    from pyteomics import parser
    sequence = _sequence(sequence)
    enzyme = resolve_enzyme(enzyme, parser.expasy_rules)
    if not 0 <= missed_cleavages <= 5:
        raise ValueError("Require 0..5 missed cleavages")
    peptides = list(parser.icleave(sequence, parser.expasy_rules[enzyme], missed_cleavages=missed_cleavages))
    return sequence, enzyme, [{"sequence": peptide, "start": start, "end": start + len(peptide)}
                              for start, peptide in peptides]


def cut_peptide(sequence: str, enzyme: str = "trypsin", missed_cleavages: int = 0):
    """Rule-based potential protease cleavage; ExPASy regex rules, zero-based half-open peptide coordinates."""
    sequence, enzyme, peptides = _digest(sequence, enzyme, missed_cleavages)
    return json.dumps({"method": "Pyteomics ExPASy sequence cleavage rules", "enzyme": enzyme,
                       "sequence": sequence, "missed_cleavages": missed_cleavages,
                       "coordinate_convention": "zero-based half-open", "peptides": peptides,
                       "experimental_cleavage_verified": False})


def predict_peptide_mass(sequence: str, enzyme: str = "trypsin", missed_cleavages: int = 0):
    """Digest canonical unmodified protein and calculate neutral monoisotopic peptide masses with free termini."""
    from pyteomics import mass
    sequence, enzyme, peptides = _digest(sequence, enzyme, missed_cleavages)
    for peptide in peptides:
        peptide["neutral_monoisotopic_mass_dalton"] = mass.fast_mass(peptide["sequence"], ion_type="M", charge=0)
    return json.dumps({"method": "Pyteomics ExPASy cleavage and elemental monoisotopic mass",
                       "enzyme": enzyme, "sequence": sequence, "missed_cleavages": missed_cleavages,
                       "coordinate_convention": "zero-based half-open", "mass_units": "Da",
                       "modifications": "none; linear peptides with free N/C termini", "peptides": peptides})


def redundancy_reduction(sequences: list[str], identity_threshold: float = 1.0):
    """Greedy sequence clustering by global alignment identity; first representative retained, input order matters."""
    from Bio.Align import PairwiseAligner
    if not 1 <= len(sequences) <= 100 or not 0 < identity_threshold <= 1:
        raise ValueError("Require 1..100 sequences and identity threshold in (0,1]")
    values = [_sequence(sequence) for sequence in sequences]
    if any(len(sequence) > 2000 for sequence in values):
        raise ValueError("Clustering supports at most 2000 residues per sequence")
    aligner = PairwiseAligner(mode="global", match_score=2, mismatch_score=-1,
                             open_gap_score=-2, extend_gap_score=-0.5)
    clusters = []
    for index, sequence in enumerate(values):
        for cluster in clusters:
            representative = values[cluster["representative_index"]]
            if identity_threshold == 1:
                identity = float(sequence == representative)
            else:
                alignment = aligner.align(representative, sequence)[0]
                a, b = alignment[0], alignment[1]
                identity = sum(x == y and x != "-" for x, y in zip(a, b)) / len(a)
            if identity >= identity_threshold:
                cluster["members"].append({"index": index, "identity_to_representative": identity})
                break
        else:
            clusters.append({"representative_index": index, "sequence": sequence,
                             "members": [{"index": index, "identity_to_representative": 1.0}]})
    return json.dumps({"method": "input-order greedy global-alignment identity clustering",
                       "identity_definition": "identical non-gap columns / all aligned columns including gaps",
                       "alignment_scoring": {"match": 2, "mismatch": -1, "gap_open": -2, "gap_extend": -0.5},
                       "identity_threshold": identity_threshold, "input_count": len(values), "clusters": clusters})


def draw_protein_structure(structure_file: str):
    """Render C-alpha backbone of first PDB/mmCIF model to PNG; chain-separated lines in angstroms."""
    from Bio.PDB import PDBParser, MMCIFParser
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    path = Path(structure_file)
    if not path.is_file() or path.stat().st_size > 30_000_000:
        raise ValueError("Require existing PDB/mmCIF <=30MB")
    parser = MMCIFParser(QUIET=True) if path.suffix.lower() in [".cif", ".mmcif"] else PDBParser(QUIET=True)
    model = next(parser.get_structure("input", str(path)).get_models())
    figure = plt.figure(figsize=(8, 8))
    axes = figure.add_subplot(111, projection="3d")
    chains, coordinates = [], []
    try:
        for chain in model:
            fragments, fragment = [], []
            for residue in chain:
                if "CA" not in residue or residue.id[0] != " ":
                    if fragment:
                        fragments.append(fragment); fragment = []
                    continue
                point = residue["CA"].coord
                if not np.isfinite(point).all():
                    raise ValueError("Non-finite structure coordinates")
                if fragment and np.linalg.norm(point - fragment[-1]) > 5.0:
                    fragments.append(fragment); fragment = []
                fragment.append(point); coordinates.append(point)
            if fragment:
                fragments.append(fragment)
            if fragments:
                chains.append({"chain": chain.id, "ca_residues": sum(map(len, fragments))})
                for i, points in enumerate(fragments):
                    arr = np.asarray(points)
                    axes.plot(*arr.T, linewidth=1.5, marker=".", markersize=2,
                              label="Chain " + chain.id if i == 0 else None)
        if not coordinates:
            raise ValueError("No protein C-alpha atoms found")
        arr = np.asarray(coordinates)
        center = (arr.max(axis=0) + arr.min(axis=0)) / 2
        radius = max(float(np.ptp(arr, axis=0).max()) / 2, 1)
        for setter, value in zip([axes.set_xlim, axes.set_ylim, axes.set_zlim], center):
            setter(value-radius, value+radius)
        axes.set_box_aspect((1, 1, 1))
        axes.set(xlabel="X (angstrom)", ylabel="Y (angstrom)", zlabel="Z (angstrom)", title="Protein C-alpha backbone")
        axes.legend()
        directory = artifacts_root() / ("protein_plot_" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        image = directory / "structure.png"
        figure.savefig(image, dpi=200, bbox_inches="tight")
    finally:
        plt.close(figure)
    return json.dumps({"image": str(image), "input_structure": str(path), "model_index": 0,
                       "method": "C-alpha backbone diagram with gaps >5 angstrom disconnected", "chains": chains})
