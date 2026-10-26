"""Direct human interaction lookup in an actual, dated HIPPIE dataset snapshot."""
from src.utils.paths import local_root, artifacts_root
import csv
import json
from pathlib import Path
import re
import requests

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()


def hippie_interactors(identifier: str, minimum_confidence: float = 0.73, max_results: int = 100):
    """HIPPIE2.4 direct human interaction partners, confidence-filtered; UniProt entry name or Entrez ID, symbol/accession resolved via UniProt."""
    if not 0 <= minimum_confidence <= 1 or not 1 <= max_results <= 1000:
        raise ValueError("Require confidence 0..1 and maximum 1..1000 rows")
    query = identifier.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{1,40}", query):
        raise ValueError("Require a UniProt identifier, human gene symbol, or Entrez ID")
    resolved = query
    resolution = None
    if not query.isdigit() and not query.endswith("_HUMAN"):
        with requests.Session() as session:
            response = request_with_retries(session, "GET", "https://rest.uniprot.org/uniprotkb/search", params={
                "query": f"(accession:{query} OR gene_exact:{query}) AND organism_id:9606 AND reviewed:true",
                "format": "json", "size": 5}, timeout=30)
        response.raise_for_status()
        records = response.json()["results"]
        if len(records) != 1:
            raise ValueError("Human UniProt resolution was ambiguous or absent; supply an exact _HUMAN entry name or Entrez ID")
        resolved = records[0]["uniProtkbId"]
        resolution = {"source": "UniProt REST", "accession": records[0]["primaryAccession"], "entry_name": resolved}
    dataset = ROOT / "reference_data/HIPPIE/hippie_v2_4_20261013.tsv"
    manifest = json.loads((ROOT / "provenance/hippie_dataset_download.json").read_text())
    matches, total = [], 0
    with dataset.open() as file:
        for values in csv.reader(file, delimiter="\t"):
            if len(values) != 6:
                raise RuntimeError("Unexpected HIPPIE six-column dataset row")
            if resolved not in values[:4]:
                continue
            confidence = float(values[4])
            if confidence < minimum_confidence:
                continue
            total += 1
            if len(matches) < max_results:
                matches.append({"protein_a": values[0], "entrez_a": values[1], "protein_b": values[2],
                                "entrez_b": values[3], "confidence": confidence, "evidence": values[5]})
    return json.dumps({"source": "HIPPIE2.4 dated local snapshot", "dataset_provenance": manifest,
                       "input": identifier, "resolved_identifier": resolved, "identifier_resolution": resolution,
                       "minimum_confidence": minimum_confidence, "total_matches": total,
                       "returned_matches": len(matches), "truncated": total > len(matches), "interactions": matches,
                       "scope": "direct reported human interactions; scores are dataset confidence, not experimental validation"})
