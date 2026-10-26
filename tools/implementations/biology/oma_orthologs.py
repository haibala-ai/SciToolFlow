"""Ortholog retrieval from the OMA (Orthologous MAtrix) public REST API.

The KG node ``GetCoronaOrthologs`` is defined as "retrieves orthologs of a
protein of interest from the OMA database" with a UniProtKB identifier as input
and orthologs as output.  This adapter performs that real retrieval: it resolves
the identifier through OMA, downloads the ortholog list, and keeps the source
URLs, species and OMA relationship types for every returned row.
"""
from src.utils.paths import local_root, artifacts_root
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import uuid

import requests

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()
API = "https://omabrowser.org/api"


def _identifier(value):
    text = value.strip().upper()
    if re.fullmatch(r"[A-Z0-9]{6,10}", text) or re.fullmatch(r"[A-Z0-9]{2,10}_[A-Z0-9]+", text):
        return text
    raise ValueError("Require a UniProtKB accession (e.g. P04637) or entry name (e.g. P53_HUMAN)")


def _session():
    session = requests.Session()
    session.trust_env = os.getenv("SCITOOL_OMA_USE_PROXY", "1") == "1"
    session.headers.update({"Accept": "application/json",
                            "User-Agent": "SciToolAgent/1.0 (OMA ortholog retrieval)"})
    return session


def _entry(session, identifier, directory):
    """Resolve an accession or entry name to a single OMA protein entry."""
    response = request_with_retries(session, "GET", f"{API}/protein/{identifier}/", timeout=45)
    if response.status_code == 404:
        raise ValueError(f"OMA has no protein entry for {identifier}; OMA does not index every UniProt entry")
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    candidates = [row for row in payload if isinstance(row, dict) and row.get("entry_nr")]
    if not candidates:
        raise ValueError(f"OMA returned no protein entry for {identifier}")
    if len(candidates) > 1:
        exact = [row for row in candidates if str(row.get("canonicalid", "")).upper() == identifier
                 or str(row.get("omaid", "")).upper() == identifier]
        if len(exact) != 1:
            raise ValueError("OMA identifier resolution is ambiguous; provide an exact OMA/canonical identifier")
        candidates = exact
    (directory / "oma_resolution.json").write_text(json.dumps(candidates[:10], indent=2))
    return candidates[0]


def get_corona_orthologs(uniprot_id: str, max_results: int = 100, minimum_score: float = 0.0):
    """Real OMA orthologs for a UniProtKB identifier; rows keep species, relationship type and score.

    ``max_results`` truncates the returned table only; ``total_orthologs`` always
    reports how many OMA returned.  A protein absent from OMA is reported as an
    explicit absence, not as a fabricated ortholog list.
    """
    identifier = _identifier(uniprot_id)
    if type(max_results) is not int or not 1 <= max_results <= 10000:
        raise ValueError("Require 1..10000 maximum results")
    if isinstance(minimum_score, bool) or not isinstance(minimum_score, (int, float)) or not math.isfinite(minimum_score) or minimum_score < 0:
        raise ValueError("minimum_score must not be negative")
    directory = artifacts_root() / ("oma_" + identifier + "_" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=True)
    with _session() as session:
        entry = _entry(session, identifier, directory)
        (directory / "oma_entry.json").write_text(json.dumps(entry, indent=2))
        entry_number = entry["entry_nr"]
        response = request_with_retries(session, "GET", f"{API}/protein/{entry_number}/orthologs/", timeout=120)
        response.raise_for_status()
        orthologs = response.json()
    (directory / "oma_orthologs.json").write_text(json.dumps(orthologs, indent=2))
    if not isinstance(orthologs, list):
        raise RuntimeError("Unexpected OMA ortholog schema; raw response retained in " + str(directory))
    rows = []
    for row in orthologs:
        if not isinstance(row, dict) or "omaid" not in row:
            continue
        score = float(row.get("score", 0.0) or 0.0)
        if score < minimum_score:
            continue
        species = row.get("species") or {}
        rows.append({"omaid": row.get("omaid"), "canonicalid": row.get("canonicalid"),
                     "species": species.get("species"), "species_code": species.get("code"),
                     "taxon_id": species.get("taxon_id"), "relationship_type": row.get("rel_type"),
                     "score": score, "distance": row.get("distance"),
                     "oma_group": row.get("oma_group"), "oma_hog_id": row.get("oma_hog_id"),
                     "sequence_length": row.get("sequence_length"), "entry_url": row.get("entry_url")})
    rows.sort(key=lambda row: (-row["score"], row["species"] or ""))
    by_species = {}
    by_relationship = {}
    for row in rows:
        by_species[row["species"] or "unknown"] = by_species.get(row["species"] or "unknown", 0) + 1
        by_relationship[row["relationship_type"] or "unknown"] = by_relationship.get(row["relationship_type"] or "unknown", 0) + 1
    return json.dumps({
        "source": "OMA (Orthologous MAtrix) public REST API",
        "query_identifier": identifier,
        "query": {"omaid": entry.get("omaid"), "canonicalid": entry.get("canonicalid"),
                  "entry_nr": entry_number, "species": (entry.get("species") or {}).get("species"),
                  "taxon_id": (entry.get("species") or {}).get("taxon_id"),
                  "sequence_length": entry.get("sequence_length"), "oma_hog_id": entry.get("oma_hog_id")},
        "source_urls": {"entry": f"{API}/protein/{identifier}/",
                        "orthologs": f"{API}/protein/{entry_number}/orthologs/"},
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "total_provider_orthologs": len(orthologs), "eligible_orthologs": len(rows),
        "total_orthologs": len(rows), "returned_orthologs": len(rows[:max_results]),
        "truncated": len(rows) > max_results, "minimum_score": minimum_score,
        "orthologs_by_species": dict(sorted(by_species.items(), key=lambda item: -item[1])),
        "orthologs_by_relationship_type": by_relationship,
        "orthologs": rows[:max_results],
        "artifacts": {"entry": str(directory / "oma_entry.json"),
                      "orthologs": str(directory / "oma_orthologs.json")},
        "scope": "OMA-published orthology calls; the OMA orthology relationship and score are preserved verbatim",
    }, ensure_ascii=False)
