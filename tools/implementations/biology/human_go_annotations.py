"""Read existing human GO annotations with explicit evidence filters.

These adapters are not the INGA prediction algorithm. They accept accessions,
never sequence inputs, submit no prediction jobs, and return no mutation advice.
"""
from src.utils.paths import local_root, artifacts_root
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import requests

from tools.implementations.shared.http_retry import request_with_retries
from tools.implementations.shared.materials_api import MissingScientificData

ROOT = local_root()


def annotations(accession, method):
    if method not in {"all", "architecture", "homology", "interaction"}:
        raise ValueError("Unsupported GO evidence filter")
    if not isinstance(accession, str):
        raise ValueError("uniprot_accession must be a string")
    accession = accession.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{6}(?:[A-Z0-9]{4})?", accession):
        raise ValueError("Provide a UniProt accession, not a protein sequence")
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
    with requests.Session() as session:
        session.trust_env = os.getenv("SCITOOL_UNIPROT_USE_PROXY", "0") == "1"
        response = request_with_retries(session, "GET", url, timeout=(8,30))
        if response.status_code == 404:
            raise MissingScientificData("No published UniProt entry for this accession")
        response.raise_for_status()
        record = response.json()
    if record.get("organism", {}).get("taxonId") != 9606:
        raise ValueError("This annotation-only adapter is limited to human entries (taxon 9606)")
    if record.get("primaryAccession") != accession:
        raise ValueError("Returned accession differs from the requested accession")
    selected = []
    for reference in record.get("uniProtKBCrossReferences", []):
        if reference.get("database") != "GO":
            continue
        properties = {p["key"]:p["value"] for p in reference.get("properties", [])}
        evidence = properties.get("GoEvidenceType", "")
        code, _, origin = evidence.partition(":")
        matches = (method == "all" or (method == "architecture" and code == "IEA" and origin == "InterPro") or
                   (method == "homology" and code in {"ISS", "ISO", "ISA", "ISM"}) or
                   (method == "interaction" and code in {"IPI", "HPI"}))
        if matches:
            selected.append({"go_id": reference["id"], "term": properties.get("GoTerm"),
                             "evidence_code":code,"evidence_source":origin})
    # Retain only the annotations we actually use, not sequence/variant data.
    source = {"source_url":url,"primary_accession":accession,"taxon_id":9606,
              "fetched_at":datetime.now(timezone.utc).isoformat(),"annotations":selected,
              "response_sha256":hashlib.sha256(response.content).hexdigest()}
    directory = artifacts_root() / "human_go_annotations"
    directory.mkdir(parents=True,exist_ok=True)
    artifact = directory / f"{accession}_{method}_{hashlib.sha256(response.content).hexdigest()[:12]}.json"
    artifact.write_text(json.dumps(source,indent=2,ensure_ascii=False)+"\n")
    return json.dumps({**source,"backend":"UniProt existing human GO evidence",
                       "method_filter":method,"annotation_count":len(selected),"artifact":str(artifact),
                       "is_INGA_prediction":False,"sequence_submitted":False,
                       "scope":"Existing evidence-filtered annotations only; empty list is a valid scientific absence"},ensure_ascii=False)


def get_human_go_annotations(uniprot_accession: str, evidence_filter: str = "all"):
    """Retrieve published human UniProt GO annotations, optionally filtering evidence.

    evidence_filter: all, interpro (IEA:InterPro), homology (ISS/ISO/ISA/ISM),
    interaction (IPI/HPI). This is a record lookup, not INGA prediction,
    sequence search, new PPI inference or ontology propagation. Only human
    entries are accepted; absent accessions, nonhuman entries and network or
    response failures raise. Empty annotation lists are valid negatives.
    """
    choices = {"all": "all", "interpro": "architecture", "homology": "homology", "interaction": "interaction"}
    if evidence_filter not in choices:
        raise ValueError("evidence_filter must be all, interpro, homology or interaction")
    return annotations(uniprot_accession, choices[evidence_filter])


def architecture_annotations(uniprot_accession: str):
    """Read existing human GO terms with IEA:InterPro evidence; not an INGA prediction."""
    return annotations(uniprot_accession,"architecture")


def homology_annotations(uniprot_accession: str):
    """Read existing human GO terms with ISS/ISO/ISA/ISM evidence; no sequence search or prediction."""
    return annotations(uniprot_accession,"homology")


def interaction_annotations(uniprot_accession: str):
    """Read existing human GO terms with IPI/HPI evidence; no interaction or mutation prediction."""
    return annotations(uniprot_accession,"interaction")
