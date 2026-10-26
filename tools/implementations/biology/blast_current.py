"""Real blastp execution: NCBI URL API first, EBI's NCBI BLAST+ service as a fallback.

The NCBI public ``nr`` queue is sometimes stalled for hours for a shared egress
address.  A submitted RID is persisted so a stalled job can be resumed later,
and when the caller's wait budget is exhausted the same query is run against
EBI's NCBI BLAST+ service (UniProtKB/Swiss-Prot) so the tool still returns real
alignments.  Every result states its provider and database.
"""
from src.utils.paths import local_root, artifacts_root
import hashlib
import json
import os
from pathlib import Path
import re
import time
import requests

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()
URL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
EBI = "https://www.ebi.ac.uk/Tools/services/rest/ncbiblast"
SIGNIFICANCE = 0.01


def _sequence(sequence_data):
    from Bio import SeqIO
    from io import StringIO
    if sequence_data.lstrip().startswith(">"):
        return str(SeqIO.read(StringIO(sequence_data), "fasta").seq).upper()
    return "".join(sequence_data.split()).upper()


def _ncbi(sequence, max_results, wait_seconds, directory):
    parameters = {"PROGRAM": "blastp", "DATABASE": "nr", "QUERY": sequence,
                  "HITLIST_SIZE": max_results}
    key = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
    state_path = directory / "request.json"
    output_path = directory / "results.json"
    session = requests.Session()
    session.trust_env = os.getenv("SCITOOL_BLAST_USE_PROXY", "0") == "1"
    if output_path.exists():
        data = json.loads(output_path.read_text())
        if data.get("query_sha256") == hashlib.sha256(sequence.encode()).hexdigest():
            return json.dumps(data)
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["request_sha256"] != key:
            raise ValueError("Saved BLAST request does not match query")
    else:
        response = request_with_retries(session, "POST", URL, data={"CMD": "Put", **parameters}, timeout=45)
        response.raise_for_status()
        (directory / "submission.txt").write_text(response.text)
        match = re.search(r"RID\s*=\s*(\S+)", response.text)
        if not match:
            raise RuntimeError("NCBI returned no RID; retained submission: " + str(directory / "submission.txt"))
        state = {"rid": match[1], "request_sha256": key, "database": "nr", "program": "blastp",
                 "submitted_at_unix": time.time(), "last_polled_at_unix": time.time(), "status": "queued"}
        state_path.write_text(json.dumps(state, indent=2))
    if state.get("status") == "queued" and time.time() - state.get("submitted_at_unix", time.time()) > max(600, wait_seconds):
        # The public nr queue has already been waiting longer than this call's
        # whole budget; poll once, then hand over to the EBI fallback.
        response = request_with_retries(session, "GET", URL, params={"CMD": "Get", "RID": state["rid"], "FORMAT_TYPE": "JSON2_S"}, timeout=45)
        state["last_polled_at_unix"] = time.time()
        state_path.write_text(json.dumps(state, indent=2))
        if not response.text.lstrip().startswith("{"):
            raise TimeoutError("NCBI blastp/nr still queued after " + str(round(time.time() - state["submitted_at_unix"])) +
                               " s; persisted RID " + state["rid"] + " can resume later. Request: " + str(state_path))
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        delay = max(0, 61 - (time.time() - state["last_polled_at_unix"]))
        if time.monotonic() + delay >= deadline:
            break
        time.sleep(delay)
        response = request_with_retries(session, "GET", URL, params={"CMD": "Get", "RID": state["rid"], "FORMAT_TYPE": "JSON2_S"}, timeout=45)
        state["last_polled_at_unix"] = time.time()
        state_path.write_text(json.dumps(state, indent=2))
        response.raise_for_status()
        (directory / "last_response.txt").write_text(response.text)
        if "Status=FAILED" in response.text or "Status=UNKNOWN" in response.text:
            state["status"] = "failed_or_expired"
            state_path.write_text(json.dumps(state, indent=2))
            raise RuntimeError("NCBI RID failed/expired; remove saved request only when intentionally resubmitting: " + str(state_path))
        if "Status=WAITING" in response.text or not response.text.lstrip().startswith("{"):
            continue
        payload = response.json()
        try:
            entry = payload["BlastOutput2"][0]
            if "error" in entry:
                raise RuntimeError("NCBI BLAST reported: " + str(entry["error"]))
            search = entry["report"]["results"]["search"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Unexpected NCBI JSON2_S result; raw response retained") from error
        hits = []
        for hit in search.get("hits", [])[:max_results]:
            hsps = [hsp for hsp in hit.get("hsps", []) if hsp["evalue"] < SIGNIFICANCE]
            if hsps:
                hits.append({"description": hit["description"], "length": hit["len"], "hsps": hsps})
        state["status"] = "completed"
        state_path.write_text(json.dumps(state, indent=2))
        result = {"source": "NCBI BLAST URL API", "program": "blastp", "database": "nr",
                  "rid": state["rid"], "search_status": "completed", "query_length": search["query_len"],
                  "query_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                  "significance_threshold_evalue": SIGNIFICANCE, "hits": hits, "raw_result": str(directory / "last_response.txt")}
        output_path.write_text(json.dumps(result, indent=2))
        return json.dumps(result)
    raise TimeoutError("NCBI blastp/nr still queued; persisted RID " + state["rid"] +
                       " can resume with the same query. Request: " + str(state_path))


def _ebi(sequence, max_results, wait_seconds, directory, reason):
    """Run the identical blastp query on EBI's NCBI BLAST+ service against Swiss-Prot."""
    session = requests.Session()
    session.trust_env = os.getenv("SCITOOL_BLAST_USE_PROXY", "0") == "1"
    payload = {"email": os.getenv("SCITOOL_BLAST_EMAIL", "scitoolagent@example.org"), "program": "blastp",
               "stype": "protein", "database": "uniprotkb_swissprot", "sequence": sequence,
               "exp": "1e-2", "alignments": str(max_results), "scores": str(max_results),
               "matrix": "BLOSUM62"}
    response = request_with_retries(session, "POST", EBI + "/run", data=payload, timeout=60)
    response.raise_for_status()
    job = response.text.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", job):
        raise RuntimeError("EBI BLAST returned an unexpected job identifier; raw response retained in " + str(directory))
    (directory / "ebi_job.txt").write_text(job)
    deadline = time.monotonic() + max(wait_seconds, 120)
    status = "QUEUED"
    while time.monotonic() < deadline:
        status = request_with_retries(session, "GET", f"{EBI}/status/{job}", timeout=45).text.strip()
        if status == "FINISHED":
            break
        if status in ["ERROR", "FAILURE", "NOT_FOUND", "KILLED"]:
            raise RuntimeError("EBI BLAST job ended with status " + status + "; job " + job)
        time.sleep(5)
    if status != "FINISHED":
        raise TimeoutError("EBI BLAST job still " + status + "; resumable job " + job)
    xml = request_with_retries(session, "GET", f"{EBI}/result/{job}/xml", timeout=90).text
    (directory / "ebi_result.xml").write_text(xml)
    import xml.etree.ElementTree as ElementTree
    root = ElementTree.fromstring(xml)
    hits = []
    for hit in root.iter():
        if hit.tag.split("}")[-1] != "hit":
            continue
        hsps = []
        for alignment in hit:
            if alignment.tag.split("}")[-1] != "alignments":
                continue
            for entry in alignment:
                values = {child.tag.split("}")[-1]: child for child in entry}
                expectation = float(values["expectation"].text)
                if expectation >= SIGNIFICANCE:
                    continue
                query = values.get("querySeq")
                subject = values.get("matchSeq")
                hsps.append({"evalue": expectation, "bit_score": float(values["bits"].text),
                             "identity_percent": float(values["identity"].text),
                             "positives_percent": float(values["positives"].text) if values.get("positives") is not None else None,
                             "alignment_length": len((values.get("pattern").text or "").replace(" ", "")) if values.get("pattern") is not None else None,
                             "query_start": int(query.get("start")), "query_end": int(query.get("end")),
                             "subject_start": int(subject.get("start")), "subject_end": int(subject.get("end"))})
        if hsps:
            hits.append({"description": hit.get("description"), "length": int(hit.get("length")),
                         "accession": hit.get("ac"), "identifier": hit.get("id"), "hsps": hsps})
        if len(hits) >= max_results:
            break
    result = {"source": "EBI NCBI BLAST+ REST service", "program": "blastp", "database": "uniprotkb_swissprot",
              "ebi_job": job, "search_status": "completed", "query_length": len(sequence),
              "query_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
              "significance_threshold_evalue": SIGNIFICANCE, "hits": hits,
              "ncbi_nr_job": reason,
              "fallback_reason": "NCBI nr queue did not return within the caller's wait budget; the same blastp query was run on EBI's NCBI BLAST+ service",
              "raw_result": str(directory / "ebi_result.xml")}
    (directory / "ebi_results.json").write_text(json.dumps(result, indent=2))
    return json.dumps(result)


def perform_blast_query(sequence_data: str, max_results: int = 20, wait_seconds: int = 300):
    """Real blastp; NCBI nr with a resumable RID, EBI NCBI BLAST+/Swiss-Prot when the NCBI queue stalls."""
    sequence = _sequence(sequence_data)
    if not sequence or len(sequence) > 10000 or set(sequence) - set("ACDEFGHIKLMNPQRSTVWYBXZJUO*"):
        raise ValueError("Require a protein sequence or a single FASTA protein record")
    if not 1 <= max_results <= 100 or not 0 <= wait_seconds <= 1800:
        raise ValueError("Require 1..100 results and 0..1800 wait seconds")
    key = hashlib.sha256(json.dumps({"sequence": sequence, "max_results": max_results}, sort_keys=True).encode()).hexdigest()
    directory = artifacts_root() / ("blast_" + key[:24])
    directory.mkdir(parents=True, exist_ok=True)
    try:
        return _ncbi(sequence, max_results, wait_seconds, directory)
    except TimeoutError as error:
        return _ebi(sequence, max_results, wait_seconds, directory, str(error))
