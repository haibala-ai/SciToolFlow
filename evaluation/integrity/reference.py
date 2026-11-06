"""Release gates for independently reviewed, native workflow references."""

import hashlib
import json
import re

from tasks.schema import validation_errors
from evaluation.integrity.files import safe_file
from evaluation.integrity.traces import (
    canonical_sha256,
    execution_calls,
    verify_trajectory,
    trajectory_bytes,
    read_trajectory,
)
from evaluation.workflow import (
    score_workflow,
    validate_workflow,
    public_answer_contract,
)


REVIEW_CHECKS = {
    "scientific_correctness",
    "evidence_grounding",
    "task_alignment",
    "tool_contracts",
    "orchestration",
}


def task_identity(task, provenance):
    identity = provenance.get("task_identity")
    if (
        not isinstance(identity, dict)
        or identity.get("current_public_task_sha256") != canonical_sha256(task)
        or any(
            not isinstance(identity.get(k), str)
            or re.fullmatch(r"[0-9a-f]{64}", identity[k]) is None
            for k in ["generation_task_sha256", "review_task_sha256"]
        )
    ):
        raise ValueError("Native reference task identity mismatch")
    return identity


def verify_generation_manifest(root, task, provenance):
    """Bind the self-contained generation record to this task and raw trace."""
    manifest = provenance.get("generation_manifest")
    if not isinstance(manifest, dict) or canonical_sha256(manifest) != provenance.get(
        "generation_manifest_sha256"
    ):
        raise ValueError("Native generation manifest hash mismatch")
    identity = task_identity(task, provenance)
    if (
        manifest.get("actor_backend") != "native_subagent"
        or manifest.get("model_api_used") is not False
        or manifest.get("task_id") != task["id"]
        or manifest.get("public_task_sha256") != identity["generation_task_sha256"]
    ):
        raise ValueError("Native generation manifest/task mismatch")
    for field in ("source_sha256", "input_asset_sha256"):
        hashes = manifest.get(field)
        if not isinstance(hashes, dict) or any(
            not isinstance(name, str)
            or not name
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            for name, digest in hashes.items()
        ):
            raise ValueError("Invalid native generation digest inventory: " + field)


def validate_workflow_reference(root, task, reference, catalog, registry):
    spec = reference["evaluation"]
    validate_workflow(spec)
    if reference.get("answer_contract") != task["answer_schema"] or validation_errors(
        reference.get("expected_answer"), task["answer_schema"]
    ):
        raise ValueError("Workflow reference violates its public answer contract")
    if "x-scoring-semantics" in task["answer_schema"]:
        declared = task["answer_schema"]["x-scoring-semantics"]
        actual = public_answer_contract(reference)
        if {canonical_sha256(r) for r in declared} != {
            canonical_sha256(r) for r in actual
        }:
            raise ValueError(
                "Public comparison metadata differs from workflow criteria"
            )
    for node in spec["nodes"]:
        for alternative in node["alternatives"]:
            for name in alternative["tools"]:
                if name not in catalog or name == "DescribeTools":
                    raise ValueError(
                        "Unregistered workflow scientific alternative: " + name
                    )
    exploration_tools = spec.get("efficiency", {}).get(
        "disambiguation_tools", []
    ) + spec.get("efficiency", {}).get("recovery_tools", [])
    exploration_tools += [tool for category in ('useful_work_rules','recovery_rules','disambiguation_rules')
        for rule in spec.get('efficiency',{}).get(category,[]) for tool in rule['tools']]
    for name in exploration_tools:
        if name not in catalog or name == "DescribeTools":
            raise ValueError("Unregistered workflow disambiguation tool")
    path = safe_file(root, reference["reference_trace"])
    raw = trajectory_bytes(path)
    trajectory = read_trajectory(path)
    provenance = reference.get("native_provenance", {})
    if (
        provenance.get("actor_backend") != "native_subagent"
        or provenance.get("model_api_used") is not False
        or not provenance.get("actor_id")
        or trajectory.get("backend") != "native_subagent"
        or provenance.get("task_sha256")
        != task_identity(task, provenance)["generation_task_sha256"]
        or provenance.get("trace_sha256") != hashlib.sha256(raw).hexdigest()
    ):
        raise ValueError("Native reference provenance/hash mismatch")
    verify_generation_manifest(root, task, provenance)
    actual = execution_calls(trajectory)
    if any(
        registry.get("aliases", {}).get(call["tool"], call["tool"])
        in {"CodeInterpreterTools", "PaperQA"}
        and call["status"] == "success"
        for call in actual
    ):
        raise ValueError("Native reference delegated reasoning to an LLM helper")
    prediction = {
        "id": task["id"],
        "dataset": trajectory.get('dataset','full'),
        "status": trajectory.get("status"),
        "completed": trajectory.get("status") == "completed",
        "failure_reason": trajectory.get("failure_reason"),
        "final_answer": trajectory.get("final_answer"),
        "calls": actual,
    }
    verify_trajectory(trajectory, prediction, registry)
    scientific = [c for c in actual if c["tool"] != "DescribeTools"]
    if canonical_sha256(prediction["final_answer"]) != canonical_sha256(
        reference["expected_answer"]
    ):
        raise ValueError("Reference expected answer differs from executed final answer")
    for call in actual:
        if call["status"] == "success" and validation_errors(
            call["arguments"], catalog[call["tool"]]["input_schema"]
        ):
            raise ValueError("Successful native reference call violates input schema")
        output_schema = catalog[call["tool"]].get("output_schema")
        if (
            call["status"] == "success"
            and output_schema
            and validation_errors(call.get("output"), output_schema)
        ):
            raise ValueError("Successful native reference call violates output schema")
    review = reference.get("review", {})
    record = review.get("record")
    if not isinstance(record, dict) or canonical_sha256(record) != review.get(
        "record_sha256"
    ):
        raise ValueError("Native reference review hash mismatch")
    if (
        review.get("status") != "approved"
        or record.get("status") != "approved"
        or not review.get("reviewer")
        or review["reviewer"] == provenance["actor_id"]
        or record.get("reviewer") != review["reviewer"]
        or record.get("task_id") != task["id"]
        or review.get("reviewed_trace_sha256") != provenance["trace_sha256"]
        or record.get("trace_sha256") != provenance["trace_sha256"]
        or record.get("task_sha256")
        != task_identity(task, provenance)["review_task_sha256"]
        or record.get("evaluation_sha256") != canonical_sha256(spec)
        or not record.get("rationale", "").strip()
        or any(record.get("checks", {}).get(k) is not True for k in REVIEW_CHECKS)
    ):
        raise ValueError("Native reference requires a distinct, approved second review")
    scored = score_workflow(
        reference, prediction, aliases=registry.get("aliases"), tool_contracts=catalog
    )
    if not scored["joint_pass"] or scored["pending_review"]:
        raise ValueError(
            "Reviewed native reference does not pass its own workflow criteria"
        )
    return len(scientific)
