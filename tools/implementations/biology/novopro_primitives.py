"""Precisely scoped NovoPro operations; failures are never scientific results."""
import math

from tools.implementations.biology.sequence_primitives import canonical_sequence
from tools.implementations.biology.novopro_current import _request


def _result(payload):
    response = _request(payload)
    if not isinstance(response, list) or len(response) < 2 or response[0] != 1:
        raise RuntimeError("Unexpected NovoPro result schema")
    return response[1]


def _finite(value, label):
    if isinstance(value, bool):
        raise RuntimeError(f"Invalid remote {label}")
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise RuntimeError(f"Invalid remote {label}") from error
    if not math.isfinite(number):
        raise RuntimeError(f"Nonfinite remote {label}")
    return number


def hydrophilicity_profile(sequence: str) -> dict:
    """Request NovoPro hp residue scores with explicit sparse-position coverage.

    The provider does not disclose its score scale/model/version here. Scores
    are retained as a provider profile, not called ExPASy ProtScale, GRAVY or a
    calibrated prediction. Canonical unmodified protein only, <=10000 residues.
    Remote failure, missing scores or malformed/out-of-range positions raise.
    """
    sequence = canonical_sequence(sequence, maximum=10000)
    raw = _result({"sr": "hp", "sq": sequence})
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError("NovoPro hp returned no position scores")
    scores = []
    for position, value in raw.items():
        if not isinstance(position, str) or not position.isdecimal() or not 1 <= int(position) <= len(sequence):
            raise RuntimeError("NovoPro hp returned an invalid sequence position")
        index = int(position)
        scores.append({"position": index, "residue": sequence[index - 1],
                       "score": _finite(value, "hydrophilicity score")})
    if len({row["position"] for row in scores}) != len(scores):
        raise RuntimeError("NovoPro hp returned duplicate normalized positions")
    scores.sort(key=lambda row: row["position"])
    positions = {row["position"] for row in scores}
    return {"provider": "NovoPro hp", "model_and_scale": "not disclosed by provider",
            "sequence_length": len(sequence), "coordinate_convention": "one-based residue positions",
            "scores": scores, "scored_position_count": len(scores),
            "unscored_positions": [i for i in range(1, len(sequence) + 1) if i not in positions]}


def optimize_codons(sequence: str, input_type: str = "DNA", host: str = "E.coli") -> dict:
    """Request one NovoPro codon optimization with explicit DNA/protein input and host.

    RNA, ambiguous symbols, modifications and partial DNA codons are unsupported.
    Host is forwarded literally (1..100 characters); upstream may reject an
    unsupported host. The objective/model/version is provider-defined. CAI/GC
    are returned provider descriptors, not experimental expression outcomes.
    """
    if input_type not in {"DNA", "protein"}:
        raise ValueError("input_type must be DNA or protein; RNA is unsupported")
    sequence = canonical_sequence(sequence, input_type, 10000)
    if input_type == "DNA" and len(sequence) % 3:
        raise ValueError("DNA input must consist of complete codons")
    if not isinstance(host, str) or not 1 <= len(host.strip()) <= 100:
        raise ValueError("host must be a nonempty string of at most100characters")
    raw = _result({"sr": "co", "sq": sequence,
                   "st": "Protein" if input_type == "protein" else "DNA",
                   "og": host.strip(), "ez": ""})
    if not isinstance(raw, list) or len(raw) < 9 or not isinstance(raw[0], str):
        raise RuntimeError("Unexpected NovoPro codon result schema")
    optimized = canonical_sequence(raw[0], "DNA", 30000)
    if len(optimized) % 3:
        raise RuntimeError("NovoPro optimized DNA is not a complete codon sequence")
    return {"provider": "NovoPro co", "input_type": input_type, "host": host.strip(),
            "optimized_dna": optimized, "cai_before": _finite(raw[1], "CAI before"),
            "cai_after": _finite(raw[2], "CAI after"),
            "gc_percent_before": _finite(raw[7], "GC before"),
            "gc_percent_after": _finite(raw[8], "GC after"),
            "model_and_objective": "provider-defined; version not disclosed",
            "experimental_expression_verified": False}


def oligonucleotide_properties(sequence: str) -> dict:
    """Retired composite; select melting-temperature or absorbance properties."""
    raise NotImplementedError(
        "OligonucleotideProperties is retired. Select OligonucleotideMeltingTemperature "
        "or OligonucleotideAbsorbanceProperties; use NucleicAcidGCCalculator for GC. "
        "The former provider mass has unknown end-group assumptions and has no "
        "automatic DNAMolecularWeight migration."
    )


def _oligonucleotide_result(sequence):
    """One provider call; expose only fields selected by the requesting primitive."""
    sequence = canonical_sequence(sequence, "DNA", 10000)
    raw = _result({"sr": "oc", "sq": sequence, "mod": "::"})
    if not isinstance(raw, list) or len(raw) < 12:
        raise RuntimeError("Unexpected NovoPro oligonucleotide result schema")
    return sequence, raw


def oligonucleotide_melting_temperature(sequence: str) -> dict:
    """Two provider Tm endpoints only for one unmodified canonical DNA oligo.

    Canonical ACGT,1..10000 bases; uppercase/whitespace normalized. Salt,
    concentration, equations and endpoint identities are undisclosed. Preserve
    provider order without calling these minimum/maximum or assigning methods.
    No validated PCR annealing temperature, GC or molecular mass is returned.
    """
    sequence, raw = _oligonucleotide_result(sequence)
    return {"provider": "NovoPro oc", "length": len(sequence), "modifications": "none",
            "tm_endpoints_celsius": [_finite(raw[8], "Tm endpoint"), _finite(raw[9], "Tm endpoint")],
            "endpoint_order": "provider fields8 and9; endpoint identities/methods not disclosed",
            "tm_conditions_and_equation": "salt, concentration and equation not disclosed by provider",
            "experimental_melting_verified": False}


def oligonucleotide_absorbance_properties(sequence: str) -> dict:
    """One provider's epsilon260 and OD260 conversions for an unmodified DNA oligo.

    Canonical ACGT,1..10000 bases; uppercase/whitespace normalized. Preserve
    epsilon and provider nmol/microgram per OD260 at1ml. The provider's base
    extinction model and end-group mass assumptions are undisclosed; no mass
    descriptor, measured concentration or equivalence to DNAMolecularWeight.
    """
    sequence, raw = _oligonucleotide_result(sequence)
    return {"provider": "NovoPro oc", "length": len(sequence), "modifications": "none",
            "extinction_coefficient_M_inv_cm_inv": _finite(raw[7], "extinction coefficient"),
            "nmol_per_OD260_1ml": _finite(raw[10], "nmol/OD260"),
            "microgram_per_OD260_1ml": _finite(raw[11], "microgram/OD260"),
            "wavelength_nm": 260,
            "extinction_and_end_group_model": "provider-defined; base extinction model and end-group mass assumptions not disclosed",
            "experimental_concentration_verified": False}


def find_sequence_repeats(sequence: str, molecule_type: str = "DNA", minimum_length: int = 2) -> dict:
    """NovoPro direct/inverted repeat search, with explicit molecule type and length.

    Canonical DNA or protein only, <=10000 symbols. Upstream inversion/matching
    rules are not locally implemented; outputs preserve provider groups. Every
    position is converted from provider zero-based to one-based coordinates.
    """
    if molecule_type not in {"DNA", "protein"}:
        raise ValueError("molecule_type must be DNA or protein")
    sequence = canonical_sequence(sequence, molecule_type, 10000)
    if type(minimum_length) is not int or not 1 <= minimum_length <= len(sequence):
        raise ValueError("minimum_length must be an integer within sequence length")
    raw = _result({"sr": "rs", "st": "DNA" if molecule_type == "DNA" else "Protein",
                   "sq": sequence, "ml": minimum_length, "ln": len(sequence)})
    if not isinstance(raw, dict) or not all(k in raw for k in ("direct", "inverted")):
        raise RuntimeError("Unexpected NovoPro repeat-search schema")
    groups = {}
    for kind in ("direct", "inverted"):
        if not isinstance(raw[kind], list):
            raise RuntimeError("Invalid repeat group")
        rows = []
        for item in raw[kind]:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise RuntimeError("Invalid repeat item")
            motif, positions = item
            if not isinstance(motif, str) or not motif or not isinstance(positions, list):
                raise RuntimeError("Invalid repeat motif/positions")
            if any(type(p) is not int or p < 0 or p + len(motif) > len(sequence) for p in positions):
                raise RuntimeError("Repeat coordinate lies outside submitted sequence")
            rows.append({"motif": motif, "length": len(motif), "positions": [p + 1 for p in positions]})
        groups[kind] = rows
    return {"provider": "NovoPro rs", "molecule_type": molecule_type,
            "sequence_length": len(sequence), "minimum_length": minimum_length,
            "coordinate_convention": "one-based starts", "repeats": groups,
            "matching_rules": "provider-defined; not independently validated"}


def antibody_domain_metadata(sequence: str, numbering_scheme: str = "imgt") -> dict:
    """NovoPro abnum domain/germline metadata under an explicit numbering scheme.

    Reports provider species/chain/domain/germline fields, not a per-residue
    numbering map. Coordinate index basis is not documented by this adapter.
    Schemes: imgt, chothia, kabat, martin. Empty domains are a valid negative;
    malformed provider structures or rejected queries raise.
    """
    sequence = canonical_sequence(sequence, maximum=10000)
    if numbering_scheme not in {"imgt", "chothia", "kabat", "martin"}:
        raise ValueError("Unsupported antibody numbering scheme")
    raw = _result({"sr": "abnum", "sq": sequence, "skm": numbering_scheme, "ct": "", "org": ""})
    if not isinstance(raw, list):
        raise RuntimeError("Unexpected antibody domain schema")
    domains = []
    for item in raw:
        try:
            species, chain_type, expectation, score, start, end = item[0][1]
            germline_species, v_gene, v_identity, j_gene, j_identity = item[1][1]
        except (TypeError, ValueError, IndexError) as error:
            raise RuntimeError("Unrecognized antibody domain/germline metadata") from error
        domains.append({"species": species, "chain_type": chain_type,
                        "provider_e_value": expectation, "provider_score": score,
                        "provider_start_index": start, "provider_end_index": end,
                        "germline_species": germline_species, "v_gene": v_gene,
                        "v_identity": v_identity, "j_gene": j_gene, "j_identity": j_identity})
    return {"provider": "NovoPro abnum", "numbering_scheme": numbering_scheme,
            "domains": domains, "domain_count": len(domains),
            "per_residue_numbering_returned": False,
            "coordinate_convention": "provider index basis not specified"}


def predict_nuclear_localization(sequence: str, probability_threshold: float = 0.5):
    """NovoPro ProtNLS nuclear-localization probability with a decision threshold.

    Threshold affects sequence-level classification only, not attention or
    residue segment scoring. Provider model/segments are retained verbatim;
    this is not the BioT5 undefined binary-localization checkpoint.
    """
    sequence = canonical_sequence(sequence, maximum=10000)
    if type(probability_threshold) not in (int, float) or not math.isfinite(probability_threshold) or not 0 <= probability_threshold <= 1:
        raise ValueError("probability_threshold must be finite within[0,1]")
    from tools.implementations.biology.novopro_current import nuclear_localization
    return nuclear_localization(sequence + ":" + str(probability_threshold))
