"""Public PubChem queries with bounded retries and genuine, dated structure-response caches."""

from src.utils.paths import local_root, artifacts_root
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
import requests
from urllib.parse import quote

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/"
TRANSIENT_CODES = {429, 500, 502, 503, 504}


class PubChemUnavailable(requests.HTTPError):
    """The real upstream remains unavailable after the bounded request budget."""


def retry_delay(response, attempt):
    """Honor Retry-After; stop instead of retrying early if it exceeds our wait budget."""
    value = response.headers.get("Retry-After")
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = (
                    parsedate_to_datetime(value) - datetime.now(timezone.utc)
                ).total_seconds()
            except (ValueError, TypeError):
                delay = 2**attempt
        return max(0.0, delay)
    return float(2**attempt)


def http_diagnostics(response):
    """Preserve upstream load feedback without recording request identifiers or credentials."""
    return {
        "status_code": response.status_code,
        "retry_after": response.headers.get("Retry-After"),
        "throttling_control": response.headers.get("X-Throttling-Control"),
    }


def get(endpoint, params=None):
    with requests.Session() as session:
        session.trust_env = False
        for attempt in range(2):
            try:
                response = session.get(
                    BASE_URL + endpoint, params=params, timeout=(5, 20)
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 1:
                    raise
                time.sleep(1)
                continue
            if response.status_code in TRANSIENT_CODES and attempt == 0:
                delay = retry_delay(response, attempt)
                if delay <= 60:
                    logging.warning(
                        "PubChem HTTP feedback %s; waiting %.1f seconds before one retry",
                        json.dumps(http_diagnostics(response)),
                        delay,
                    )
                    response.close()
                    time.sleep(delay)
                    continue
            if response.status_code in TRANSIENT_CODES:
                raise PubChemUnavailable(
                    f"PubChem HTTP {response.status_code} after bounded retries; "
                    "retry this task later; upstream feedback="
                    + json.dumps(http_diagnostics(response)),
                    response=response,
                )
            response.raise_for_status()
            return response


def cache_directory():
    default = local_root() / "data/pubchem_structure_cache"
    return Path(os.getenv("SCITOOL_PUBCHEM_CACHE", str(default)))


def read_cache(path, url):
    try:
        cached = json.loads(path.read_text())
        raw = cached["response_text"]
        age = (
            datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])
        ).total_seconds()
        if (
            cached["source_url"] == url
            and 0 <= age <= 7 * 86400
            and cached["response_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
        ):
            record = json.loads(raw)["PropertyTable"]["Properties"][0]
            smiles_property(record)
            return cached, record, age
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass
    return None


def properties(identifier, kind="name"):
    """Return a PubChem structure record plus _scitool_source provenance (never benchmark data)."""
    if kind not in {"name", "inchikey", "cid", "smiles", "inchi"}:
        raise ValueError("Unsupported PubChem structure identifier kind")
    endpoint = f"rest/pug/compound/{kind}/{quote(str(identifier).strip(), safe='')}/property/SMILES,InChI/JSON"
    url = BASE_URL + endpoint
    path = cache_directory() / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    cached = read_cache(path, url) if kind == "name" else None
    if cached and cached[2] <= 86400:
        entry, record, age = cached
        record["_scitool_source"] = {
            "source_url": url,
            "fetched_at": entry["fetched_at"],
            "response_sha256": entry["response_sha256"],
            "mode": "cache",
            "age_seconds": age,
        }
        return record
    try:
        response = get(endpoint)
    except requests.RequestException as error:
        status = error.response.status_code if error.response is not None else None
        if not cached or (status is not None and status not in TRANSIENT_CODES):
            raise
        entry, record, age = cached
        record["_scitool_source"] = {
            "source_url": url,
            "fetched_at": entry["fetched_at"],
            "response_sha256": entry["response_sha256"],
            "mode": "cache_after_transient_error",
            "age_seconds": age,
            "live_error": type(error).__name__,
            "live_http_status": status,
        }
        return record
    record = response.json()["PropertyTable"]["Properties"][0]
    smiles_property(record)
    entry = {
        "source_url": response.url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "response_sha256": hashlib.sha256(response.text.encode()).hexdigest(),
        "response_text": response.text,
    }
    try:
        if kind != "name":
            record["_scitool_source"] = {
                key: value for key, value in entry.items() if key != "response_text"
            }
            record["_scitool_source"]["mode"] = "live"
            return record
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False, encoding="utf-8"
        ) as temporary:
            temporary.write(json.dumps(entry, ensure_ascii=False) + "\n")
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    except OSError as error:
        logging.warning(
            "Cannot persist PubChem response cache: %s", type(error).__name__
        )
    record["_scitool_source"] = {
        key: value for key, value in entry.items() if key != "response_text"
    }
    record["_scitool_source"]["mode"] = "live"
    return record


def smiles_property(record):
    for key in ["SMILES", "IsomericSMILES", "CanonicalSMILES", "ConnectivitySMILES"]:
        if key in record:
            return record[key]
    raise KeyError("PubChem record contains no SMILES property")
