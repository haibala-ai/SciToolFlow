"""Local Qwen generation and embeddings; requests and replies are JSON lines."""

import argparse
import contextlib
import json
import os
import sys
import time
import traceback


_RESIDENT = {"checked": False, "base": None}


def service_setting(name, default):
    return os.getenv("SCITOOLFLOW_VLLM_" + name) or os.getenv(
        "SCITOOL_VLLM_" + name, default
    )


def service_session():
    import requests

    session = requests.Session()
    session.trust_env = False
    return session


def resident_service(model_path):
    """Return the base URL of the resident vLLM service, or None when it is not serving.

    The service is the same Qwen3.5-9B weights this worker would otherwise load itself.
    Loading a second copy costs another 19 GiB of device memory and competes with the
    service for the same devices, so the worker forwards to the service whenever it
    answers and only loads weights in-process when it does not.  The probe is cached:
    a service that is down at startup is not retried on every request.
    """
    if _RESIDENT["checked"]:
        return _RESIDENT["base"]
    _RESIDENT["checked"] = True
    base = service_setting("BASE", "http://127.0.0.1:8016/v1").rstrip("/")
    try:
        from urllib.parse import urlparse

        if urlparse(base).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Resident model service must use a loopback address")
        with service_session() as session:
            response = session.get(
                base + "/models",
                timeout=5,
                headers={"Authorization": "Bearer " + service_setting("KEY", "EMPTY")},
            )
        if response.status_code == 200:
            models = response.json().get("data", [])
            from pathlib import Path

            if not any(
                Path(m.get("root", "")).expanduser().resolve()
                == Path(model_path).expanduser().resolve()
                for m in models
            ):
                return None
            _RESIDENT["base"] = base
            print(
                "local worker: using resident service at %s" % base,
                file=sys.stderr,
                flush=True,
            )
            return base
    except Exception as error:
        print(
            "local worker: resident service unavailable (%s); loading weights in-process"
            % type(error).__name__,
            file=sys.stderr,
            flush=True,
        )
    return None


def forward_to_service(base, request):
    """Send one chat request to the resident service; the caller treats the reply as its own."""
    cap = int(service_setting("MAX_COMPLETION_TOKENS", "8192"))
    payload = {
        "model": service_setting("MODEL", "Qwen3.5-9B"),
        "messages": request["messages"],
        "max_tokens": min(int(request.get("max_tokens") or cap), cap),
        # Keep resident-service sampling explicit for the local worker.
        "temperature": float(service_setting("TEMPERATURE", "0.2")),
        "top_p": float(service_setting("TOP_P", "0.95")),
        "repetition_penalty": float(service_setting("REPETITION_PENALTY", "1.08")),
        "chat_template_kwargs": {
            "enable_thinking": os.getenv("SCITOOLFLOW_ENABLE_MODEL_THINKING", "0")
            == "1"
        },
    }
    with service_session() as session:
        response = session.post(
            base + "/chat/completions",
            headers={"Authorization": "Bearer " + service_setting("KEY", "EMPTY")},
            json=payload,
            timeout=float(service_setting("TIMEOUT", "600")),
        )
    if response.status_code != 200:
        raise RuntimeError("resident service returned HTTP %d" % response.status_code)
    value = response.json()
    choice = value["choices"][0]
    text = choice["message"].get("content") or ""
    usage = value.get("usage") or {}
    return {
        "ok": True,
        "text": text.strip(),
        "truncated": choice.get("finish_reason") == "length",
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        },
        "model": value.get("model", payload["model"]),
        "dtype": "bfloat16",
        "device_map": "resident_service",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--embedding", required=True)
    args = parser.parse_args()
    protocol_stdout = sys.stdout
    generator = None
    chat_tokenizer = None
    encoder = None
    tokenizer = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            start = time.monotonic()
            with contextlib.redirect_stdout(sys.stderr):
                if request["operation"] == "chat":
                    base = resident_service(args.model)
                    if base is not None:
                        reply = forward_to_service(base, request)
                        reply["duration_seconds"] = round(time.monotonic() - start, 3)
                        print(json.dumps(reply), file=protocol_stdout, flush=True)
                        continue
                    import torch

                    if generator is None:
                        from transformers import (
                            AutoTokenizer,
                            Qwen3_5ForConditionalGeneration,
                        )

                        torch.set_num_threads(8)
                        chat_tokenizer = AutoTokenizer.from_pretrained(
                            args.model, local_files_only=True
                        )
                        # Keep official BF16 weights. Reserve memory for other workloads
                        # and our activations; Accelerate can offload remaining layers to CPU.
                        budgets = {"cpu": "64GiB"}
                        # Neighbouring tenants can grow while we load, so the free-memory
                        # reading is only an upper bound. Reserve a configurable margin and
                        # optionally use only a fraction of what is free; without that the
                        # device map over-commits and generation dies on allocation.
                        reserve = (
                            int(os.getenv("SCITOOL_LLM_GPU_RESERVE_MB", "2048"))
                            * 1024**2
                        )
                        fraction = float(
                            os.getenv("SCITOOL_LLM_GPU_BUDGET_FRACTION", "1.0")
                        )
                        for device in range(torch.cuda.device_count()):
                            free, _ = torch.cuda.mem_get_info(device)
                            budget = int(max(0, free * fraction - reserve))
                            if budget > 1024**3:
                                budgets[device] = budget
                        print(
                            "local inference budgets: %s" % budgets,
                            file=sys.stderr,
                            flush=True,
                        )
                        generator = Qwen3_5ForConditionalGeneration.from_pretrained(
                            args.model,
                            local_files_only=True,
                            dtype=torch.bfloat16,
                            device_map="auto",
                            max_memory=budgets,
                            attn_implementation="sdpa",
                        ).eval()
                    messages = request["messages"]
                    batch = chat_tokenizer.apply_chat_template(
                        messages,
                        add_generation_prompt=True,
                        enable_thinking=os.getenv(
                            "SCITOOLFLOW_ENABLE_MODEL_THINKING", "0"
                        )
                        == "1",
                        tokenize=True,
                        return_tensors="pt",
                        return_dict=True,
                    ).to(generator.device)
                    prompt_tokens = batch["input_ids"].shape[-1]
                    if prompt_tokens > int(
                        os.getenv("SCITOOL_MAX_INPUT_TOKENS", "8192")
                    ):
                        raise ValueError(
                            "Prompt exceeds the configured local inference input limit"
                        )
                    with torch.inference_mode():
                        output = generator.generate(
                            **batch,
                            max_new_tokens=request.get("max_tokens", 768),
                            do_sample=False,
                            pad_token_id=chat_tokenizer.eos_token_id,
                        )
                    generated = output[0, prompt_tokens:]
                    eos_ids = generator.generation_config.eos_token_id
                    eos_ids = (
                        eos_ids if isinstance(eos_ids, (list, tuple)) else [eos_ids]
                    )
                    reply = {
                        "ok": True,
                        "text": chat_tokenizer.decode(
                            generated, skip_special_tokens=True
                        ).strip(),
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": len(generated),
                        },
                        "model": args.model,
                        "truncated": len(generated) >= request.get("max_tokens", 768)
                        and int(generated[-1]) not in eos_ids,
                        "dtype": "bfloat16",
                        "device_map": {
                            k: str(v) for k, v in generator.hf_device_map.items()
                        },
                    }
                elif request["operation"] == "embed":
                    import torch
                    import torch.nn.functional as F

                    if encoder is None:
                        from transformers import AutoTokenizer, AutoModel

                        torch.set_num_threads(8)
                        tokenizer = AutoTokenizer.from_pretrained(
                            args.embedding, local_files_only=True, padding_side="left"
                        )
                        encoder = AutoModel.from_pretrained(
                            args.embedding,
                            local_files_only=True,
                            torch_dtype=torch.float32,
                        ).eval()
                    vectors = []
                    for offset in range(0, len(request["texts"]), 16):
                        batch = tokenizer(
                            request["texts"][offset : offset + 16],
                            padding=True,
                            truncation=True,
                            max_length=512,
                            return_tensors="pt",
                        )
                        with torch.inference_mode():
                            hidden = encoder(**batch).last_hidden_state[:, -1]
                            vectors.extend(F.normalize(hidden, p=2, dim=1).tolist())
                    reply = {
                        "ok": True,
                        "vectors": vectors,
                        "model": "Qwen3-Embedding-0.6B",
                    }
                else:
                    raise ValueError("Unknown inference operation")
            reply["duration_seconds"] = round(time.monotonic() - start, 3)
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            reply = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
