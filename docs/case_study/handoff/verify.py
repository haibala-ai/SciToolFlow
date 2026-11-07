"""Verify the unpacked handoff: python verify.py (requires NumPy)."""
import csv
import hashlib
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parent
load = lambda name: json.loads((ROOT / name).read_text(encoding="utf-8"))
manifest = load("manifest.json")
for item in manifest["files"]:
    p = ROOT / item["path"]
    assert p.stat().st_size == item["bytes"], item["path"]
    assert hashlib.sha256(p.read_bytes()).hexdigest() == item["sha256"], item["path"]

d = load("case_data.json")
raw = load("source/trajectory.json")
assert d["final_answer"] == raw["final_answer"]
assert hashlib.sha256((ROOT / "source/trajectory.json").read_bytes()).hexdigest() == d["trace_sha256"]
assert hashlib.sha256((ROOT / "source/water.qout").read_bytes()).hexdigest() == d["source_sha256"]
source = (ROOT / "source/water.qout").read_text()
block = source.split("IR Intens:")[1].split("TransDip")[0]
printed = [[float(v) for v in row.split()[1:]] for row in block.splitlines()
           if re.match(r"\s*[OH]\s+[-\d.]", row)]
modes = np.array(printed).reshape(3, 3, 3).transpose(1, 0, 2)
np.testing.assert_array_equal(modes, d["source_mode_vectors"])
M = modes.reshape(3, 9)
MD = M * np.array(d["metric_diagonal"])
I = np.array([float(v) for v in re.search(r"^ IR Intens:\s*(.*)$", source, re.M)[1].split()])
fields = {
    "plain_gram": M @ M.T,
    "weighted_gram": MD @ MD.T,
    "plain_spectrum": np.linalg.eigvalsh(M @ M.T),
    "weighted_spectrum": np.linalg.eigvalsh(MD @ MD.T),
    "frequencies": [float(v) for v in re.search(r"^ Frequency:\s*(.*)$", source, re.M)[1].split()],
    "ir_intensities": I, "intensity_fractions": I / I.sum(),
}
for key, values in fields.items():
    np.testing.assert_allclose(values, d["final_answer"][key], atol=1e-12, rtol=1e-12)
with (ROOT / "mode_vectors.csv").open() as f:
    for row in csv.DictReader(f):
        i, j = int(row["mode"]) - 1, int(row["atom_index"])
        np.testing.assert_array_equal([float(row[k]) for k in ["dx", "dy", "dz"]], modes[i, j])
        np.testing.assert_array_equal([float(row[k]) for k in ["x_angstrom", "y_angstrom", "z_angstrom"]],
                                      d["source_geometry_angstrom"][j])
calls = load("tool_calls.json")["calls"]
assert len(calls) == 12
assert sum(c["kind"] == "scientific" for c in calls) == 11
graphs = load("task_graphs.json")["graphs"]
assert [len(g["nodes"]) for g in graphs] == [9, 10]
assert len(graphs[1]["edges"]) == 7
print("PASS: archive hashes, source data, seven answer fields, plotting CSV, calls and graphs")
