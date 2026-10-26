"""Actual current MusiteDeep2020 web backend; retired port5000 API is not used."""
from src.utils.paths import local_root, artifacts_root
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid
import requests

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()


def predict_musite(sequence: str, cutoff: float = 0.5):
    """Real MusiteDeep2020 S/T phosphorylation scores; current public /cmd protocol, caller's cutoff applied to returned scores."""
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence, maximum=5000)
    if isinstance(cutoff, bool) or not isinstance(cutoff, (int, float)) or not math.isfinite(cutoff):
        raise ValueError("cutoff must be a finite probability")
    if not 1 <= len(sequence) <= 5000 or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY") or not 0 <= cutoff <= 1:
        raise ValueError("Require 1..5000 canonical amino acids and cutoff 0..1")
    directory = artifacts_root() / ("musite_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    payload = {"input": ">ToolKG_input\n" + sequence + "\n",
               "model": [{"label": "S/T phosphorylation", "value": "Phosphoserine_Phosphothreonine"}],
               "userId": "ToolKG_" + uuid.uuid4().hex,
               "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), "seqNum": 1}
    (directory / "request.json").write_text(json.dumps(payload, indent=2))
    with requests.Session() as session:
        response = request_with_retries(session, "POST", "https://www.musite.net/cmd", json=payload, timeout=120)
    response.raise_for_status()
    (directory / "response.json").write_text(response.text)
    data = response.json()
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[0], str) or not isinstance(data[1], str):
        raise RuntimeError("MusiteDeep did not return completed prediction data; retained response: " + str(directory))
    if sequence not in data[0] or not data[1].startswith("ID\tPosition\tResidue\tPTMscores"):
        raise RuntimeError("MusiteDeep returned mismatched input or an unexpected result schema")
    scores = []
    for line in data[1].splitlines()[1:]:
        if not line or line.startswith(">"):
            continue
        columns = line.split("\t")
        if len(columns) != 5:
            raise RuntimeError("Unexpected PTM result row")
        position = int(columns[1])
        if not 1 <= position <= len(sequence) or columns[2] != sequence[position-1]:
            raise RuntimeError("PTM site does not match the actual submitted sequence")
        label, score = columns[3].rsplit(":", 1)
        probability = float(score)
        if label not in ["Phosphoserine", "Phosphothreonine"] or not 0 <= probability <= 1:
            raise RuntimeError("Invalid S/T phosphorylation label or score")
        scores.append({"position_one_based": position, "residue": columns[2], "modification": label,
                       "score": probability, "passes_requested_cutoff": probability >= cutoff,
                       "server_classification_at_0_5": columns[4]})
    expected = [i+1 for i, residue in enumerate(sequence) if residue in "ST"]
    if [site["position_one_based"] for site in scores] != expected:
        raise RuntimeError("Server output does not cover every S/T residue exactly once")
    return json.dumps({"source": "MusiteDeep2020 current public web backend", "completed": True,
                       "sequence": sequence, "model": "Phosphoserine_Phosphothreonine", "requested_cutoff": cutoff,
                       "server_cutoff": 0.5, "scores": scores, "raw_response": str(directory / "response.json"),
                       "scope": "S/T phosphorylation only; other PTM classifiers are not implemented by this adapter",
                       "experimental_phosphorylation_verified": False})
