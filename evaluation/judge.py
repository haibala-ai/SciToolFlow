"""Optional API or local-model review, bound to exact pending score requests."""

from datetime import datetime, timezone
import json
from pathlib import Path
from scitoolflow.models.client import GenerationClient
from scitoolflow.protocol import parse_reply

PROMPT = """Review a scientific tool-use evaluation using the full question, inputs,
actual tool evidence and reference. Judge only dimensions marked pending (null).
Never override an already false numerical/schema answer judgement. A shorter plan can
be valid if its real tool results provide the required information; mere tool names,
imagined outputs and a copied final answer do not prove execution. Equivalent English
wording can pass when all required scientific statements, objects, units and values agree.
Return one JSON object with planning_pass and answer_pass (boolean or null) and a brief
rationale. Use null when evidence is incomplete or you cannot decide. Do not include
private chain-of-thought or invent missing scientific evidence."""


def judge_requests(
    request_path,
    output,
    *,
    client=None,
    backend="vllm",
    model=None,
    max_output_tokens=1536,
    max_context_chars=200000
):
    if max_output_tokens <= 0 or max_context_chars <= 0:
        raise ValueError("Judge token/context limits must be positive")
    owned = client is None
    if owned:
        from scitoolflow.paths import load_environment

        load_environment()
    client = client or GenerationClient(backend)
    if model:
        client.model = model
    model_name = getattr(client, "model", "injected")
    if client.backend not in {"api", "vllm", "local", "injected"}:
        raise ValueError("Judge backend must be api, vllm or local")
    if client.backend == "api" and not client.model:
        raise ValueError("Configure --model or SCITOOLFLOW_API_MODEL for the API judge")
    provider = client.public_settings() if hasattr(client, "public_settings") else {}
    requests = json.loads(Path(request_path).read_text())["tasks"]
    reviews = []
    unresolved = []
    model_requests = 0
    try:
        for request in requests:
            if request.get("requires_independent_review"):
                unresolved.append(
                    {
                        "id": request["id"],
                        "reason": "Changed data source requires independent review; automatic model judgement skipped.",
                    }
                )
                continue
            messages = [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
            ]
            try:
                too_large = (
                    len(json.dumps(messages, ensure_ascii=False)) > max_context_chars
                )
                if client.backend == "vllm":
                    too_large |= client.count_tokens(messages) > client.input_budget(
                        max_output_tokens
                    )
                if too_large:
                    unresolved.append(
                        {
                            "id": request["id"],
                            "reason": "Complete evidence does not fit the judge context; no truncated judgement made.",
                        }
                    )
                    continue
                # Only an explicit judge command reaches this generation scope.
                model_requests += 1
                with client.react_request_scope():
                    reply = client.request(
                        messages, max_tokens=max_output_tokens, timeout=180
                    )
                verdict = parse_reply(reply["text"])
                rationale = verdict.get("rationale")
                if not isinstance(rationale, str) or not rationale.strip():
                    raise ValueError("Judge must supply a brief rationale")
                row = {
                    k: request[k]
                    for k in ["id", "reference_sha256", "prediction_sha256"]
                }
                for key in ["planning_pass", "answer_pass"]:
                    value = verdict.get(key)
                    if request.get(key) is None and value is not None:
                        if type(value) is not bool:
                            raise ValueError("Judge verdicts must be boolean or null")
                        row[key] = value
                row.update(
                    reviewer=(
                        "local_vllm" if client.backend == "vllm" else client.backend
                    )
                    + ":"
                    + model_name,
                    reviewer_kind="llm",
                    rationale=rationale,
                    reviewed_at=datetime.now(timezone.utc).isoformat(),
                    model=model_name,
                    response_id=reply.get("response_id"),
                    usage=reply.get("usage"),
                    response_model=reply.get("model"),
                    execution_mode=(
                        "resident_service"
                        if reply.get("device_map") == "resident_service"
                        else (
                            "transformers"
                            if isinstance(reply.get("device_map"), dict)
                            else None
                        )
                    ),
                )
                reviews.append(row)
            except Exception as error:
                unresolved.append(
                    {
                        "id": request["id"],
                        "reason": type(error).__name__ + ": " + str(error)[:500],
                    }
                )
    finally:
        if owned:
            client.close()
    from urllib.parse import urlparse

    external_api = (
        client.backend == "api"
        and model_requests > 0
        and urlparse(provider.get("endpoint", "")).hostname
        not in {"localhost", "127.0.0.1", "::1"}
    )
    result = {
        "reviews": reviews,
        "unresolved": unresolved,
        "judge": client.backend + ":" + model_name,
        "backend": client.backend,
        "provider": provider,
        "model_requests": model_requests,
        "api_backend_used": client.backend == "api" and model_requests > 0,
        "external_api_used": external_api,
        "automatic_llm_review_not_human_certification": True,
        "paid_model_api_used": None if external_api else False,
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result
