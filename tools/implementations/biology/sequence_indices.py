"""Independent sequence indices retained after retiring the broad ProtParam report.

Method/table reference: https://web.expasy.org/protparam/protparam-doc.html
Only the first encoded residue is used by the N-end-rule lookup. No terminal
processing, initiator-Met cleavage, modification or experimental state is inferred.
"""

REFERENCE = "https://web.expasy.org/protparam/protparam-doc.html"


def protein_instability_index(sequence: str) -> dict:
    """Guruprasad DIWV instability index only; not measured stability or half-life.

    Canonical unmodified protein,2..100000 residues. BioPython implements
    (10/length)*sum of adjacent dipeptide instability weights. The original
    empirical below/above40 interpretation is reported only as a heuristic;
    no sample degradation rate, melting temperature or activity is inferred.
    """
    import Bio
    from Bio.SeqUtils.ProtParam import ProteinAnalysis
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence)
    if len(sequence) < 2:
        raise ValueError("Instability index requires at least one dipeptide")
    value = float(ProteinAnalysis(sequence).instability_index())
    return {"instability_index": value, "sequence_length": len(sequence),
            "method": "Guruprasad et al.1990 adjacent-dipeptide DIWV index",
            "backend": "Bio.SeqUtils.ProtParam.ProteinAnalysis.instability_index",
            "biopython_version": Bio.__version__, "units": "dimensionless empirical index",
            "original_heuristic_category": "below40" if value < 40 else "above40" if value > 40 else "at40",
            "interpretation": "Original below40/above40 stable/possibly-unstable rule is an empirical index classification, not measured sample stability or a half-life estimate",
            "reference": REFERENCE, "experimental_stability_verified": False}


def protein_aliphatic_index(sequence: str) -> dict:
    """Ikai residue-composition aliphatic index only, not molecular Csp3 or temperature.

    Canonical unmodified protein,1..100000 residues. Uses molar percentages of
    A,V,I,L and fixed relative-volume coefficients2.9 for V and3.9 for I/L.
    Values can exceed100; this empirical index is not a probability or a
    calibrated melting-temperature prediction.
    """
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence)
    value = 100.0 * (sequence.count("A") + 2.9 * sequence.count("V")
                     + 3.9 * (sequence.count("I") + sequence.count("L"))) / len(sequence)
    return {"aliphatic_index": value, "sequence_length": len(sequence),
            "method": "Ikai1980 residue-composition relative-side-chain-volume index",
            "formula": "100*(n_A+2.9*n_V+3.9*(n_I+n_L))/sequence_length",
            "units": "dimensionless empirical index; not bounded by100",
            "reference": REFERENCE, "experimental_thermostability_verified": False}


# ExPASy ProtParam's published N-end-rule table. Tuple order is mammalian
# reticulocytes in vitro, yeast in vivo, E.coli in vivo. Preserve inequality
# and the explicitly unknown Pro/E.coli cell; never fill it with >10hours.
_HALF_LIFE = {
    "A": ((4.4,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
    "R": ((1,"hour","table_point"),(2,"minute","table_point"),(2,"minute","table_point")),
    "N": ((1.4,"hour","table_point"),(3,"minute","table_point"),(10,"hour","greater_than")),
    "D": ((1.1,"hour","table_point"),(3,"minute","table_point"),(10,"hour","greater_than")),
    "C": ((1.2,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
    "Q": ((0.8,"hour","table_point"),(10,"minute","table_point"),(10,"hour","greater_than")),
    "E": ((1,"hour","table_point"),(30,"minute","table_point"),(10,"hour","greater_than")),
    "G": ((30,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
    "H": ((3.5,"hour","table_point"),(10,"minute","table_point"),(10,"hour","greater_than")),
    "I": ((20,"hour","table_point"),(30,"minute","table_point"),(10,"hour","greater_than")),
    "L": ((5.5,"hour","table_point"),(3,"minute","table_point"),(2,"minute","table_point")),
    "K": ((1.3,"hour","table_point"),(3,"minute","table_point"),(2,"minute","table_point")),
    "M": ((30,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
    "F": ((1.1,"hour","table_point"),(3,"minute","table_point"),(2,"minute","table_point")),
    "P": ((20,"hour","greater_than"),(20,"hour","greater_than"),(None,None,"unknown")),
    "S": ((1.9,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
    "T": ((7.2,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
    "W": ((2.8,"hour","table_point"),(3,"minute","table_point"),(2,"minute","table_point")),
    "Y": ((2.8,"hour","table_point"),(10,"minute","table_point"),(2,"minute","table_point")),
    "V": ((100,"hour","table_point"),(20,"hour","greater_than"),(10,"hour","greater_than")),
}
_SYSTEMS = {"mammalian_reticulocyte_in_vitro": 0, "yeast_in_vivo": 1, "E_coli_in_vivo": 2}


def protein_n_terminal_half_life(sequence: str, system: str) -> dict:
    """One ExPASy N-end-rule table estimate for an explicitly selected model system.

    Canonical unmodified encoded sequence,1..100000 residues. The first supplied
    residue is used literally; no initiator-Met removal or mature-chain/PTM
    inference. system is mammalian_reticulocyte_in_vitro, yeast_in_vivo, or
    E_coli_in_vivo. Table points are empirical estimates; greater_than retains
    a strict lower bound, and Pro/E.coli remains unknown with null value/unit.
    This does not predict sample-specific or general human cellular half-life.
    """
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence)
    if not isinstance(system, str) or system not in _SYSTEMS:
        raise ValueError("Choose an explicit supported N-end-rule model system")
    value, units, relation = _HALF_LIFE[sequence[0]][_SYSTEMS[system]]
    return {"n_terminal_residue": sequence[0], "system": system,
            "half_life": {"value": value, "units": units, "relation": relation},
            "method": "ExPASy published N-end-rule first-encoded-residue table",
            "n_terminal_policy": "First supplied encoded residue; no cleavage, terminal blocking, PTM or mature-chain inference",
            "reference": REFERENCE, "reference_table_checked": "2026-10-22",
            "experimental_half_life_verified": False}
