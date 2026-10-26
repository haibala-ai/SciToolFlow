"""Adapt the live NovoPro forms; preserve raw scientific results and provenance."""
from src.utils.paths import local_root, artifacts_root
import json
from pathlib import Path
import time
import uuid

from tools.implementations.adapters import _peptide
from tools.implementations.shared.http_clients import send_novopro_request


def _request(payload):
    raw = send_novopro_request(payload)
    if raw is None:
        raise RuntimeError("NovoPro network request failed")
    result = json.loads(raw)
    if isinstance(result, list) and (not result or result[0] != 1):
        raise RuntimeError("NovoPro reported failure: " + str(result[1:]))
    if isinstance(result, dict) and result.get("status") in [0, "failed"]:
        raise RuntimeError("NovoPro reported failure: " + str(result.get("msg", result.get("error"))))
    return result


def _artifact(name, result):
    directory = artifacts_root()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + "_" + uuid.uuid4().hex + ".json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return path


def _async(operation, sequence):
    sequence = _peptide(sequence)
    submitted = _request({"sr": operation, "input_data": json.dumps({"sequence1": sequence})})
    if not isinstance(submitted, dict) or submitted.get("status") != 1 or not submitted.get("task_id"):
        raise RuntimeError("Unexpected NovoPro asynchronous submission schema")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        reply = _request({"sr": "result", "task_id": submitted["task_id"]})
        if reply.get("status") == "done":
            result = reply.get("result")
            items = result.get("items", []) if isinstance(result, dict) else []
            if len(items) != 1 or items[0].get("sequence") != sequence:
                raise RuntimeError("NovoPro result does not match the submitted sequence")
            path = _artifact(operation, {"submission": submitted, "response": reply})
            return items[0], str(path)
        time.sleep(3)
    raise TimeoutError("NovoPro asynchronous prediction exceeded 180 seconds")


def transmembrane(sq: str):
    """NovoPro current model topology/regions, 1-based inclusive; not the historical TMHMM version."""
    item, path = _async("tmhmm", sq)
    if len(item.get("topology", "")) != len(item["sequence"]):
        raise RuntimeError("Unexpected topology length")
    return json.dumps({"provider": "NovoPro current ProtTM", "result": item, "artifact": path})


def disordered(sequence: str):
    """NovoPro current disorder probabilities/labels and a locally plotted PNG; model changed upstream."""
    item, path = _async("idr", sequence)
    length = len(item["sequence"])
    if len(item.get("prob_idr", [])) != length or len(item.get("labels", [])) != length:
        raise RuntimeError("Unexpected disorder prediction length")
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(range(1, length + 1), item["prob_idr"])
    ax.axhline(item["threshold"], linestyle="--", label="Provider threshold")
    ax.set(xlabel="Residue (1-based)", ylabel="Disorder probability", ylim=(0, 1))
    ax.legend()
    image = Path(path).with_suffix(".png")
    fig.savefig(image, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return json.dumps({"provider": "NovoPro current ProtIDR", "result": item,
                       "image": str(image), "artifact": path})


def nuclear_localization(sequence_threshold: str):
    """Current ProtNLS prediction; requested threshold applies to sequence-level probability, not attention."""
    sequence, text = sequence_threshold.rsplit(":", 1)
    threshold = float(text)
    if not 0 <= threshold <= 1:
        raise ValueError("Probability threshold must be in [0,1]")
    item, path = _async("nls", sequence)
    probability = float(item["probability"])
    if not 0 <= probability <= 1:
        raise RuntimeError("Unexpected localization probability")
    return json.dumps({"provider": "NovoPro current ProtNLS", "result": item,
                       "requested_threshold": threshold, "threshold_scope": "sequence-level probability",
                       "classified_nuclear": probability >= threshold, "artifact": path})


def isoelectric_point(sequence: str):
    """NovoPro ProtPIC pI with automatic upstream model choice, canonical sequence only.

    There is no protein/peptide model selector in this adapter. Suffixes,
    modifications and unsupported alphabets fail rather than pretending to
    enforce a model. Returns the unchanged provider result and provenance.
    """
    sequence = _peptide(sequence)
    item, path = _async("ipc", sequence)
    if "pI" not in item:
        raise RuntimeError("NovoPro returned no isoelectric point")
    return json.dumps({"provider": "NovoPro current ProtPIC (upstream model auto-selection)",
                       "model_selection": "upstream automatic; no local type override",
                       "result": item, "artifact": path})


def peptide_properties(sequence: str):
    """Retired broad descriptor bundle; use molecular primitives or PeptideChargeProfile."""
    raise NotImplementedError("Broad peptide descriptor report retired; construct explicit peptide SMILES then request one declared property, or use PeptideChargeProfile")


def _repeats(sequence_length, kind):
    sequence, text = sequence_length.rsplit(".", 1)
    sequence = "".join(sequence.split()).upper()
    length = int(text)
    if not sequence or length < 1 or length > len(sequence):
        raise ValueError("Require a non-empty sequence and 1 <= minimum length <= sequence length")
    if kind == "Protein":
        sequence = _peptide(sequence)
    elif set(sequence) - set("ACGT"):
        raise ValueError("Require unambiguous A/C/G/T DNA")
    reply = _request({"sr": "rs", "st": kind, "sq": sequence, "ml": length, "ln": len(sequence)})
    result = reply[1]
    if not isinstance(result, dict) or not all(key in result for key in ["direct", "inverted"]):
        raise RuntimeError("Unexpected repeat-search schema")
    groups = {}
    for group in ["direct", "inverted"]:
        groups[group] = [{"sequence": motif, "length": len(motif), "positions": [int(p) + 1 for p in positions]}
                         for motif, positions in result[group]]
    return json.dumps({"provider": "NovoPro", "sequence": sequence, "positions_are": "1-based",
                       "minimum_length": length, "repeats": groups})


def repeat_dna(sequence_length: str):
    """Search DNA direct/inverted repeats using the current NovoPro response schema."""
    return _repeats(sequence_length, "DNA")


def repeat_protein(sequence_length: str):
    """Search protein repeats using the current NovoPro response schema."""
    return _repeats(sequence_length, "Protein")


def protein_motifs(sequence: str):
    """Return current NovoPro motif matches; an empty match list is a valid negative result."""
    sequence = _peptide(sequence)
    reply = _request({"sr": "motifscan", "sq": sequence})
    matches = reply[1]
    if not isinstance(matches, dict) and matches != []:
        raise RuntimeError("Unexpected protein motif schema")
    return json.dumps({"provider": "NovoPro", "sequence": sequence, "matches": matches or {},
                       "match_status": "matches_found" if matches else "no_matches"})


def circular_dna_alignment(sequence: str):
    """Rotation-aware circular DNA comparison; the retired NovoPro ``csa`` action is no longer used.

    For every pair the best rotational offset of the second sequence relative to
    the first is located with a shared k-mer seed, then scored with a documented
    Biopython global alignment.  Offsets are reported so the rotation is auditable.
    """
    from Bio.Align import PairwiseAligner
    import re as _re
    sequences = [part.upper() for part in _re.split(r"[^A-Za-z]+", sequence.strip()) if part]
    if not 2 <= len(sequences) <= 100 or any(not part or set(part) - set("ACGT") for part in sequences):
        raise ValueError("Require 2-100 unambiguous DNA sequences separated by '.', '|', ',' or whitespace")
    if max(len(part) for part in sequences) > 5000:
        raise ValueError("Circular alignment supports at most 5000 bases per sequence")
    if sum(len(sequences[0]) * len(part) for part in sequences[1:]) * 8 > 100000000:
        raise ValueError("Circular alignment candidate work exceeds 100 million alignment cells")
    aligner = PairwiseAligner(mode="global", match_score=2, mismatch_score=-1,
                              open_gap_score=-2, extend_gap_score=-0.5)

    def best_rotation(first, second):
        length = len(second)
        seed = min(10, max(1, min(len(first), length) // 2))
        index = {}
        for position in range(len(first) - seed + 1):
            index.setdefault(first[position:position + seed], []).append(position)
        doubled = second + second
        votes = {}
        for offset in range(len(doubled) - seed + 1):
            for start in index.get(doubled[offset:offset + seed], []):
                rotation = (start - offset) % length
                votes[rotation] = votes.get(rotation, 0) + 1
        candidates = [rotation for rotation, _ in sorted(votes.items(), key=lambda item: -item[1])[:8]] or [0]
        best = None
        for rotation in candidates:
            rotated = second[rotation:] + second[:rotation]
            alignment = aligner.align(first, rotated)[0]
            if best is None or alignment.score > best[0].score:
                best = (alignment, rotation, rotated)
        return best

    pairs = []
    for index in range(1, len(sequences)):
        alignment, rotation, rotated = best_rotation(sequences[0], sequences[index])
        columns = [column for column in zip(str(alignment[0]), str(alignment[1])) if column != ("-", "-")]
        identical = sum(left == right for left, right in columns)
        pairs.append({"sequence_indices": [1, index + 1], "rotation_offset_of_second": rotation,
                      "aligned_second_sequence": rotated, "score": alignment.score,
                      "compared_columns": len(columns),
                      "identity_percent": 100 * identical / len(columns) if columns else 0.0,
                      "alignment": str(alignment)})
    return json.dumps({"provider": "local rotation-aware circular DNA alignment",
                       "algorithm": "k-mer seeded candidate rotation search + Bio.Align.PairwiseAligner global",
                       "rotation_search": "up to eight highest-vote offsets; heuristic, not exhaustive or guaranteed globally optimal",
                       "scoring": {"match": 2, "mismatch": -1, "gap_open": -2, "gap_extend": -0.5},
                       "seed_length": min(10, max(1, min(len(sequences[0]), min(len(part) for part in sequences)) // 2)),
                       "reference_sequence": sequences[0], "pairwise_to_reference": pairs,
                       "note": "Retired upstream NovoPro circular-alignment action replaced by an explicit local algorithm"})
