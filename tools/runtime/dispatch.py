"""Lazy, per-tool dispatch with explicit dependencies and real execution status."""

import importlib
import inspect
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from src.utils.paths import project_root, work_root
from tools.catalog import ToolCatalog

ROOT = work_root()
ROOT.mkdir(parents=True, exist_ok=True)
REPO = project_root()
REGISTRY = ToolCatalog().registry()


def credentials_in(environment):
    # Match credential name components, not TOKENIZERS_PARALLELISM or other
    # ordinary configuration flags whose values can occur in scientific JSON.
    return [
        value
        for key, value in environment.items()
        if value
        and len(value) > 4
        and re.search(r"(?:^|_)(?:KEY|TOKEN|PASSWORD|SECRET|APPID)(?:_|$)", key.upper())
        and value.lower() not in {"true", "false", "none", "null"}
    ]


def canonical_name(name):
    return REGISTRY["aliases"].get(name, name)


def descriptor(name):
    canonical = canonical_name(name)
    if canonical in REGISTRY.get("retired_tools", {}):
        raise ValueError(
            "Retired tool: "
            + str(name)
            + ". Query DescribeTools for replacements and explicit migration guidance."
        )
    if canonical not in REGISTRY["tools"]:
        raise KeyError(f"Unregistered tool: {name}")
    return canonical, REGISTRY["tools"][canonical]


def missing_resources(spec):
    from tools.runtime.config import Config

    config = Config()
    missing = []
    for key in spec.get("requires", []):
        value = os.getenv(key) or getattr(config, key, None)
        if not value or str(value).lower().startswith(("your", "placeholder")):
            missing.append(key)
        elif "PATH" in key or "MODELS" in key or key.endswith("_PYTHON"):
            if not Path(value).exists():
                missing.append(key)
    checkpoint = spec.get("checkpoint_subdirectory")
    if checkpoint:
        directory = Path(config.QizhiPei_MODEL_PATH) / checkpoint
        if not any(
            (directory / name).is_file()
            for name in ["model.safetensors", "pytorch_model.bin"]
        ):
            missing.append("BioT5 checkpoint: " + checkpoint)
    checkpoint_root = spec.get("checkpoint_root_key")
    if checkpoint_root:
        directory = Path(os.getenv(checkpoint_root) or getattr(config, checkpoint_root))
        if not any((directory / name).is_file() for name in spec["checkpoint_files"]):
            missing.append(checkpoint_root + " weights")
    return missing


def resolve_function(name):
    _, spec = descriptor(name)
    module = importlib.import_module(spec["module"])
    function = getattr(module, spec["function"])
    if not callable(function):
        raise TypeError(f"{name} resolves to a non-callable object")
    return function


def invoke_here(name, input_str, file_path_list=None):
    from tools.runtime.config import UPLOAD_CONTEXT

    files = file_path_list or []
    info = {}
    if files:
        from tools.implementations.shared.common import InputValidationError

        files = [str(Path(path).expanduser().resolve()) for path in files]
        if any(not Path(path).is_file() for path in files):
            raise InputValidationError(
                "Every uploaded attachment must be an existing file"
            )
        final = Path(files[-1])
        selected = [
            Path(path)
            for path in files
            if Path(path).suffix.lower() == final.suffix.lower()
        ]
        # Complete absolute paths are the attachment identity. Modern readers
        # resolve their explicit allowlist and reject ambiguous basenames; they
        # must not be blocked by a legacy convenience directory. Legacy tools
        # retain the final attachment's base directory and can receive absolute
        # filenames when their inputs reside in different directories.
        info = {
            "type": final.suffix.lstrip(".").lower(),
            "base_path": str(final.parent),
            "names": [path.name for path in selected],
            "paths": [str(path) for path in selected],
            "all_paths": files,
        }
    token = UPLOAD_CONTEXT.set(info)
    try:
        from tools.implementations.shared.common import (
            InputValidationError,
            parse_parameters,
        )

        _, spec = descriptor(name)
        if spec.get("strict_arguments", False):
            from tools.runtime.contracts import contract_errors

            try:
                supplied = (
                    json.loads(input_str) if isinstance(input_str, str) else input_str
                )
            except (TypeError, ValueError) as error:
                raise InputValidationError(
                    "Expected a JSON object of tool arguments"
                ) from error
            if not isinstance(supplied, dict):
                raise InputValidationError("Expected a JSON object of tool arguments")
            errors = contract_errors(supplied, spec["input_schema"])
            if errors:
                raise InputValidationError(
                    "Arguments violate the tool input schema: "
                    + "; ".join(str(error) for error in errors[:8])
                    + ". Query DescribeTools for the full contract."
                )
        function = inspect.unwrap(resolve_function(name))
        args, kwargs = parse_parameters(
            function,
            input_str,
            coerce_scalar_strings=not spec.get("strict_arguments", False),
            coerce_integral_floats=bool(spec.get("strict_arguments", False)),
        )
        return function(*args, **kwargs)
    finally:
        UPLOAD_CONTEXT.reset(token)


def run_worker(command, **kwargs):
    """Bound the whole worker process group, including its child processes."""
    payload = kwargs.pop("input")
    timeout = kwargs.pop("timeout")
    kwargs.pop("capture_output", None)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        **kwargs,
    )
    try:
        stdout, stderr = process.communicate(payload, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def execute(name, input_str, file_path_list=None, timeout=None):
    started = time.monotonic()
    result = {"tool": name, "input": input_str, "status": "error", "output": None}
    try:
        canonical, spec = descriptor(name)
        from tools.runtime.scope import tool_allowed

        if not tool_allowed(name):
            result.update(
                status="skipped",
                canonical_tool=canonical_name(name),
                error_type="ExecutionScopeExcluded",
                error="Tool excluded from the requested non-biological execution scope",
            )
            return result
        if spec.get("backend") == "host":
            output = invoke_here(name, input_str, file_path_list)
            result.update(
                validate_result(output, spec),
                canonical_tool=canonical,
                environment="host",
                logical_environment="host",
            )
            return result
        timeout = float(spec.get("timeout_seconds", 90) if timeout is None else timeout)
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        from tools.runtime.environments import tool_environment

        environment = tool_environment(spec["environment"])
        result.update(
            canonical_tool=canonical,
            environment=environment,
            logical_environment=spec["environment"],
        )
        if spec.get("unavailable_service"):
            result.update(
                status="blocked",
                error_type="ServiceRetired",
                error=spec["unavailable_service"],
            )
            return result
        missing = missing_resources(spec)
        if missing:
            result.update(
                status="blocked",
                error_type="MissingResource",
                missing_resources=missing,
                error="Missing required resources: " + ", ".join(missing),
            )
            return result
        if spec.get("in_process"):
            if Path(sys.prefix).name != environment:
                raise RuntimeError(
                    "This tool must run in its configured Agent environment"
                )
            from tools.runtime.context import TOOL_DEADLINE

            token = TOOL_DEADLINE.set(started + timeout)
            try:
                result.update(
                    validate_result(
                        invoke_here(canonical, input_str, file_path_list), spec
                    )
                )
            finally:
                TOOL_DEADLINE.reset(token)
            return result
        from tools.runtime.environments import environment_python

        python = environment_python(environment)
        if not python.exists():
            result.update(
                status="blocked",
                error_type="MissingEnvironment",
                missing_resources=[environment],
                error="Conda environment Python not found: " + str(python),
            )
            return result
        payload = {"tool": canonical, "input": input_str, "files": file_path_list or []}
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO)
        env["PYTHONNOUSERSITE"] = "1"
        if spec.get("cpu_only"):
            env["CUDA_VISIBLE_DEVICES"] = ""
        if (
            spec["module"] == "tools.implementations.materials.materials_project"
            and not spec.get("public_object_download")
            and os.getenv("SCITOOL_MP_USE_PROXY", "0") != "1"
        ):
            for key in [
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
            ]:
                env.pop(key, None)
        completed = run_worker(
            [str(python), "-m", "tools.runtime.worker"],
            input=json.dumps(payload),
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        replies = [
            line
            for line in completed.stdout.splitlines()
            if line.startswith('{"toolkg_result":')
        ]
        if not replies:
            raise RuntimeError(
                "Tool worker returned no result: " + completed.stderr[-1500:]
            )
        response = json.loads(replies[-1])["toolkg_result"]
        if (
            completed.returncode
            or not isinstance(response, dict)
            or response.get("status") not in {"success", "error", "blocked", "skipped"}
        ):
            raise RuntimeError(
                "Tool worker returned an invalid result or failed to exit normally"
            )
        result.update(response)
        if result["status"] != "success":
            diagnostic_stdout = "\n".join(
                line
                for line in completed.stdout.splitlines()
                if not line.startswith('{"toolkg_result":')
            )[-6000:]
            if diagnostic_stdout:
                result["worker_stdout"] = diagnostic_stdout
        if result["status"] != "success" and completed.stderr:
            diagnostic = completed.stderr[-6000:]
            for value in credentials_in(env):
                diagnostic = diagnostic.replace(value, "[redacted]")
            result["worker_stderr"] = diagnostic
    except subprocess.TimeoutExpired:
        result.update(error_type="Timeout", error=f"Tool exceeded {timeout} seconds")
    except TimeoutError:
        result.update(error_type="Timeout", error=f"Tool exceeded {timeout} seconds")
    except (ModuleNotFoundError, ImportError) as error:
        result.update(
            status="blocked", error_type=type(error).__name__, error=str(error)
        )
    except Exception as error:
        from tools.implementations.shared.common import InputValidationError

        result.update(
            error_type=(
                "InvalidInput"
                if isinstance(error, InputValidationError)
                else type(error).__name__
            ),
            error=str(error),
        )
    finally:
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        # Request exceptions can put AppIDs into URLs, including the structured
        # worker error itself. Redact every returned string, not just stderr.
        credentials = credentials_in(os.environ)

        def redact(value):
            if isinstance(value, str):
                for credential in credentials:
                    value = value.replace(credential, "[redacted]")
                return value
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        result.update(redact(result))
    return result


def normalize_output(output):
    if output is None:
        return {
            "status": "error",
            "output": None,
            "error_type": "EmptyResult",
            "error": "Tool returned None",
        }
    text = str(output).strip()
    if not text:
        return {
            "status": "error",
            "output": output,
            "error_type": "EmptyResult",
            "error": "Tool returned an empty string",
        }
    structured = output
    if isinstance(output, str):
        try:
            structured = json.loads(output)
        except (ValueError, TypeError):
            pass
    if isinstance(structured, dict):
        state = str(structured.get("status", "")).lower()
        standalone_error = bool(structured.get("error")) and set(structured) <= {
            "error",
            "error_type",
            "status",
            "message",
            "detail",
            "success",
        }
        if (
            state
            in {
                "error",
                "failed",
                "failure",
                "blocked",
                "unavailable",
                "pending",
                "running",
                "queued",
            }
            or structured.get("success") is False
            or standalone_error
        ):
            blocked = state in {
                "blocked",
                "unavailable",
                "pending",
                "running",
                "queued",
            }
            return {
                "status": "blocked" if blocked else "error",
                "output": output,
                "error_type": (
                    "UpstreamPending"
                    if state in {"pending", "running", "queued"}
                    else "ToolReportedError"
                ),
                "error": str(
                    structured.get("error")
                    or structured.get("message")
                    or state
                    or "Tool reported success=false"
                )[:1500],
            }
    if re.search(
        r"(?im)^\s*(?:#+\s*)?(?:\*\*)?(?:error\b|erro\b|an error|input error|invalid\b|network error|failed\b|unable to\b|could not\b|explosive check error|molecule not found|no .* found|pdf directory does not exist|the input .*must|tool function execution error|parameter or request error|调用服务失败|服务调用失败|请求失败|执行失败|发生错误|错误\s*[:：])",
        text,
    ):
        return {
            "status": "error",
            "output": output,
            "error_type": "ToolReportedError",
            "error": text[:1500],
        }
    return {"status": "success", "output": output}


def validate_result(output, spec):
    """Apply the same finite JSON and output contract to every execution backend."""
    from tools.runtime.contracts import contract_errors

    result = normalize_output(output)
    errors = contract_errors(output, {})
    if not errors and result["status"] == "success":
        errors = contract_errors(output, spec["output_schema"])
        encoding = spec.get("output_encoding", {})
        if (
            not errors
            and isinstance(output, str)
            and (
                encoding.get("decoded_schema")
                or encoding.get("decoded_type") in {"json_object", "json_array"}
            )
        ):

            def unique_object(pairs):
                found = {}
                for key, value in pairs:
                    if key in found:
                        raise ValueError("Duplicate JSON output key: " + key)
                    found[key] = value
                return found

            def reject_constant(value):
                raise ValueError("Nonfinite JSON output constant: " + value)

            try:
                decoded = json.loads(
                    output,
                    object_pairs_hook=unique_object,
                    parse_constant=reject_constant,
                )
                schema = encoding.get("decoded_schema") or {
                    "type": (
                        "object"
                        if encoding.get("decoded_type") == "json_object"
                        else "array"
                    )
                }
                errors = [
                    "decoded output " + message
                    for message in contract_errors(decoded, schema)
                ]
            except (ValueError, TypeError) as error:
                errors = ["Invalid declared JSON output: " + str(error)]
    if errors:
        return dict(
            status="error",
            output=None,
            error_type="InvalidOutput",
            error="Result violates the finite JSON/public output contract: "
            + "; ".join(errors),
        )
    return result
