"""Explicit public protein record retrieval; no hidden first-hit identity choice."""
import hashlib
from pathlib import Path
import re
import uuid

import requests
from src.utils.paths import artifacts_root
from tools.implementations.shared.http_retry import request_with_retries


def fetch_pdb_coordinate_file(pdb_id: str) -> dict:
    """Fetch one deposited RCSB plain-PDB file into a new task artifact.

    Valid four-character identifiers only. Returns exact-byte SHA256 and URL.
    No biological assembly, experimental method, missing atom or function is
    inferred. Downstream tools should reuse this explicit file to avoid
    independent downloads/versions. Missing/oversized/non-PDB responses raise.
    """
    if not isinstance(pdb_id, str) or not re.fullmatch(r"[0-9][A-Za-z0-9]{3}", pdb_id):
        raise ValueError("pdb_id must be a four-character PDB identifier")
    identifier = pdb_id.upper()
    url = f"https://files.rcsb.org/download/{identifier}.pdb"
    with requests.Session() as session:
        session.trust_env = False
        response = request_with_retries(session, "GET", url, timeout=30)
    response.raise_for_status()
    raw = response.content
    if not raw or len(raw) > 25 * 1024 * 1024 or not any(line.startswith((b"ATOM  ", b"HETATM")) for line in raw.splitlines()):
        raise RuntimeError("RCSB did not return a bounded PDB coordinate record")
    directory = artifacts_root() / ("pdb_record_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    path = directory / (identifier + ".pdb")
    path.write_bytes(raw)
    return {"pdb_id": identifier, "pdb_path": str(path), "source_url": url,
            "source_sha256": hashlib.sha256(raw).hexdigest(), "source_bytes": len(raw),
            "scope": "deposited coordinate record; no assembly/completeness/experimental-status inference"}


def search_protein_sequences_by_name(protein_name: str, max_results: int = 20) -> dict:
    """Return EBI protein-name search candidates, preserving accessions and sequences.

    A name may resolve to several records; no first-hit or unique-match claim.
    max_results1..128 limits the requested candidate page; completeness beyond
    that page is unknown. Sequences are unchanged provider fields, not repaired
    or independently validated. HTTP/schema failure raises.
    """
    if not isinstance(protein_name, str) or not 1 <= len(protein_name.strip()) <= 200:
        raise ValueError("protein_name must be1..200characters")
    if type(max_results) is not int or not 1 <= max_results <= 128:
        raise ValueError("max_results must be integer1..128")
    url = "https://www.ebi.ac.uk/proteins/api/proteins"
    with requests.Session() as session:
        session.trust_env = False
        response = request_with_retries(session, "GET", url,
                                       params={"offset": 0, "size": max_results, "protein": protein_name.strip()},
                                       headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list):
        raise RuntimeError("Unexpected EBI protein-record search schema")
    candidates = []
    for record in records[:max_results]:
        accession = record.get("accession") if isinstance(record, dict) else None
        sequence = record.get("sequence", {}).get("sequence") if isinstance(record, dict) else None
        if not isinstance(accession, str) or not isinstance(sequence, str) or not sequence:
            raise RuntimeError("EBI candidate lacks explicit accession/sequence")
        candidates.append({"accession": accession, "sequence": sequence, "length": len(sequence)})
    return {"provider": "EBI proteins API", "query_name": protein_name.strip(),
            "candidates": candidates, "returned_count": len(candidates),
            "requested_max_results": max_results, "unique_identity_inferred": False,
            "completeness": "one bounded provider page; total matches unknown",
            "response_sha256": hashlib.sha256(response.content).hexdigest()}
