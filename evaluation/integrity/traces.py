"""Verify local production evidence before workflow scoring.

Hashes bind files and cross-record identity inside a trusted harness run. They do
not authenticate a third party, prove external scientific truth, or protect
against a person who can rewrite both the trace and its recorded digest.
"""

import copy
import hashlib
import gzip
import json
from pathlib import Path


CALL_FIELDS = (
    "observation_id",
    "tool",
    "arguments",
    "status",
    "output",
    "error",
    "error_type",
)


def canonical_sha256(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def trajectory_bytes(path):
    path = Path(path)
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def read_trajectory(path):
    def reject_constant(value):
        raise ValueError("Nonfinite JSON: " + value)

    return json.loads(trajectory_bytes(path), parse_constant=reject_constant)


def execution_calls(trajectory):
    steps = trajectory.get("steps")
    if not isinstance(steps, list):
        raise ValueError("Production trajectory requires steps")
    calls = []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("calls", []), list):
            raise ValueError("Invalid production step/calls")
        calls.extend(step.get("calls", []))
    preparations = trajectory.get("preparations", [])
    if not isinstance(preparations, list):
        raise ValueError("Invalid automatic contract preparations")
    for call in preparations:
        if (
            not isinstance(call, dict)
            or trajectory.get("baseline") != "scitoolagent"
            or call.get("tool") != "DescribeTools"
            or call.get("kind") != "discovery"
            or call.get("automatic") is not True
        ):
            raise ValueError("Preparations must be automatic DescribeTools calls")
    # Preparations are outside model decisions. They have independent discovery
    # IDs; their placement cannot reorder any scientific observation.
    calls.extend(preparations)
    if any(not isinstance(c, dict) for c in calls):
        raise ValueError("Invalid production call")
    return calls


def validate_calls(calls, registry):
    aliases = registry.get("aliases", {})
    seen = set()
    projected = []
    for call in calls:
        if not isinstance(call, dict):
            raise ValueError("Calls must be objects")
        name = aliases.get(call.get("tool"), call.get("tool"))
        if name not in registry["tools"]:
            raise ValueError("Unregistered observation tool")
        identifier = call.get("observation_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("Missing or duplicate observation ID")
        seen.add(identifier)
        if not isinstance(call.get("arguments"), dict):
            raise ValueError("Observation arguments must be an object")
        if call.get("status") not in {
            "success",
            "error",
            "failed",
            "timeout",
            "blocked",
        }:
            raise ValueError("Observation status must be explicit")
        if "output" not in call:
            raise ValueError(
                "Observation requires full output, including null on failure"
            )
        projected.append({k: call.get(k) for k in CALL_FIELDS})
    return projected


def verify_trajectory(trajectory, prediction, registry):
    if trajectory.get("dataset", "full") != prediction.get("dataset", "full"):
        raise ValueError("Trace/prediction dataset differs")
    if trajectory.get("task_id") != prediction["id"]:
        raise ValueError("Trace task ID differs")
    for field in ("status", "final_answer", "failure_reason"):
        if canonical_sha256(trajectory.get(field)) != canonical_sha256(
            prediction.get(field)
        ):
            raise ValueError("Trace/prediction differs: " + field)
    if prediction.get("completed") is not (trajectory.get("status") == "completed"):
        raise ValueError("Trace/prediction completion differs")
    actual = execution_calls(trajectory)
    supplied = prediction.get("calls")
    if not isinstance(supplied, list):
        raise ValueError("Prediction calls must be a list")
    expected, submitted = validate_calls(actual, registry), validate_calls(
        supplied, registry
    )
    if trajectory.get("preparations"):
        # Preserve exact scientific order; automatic discovery is stored in a
        # separate trace section and is compared by its unique observation ID.
        def sections(rows):
            return {
                "scientific": [r for r in rows if r["tool"] != "DescribeTools"],
                "discovery": sorted(
                    (r for r in rows if r["tool"] == "DescribeTools"),
                    key=lambda r: r["observation_id"],
                ),
            }

        expected, submitted = sections(expected), sections(submitted)
    if canonical_sha256(expected) != canonical_sha256(submitted):
        raise ValueError("Trace calls differ from supplied evidence")
    return actual


def authenticate_prediction(prediction, root, run_directory, registry, dataset="full"):
    """Return a fail-closed row and diagnostic; invalid rows cannot earn credit."""
    result = copy.deepcopy(prediction)
    try:
        if prediction.get("dataset", "full") != dataset:
            raise ValueError("Prediction belongs to a different dataset")
        name = prediction.get("trace_path")
        expected = prediction.get("trace_sha256")
        if not name or not isinstance(expected, str) or len(expected) != 64:
            raise ValueError("Missing production trace path/digest")
        raw = Path(name)
        roots = [Path(root).resolve(), Path(run_directory).resolve()]
        candidates = [raw] if raw.is_absolute() else [base / raw for base in roots]
        paths = {p.resolve() for p in candidates if p.is_file()}
        if len(paths) != 1:
            raise ValueError("Missing or ambiguous production trace")
        path = paths.pop()
        if not any(base in path.parents for base in roots):
            raise ValueError("Production trace escapes project/run directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Production trace hash mismatch")
        trajectory = read_trajectory(path)
        if trajectory.get("dataset", "full") != dataset:
            raise ValueError("Production trace belongs to a different dataset")
        verify_trajectory(trajectory, prediction, registry)
        # Dispatcher timing/provenance used for parallel causal grading must come
        # from the hash-bound trace, not unverified extra fields in a prediction.
        result["calls"] = execution_calls(trajectory)
        from evaluation.workflow.causality import _times
        for call in result['calls']:
            interval=_times(call)
            if trajectory.get('baseline')=='scimas' and call.get('tool')!='DescribeTools' and interval is None:
                raise ValueError('Parallel SciMas evidence requires dispatcher call intervals')
        result["_resource_usage"] = trajectory.get("resource_usage")
        result["_execution_limits"] = trajectory.get("limits", {})
        result["_model_steps"] = sum(
            isinstance(s.get("model"), dict) for s in trajectory["steps"]
        )
        types = [s.get("type") for s in trajectory["steps"]]
        result["_think_steps"] = types.count("think")
        streak = peak = 0
        for kind in types:
            streak = streak + 1 if kind == "think" else 0
            peak = max(peak, streak)
        result["_consecutive_thinks"] = peak
        return result, {"verified": True, "trace_sha256": expected}
    except (ValueError, TypeError, KeyError, OSError) as error:
        # Worker exceptions may have no trajectory. Keep them in the denominator
        # as individual failures rather than aborting an entire experiment.
        reason = type(error).__name__ + ": " + str(error)
        result.update(
            calls=[],
            completed=False,
            status="failed",
            final_answer=None,
            failure_reason="EvidenceIntegrityError: " + reason,
        )
        return result, {
            "verified": False,
            "reason": reason,
            "original_runtime_failure": prediction.get("failure_reason"),
        }


def verify_release_envelope(envelope, root, dataset="full"):
    if not isinstance(envelope, dict):
        raise ValueError("workflow.v1 requires a fingerprinted production checkpoint")
    settings = envelope.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("Missing production settings")
    from tasks.datasets import dataset_files

    required_files = dataset_files(dataset) + ["tools/catalog/catalog.json"]
    if settings.get("dataset", "full") != dataset:
        raise ValueError(
            "Prediction dataset differs from the requested scoring dataset"
        )
    expected = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    if envelope.get("fingerprint") != expected:
        raise ValueError("Production settings fingerprint mismatch")
    hashes = settings.get("actor_file_hashes", {})
    if not all(name in hashes for name in required_files):
        raise ValueError("Task release and tool catalog hashes are required")
    from evaluation.integrity.files import safe_file

    for name, digest in hashes.items():
        if hashlib.sha256(safe_file(root, name).read_bytes()).hexdigest() != digest:
            raise ValueError("Actor source/release changed: " + name)
    return expected
