"""Versioned plans and explicit evidence bindings; never executes model-written code."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

PUBLIC_FIELDS = (
    "id",
    "domain",
    "question",
    "inputs",
    "files",
    "answer_schema",
    "unit_annotations",
)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def public_task(task):
    return {key: deepcopy(task[key]) for key in PUBLIC_FIELDS if key in task}


def at(value, path):
    for part in path:
        if isinstance(value, list) and type(part) is int:
            value = value[part]
        elif isinstance(value, dict) and isinstance(part, str):
            value = value[part]
        else:
            raise ValueError("Path does not address the actual value")
    return value


def _json_equal(left, right):
    """Exact JSON value equality; numbers share a domain, Booleans do not.

    Use the same rule for equality and membership, including nested records.
    This does not introduce a floating-point tolerance or coerce strings/IDs.
    """
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    return left == right


def bindings(value):
    """Walk binding syntax, treating literal JSON and semantic metadata as opaque."""
    if not isinstance(value, dict):
        return
    if "kind" in value:
        yield value
        if value["kind"] == "list":
            for item in value["items"] + value.get("provenance", []):
                yield from bindings(item)
    elif "op" in value:
        for key in ("left", "right", "arg"):
            yield from bindings(value.get(key))
        for item in value.get("args", []):
            yield from bindings(item)


def node_dependencies(node):
    data, control = set(), set()
    for value in [*node["arguments"].values(), node.get("for_each")]:
        data.update(
            b["node"] for b in bindings(value) if b["kind"] in {"node", "collect"}
        )
    control.update(
        b["node"]
        for b in bindings(node.get("when"))
        if b["kind"] in {"node", "collect"}
    )
    return data, control


def dependencies(plan):
    return {n["id"]: set.union(*node_dependencies(n)) for n in plan["nodes"]}


def descendants(plan, changed):
    affected = set(changed)
    deps = dependencies(plan)
    while True:
        expanded = affected | {n for n, parents in deps.items() if parents & affected}
        if expanded == affected:
            return affected
        affected = expanded


@dataclass
class TaskGraph:
    task: dict
    requirements: list
    plan: dict
    dataset: str
    contracts: dict
    version: int = 1
    parent: str | None = None

    @classmethod
    def create(cls, task, requirements, plan, catalog, dataset="full"):
        from tasks.datasets import DATASETS

        if dataset not in {*DATASETS, "custom"}:
            raise ValueError("Unknown task namespace")
        return cls(
            public_task(task),
            deepcopy(requirements),
            deepcopy(plan),
            dataset,
            {
                n["tool"]: digest(catalog.tools[n["tool"]])
                for n in plan["nodes"]
                if n["tool"] in catalog.tools
            },
        )

    @classmethod
    def load(cls, document, task, catalog):
        """Reload a saved plan against the same public task and current contracts."""
        from .validation import validate_graph

        if document.get("schema_version") != "scimas.task_graph.v1":
            raise ValueError("Unsupported task graph version")
        graph = cls.create(
            task,
            document["requirements"],
            document["plan"],
            catalog,
            document["dataset"],
        )
        if (
            document.get("task_id") != graph.task["id"]
            or document.get("task_sha256") != digest(graph.task)
            or document.get("contracts") != graph.contracts
        ):
            raise ValueError("Saved graph task/contract identity mismatch")
        if type(document.get("version")) is not int or document["version"] < 1:
            raise ValueError("Invalid graph revision")
        graph.version, graph.parent = document["version"], document.get("parent")
        report = validate_graph(graph, catalog)
        if not report["valid"]:
            raise ValueError(str(report["errors"]))
        return graph

    def document(self):
        return {
            "schema_version": "scimas.task_graph.v1",
            "dataset": self.dataset,
            "task_id": self.task["id"],
            "task_sha256": digest(self.task),
            "requirements": deepcopy(self.requirements),
            "plan": deepcopy(self.plan),
            "contracts": dict(self.contracts),
            "version": self.version,
            "parent": self.parent,
        }

    @property
    def identity(self):
        return digest(self.document())

    def node(self, node_id):
        return next(n for n in self.plan["nodes"] if n["id"] == node_id)

    def node_identity(self, node_id):
        """Bind evidence to transitive inputs and guards, not an unrelated graph edit."""
        ids = set()
        todo = [node_id]
        deps = dependencies(self.plan)
        while todo:
            current = todo.pop()
            if current not in ids:
                ids.add(current)
                todo.extend(deps[current])
        return digest(
            {
                "task": digest(self.task),
                "dataset": self.dataset,
                "requirements": self.requirements,
                "nodes": [self.node(i) for i in sorted(ids)],
                "contracts": {
                    self.node(i)["tool"]: self.contracts[self.node(i)["tool"]]
                    for i in ids
                },
            }
        )

    def revise(self, replacement, catalog):
        """Atomic validated replacement. Scientific requirements stay immutable."""
        from .validation import validate_graph

        new = TaskGraph.create(
            self.task, self.requirements, replacement, catalog, self.dataset
        )
        new.version, new.parent = self.version + 1, self.identity
        report = validate_graph(new, catalog)
        if not report["valid"]:
            raise ValueError(json.dumps(report["errors"], ensure_ascii=False))
        old_nodes = {n["id"]: n for n in self.plan["nodes"]}
        new_nodes = {n["id"]: n for n in new.plan["nodes"]}
        changed = {
            i
            for i in old_nodes.keys() | new_nodes.keys()
            if old_nodes.get(i) != new_nodes.get(i)
        }
        changed |= {
            i
            for i, n in new_nodes.items()
            if self.contracts.get(n["tool"]) != new.contracts[n["tool"]]
        }
        return new, {
            "changed": sorted(changed),
            "invalidate": sorted(
                descendants(self.plan, changed) | descendants(new.plan, changed)
            ),
        }

    def resolve(self, binding, results):
        kind = binding["kind"]
        if kind == "literal":
            return deepcopy(binding["value"])
        if kind == "task":
            return deepcopy(at(self.task, binding["path"]))
        if kind == "list":
            for evidence in binding.get("provenance", []):
                self.resolve(evidence, results)
            return [self.resolve(b, results) for b in binding["items"]]
        if kind != "node":
            raise ValueError("Template must be expanded before resolving item/collect")
        node_id = binding["node"]
        result = results[node_id]
        if result.get("status") != "valid" or result.get(
            "node_sha256"
        ) != self.node_identity(node_id):
            raise ValueError("Missing, invalid or stale node evidence: " + node_id)
        output = result["output"]
        if binding.get("decoded"):
            output = json.loads(output)
        expected = binding.get("expect", {})
        if any(result.get("semantics", {}).get(k) != v for k, v in expected.items()):
            raise ValueError("Unconfirmed or conflicting scientific semantics")
        try:
            return deepcopy(at(output, binding["path"]))
        except (KeyError, IndexError, ValueError, TypeError) as error:
            raise ValueError(
                "Cannot resolve output binding from node " + node_id
                + " at path " + repr(binding["path"]) + ": " + str(error)
            ) from error

    def accept_result(
        self, node_id, response, catalog, *, semantics=None, environment=None
    ):
        """Validate real dispatcher output before it becomes available to dependents.

        Semantic annotations must come from a reviewer/metadata, not the plan's
        claims. This helper checks contracts; it does not authenticate benchmark traces.
        """
        from tools.runtime.contracts import contract_errors
        from .validation import output_schema, local_schema

        node = self.node(node_id)
        spec = catalog.tools[node["tool"]]
        if digest(spec) != self.contracts[node["tool"]]:
            raise ValueError("Tool contract changed")
        if (
            response.get("status") != "success"
            or response.get("tool", node["tool"]) != node["tool"]
        ):
            raise ValueError("Failed or foreign tool output is not scientific evidence")
        value = response.get("output")
        errors = contract_errors(value, spec["output_schema"])
        if errors:
            raise ValueError("; ".join(errors))
        if spec["output_schema"].get("type") == "string" and spec.get("output_encoding", {}).get("decoded_type") in {
            "json_object",
            "json_array",
        }:
            decoded = json.loads(value)
            errors = contract_errors(decoded, output_schema(spec, True))
            if errors:
                raise ValueError("; ".join(errors))
        for check in node.get("checks", []):
            local_schema(check["schema"])
            selected = at(
                json.loads(value) if check.get("decoded") else value, check["path"]
            )
            errors = contract_errors(selected, check["schema"])
            if errors:
                raise ValueError("; ".join(errors))
        return {
            "status": "valid",
            "node_sha256": self.node_identity(node_id),
            "output": deepcopy(value),
            "semantics": deepcopy(semantics or {}),
            "environment": deepcopy(environment),
            "tool": node["tool"],
        }

    def arguments(self, node_id, results, catalog):
        from tools.runtime.contracts import contract_errors

        node = self.node(node_id)
        if "for_each" in node:
            raise ValueError("Expand template before invocation")
        if self.contracts[node["tool"]] != digest(catalog.tools[node["tool"]]):
            raise ValueError("Tool contract changed")
        args = {k: self.resolve(v, results) for k, v in node["arguments"].items()}
        errors = contract_errors(args, catalog.tools[node["tool"]]["input_schema"])
        if errors:
            raise ValueError("; ".join(errors))
        return args

    def condition_state(self, node_id, results, *, approved_gates=()):
        node = self.node(node_id)
        if "when" not in node:
            return True
        if not isinstance(approved_gates, dict) or approved_gates.get(
            node_id
        ) != self.node_identity(node_id):
            return None

        def evaluate(expr):
            op = expr["op"]
            if op in {"all", "any"}:
                states = [evaluate(e) for e in expr["args"]]
                if op == "all":
                    return (
                        False if False in states else (None if None in states else True)
                    )
                return True if True in states else (None if None in states else False)
            if op == "not":
                state = evaluate(expr["arg"])
                return None if state is None else not state
            try:
                left, right = self.resolve(expr["left"], results), self.resolve(
                    expr["right"], results
                )
                if op in {"lt", "le", "gt", "ge"}:
                    if type(left) not in (int, float) or type(right) not in (
                        int,
                        float,
                    ):
                        return None
                if op in {"eq", "ne"}:
                    equal = _json_equal(left, right)
                    return equal if op == "eq" else not equal
                if op == "in":
                    if not isinstance(right, list):
                        return None
                    return any(_json_equal(left, item) for item in right)
                return {
                    "lt": lambda: left < right,
                    "le": lambda: left <= right,
                    "gt": lambda: left > right,
                    "ge": lambda: left >= right,
                }[op]()
            except (KeyError, IndexError, ValueError, TypeError):
                return None

        return evaluate(node["when"])

    def ready(self, results, catalog, *, approved_gates=(), running=(), early_stop=True):
        ready = []
        for node in self.plan["nodes"]:
            nid = node["id"]
            if nid in running or (
                results.get(nid, {}).get("status") == "valid"
                and results[nid].get("node_sha256") == self.node_identity(nid)
            ):
                continue
            state = self.condition_state(nid, results, approved_gates=approved_gates)
            # Disabling screening permits a *resolved false* predicate, never
            # unreviewed guards, missing evidence or invalid input contracts.
            if "for_each" in node or state is None or (early_stop and state is False):
                continue
            if not early_stop and not set.union(*node_dependencies(node)) <= results.keys():
                continue
            try:
                self.arguments(nid, results, catalog)
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            ready.append(nid)
        return ready

    def expand(self, template_id, results, catalog, *, max_items=128):
        """Materialize one bounded map, preserving source dependencies and order."""
        node = self.node(template_id)
        source = node["for_each"]
        if source["kind"] not in {"node", "task", "list"}:
            raise ValueError("Expand the producing template before mapping its collected outputs")
        values = self.resolve(source, results)
        if not isinstance(values, list) or len(values) > max_items:
            raise ValueError(
                "Template source must be an array within the expansion limit"
            )
        ids = [template_id + "__" + str(i) for i in range(len(values))]
        if set(ids) & {n["id"] for n in self.plan["nodes"]}:
            raise ValueError("Expansion ID collision")

        def item_binding(index, path):
            if source["kind"] != "list":
                return {**source, "path": source["path"] + [index] + path}
            selected = deepcopy(source["items"][index])
            while path and selected["kind"] == "list":
                head, *path = path
                if type(head) is not int or head < 0:
                    raise ValueError("Mapped list path requires a nonnegative index")
                selected = selected["items"][head]
            if not path:
                return selected
            if selected["kind"] in {"node", "task"}:
                return {**selected, "path": selected["path"] + path}
            if selected["kind"] == "literal":
                return {"kind": "literal", "value": at(selected["value"], path)}
            raise ValueError("Map item must resolve to a concrete task, node, list or literal binding")

        def transform(value, index=None, preserve_item=False):
            if not isinstance(value, dict):
                return deepcopy(value)
            if value.get("kind") == "literal":
                return deepcopy(value)
            if value.get("kind") == "item":
                if index is None:
                    if preserve_item:
                        return deepcopy(value)
                    raise ValueError("Item binding outside template")
                return item_binding(index, value["path"])
            if value.get("kind") == "collect" and value["node"] == template_id:
                return {
                    "kind": "list",
                    "items": [{**value, "kind": "node", "node": i} for i in ids],
                    "provenance": [deepcopy(source)],
                }
            return {
                k: (
                    [transform(x, index, preserve_item) for x in v]
                    if isinstance(v, list)
                    else transform(v, index, preserve_item)
                )
                for k, v in value.items()
            }

        plan = deepcopy(self.plan)
        plan["nodes"] = []
        for old in self.plan["nodes"]:
            if old["id"] == template_id:
                for index, nid in enumerate(ids):
                    child = {k: v for k, v in old.items() if k != "for_each"}
                    child = transform(child, index)
                    child["id"] = nid
                    child["object"] = old["object"] + "[" + str(index) + "]"
                    plan["nodes"].append(child)
            else:
                plan["nodes"].append(transform(old, preserve_item="for_each" in old))
        for delivery in plan["deliverables"]:
            delivery["nodes"] = [
                j for i in delivery["nodes"] for j in (ids if i == template_id else [i])
            ]
            if not delivery["nodes"]:
                # An empty candidate set is evidenced by its producer, not a fabricated invocation.
                producers = [b["node"] for b in bindings(source) if b["kind"] == "node"]
                if producers:
                    delivery["nodes"] = list(dict.fromkeys(producers))
                else:
                    raise ValueError(
                        "Empty task-input expansion needs an explicit reporting node"
                    )
        return self.revise(plan, catalog)
