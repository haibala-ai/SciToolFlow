from copy import deepcopy
import json
from pathlib import Path
import time
import pytest
from baselines.scimas.knowledge import ToolKnowledge
from baselines.scimas.planner import Planner, PlanningFailure
from baselines.scimas.task_graph import TaskGraph
from tools.catalog import ToolCatalog


class EchoEmbedding:
    def __init__(self, vector):
        self.vector = vector
        self.stats = {"requests": 0, "texts": 0}

    def encode(self, texts, deadline):
        self.stats["requests"] += 1
        self.stats["texts"] += len(texts)
        return [self.vector for _ in texts]


@pytest.fixture(scope="module")
def kg():
    return ToolKnowledge()


def test_independent_kg_complete_and_discovery_excluded(kg):
    assert len(kg.tools) == 472
    assert len([v for v in kg.graph["nodes"].values() if v["type"] == "port"]) == 1755
    assert "DescribeTools" not in kg.tools and "DescribeTools" not in kg.vectors
    assert (
        kg.describe("DescribeTools")["DescribeTools"]["planning"]["graph_indexed"]
        is False
    )
    for name, row in kg.tools.items():
        assert row["planning"]["output_access"] in {
            "native_fields",
            "declared_json_decode",
            "reviewer_extraction",
        }
        assert (
            row["planning"]["scientific_substitution"]
            == "requires_task_specific_review"
        )


def test_runtime_does_not_read_scitoolagent_graph_or_author_data(monkeypatch):
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        text = str(path)
        if any(
            part in text
            for part in [
                "graph_store.json",
                "index_store.json",
                "evaluation/data",
                "selection.json",
                "SciMas/科学",
            ]
        ):
            raise AssertionError("Forbidden read: " + text)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    assert ToolKnowledge().describe("MatrixMultiply")


def test_port_connections_retain_paths_and_uncertainty(kg):
    result = kg.connections("MatrixMultiply", limit=500)
    matching = [c for c in result["connections"] if c["source_tool"] == "MatrixInverse"]
    assert matching
    assert all(c["output_path"] == ["inverse"] for c in matching)
    assert {c["input_parameter"] for c in matching} == {"left", "right"}
    assert all(c["status"] == "candidate_requires_scientific_review" for c in matching)
    assert all(c["provenance"] for c in matching)
    assert all(
        a["status"] == "candidate_only_not_method_equivalence"
        for a in kg.alternatives("MatrixInverse")
    )


def test_query_describe_is_not_mutable_kg(kg):
    data = kg.describe("MatrixMultiply")
    data["MatrixMultiply"]["planning"]["parallel_safe"] = "invented"
    assert kg.tools["MatrixMultiply"]["planning"]["parallel_safe"] != "invented"


def test_subtask_retrieval_uses_scimas_index_and_ports(kg):
    fake = EchoEmbedding(kg.vectors["MatrixInverse"])
    other = ToolKnowledge(embedding=fake)
    found = other.search(
        ["Invert a matrix", "Assess invertibility"],
        time.monotonic() + 10,
        top_k=1,
        max_tools_per_query=6,
    )
    assert all(q["seeds"] == ["MatrixInverse"] for q in found["queries"])
    assert found["tools"]["MatrixInverse"]["planning"]["reviewed_annotation"]
    assert all(q["candidate_connections"] for q in found["queries"])
    assert fake.stats["requests"] == 1


def test_corrupt_kg_fails_closed(tmp_path, kg):
    folder = kg.folder
    for name in (
        "graph.json",
        "manifest.json",
        "annotations.json",
        "embeddings.json.gz",
    ):
        (tmp_path / name).symlink_to(folder / name)
    (tmp_path / "manifest.json").unlink()
    modified = deepcopy(kg.manifest)
    modified["catalog_sha256"] = "wrong"
    (tmp_path / "manifest.json").write_text(json.dumps(modified))
    with pytest.raises(ValueError, match="Stale/corrupt"):
        ToolKnowledge(folder=tmp_path)


class ScriptedClient:
    supports_response_schema = True

    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def request(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {
            "text": json.dumps(next(self.values)),
            "usage": {"completion_tokens": 1},
            "model": "scripted_test_double",
        }


class FixedKnowledge:
    def __init__(self):
        self.catalog = ToolCatalog()
        self.allowed = lambda n: True
        self.manifest = {"graph_sha256": "test-double"}
        self.embedding = EchoEmbedding([])

    def search(self, queries, deadline):
        self.embedding.stats["requests"] += 1
        return {
            "tools": {
                n: self.catalog.describe(n)["tools"][n]
                for n in ["MatrixInverse", "MatrixMultiply"]
            },
            "queries": queries,
        }


def public_example():
    return {
        "id": "example",
        "question": "Report the inverse and its identity-product check.",
        "inputs": {"matrix": [[2, 0], [0, 4]]},
        "gold": "must not be seen",
    }


def decomposition():
    return {
        "requirements": [
            {
                "id": "report",
                "description": "Inverse and check",
                "evidence": "Report the inverse and its identity-product check.",
                "mode": "complete",
            }
        ],
        "queries": ["matrix inverse", "matrix multiplication"],
    }


def valid_plan():
    return {
        "nodes": [
            {
                "id": "inverse",
                "tool": "MatrixInverse",
                "purpose": "Invert input",
                "object": "matrix",
                "arguments": {"values": {"kind": "task", "path": ["inputs", "matrix"]}},
            },
            {
                "id": "check",
                "tool": "MatrixMultiply",
                "purpose": "Check inverse",
                "object": "matrix",
                "arguments": {
                    "left": {"kind": "task", "path": ["inputs", "matrix"]},
                    "right": {"kind": "node", "node": "inverse", "path": ["inverse"]},
                },
            },
        ],
        "deliverables": [
            {
                "requirement": "report",
                "nodes": ["inverse", "check"],
                "description": "Inverse and residual evidence",
            }
        ],
    }


def test_model_loop_repairs_bad_field_without_gold():
    bad = valid_plan()
    bad["nodes"][1]["arguments"]["right"]["path"] = ["imaginary"]
    client = ScriptedClient([decomposition(), {"plan": bad}, {"plan": valid_plan()}])
    report = Planner(FixedKnowledge(), client).plan(public_example(), dataset="custom")
    assert report["status"] == "planned" and report["scientific_calls"] == 0
    assert len(report["steps"]) == 3
    assert "not declared" in str(report["steps"][1]["validation"]["errors"])
    assert "must not be seen" not in json.dumps(client.calls)
    graph = TaskGraph.load(report["graph"], public_example(), ToolCatalog())
    assert graph.identity == report["graph_sha256"]


def test_missing_tools_can_trigger_more_retrieval():
    client = ScriptedClient(
        [
            decomposition(),
            {"queries": ["explicit numerical inverse adapter"]},
            {"plan": valid_plan()},
        ]
    )
    report = Planner(FixedKnowledge(), client).plan(public_example(), dataset="custom")
    assert len(report["retrievals"]) == 2 and report["status"] == "planned"


def test_invalid_plan_never_becomes_accepted_by_budget_exhaustion():
    bad = valid_plan()
    bad["nodes"][1]["arguments"]["right"]["path"] = ["missing"]
    client = ScriptedClient([decomposition(), {"plan": bad}])
    with pytest.raises(PlanningFailure) as failure:
        Planner(FixedKnowledge(), client, max_requests=2).plan(
            public_example(), dataset="custom"
        )
    assert failure.value.report["status"] == "failed"
    assert "graph" not in failure.value.report


def test_context_limit_stops_before_request():
    client = ScriptedClient([])
    with pytest.raises(PlanningFailure, match="context"):
        Planner(FixedKnowledge(), client, max_context_chars=10).plan(
            public_example(), dataset="custom"
        )
    assert not client.calls


def test_rebuild_is_reproducible_and_independent(tmp_path, kg):
    from baselines.scimas.build_knowledge import build

    original_files = [
        "graph_store.json",
        "index_store.json",
        "tool_foundation_manifest.json",
    ]
    import hashlib

    before = {
        name: hashlib.sha256(
            (kg.catalog.root / "tools/graph" / name).read_bytes()
        ).hexdigest()
        for name in original_files
    }
    rebuilt = build(kg.catalog, tmp_path)
    assert rebuilt["graph_sha256"] == kg.manifest["graph_sha256"]
    assert rebuilt["embedding_file_sha256"] == kg.manifest["embedding_file_sha256"]
    assert rebuilt["new_embedding_api_calls"] == 0
    assert len(ToolKnowledge(folder=tmp_path).tools) == 472
    assert before == {
        name: hashlib.sha256(
            (kg.catalog.root / "tools/graph" / name).read_bytes()
        ).hexdigest()
        for name in original_files
    }


@pytest.mark.parametrize("dataset_name", ["full", "mini"])
def test_public_dataset_runner_and_no_overwrite(tmp_path, monkeypatch, dataset_name):
    from types import SimpleNamespace
    from tasks.datasets import load_dataset
    from baselines.scimas.task_graph import public_task, digest
    from baselines.scimas import runner

    observed = []

    class Client:
        def __init__(self, backend):
            self.model = "placeholder"

        def close(self):
            pass

    class TestPlanner:
        def __init__(self, *args, **kwargs):
            pass

        def plan(self, task, **kwargs):
            observed.append((public_task(task), kwargs))
            return {
                "status": "planned",
                "steps": [],
                "dataset": kwargs["dataset"],
                "task_id": task["id"],
                "public_task_sha256": digest(public_task(task)),
            }

    monkeypatch.setattr(runner, "GenerationClient", Client)
    monkeypatch.setattr(runner, "Planner", TestPlanner)
    monkeypatch.setattr(runner, "ToolKnowledge", lambda: object())
    args = SimpleNamespace(
        dataset=dataset_name,
        tasks="SMAS-0004" if dataset_name == "mini" else "FLOW-0004",
        output=str(tmp_path),
        backend="vllm",
        model="test",
        max_model_requests=3,
        max_output_tokens=500,
        task_timeout=10,
    )
    summary = runner.run_planning(args)
    assert summary["planned"] == 1
    source = load_dataset(dataset_name).select(args.tasks)[0]
    assert observed[0][0]["question"] == source["question"]
    assert observed[0][1]["dataset"] == dataset_name
    with pytest.raises(ValueError, match="already exists"):
        runner.run_planning(args)


def test_high_degree_ports_are_ranked_before_truncation(kg):
    found = kg.connections("MatrixMultiply", limit=1, relevance={"MatrixInverse": 100})
    assert found["connections"][0]["source_tool"] == "MatrixInverse"
    assert found["truncated"]


def test_grounding_feedback_supplies_exact_public_spelling():
    bad = decomposition()
    bad["requirements"][0]["evidence"] = "report the inverse"
    client = ScriptedClient([bad, decomposition(), {"plan": valid_plan()}])
    result = Planner(FixedKnowledge(), client).plan(public_example(), dataset="custom")
    assert result["status"] == "planned"
    feedback = json.loads(client.calls[1][0][1]["content"])["instructions"]
    assert feedback["verbatim_source_options"]["report"] == ["Report the inverse"]
    assert result["steps"][0]["grounding_errors"] == ["report"]


def test_requirement_quotes_can_come_from_verified_public_attachments():
    from baselines.scimas.validation import grounded
    from tasks.datasets import load_dataset
    from tasks.assets import load_agent_input

    dataset = load_dataset("full")
    task = load_agent_input(dataset.select("FLOW-0481")[0], dataset.asset_root)
    assert "Return pooled estimate" not in task["question"]
    assert grounded("Return pooled estimate", task)
    assert not grounded("Invented unpublished estimate", task)


def test_grounding_never_reads_arbitrary_unattached_files(tmp_path):
    from baselines.scimas.validation import grounded

    path = tmp_path / "not-a-release-asset.json"
    path.write_text("A fabricated threshold")
    with pytest.raises(ValueError, match="outside the public release"):
        grounded("fabricated", {"question": "Public task", "files": [str(path)]})


def test_asset_quote_rejects_changed_bytes_even_if_quote_remains(tmp_path, monkeypatch):
    import hashlib
    from baselines.scimas import assets
    from baselines.scimas.validation import grounded

    root = tmp_path / "tasks/full"
    (root / "assets").mkdir(parents=True)
    file = root / "assets" / "public.json"
    raw = b'{"criterion":"Require value <= 3"}'
    file.write_bytes(raw)
    (root / "asset_manifest.json").write_text(
        json.dumps(
            {"files": {"public.json": {"sha256": hashlib.sha256(raw).hexdigest()}}}
        )
    )
    monkeypatch.setattr(assets, "project_root", lambda: tmp_path)
    task = {"question": "Follow the attached public criterion.", "files": [str(file)]}
    assert grounded("Require value <= 3", task)
    file.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="Public asset changed"):
        grounded("Require value <= 3", task)


def test_stateless_planner_receives_search_history_and_remaining_budget():
    client = ScriptedClient(
        [
            decomposition(),
            {"queries": ["primitive matrix arithmetic"]},
            {"plan": valid_plan()},
        ]
    )
    result = Planner(FixedKnowledge(), client, max_retrieval_rounds=2).plan(
        public_example(), dataset="custom"
    )
    assert result["status"] == "planned"
    payload = json.loads(client.calls[-1][0][1]["content"])
    assert len(payload["instructions"]["search_history"]) == 2
    assert payload["instructions"]["remaining_retrieval_rounds"] == 0
    assert not any(
        "queries" in branch["properties"]
        for branch in payload["response_schema"]["oneOf"]
    )


def test_planner_can_report_missing_capability_without_fabricated_plan():
    client = ScriptedClient(
        [
            decomposition(),
            {"stop": "Required method is not available in inspected contracts"},
            {"stop": "The suggested primitives still cannot express the required method"},
        ]
    )
    with pytest.raises(PlanningFailure, match="PlannerStopped"):
        Planner(FixedKnowledge(), client).plan(public_example(), dataset="custom")
