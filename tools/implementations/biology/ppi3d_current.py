"""Real PPI3D structure/sequence queries, including normal browser AJAX headers and resumable jobs."""
from scitoolflow.paths import local_root, artifacts_root
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()
BASE = "https://bioinformatics.lt/ppi3d/"
DEFAULTS = {"sequence": "", "uniprot_ac": "", "job_name": "ToolKG_call_validation", "email_value": "",
            "two_sequences_query": "", "nucleic_acid_query": "", "sequence_search_method": "blast",
            "psiblast_num_iterations": "2", "psiblast_inclusion_ethresh": "0.002", "e_value": "0.01",
            "word_size": "3", "matrix": "BLOSUM62", "gap_costs": "11 1", "composition_based_statistics": "2",
            "mask_lowercase_letters": "0", "filter_low_complexity": "0", "use_soft_masking": "1", "pseudocount": "0"}


def _report(html, url, directory, scope):
    path = directory / "results.html"
    path.write_text(html)
    soup = BeautifulSoup(html, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
        rows = [[cell.get_text(" ", strip=True) for cell in row.find_all("td", recursive=False)]
                for row in table.find_all("tr") if row.find_all("td", recursive=False)]
        if headers and rows:
            tables.append({"headers": headers, "rows": rows[:50], "total_rows": len(rows), "truncated": len(rows) > 50})
    text = soup.get_text(" ", strip=True)
    if not tables and not re.search(r"no (?:interactions|results|matches|binding sites)", text, re.I):
        raise RuntimeError("No completed PPI3D scientific result table or explicit negative result: " + str(path))
    return json.dumps({"source": "PPI3D current public service", "completed": True, "scope": scope,
                       "source_url": url, "tables": tables, "source_report": text[:30000],
                       "source_report_truncated": len(text) > 30000, "raw_response": str(path)})


def ppi3d_pdb(pdb_id: str):
    """Actual PPI3D clustered structural interaction interfaces for a PDB entry; reports source contacts and buried areas."""
    if not re.fullmatch(r"[0-9][A-Za-z0-9]{3}", pdb_id):
        raise ValueError("Require a four-character PDB ID")
    pdb_id = pdb_id.lower()
    directory = artifacts_root() / ("ppi3d_pdb_" + pdb_id)
    directory.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    page_url = BASE + "site/interactions_in_pdb_entry/" + pdb_id
    response = request_with_retries(session, "GET", page_url, timeout=30)
    response.raise_for_status()
    (directory / "landing.html").write_text(response.text)
    url = BASE + "site/load_interactions_in_pdb_entry_table/" + pdb_id
    response = request_with_retries(session, "GET", url, headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url}, timeout=45)
    response.raise_for_status()
    return _report(response.text, page_url, directory, "binary interfaces in the queried PDB entry")


def _sequence_input(sequence):
    sequence = "".join(sequence.split()).upper()
    if not 1 <= len(sequence) <= 5000:
        raise ValueError("Require canonical protein sequence <=5000 residues or a single UniProt accession")
    if set(sequence) <= set("ACDEFGHIKLMNPQRSTVWY"):
        return "sequence", sequence
    if re.fullmatch(r"[A-Z0-9]{6,10}", sequence):
        return "uniprot_ac", sequence
    raise ValueError("Unsupported sequence/accession format")


def _query(sequence, second_sequence, wait_seconds):
    if not 0 <= wait_seconds <= 600:
        raise ValueError("Require wait_seconds 0..600")
    data = DEFAULTS.copy()
    key, value = _sequence_input(sequence)
    data[key] = value
    if second_sequence:
        key, value = _sequence_input(second_sequence)
        data[key + "_2"] = value
        data["two_sequences_query"] = "1"
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    directory = artifacts_root() / ("ppi3d_seq_" + digest[:24])
    directory.mkdir(parents=True, exist_ok=True)
    state_path = directory / "request.json"
    session = requests.Session()
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        response = request_with_retries(session, "POST", BASE + "site/submit_data", data=data, timeout=45)
        response.raise_for_status()
        (directory / "submission.html").write_text(response.text)
        if not re.fullmatch(r"/ppi3d/site/results/[A-Za-z0-9_-]+", urlparse(response.url).path):
            raise RuntimeError("PPI3D did not create a sequence search job; submission: " + str(directory))
        state = {"url": response.url, "request_sha256": digest, "parameters": data, "status": "queued"}
        state_path.write_text(json.dumps(state, indent=2))
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        response = request_with_retries(session, "GET", state["url"], timeout=30)
        response.raise_for_status()
        (directory / "last_response.html").write_text(response.text)
        text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        if "Summary of results" in text or re.search(r"no (?:interactions|results|matches|binding sites)", text, re.I):
            report = json.loads(_report(response.text, state["url"], directory,
                              "interactions of homologs to two query proteins" if second_sequence else "binding sites of query protein homologs"))
            report["search_parameters"] = data
            state["status"] = "completed"
            state_path.write_text(json.dumps(state, indent=2))
            return json.dumps(report)
        if "Query queued" not in text and "Processing your query" not in text:
            raise RuntimeError("Unexpected PPI3D job state; retained response: " + str(directory))
        time.sleep(min(10, max(0, deadline - time.monotonic())))
    raise TimeoutError("PPI3D job remains queued; repeat same inputs to resume: " + str(state_path))


def ppi3d_single(sequence: str, wait_seconds: int = 240):
    """Real PPI3D BLAST single-sequence search for structurally resolved homolog binding sites; persistent job ID."""
    return _query(sequence, None, wait_seconds)


def ppi3d_two(sequence: str, second_sequence: str, wait_seconds: int = 240):
    """Real PPI3D BLAST search for interfaces between two query proteins or their homologs; persistent job ID."""
    return _query(sequence, second_sequence, wait_seconds)
