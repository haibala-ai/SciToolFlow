"""Generation clients for compatible APIs, resident vLLM and local Qwen workers."""

import json
import math
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlparse

GENERATION_ACTIVE = ContextVar("scitoolflow_generation_active", default=False)


def response_error(message, response):
    error = RuntimeError(message)
    error.generation_usage = response.get("usage")
    # Preserve returned model content on truncation/failure without storing
    # request headers, credentials or an arbitrary provider error body.
    choice = (response.get("choices") or [{}])[0]
    returned_message = choice.get("message") or {}
    error.generation_response = {
        "text": returned_message.get("content"),
        "message_metadata": {
            k: v for k, v in returned_message.items() if k != "content"
        },
        "finish_reason": choice.get("finish_reason"),
        "usage": response.get("usage"),
        "model": response.get("model"),
        "response_id": response.get("id"),
    }
    return error


def preflight_timeout(default, remaining):
    if remaining is None:
        return default
    if (
        isinstance(remaining, bool)
        or not isinstance(remaining, (int, float))
        or not math.isfinite(remaining)
        or remaining <= 0
    ):
        raise ValueError("Remaining preflight timeout must be finite and positive")
    return min(default, remaining)


def resolve_api_connection():
    """Generation credentials are configured separately from retrieval embeddings."""
    from src.utils.paths import load_environment

    load_environment()
    base = (
        os.getenv("SCITOOLFLOW_API_BASE")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    key = os.getenv("SCITOOLFLOW_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if not key:
        raise ValueError(
            "API generation requires SCITOOLFLOW_API_KEY (or OPENAI_API_KEY); embedding credentials are separate"
        )
    return base, key


class GenerationClient:
    supports_preflight_timeout = True

    def __init__(self, backend=None, session=None):
        self.backend = backend or os.getenv("SCITOOLFLOW_LLM_BACKEND", "vllm")
        if self.backend == "local":
            from src.utils.paths import local_root

            self.model = os.getenv(
                "SCITOOL_MODEL_PATH", str(local_root() / "models/Qwen3.5-9B")
            )
        elif self.backend == "vllm":
            # A resident service keeps the selected model loaded between tasks.
            self.model = os.getenv("SCITOOLFLOW_VLLM_MODEL", "Qwen3.5-9B")
        else:
            self.model = os.getenv("SCITOOLFLOW_API_MODEL", "")
        self._session = session
        self._owns_session = session is None
        self._api_connection = None
        self._transport = (
            "requests"
            if session is not None
            else os.getenv("SCITOOLFLOW_API_TRANSPORT", "requests")
        )
        self._trust_env = os.getenv("SCITOOLFLOW_API_TRUST_ENV", "1") != "0"
        if self.backend not in ["local", "api", "vllm"]:
            raise ValueError("Backend must be local, api or vllm")

    @contextmanager
    def generation_scope(self):
        """Authorize generation within an explicitly requested baseline session."""
        token = GENERATION_ACTIVE.set(True)
        try:
            yield
        finally:
            GENERATION_ACTIVE.reset(token)

    @property
    def supports_response_schema(self):
        return self.backend == "vllm" or (
            self.backend == "api"
            and os.getenv("SCITOOLFLOW_API_STRUCTURED_OUTPUT", "0") == "1"
        )

    def public_settings(self):
        """Bind runs to effective provider settings without recording credentials."""
        import hashlib

        if self.backend == "api":
            base, _ = resolve_api_connection()
            parsed = urlparse(base)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError(
                    "API base must not contain credentials, query parameters or fragments"
                )
            extra = json.loads(os.getenv("SCITOOLFLOW_API_EXTRA_BODY", "{}"))
            if not isinstance(extra, dict):
                raise ValueError("SCITOOLFLOW_API_EXTRA_BODY must be a JSON object")
            return {
                "endpoint": base,
                "transport": self._transport,
                "trust_env": self._trust_env,
                "connect_timeout_seconds": (
                    float(os.environ["SCITOOLFLOW_API_CONNECT_TIMEOUT"])
                    if "SCITOOLFLOW_API_CONNECT_TIMEOUT" in os.environ
                    else None
                ),
                "connect_retries": 2 if self._transport == "httpx" else 0,
                "token_parameter": os.getenv(
                    "SCITOOLFLOW_API_TOKEN_PARAMETER", "max_completion_tokens"
                ),
                "json_mode": os.getenv("SCITOOLFLOW_API_JSON_MODE", "1") == "1",
                "structured_output": self.supports_response_schema,
                "sampling": {
                    k: extra[k]
                    for k in [
                        "temperature",
                        "top_p",
                        "top_k",
                        "repetition_penalty",
                        "seed",
                    ]
                    if k in extra
                },
                "extra_body_sha256": hashlib.sha256(
                    json.dumps(extra, sort_keys=True).encode()
                ).hexdigest(),
                "max_completion_tokens": int(
                    os.getenv("SCITOOLFLOW_API_MAX_COMPLETION_TOKENS", "4096")
                ),
                "timeout_seconds": float(os.getenv("SCITOOLFLOW_API_TIMEOUT", "120")),
            }
        if self.backend == "vllm":
            base = os.getenv(
                "SCITOOLFLOW_VLLM_BASE", "http://127.0.0.1:8016/v1"
            ).rstrip("/")
            parsed = urlparse(base)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError(
                    "vLLM base must not contain credentials, query parameters or fragments"
                )
            return {
                "endpoint": base,
                "temperature": float(os.getenv("SCITOOLFLOW_VLLM_TEMPERATURE", "0.2")),
                "top_p": float(os.getenv("SCITOOLFLOW_VLLM_TOP_P", "0.95")),
                "top_k": int(os.getenv("SCITOOLFLOW_VLLM_TOP_K", "-1")),
                "repetition_penalty": float(
                    os.getenv("SCITOOLFLOW_VLLM_REPETITION_PENALTY", "1.08")
                ),
                "structured_output": True,
                "native_thinking": os.getenv("SCITOOLFLOW_ENABLE_MODEL_THINKING", "0")
                == "1",
            }
        from src.models.local_worker import service_setting
        from src.models.local import local_gpu_devices

        resident_base = service_setting("BASE", "http://127.0.0.1:8016/v1").rstrip("/")
        parsed = urlparse(resident_base)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "Resident service base must not contain credentials, query parameters or fragments"
            )
        return {
            "endpoint": None,
            "model_path": self.model,
            "structured_output": False,
            "gpu_devices": local_gpu_devices(),
            "gpu_reserve_mb": int(os.getenv("SCITOOL_LLM_GPU_RESERVE_MB", "2048")),
            "gpu_budget_fraction": float(
                os.getenv("SCITOOL_LLM_GPU_BUDGET_FRACTION", "1.0")
            ),
            "native_thinking": os.getenv("SCITOOLFLOW_ENABLE_MODEL_THINKING", "0")
            == "1",
            "direct_decoding": "greedy",
            "same_weight_resident_settings": {
                "endpoint": resident_base,
                "model": service_setting("MODEL", "Qwen3.5-9B"),
                "temperature": float(service_setting("TEMPERATURE", "0.2")),
                "top_p": float(service_setting("TOP_P", "0.95")),
                "repetition_penalty": float(
                    service_setting("REPETITION_PENALTY", "1.08")
                ),
            },
        }

    def request(self, messages, max_tokens=4096, timeout=None, response_schema=None):
        if response_schema is not None and not self.supports_response_schema:
            raise ValueError(
                "Enable API structured output support or use the vLLM backend for schema-constrained replies"
            )
        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or max_tokens <= 0
        ):
            raise ValueError("max_tokens must be a positive integer")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("Remaining request timeout must be positive")
        if self.backend == "local":
            from src.utils.paths import bootstrap_runtime

            bootstrap_runtime()
            from src.models.local import RUNTIME

            if timeout is None:
                return RUNTIME.request(
                    "chat",
                    messages=messages,
                    max_tokens=max_tokens,
                    model_path=self.model,
                )
            from tools.runtime.context import TOOL_DEADLINE

            parent_deadline = TOOL_DEADLINE.get()
            deadline = time.monotonic() + timeout
            token = TOOL_DEADLINE.set(
                min(deadline, parent_deadline) if parent_deadline else deadline
            )
            try:
                return RUNTIME.request(
                    "chat",
                    messages=messages,
                    max_tokens=max_tokens,
                    model_path=self.model,
                )
            finally:
                TOOL_DEADLINE.reset(token)
        if not GENERATION_ACTIVE.get():
            raise RuntimeError("Generation requires an explicit baseline request scope")
        if self.backend == "vllm":
            return self._vllm_request(messages, max_tokens, timeout, response_schema)
        if self._api_connection is None:
            self._api_connection = resolve_api_connection()
        if not self.model:
            raise ValueError(
                "Configure --model or SCITOOLFLOW_API_MODEL for API generation"
            )
        base, key = self._api_connection
        parsed = urlparse(base)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in ["localhost", "127.0.0.1"]
        ):
            raise ValueError(
                "Use HTTPS for the generation API, or a loopback HTTP test server"
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "API base must not contain credentials, query parameters or fragments"
            )
        import requests

        exceptions = (requests.RequestException,)
        if self._transport == "httpx":
            import httpx

            exceptions = exceptions + (httpx.HTTPError,)
        elif self._transport != "requests":
            raise ValueError("API transport must be requests or httpx")
        cap = int(os.getenv("SCITOOLFLOW_API_MAX_COMPLETION_TOKENS", "4096"))
        request_timeout = float(os.getenv("SCITOOLFLOW_API_TIMEOUT", "120"))
        if cap <= 0 or not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("API token and timeout caps must be positive")
        connect_timeout = os.getenv("SCITOOLFLOW_API_CONNECT_TIMEOUT")
        if connect_timeout is not None:
            connect_timeout = float(connect_timeout)
            if not math.isfinite(connect_timeout) or connect_timeout <= 0:
                raise ValueError("API connect timeout must be positive and finite")
        if timeout is not None:
            request_timeout = min(request_timeout, timeout)
        token_parameter = os.getenv(
            "SCITOOLFLOW_API_TOKEN_PARAMETER", "max_completion_tokens"
        )
        if token_parameter not in {"max_tokens", "max_completion_tokens"}:
            raise ValueError(
                "SCITOOLFLOW_API_TOKEN_PARAMETER must be max_tokens or max_completion_tokens"
            )
        payload = {
            "model": self.model,
            "messages": messages,
            token_parameter: min(max_tokens, cap),
        }
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "scitoolflow_decision",
                    "strict": False,
                    "schema": response_schema,
                },
            }
        elif os.getenv("SCITOOLFLOW_API_JSON_MODE", "1") == "1":
            payload["response_format"] = {"type": "json_object"}
        extra = json.loads(os.getenv("SCITOOLFLOW_API_EXTRA_BODY", "{}"))
        if not isinstance(extra, dict):
            raise ValueError("SCITOOLFLOW_API_EXTRA_BODY must be a JSON object")
        if {
            "model",
            "messages",
            "max_completion_tokens",
            "max_tokens",
            "response_format",
        } & set(extra):
            raise ValueError(
                "Extra API parameters cannot override model, messages or token budget"
            )
        payload.update(extra)
        if self._session is None:
            if self._transport == "httpx":
                self._session = httpx.Client(trust_env=self._trust_env)
            else:
                self._session = requests.Session()
                self._session.trust_env = self._trust_env
        start = time.monotonic()
        connection_attempts = 0
        try:
            while True:
                connection_attempts += 1
                remaining = request_timeout - (time.monotonic() - start)
                attempt_timeout = max(0.001, remaining)
                if connect_timeout is not None:
                    attempt_timeout = (
                        httpx.Timeout(
                            attempt_timeout,
                            connect=min(connect_timeout, attempt_timeout),
                        )
                        if self._transport == "httpx"
                        else (min(connect_timeout, attempt_timeout), attempt_timeout)
                    )
                try:
                    response = self._session.post(
                        base + "/chat/completions",
                        headers={"Authorization": "Bearer " + key},
                        json=payload,
                        timeout=attempt_timeout,
                    )
                    break
                except exceptions as error:
                    # ConnectError/ConnectTimeout occur before the HTTP request
                    # is sent. Never retry read/write failures or HTTP responses:
                    # those may already represent a billed model generation.
                    retryable = self._transport == "httpx" and isinstance(
                        error, (httpx.ConnectError, httpx.ConnectTimeout)
                    )
                    remaining = request_timeout - (time.monotonic() - start)
                    if not retryable or connection_attempts >= 3 or remaining <= 0.25:
                        raise
                    time.sleep(0.25)
        except exceptions as error:
            diagnostic = []
            cause = error
            for _ in range(5):
                if cause is None:
                    break
                diagnostic.append(type(cause).__name__)
                cause = cause.__cause__ or cause.__context__
            markers = [
                name
                for name in [
                    "CERTIFICATE_VERIFY_FAILED",
                    "UNEXPECTED_EOF",
                    "WRONG_VERSION_NUMBER",
                    "TLSV1_ALERT",
                    "EOF occurred",
                    "Connection reset",
                    "timed out",
                ]
                if name in str(error)
            ]
            raise RuntimeError(
                "Generation API network request failed ("
                + " -> ".join(diagnostic)
                + "; "
                + ",".join(markers)
                + "); credentials and server response are not logged"
            ) from None
        if response.status_code != 200:
            raise RuntimeError(
                f"Generation API returned HTTP {response.status_code}; no automatic billing retry performed"
            )
        value = response.json()
        choice = value["choices"][0]
        if choice.get("finish_reason") == "length":
            raise response_error(
                "Generation API output token budget exhausted (finish_reason=length); partial completion discarded, no automatic retry",
                value,
            )
        if choice.get("finish_reason") == "content_filter":
            raise response_error(
                "Generation API content_filter; case skipped without retry", value
            )
        text = choice["message"].get("content")
        empty_json_completion = (
            isinstance(text, str)
            and not text.strip()
            and choice.get("finish_reason") == "stop"
            and payload.get("response_format", {}).get("type") == "json_object"
        )
        if not isinstance(text, str) or (
            not text.strip() and not empty_json_completion
        ):
            raise response_error("Generation API returned no textual completion", value)
        return {
            "text": text,
            "model": value.get("model", self.model),
            "request_model": self.model,
            "duration_seconds": round(time.monotonic() - start, 3),
            "usage": value.get("usage"),
            "provider_backend": "api",
            "connection_attempts": connection_attempts,
            "response_id": value.get("id"),
            "finish_reason": choice.get("finish_reason"),
            "empty_json_completion": empty_json_completion,
            "message_metadata": {
                k: v for k, v in choice["message"].items() if k != "content"
            },
        }

    def _vllm_request(self, messages, max_tokens, timeout=None, response_schema=None):
        """OpenAI-compatible call to the resident local vLLM service.

        Kept separate from the paid API path so the published endpoint, credentials and
        retry rules of that path are untouched.  Loopback only: this backend exists to
        reach a service on this machine.
        """
        import requests

        base = (os.getenv("SCITOOLFLOW_VLLM_BASE", "http://127.0.0.1:8016/v1")).rstrip(
            "/"
        )
        api_key = os.getenv("SCITOOLFLOW_VLLM_KEY", "EMPTY")
        parsed = urlparse(base)
        if parsed.hostname not in ["localhost", "127.0.0.1", "::1"]:
            raise ValueError("The vLLM backend only reaches a loopback service")
        cap = int(os.getenv("SCITOOLFLOW_VLLM_MAX_COMPLETION_TOKENS", "8192"))
        request_timeout = float(os.getenv("SCITOOLFLOW_VLLM_TIMEOUT", "600"))
        if cap <= 0 or not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("vLLM token and timeout caps must be positive")
        if timeout is not None:
            request_timeout = min(request_timeout, timeout)
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": min(max_tokens, cap),
        }
        # The actor emits structured JSON, and unconstrained decoding lets it fall into a
        # repetition loop: a run was observed spending its whole output budget repeating the
        # token "string" inside a malformed action. A mild repetition penalty and a little
        # temperature break the loop without making the JSON unreliable.
        for key, default, cast in [
            ("temperature", "0.2", float),
            ("top_p", "0.95", float),
            ("repetition_penalty", "1.08", float),
            ("top_k", "-1", int),
        ]:
            raw = os.getenv("SCITOOLFLOW_VLLM_" + key.upper())
            if raw is None:
                raw = default
            try:
                payload[key] = cast(raw)
            except ValueError:
                raise ValueError("Invalid vLLM sampling parameter: " + key) from None
            if isinstance(payload[key], float) and not math.isfinite(payload[key]):
                raise ValueError("Sampling parameters must be finite")
        if (
            not 0 <= payload["temperature"] <= 2
            or not 0 < payload["top_p"] <= 1
            or payload["repetition_penalty"] <= 0
            or (payload["top_k"] != -1 and payload["top_k"] < 1)
        ):
            raise ValueError("Invalid vLLM sampling parameter range")
        payload["chat_template_kwargs"] = {
            "enable_thinking": os.getenv("SCITOOLFLOW_ENABLE_MODEL_THINKING", "0")
            == "1"
        }
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "react_decision",
                    "strict": True,
                    "schema": response_schema,
                },
            }
        elif os.getenv("SCITOOLFLOW_VLLM_JSON_MODE", "1") == "1":
            payload["response_format"] = {"type": "json_object"}
        if self._session is None:
            self._session = requests.Session()
            self._session.trust_env = False
        start = time.monotonic()
        try:
            response = self._session.post(
                base + "/chat/completions",
                headers={"Authorization": "Bearer " + api_key},
                json=payload,
                timeout=request_timeout,
            )
        except requests.RequestException as error:
            raise RuntimeError(
                "vLLM service request failed ("
                + type(error).__name__
                + "); is the local service running?"
            ) from None
        if response.status_code != 200:
            raise RuntimeError(f"vLLM service returned HTTP {response.status_code}")
        value = response.json()
        choice = value["choices"][0]
        # A reply cut off at the output limit is still the actor speaking. Passing it on lets the
        # ReAct layer treat it as a protocol slip it can recover from, instead of aborting a run
        # that has already gathered evidence. The flag tells the layer why the text is partial.
        truncated = choice.get("finish_reason") == "length"
        text = choice["message"].get("content")
        if not isinstance(text, str) or not text.strip():
            raise response_error(
                "vLLM service returned no textual completion"
                + (" (output token budget exhausted)" if truncated else ""),
                value,
            )
        return {
            "text": text,
            "model": value.get("model", self.model),
            "request_model": self.model,
            "duration_seconds": round(time.monotonic() - start, 3),
            "usage": value.get("usage"),
            "provider_backend": "vllm",
            "response_id": value.get("id"),
            "truncated": truncated,
            "finish_reason": choice.get("finish_reason"),
            "message_metadata": {
                k: v for k, v in choice["message"].items() if k != "content"
            },
        }

    def _local_http_session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
            self._session.trust_env = False
        return self._session

    def input_budget(self, output_tokens, timeout=None):
        limit = int(os.getenv("SCITOOL_MAX_INPUT_TOKENS", "40960"))
        if self.backend == "vllm":
            base = os.getenv(
                "SCITOOLFLOW_VLLM_BASE", "http://127.0.0.1:8016/v1"
            ).rstrip("/")
            if urlparse(base).hostname not in ["localhost", "127.0.0.1", "::1"]:
                raise ValueError("vLLM token preflight requires a loopback service")
            response = self._local_http_session().get(
                base + "/models",
                timeout=preflight_timeout(10, timeout),
                headers={
                    "Authorization": "Bearer "
                    + os.getenv("SCITOOLFLOW_VLLM_KEY", "EMPTY")
                },
            )
            response.raise_for_status()
            model = next(r for r in response.json()["data"] if r["id"] == self.model)
            limit = min(limit, int(model["max_model_len"]) - output_tokens)
        if limit <= 0:
            raise ValueError("No input token budget remains after reserving output")
        return limit

    def count_tokens(self, messages, timeout=None):
        if self.backend != "vllm":
            raise ValueError(
                "Exact token counting is available for the resident vLLM backend"
            )
        base = os.getenv("SCITOOLFLOW_VLLM_BASE", "http://127.0.0.1:8016/v1").rstrip(
            "/"
        )
        response = self._local_http_session().post(
            base.rsplit("/v1", 1)[0] + "/tokenize",
            headers={
                "Authorization": "Bearer " + os.getenv("SCITOOLFLOW_VLLM_KEY", "EMPTY")
            },
            json={
                "model": self.model,
                "messages": messages,
                "add_generation_prompt": True,
                "chat_template_kwargs": {
                    "enable_thinking": os.getenv(
                        "SCITOOLFLOW_ENABLE_MODEL_THINKING", "0"
                    )
                    == "1"
                },
            },
            timeout=preflight_timeout(15, timeout),
        )
        response.raise_for_status()
        return int(response.json()["count"])

    def close(self):
        if self._session is not None and self._owns_session:
            self._session.close()
            self._session = None
