"""One scientific quantity per sequence descriptor; methods are explicit."""
import math


def protein_gravy(sequence: str) -> dict:
    """Kyte-Doolittle GRAVY: mean residue hydropathy, not pI or molecular polarity.

    Canonical unmodified protein only, whitespace-normalized/uppercase. The
    dimensionless average is computed by Bio.SeqUtils.ProtParam using its
    default Kyte-Doolittle table; no local window, aggregation, solubility or
    biological-function prediction. Does not return other descriptor quantities.
    """
    import Bio
    from Bio.SeqUtils.ProtParam import ProteinAnalysis
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence)
    return {"gravy": float(ProteinAnalysis(sequence).gravy()),
            "method": "Kyte-Doolittle mean residue hydropathy",
            "units": "dimensionless hydropathy scale", "sequence_length": len(sequence),
            "backend": "Bio.SeqUtils.ProtParam.ProteinAnalysis.gravy", "biopython_version": Bio.__version__}


def protein_isoelectric_point(sequence: str, method: str) -> dict:
    """Theoretical pI of a canonical unmodified linear protein, selected method.

    biopython uses Bjellqvist pKa tables with sequence-specific terminal values,
    Henderson-Hasselbalch charge and explicit bisection over pH0..14, resolution
    0.0001. The wider bracket avoids silently clipping acidic sequences at the
    library default lower bound4.05. Free N/C termini, no disulfide/PTM or
    structure-environment shifts. expasy retrieves the theoretical pI field
    from the current Compute pI/Mw service, discarding its duplicate mass field;
    novopro collects the current automatic ProtPIC model's completed pI only.
    Remote pKa constants/version are not disclosed and may differ from local
    Bjellqvist. Queued/missing/nonfinite values fail. pI is dimensionless pH, not
    molecular polarity, mass or experimental titration.
    """
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence)
    if method not in {"biopython", "expasy", "novopro"}:
        raise NotImplementedError("Supported pI methods are biopython, expasy and novopro")
    if method != "biopython":
        if method == "expasy":
            import re
            from tools.implementations.biology.common import compute_pI_mW
            report = compute_pI_mW(sequence)
            match = re.search(r"\*\*Theoretical pI:\*\*\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))", report)
            if not match:
                raise RuntimeError("ExPASy did not return a completed parseable theoretical pI field")
            value = float(match.group(1))
            backend = "https://web.expasy.org/cgi-bin/compute_pi/pi_tool (average-resolution request; mass field discarded)"
        else:
            from tools.implementations.biology.novopro_current import _async
            item, _ = _async("ipc", sequence)
            value = item.get("pI")
            if type(value) not in (int, float):
                raise RuntimeError("NovoPro did not return a completed numeric pI field")
            value = float(value)
            backend = "NovoPro current ProtPIC, automatic upstream model selection"
        if not math.isfinite(value) or not 0 <= value <= 14:
            raise RuntimeError("Remote pI is not finite in pH0..14")
        return {"pI": value, "method": method, "backend": backend,
                "pka_model": "provider-controlled; exact pKa tables/model version not disclosed",
                "sequence_length": len(sequence), "experimental_titration_verified": False}
    import Bio
    from Bio.SeqUtils.IsoelectricPoint import IsoelectricPoint
    model = IsoelectricPoint(sequence)
    lower, upper = model.charge_at_pH(0), model.charge_at_pH(14)
    if not lower >= 0 >= upper:
        raise RuntimeError("The declared pKa model has no pI root in the supported pH interval0..14")
    value = float(model.pi(pH=7.0, min_=0.0, max_=14.0))
    if not math.isfinite(value) or not 0 <= value <= 14:
        raise RuntimeError("The pKa model did not return a finite in-range pI")
    return {"pI": value, "method": "biopython", "pka_model": "Bjellqvist tables with sequence-specific termini",
            "backend": "Bio.SeqUtils.IsoelectricPoint", "biopython_version": Bio.__version__,
            "search_interval_pH": [0.0, 14.0], "bisection_interval_tolerance_pH": 0.0001,
            "positive_pKa_values": model.pos_pKs, "negative_pKa_values": model.neg_pKs,
            "sequence_length": len(sequence), "experimental_titration_verified": False}
