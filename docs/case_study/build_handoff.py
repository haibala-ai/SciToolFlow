"""Export a portable, trace-grounded handoff for the SMAS-0070 case designer."""
import csv
import hashlib
import json
from pathlib import Path
import zipfile

from build_case import extract

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "handoff"
OUT.mkdir(exist_ok=True)
e = extract()  # Verifies hashes and all seven numeric answer fields.
trace_path = ROOT / e["trace"]
trace = json.loads(trace_path.read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def bindings(value):
    if isinstance(value, dict):
        if value.get("kind") == "node":
            yield value
        for child in value.values():
            yield from bindings(child)
    elif isinstance(value, list):
        for child in value:
            yield from bindings(child)


calls = []
timeline = []
for index, step in enumerate(trace["steps"]):
    event = {"array_index": index, "step_id": step["step_id"], "type": step["type"],
             "role": step.get("role", ""), "recorded_seconds": step.get("recorded_seconds"),
             "recorded_at": step.get("recorded_at"), "node": step.get("node", ""),
             "observation_ids": "", "action": ""}
    if step["type"] == "tools":
        for c in step["calls"]:
            calls.append({"step_id": step["step_id"], "array_index": index,
                          **{k: c[k] for k in ["observation_id", "node", "tool", "kind", "arguments",
                                              "status", "output", "started_seconds", "finished_seconds",
                                              "duration_seconds"] if k in c},
                          "review_state_at_recording": c.get("review_state"),
                          "final_result_status": trace["results"].get(c.get("node"), {}).get("status"),
                          "selected_observation_for_final_node": trace["results"].get(c.get("node"), {}).get("observation_id")})
        event["observation_ids"] = ",".join(c["observation_id"] for c in step["calls"])
        event["node"] = ",".join(c.get("node", "") for c in step["calls"])
        event["action"] = ",".join(c["tool"] for c in step["calls"])
    elif step["type"] == "decision":
        event["action"] = ",".join(step.get("decision", {})) or "protocol_error"
    elif step["type"] == "dispatch":
        event["action"] = step["tool"]
    elif step["type"] == "finish":
        event["action"] = "final_answer"
    timeline.append(event)

graphs = []
for graph in trace["graphs"]:
    edges = []
    for node in graph["plan"]["nodes"]:
        grouped = {}
        for b in bindings(node["arguments"]):
            grouped.setdefault(b["node"], []).append(b["path"])
        for parent, paths in grouped.items():
            unique = list({json.dumps(p): p for p in paths}.values())
            edges.append({"source": parent, "target": node["id"], "source_paths": unique})
    graphs.append({"version": graph["version"], "parent_sha256": graph["parent"],
                   "nodes": graph["plan"]["nodes"], "edges": edges,
                   "deliverables": graph["plan"]["deliverables"],
                   "requirements": graph["requirements"], "contract_hashes": graph["contracts"]})

save("tool_calls.json", {"notes": "Exact recorded arguments and outputs; original absolute source paths are historical. Use source/water.qout in the zip for the same bytes. review_state_at_recording can remain pending even when later accepted; consult final_result_status and reviewer records.",
                         "calls": calls})
save("task_graphs.json", {"notes": "Dependency edges, not execution chronology. version 1 has the incorrect modes shape; version 2 is the accepted repaired graph.", "graphs": graphs})
data = {
    **e, "started_at_utc": trace["started_at"], "finished_at_utc": trace["finished_at"],
    "public_task_as_logged": trace["task"], "limits": trace["limits"],
    "graph_versions": [g["version"] for g in graphs],
    "final_node_results": trace["results"],
    "reviewer_records": trace["reviews"], "repair_records": trace["repairs"],
    "repair_attempts": trace["repair_attempts"],
    "planner_requirements": trace["planning"]["requirements"],
    "planner_retrievals": [{"queries": r["queries"], "kg_sha256": r["kg_sha256"],
                            "embedding_usage": r.get("embedding_usage")} for r in trace["planning"]["retrievals"]],
    "planner_contract_queries": trace["planning"]["contract_queries"],
    "embedding_usage": trace["planning"]["embedding_usage"],
    "recorded_experience_count": len(trace["experiences"]),
    "plain_mode_matrix": [sum(mode, []) for mode in e["source_mode_vectors"]],
    "metric_diagonal": [4, 4, 4, 1, 1, 1, 1, 1, 1],
    "figure_reference": "reference/SciToolAgent_case.png",
    "original_trace_in_bundle": "source/trajectory.json",
    "source_asset_in_bundle": "source/water.qout",
    "timing_note": "recorded_seconds is the logged event timestamp, not necessarily completion time of the associated model call. Use started_seconds/finished_seconds from tool_calls.json to establish actual tool overlap.",
}
save("case_data.json", data)
with (OUT / "event_timeline.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(timeline[0]), lineterminator="\n"); w.writeheader(); w.writerows(timeline)
with (OUT / "mode_vectors.csv").open("w", newline="") as f:
    fields = ["mode", "atom_index", "element", "x_angstrom", "y_angstrom", "z_angstrom",
              "dx", "dy", "dz", "frequency_cm_inverse", "ir_intensity_km_per_mol", "ir_fraction"]
    w = csv.writer(f, lineterminator="\n"); w.writerow(fields)
    for i, mode in enumerate(e["source_mode_vectors"]):
        for j, vector in enumerate(mode):
            w.writerow([i + 1, j, ["O", "H", "H"][j], *e["source_geometry_angstrom"][j], *vector,
                        e["final_answer"]["frequencies"][i], e["final_answer"]["ir_intensities"][i],
                        e["final_answer"]["intensity_fractions"][i]])

# Include immutable source bytes in the portable archive without duplicating them in the repo tree.
items = {p.name: p for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"}
items.update({"source/trajectory.json": trace_path, "source/water.qout": ROOT / e["source_asset"],
              "reference/SciToolAgent_case.png": ROOT / "SciMas/case.png"})
for name in ["SMAS-0070.png", "SMAS-0070.svg", "SMAS-0070.pdf", "build_case.py"]:
    items["draft/" + name] = HERE / name
manifest = {"task_id": "SMAS-0070", "files": [
    {"path": name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    for name, p in sorted(items.items())]}
save("manifest.json", manifest)
items["manifest.json"] = OUT / "manifest.json"
archive = HERE / "SMAS-0070_handoff.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name, path in sorted(items.items()):
        z.write(path, "SMAS-0070_handoff/" + name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for entry in manifest["files"]:
        assert hashlib.sha256(z.read("SMAS-0070_handoff/" + entry["path"])).hexdigest() == entry["sha256"]
print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size,
                  "steps": len(timeline), "calls": len(calls),
                  "final_graph_nodes": len(graphs[-1]["nodes"]),
                  "final_graph_edges": len(graphs[-1]["edges"]),
                  "all_archive_hashes_verified": True}, ensure_ascii=False))
