"""Conventional Brave web search with readable failures and result provenance.

The benchmark name BingSearch is retained, but the retired Bing Web Search v7
endpoint is never requested. Proxy settings follow the deployment environment.
"""

import json

import requests

from tools.runtime.config import Config
from tools.implementations.shared.materials_api import UnavailableScientificEndpoint

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def _brave(query, max_results, key):
    response = requests.get(
        BRAVE_URL,
        headers={"Accept": "application/json", "X-Subscription-Token": key},
        params={"q": query, "count": max_results},
        timeout=25,
    )
    if not response.ok:
        raise RuntimeError(f"Brave Web Search HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("web", {}), dict):
        raise RuntimeError("Unexpected Brave web response schema")
    records = payload.get("web", {}).get("results", [])
    if not isinstance(records, list):
        raise RuntimeError("Unexpected Brave web result schema")
    if any(
        not isinstance(record, dict)
        or not isinstance(record.get("title"), str)
        or not isinstance(record.get("url"), str)
        for record in records
    ):
        raise RuntimeError("Unexpected Brave result fields")
    return "Brave Web Search", [
        {
            "title": record["title"],
            "url": record["url"],
            "description": record.get("description", ""),
        }
        for record in records[:max_results]
    ]


def search_web(query: str, max_results: int = 5):
    """Return web search URLs, titles and snippets from Brave Search; Bing v7 is retired."""
    if (
        not isinstance(query, str)
        or not query.strip()
        or isinstance(max_results, bool)
        or not isinstance(max_results, int)
        or not 1 <= max_results <= 20
    ):
        raise ValueError("Require a non-empty query and 1-20 results")
    config = Config()
    attempts = []
    for name, key, call in [("Brave Web Search", config.BRAVE_SEARCH_API_KEY, _brave)]:
        if not key:
            attempts.append(f"{name}: no API key configured")
            continue
        try:
            provider, results = call(query, max_results, key)
        except requests.exceptions.RequestException as error:
            attempts.append(f"{name}: unreachable ({type(error).__name__})")
            continue
        except Exception as error:  # provider answered but not with a usable payload
            attempts.append(f"{name}: {error}")
            continue
        return json.dumps(
            {
                "provider": provider,
                "query": query,
                "results": results,
                "result_status": "results_found" if results else "no_results",
                "provider_attempts": attempts,
            }
        )
    raise UnavailableScientificEndpoint(
        "No web search provider is available. Configure BRAVE_SEARCH_API_KEY (https://brave.com/search/api/) "
        "and check the HTTPS proxy/network. Bing Web Search v7 retired on 2025-08-11; "
        "BING_SUBSCRIPTION_KEY cannot restore it. Attempts: " + "; ".join(attempts)
    )
