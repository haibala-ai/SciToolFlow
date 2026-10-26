"""Actual current SIB HAMAP-Scan and Sulfinator submissions with retained scientific reports."""
from src.utils.paths import local_root, artifacts_root
import json
from pathlib import Path
import re
import uuid
import requests
from bs4 import BeautifulSoup

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()


def _input(sequence):
    value = "".join(sequence.split()).upper()
    if not value or len(value) > 10000:
        raise ValueError("Require a single canonical protein sequence or UniProt identifier")
    if set(value) <= set("ACDEFGHIKLMNPQRSTVWY"):
        return ">ToolKG_input\n" + value + "\n"
    if re.fullmatch(r"[A-Z0-9]{2,10}(?:_[A-Z0-9]+)?", value):
        return value
    raise ValueError("Unsupported protein sequence or identifier format")


def _submit(name, url, payload):
    with requests.Session() as session:
        response = request_with_retries(session, "POST", url, data=payload, files={"upload_file": ("", b"")}, timeout=90)
    response.raise_for_status()
    directory = artifacts_root() / (name + "_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    path = directory / "response.html"
    path.write_text(response.text)
    return BeautifulSoup(response.text, "html.parser"), path


def scan_hamap(sequence: str):
    """Real SIB HAMAP family profile scan; accepts a protein sequence or UniProt identifier, returns profile scores/regions."""
    soup, path = _submit("hamap", "https://hamap.expasy.org/cgi-bin/hamap/hamap-scan/scan_only.cgi",
                         {"seq": _input(sequence), "mandatory": "", "submit": "Scan"})
    text = soup.get_text(" ", strip=True)
    if "HAMAP-Scan results" not in text or "Showing results for" not in text:
        raise RuntimeError("SIB did not return a completed HAMAP scan; raw response: " + str(path))
    rows = []
    names = ["query", "profile_accession", "profile_name", "trusted_cutoff", "match_score", "match_region", "match_quality"]
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 7:
            values = [cell.get_text(" ", strip=True) for cell in cells]
            rows.append(dict(zip(names, values)))
    if not rows:
        raise RuntimeError("Completed HAMAP scan has no parseable query rows; raw response: " + str(path))
    return json.dumps({"source": "SIB HAMAP-Scan current public service", "input": sequence,
                       "completed": True, "profile_matches": [row for row in rows if row["profile_accession"] != "-"],
                       "all_query_rows": rows, "source_report": text, "raw_response": str(path)})


def predict_sulfinator(sequence: str):
    """Real SIB Sulfinator tyrosine sulfation prediction; returns the authoritative source report, not inferred annotations."""
    soup, path = _submit("sulfinator", "https://web.expasy.org/cgi-bin/sulfinator/sulfinator.pl",
                         {"sequence": _input(sequence)})
    text = soup.get_text(" ", strip=True)
    if "Sulfinator - Results" not in text or "E-cutoff value" not in text:
        raise RuntimeError("SIB did not return a completed Sulfinator prediction; raw response: " + str(path))
    return json.dumps({"source": "SIB Sulfinator public service", "input": sequence,
                       "completed": True, "source_report": text, "raw_response": str(path),
                       "result_note": "Predicted sites/scores or explicit No hits are in the unchanged source report"})
