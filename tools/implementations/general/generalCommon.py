"""Remote computational query and local PDF QA adapters.

Obsolete Bing/download implementations are excluded from the active runtime.
"""

import os
import requests
from tools.runtime.config import Config


def wolfram_alpha_query_tool(query: str) -> str:
    """
    Returns an answer to a query using the Wolfram Alpha API.

    Args:
        query (str): The query for the search.

    Returns:
        str: A summary of the answer from Wolfram Alpha.

    Notes:
    - Ensure you have a Wolfram Alpha developer account and an App ID.
    - Uses the Full Results REST API and the requests package.
    - Set your Wolfram Alpha App ID in the WOLFRAM_ALPHA_APPID environment variable.
    """
    with requests.Session() as session:
        session.trust_env = os.getenv("SCITOOL_WOLFRAM_USE_PROXY", "0") == "1"
        response = session.get(
            "https://api.wolframalpha.com/v2/query",
            params={
                "appid": Config().WOLFRAM_ALPHA_APPID,
                "input": query,
                "output": "JSON",
            },
            timeout=25,
        )
    if not response.ok:
        raise RuntimeError(f"Wolfram Alpha HTTP {response.status_code}")
    result = response.json()["queryresult"]
    if not result.get("success"):
        raise ValueError("Wolfram Alpha could not answer this query")
    pods = result.get("pods", [])
    assumption = (
        "\n".join(part.get("plaintext", "") for part in pods[0].get("subpods", []))
        if pods
        else ""
    )
    answers = [
        part.get("plaintext", "")
        for pod in pods
        if pod.get("primary") or pod.get("id") == "Result"
        for part in pod.get("subpods", [])
    ]
    answers = [answer for answer in answers if answer]
    if not answers:
        raise ValueError("Wolfram Alpha returned no textual result")
    return f"Assumption: {assumption}\nAnswer: " + "\n".join(answers)


def get_paperqa(question):
    """Answer questions from local PDFs with local Qwen retrieval and generation."""
    from tools.implementations.general.local_paperqa import answer_question

    return answer_question(question)


def bing_search_tool(query: str):
    """Obsolete internal adapter; query the current BingSearch contract."""
    raise ValueError("Obsolete adapter. Call BingSearch through tools.executor with its explicit current contract.")


def download_papers_from_arxiv_single(keyword):
    """Obsolete internal adapter; query the current DownloadPapers contract."""
    raise ValueError("Obsolete adapter. Call DownloadPapers through tools.executor with its explicit current contract.")


def download_papers_from_arxiv(keywords_str, max_results=5):
    """Obsolete internal adapter; query the current DownloadPapers contract."""
    raise ValueError("Obsolete adapter. Call DownloadPapers through tools.executor with its explicit current contract.")


