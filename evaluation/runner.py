"""Load predictions and run the same scoring protocol for every baseline."""

from pathlib import Path
import copy
import json
from tools.catalog import ToolCatalog
from src.utils.io import read_jsonl
from evaluation.integrity.package import validate_package
from evaluation.integrity.files import manifest
from evaluation.integrity.traces import verify_release_envelope
from evaluation.integrity.resources import validate_policy, check_resources


def evaluate_package(
    root, predictions, output, reviews=None, task_ids=None, dataset="full"
):
    """Validate and score a fingerprinted checkpoint against workflow.v1 only."""
    root = Path(root).resolve()
    validate_package(root)
    metadata = manifest(root)
    refs = read_jsonl(root / metadata["references"])
    if {r.get("evaluation", {}).get("schema_version") for r in refs} != {"workflow.v1"}:
        raise ValueError("Only workflow.v1 task releases are supported")
    source_ids = {r["id"]: r["id"] for r in refs}
    if dataset == "mini":
        from tasks.datasets import load_dataset

        public = load_dataset("mini", root)
        selected = public.select(task_ids)
        by_source = {r["id"]: r for r in refs}
        refs = []
        source_ids = {}
        for question in selected:
            identifier = question["id"]
            source = public.source_id(identifier)
            if source not in by_source:
                raise ValueError("Missing full reference for Mini task: " + identifier)
            reference = copy.deepcopy(by_source[source])
            reference["id"] = identifier
            refs.append(reference)
            source_ids[identifier] = source
    elif task_ids is not None:
        ids = set(task_ids)
        if not ids or len(ids) != len(task_ids) or ids - {r["id"] for r in refs}:
            raise ValueError("Unknown or empty scoring selection")
        refs = [r for r in refs if r["id"] in ids]
    path = Path(predictions)
    envelope = json.loads(path.read_text())
    release_fingerprint = verify_release_envelope(envelope, root, dataset=dataset)
    execution_policy = validate_policy(envelope["settings"].get("resource_policy"))
    predicted = envelope.get("predictions")
    if not isinstance(predicted, list):
        raise ValueError("Checkpoint predictions must be a JSON array")
    return _evaluate_workflow_package(
        root,
        refs,
        predicted,
        output,
        path.parent,
        task_ids,
        release_fingerprint,
        reviews=reviews,
        execution_policy=execution_policy,
        dataset=dataset,
        source_ids=source_ids,
    )


def _evaluate_workflow_package(
    root,
    refs,
    predictions,
    output,
    run_directory,
    task_ids,
    release_fingerprint,
    *,
    execution_policy,
    reviews=None,
    dataset="full",
    source_ids=None,
):
    """Evidence integrity precedes scoring; pending novel routes need policy review."""
    from evaluation.integrity.traces import authenticate_prediction, canonical_sha256
    from evaluation.workflow import evaluate_workflows
    from tasks.schema import validation_errors

    execution_policy = validate_policy(execution_policy)
    catalog = ToolCatalog(root)
    registry = catalog.registry()
    aliases = registry.get("aliases", {})
    reference_ids = {r["id"] for r in refs}
    predictions = list(predictions)
    ids = [p["id"] for p in predictions]
    if len(set(ids)) != len(ids) or set(ids) - reference_ids:
        raise ValueError("Unknown or duplicate prediction task IDs")
    verified, integrity, overruns, resource_checks = [], {}, {}, {}
    original = {p["id"]: p for p in predictions}
    authenticated = {}
    reference_by_id = {r["id"]: r for r in refs}
    contract_errors = {}
    for prediction in predictions:
        row, check = authenticate_prediction(
            prediction, root, run_directory, registry, dataset=dataset
        )
        identifier = row["id"]
        integrity[identifier] = check
        contract_errors[identifier] = validation_errors(
            row.get("final_answer"), reference_by_id[identifier]["answer_contract"]
        )
        if contract_errors[identifier] and row.get("completed"):
            row.update(completed=False, failure_reason="AnswerContractViolation")
        if check["verified"]:
            try:
                resource_checks[identifier] = check_resources(row, execution_policy)
                overruns[identifier] = resource_checks[identifier]["exceeded"]
                if overruns[identifier]:
                    row.update(
                        completed=False,
                        failure_reason="ExperimentResourceBudgetExceeded",
                    )
            except (ValueError, TypeError, KeyError) as error:
                resource_checks[identifier] = {"verified": False, "error": str(error)}
                overruns[identifier] = False
                row.update(
                    completed=False,
                    failure_reason="ResourceIntegrityError: " + str(error),
                )
        verified.append(row)
        authenticated[identifier] = row
    result = evaluate_workflows(
        refs, verified, aliases=aliases, catalog_tools=registry["tools"]
    )
    by_id = {r["id"]: r for r in refs}
    requests = []
    for row in result["results"]:
        identifier = row["id"]
        row.update(
            dataset=dataset,
            source_id=(source_ids or {}).get(identifier, identifier),
            evidence_integrity=integrity.get(identifier),
            resource_usage=resource_checks.get(identifier),
            resource_policy_version=execution_policy["version"],
            resource_exhausted=original.get(identifier, {}).get("failure_reason")
            in {
                "ModelRequestBudget",
                "TaskDeadline",
                "DecisionBudget",
                "ScientificCallBudget",
                "DiscoveryCallBudget",
            }
            or overruns.get(identifier, False),
            resource_limit_exceeded=overruns.get(identifier, False),
            answer_contract_errors=contract_errors.get(identifier, []),
        )
        row["scientific_fields_pass"] = row["answer_pass"]
        if contract_errors.get(identifier):
            row["answer_pass"] = False
        if not row["supplied"] or not integrity[identifier]["verified"]:
            continue
        ref = by_id[identifier]
        allowed = {
            aliases.get(t, t)
            for node in ref["evaluation"]["nodes"]
            for alt in node["alternatives"]
            for t in alt["tools"]
        }
        novel = (
            set(row["successful_tool_names"]) - allowed
            if not row["planning_pass"] and row["runtime_pass"]
            else set()
        )
        # A demonstrably wrong scientific answer is not an unresolved method.
        from evaluation.review.methods import classify, unresolved_or_correct_answer

        if novel and unresolved_or_correct_answer(row):
            row.update(pending_review=True, possible_unlisted_route=sorted(novel))
        method = classify(ref, authenticated[identifier], row, catalog.tools)
        if method:
            row.update(
                pending_review=True, pending_method_review=True, method_review=method
            )
        if row["pending_review"]:
            requests.append(
                {
                    "id": identifier,
                    "dataset": dataset,
                    "source_id": (source_ids or {}).get(identifier, identifier),
                    "schema_version": "workflow.v1",
                    "requires_independent_review": True,
                    "reference_sha256": canonical_sha256(
                        {**ref, "id": (source_ids or {}).get(identifier, identifier)}
                    ),
                    "evaluation_view_sha256": canonical_sha256(ref),
                    "prediction_sha256": canonical_sha256(original[identifier]),
                    "planning_pass": None if not row["planning_pass"] else True,
                    "answer_pass": None if not row["answer_pass"] else True,
                    "question": ref["question"],
                    "inputs": ref.get("inputs", {}),
                    "evaluation": ref["evaluation"],
                    "actual_calls": original[identifier]["calls"],
                    "predicted_answer": original[identifier].get("final_answer"),
                    "diagnostics": row,
                    "reason": "Unresolved branch/search or possible unlisted route. Independently inspect science and version the shared evaluation policy; a model self-review cannot turn this into a pass.",
                }
            )
    # Reviews are evidence for a shared criterion update, not model-specific overrides.
    # The current judge safely skips these requires_independent_review requests.
    if reviews is not None:
        raw = json.loads(Path(reviews).read_text())
        entries = (
            raw.get("reviews", raw.get("tasks", [])) if isinstance(raw, dict) else raw
        )
        if entries:
            raise ValueError(
                "workflow.v1 reviews require a versioned shared policy update; per-prediction semantic overrides are disabled"
            )
    rows = result["results"]
    pending_count = sum(bool(r["pending_review"]) for r in rows)
    lower = sum(bool(r["joint_pass"]) for r in rows) / len(rows)
    result["summary"].update(
        dataset=dataset,
        selection="all" if task_ids is None else sorted(task_ids),
        release_fingerprint=release_fingerprint,
        evidence_integrity_failures=sum(not c["verified"] for c in integrity.values()),
        pending_reviews=sum(bool(r["pending_review"]) for r in rows),
        pending_semantic_review=sum(bool(r["pending_review"]) for r in rows),
        joint_accuracy_upper_bound=sum(
            r["joint_pass"] or (r["runtime_pass"] and r["pending_review"]) for r in rows
        )
        / len(rows),
        joint_accuracy_lower_bound=lower,
        final_metric_available=pending_count == 0,
        final_answer_accuracy=sum(bool(r["answer_pass"]) for r in rows) / len(rows),
        joint_success_rate=lower if pending_count == 0 else None,
        evaluation_policy_version="workflow.v1+task-resources.v1",
        resource_policy=execution_policy,
        resource_exhausted_tasks=sum(r.get("resource_exhausted", False) for r in rows),
        resource_integrity_failures=sum(
            not r.get("verified", False) for r in resource_checks.values()
        ),
        known_prompt_tokens=sum(
            r.get("observed_prompt_tokens") or 0 for r in resource_checks.values()
        ),
        known_completion_tokens=sum(
            r.get("observed_completion_tokens") or 0 for r in resource_checks.values()
        ),
        tasks_with_complete_token_usage=sum(
            r.get("prompt_tokens") is not None
            and r.get("completion_tokens") is not None
            for r in resource_checks.values()
        ),
        formal_benchmark_accuracy=pending_count == 0,
        independent_review_policy="Pending cases remain in denominator; update shared versioned criteria after review, never an actor-specific pass override.",
    )
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    Path(output).with_name(Path(output).stem + "_review_requests.json").write_text(
        json.dumps(
            {
                "tasks": requests,
                "separate_api_calls": 0,
                "schema_version": "workflow.v1",
                "requires_independent_review": True,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    return result
