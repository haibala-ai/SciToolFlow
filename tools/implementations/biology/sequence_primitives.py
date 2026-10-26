"""Small sequence primitives with explicit alphabets and no implicit repair."""
from collections import Counter


ALPHABETS = {"protein": "ACDEFGHIKLMNPQRSTVWY", "DNA": "ACGT", "RNA": "ACGU"}


def canonical_sequence(sequence, molecule_type="protein", maximum=100000):
    if molecule_type not in ALPHABETS:
        raise ValueError("molecule_type must be protein, DNA or RNA")
    if not isinstance(sequence, str):
        raise ValueError("sequence must be a string")
    value = "".join(sequence.split()).upper()
    if not 1 <= len(value) <= maximum or set(value) - set(ALPHABETS[molecule_type]):
        raise ValueError(f"Require 1..{maximum} canonical {molecule_type} symbols; no headers, gaps, stops, ambiguity or modifications")
    return value


def sequence_composition(sequence: str, molecule_type: str = "protein") -> dict:
    """Counts and fractions of a canonical sequence, including zero-count alphabet members.

    Whitespace is removed and letters uppercased. The denominator is the number
    of canonical symbols. This does not infer biological function or repair
    ambiguous/gapped input; SequenceQualityMetrics diagnoses those inputs.
    """
    value = canonical_sequence(sequence, molecule_type)
    counts = Counter(value)
    return {"molecule_type": molecule_type, "length": len(value),
            "counts": {symbol: counts[symbol] for symbol in ALPHABETS[molecule_type]},
            "fractions": {symbol: counts[symbol] / len(value) for symbol in ALPHABETS[molecule_type]},
            "denominator": "all canonical sequence symbols after whitespace removal and uppercase normalization",
            "method": "literal symbol counting; no biological inference"}


def pairwise_sequence_alignment(sequence1: str, sequence2: str, mode: str = "global",
                                molecule_type: str = "protein") -> dict:
    """Generic-score global/local pairwise alignment of two canonical sequences.

    The objective is selected explicitly: local optimizes a subsequence match,
    global aligns complete sequences. These are different objectives, not
    interchangeable similarity estimates. No substitution matrix, homology
    significance, circular rotation or sequence correspondence is inferred.
    """
    if mode not in {"global", "local"}:
        raise ValueError("mode must be global or local")
    first = canonical_sequence(sequence1, molecule_type, 10000)
    second = canonical_sequence(sequence2, molecule_type, 10000)
    if len(first) * len(second) > 20000000:
        raise ValueError("Alignment supports at most 20000000 pairwise residue cells")
    from Bio.Align import PairwiseAligner
    scores = {"match_score": 2.0, "mismatch_score": -1.0,
              "open_gap_score": -2.0, "extend_gap_score": -0.5}
    aligner = PairwiseAligner(mode=mode, **scores)
    alignment = next(iter(aligner.align(first, second)), None)
    columns = list(zip(str(alignment[0]), str(alignment[1]))) if alignment is not None else []
    compared = [(a, b) for a, b in columns if (a, b) != ("-", "-")]
    identical = sum(a == b and a != "-" for a, b in compared)
    return {"method": "Bio.Align.PairwiseAligner", "algorithm": aligner.algorithm,
            "mode": mode, "molecule_type": molecule_type, "scoring": scores,
            "score": float(alignment.score) if alignment is not None else 0.0,
            "coordinates": alignment.coordinates.tolist() if alignment is not None else [],
            "coordinate_convention": "zero-based half-open",
            "aligned_column_count": len(compared), "identical_column_count": identical,
            "identity_fraction": identical / len(compared) if compared else None,
            "identity_scope": "returned alignment only; single gaps are nonmatches; double gaps excluded",
            "alignment": str(alignment) if alignment is not None else ""}
