"""ChemSpider's current authenticated API; ChemSpider record IDs remain distinct from PubChem CIDs."""

import json
import time
import requests
from tools.runtime.config import Config


def inchi_to_csid(inchi: str):
    """Resolve an InChI to actual ChemSpider record IDs using the RSC filter API and personal API key."""
    inchi = inchi.strip()
    if not inchi.startswith(("InChI=1S/", "InChI=1/")) or len(inchi) > 4000:
        raise ValueError("Expected a valid InChI string of at most 4000 characters")
    key = Config().CHEMSPIDER_API_KEY
    if not key:
        raise RuntimeError("Missing CHEMSPIDER_API_KEY")
    base = "https://api.rsc.org/compounds/v1"
    with requests.Session() as session:
        session.headers["apikey"] = key

        def request(method, path, **kwargs):
            response = session.request(method, base + path, timeout=20, **kwargs)
            if not response.ok:
                raise RuntimeError(f"ChemSpider HTTP {response.status_code} at {path}")
            return response.json()

        submitted = request("POST", "/filter/inchi", json={"inchi": inchi})
        query_id = submitted["queryId"]
        deadline = time.monotonic() + 60
        time.sleep(10)  # Publisher recommendation: wait ten seconds before polling.
        while time.monotonic() < deadline:
            status = request("GET", "/filter/" + query_id + "/status")
            state = status.get("status")
            if state == "Complete":
                result = request(
                    "GET",
                    "/filter/" + query_id + "/results",
                    params={"start": 0, "count": 100},
                )
                ids = result.get("results")
                if not isinstance(ids, list) or any(
                    not isinstance(value, int) or value <= 0 for value in ids
                ):
                    raise RuntimeError("Unexpected ChemSpider record ID schema")
                return json.dumps(
                    {
                        "source": "ChemSpider RSC compounds/v1",
                        "inchi": inchi,
                        "chemspider_record_ids": ids,
                        "match_status": "matched" if ids else "no_matches",
                        "limited_to_max_allowed": result.get("limitedToMaxAllowed"),
                    }
                )
            if state in ["Suspended", "Failed", "NotFound", "Not Found"]:
                raise RuntimeError("ChemSpider query ended with status " + state)
            time.sleep(5)
    raise TimeoutError("ChemSpider query did not complete within sixty seconds")
