"""Task-quality counterexamples: invariance, changing evidence, and negative controls."""

import copy
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.answer import score_answer
from evaluation.evidence import condition_reference
from evaluation.source_drift import selector_drift
from evaluation.judge import judge_requests
from scitoolflow.benchmark.schema import answer_schema


def reference(value, tools=()):
    return {
        "id": "test",
        "tool_path": list(tools),
        "expected_answer": value,
        "answer_contract": answer_schema(value),
        "scoring": {
            "mathematical_equivalence": True,
            "field_rules": [
                {"field": "results", "path": ["results"], "atol": 1e-8, "rtol": 1e-6}
            ],
        },
    }


class MathematicalEquivalenceTests(unittest.TestCase):
    def test_eigenbasis_joint_sign_and_degenerate_rotation(self):
        g = {"results": {"eigenvalues": [1, 2], "eigenvectors": [[1, 0], [0, 1]]}}
        r = reference(g)
        a = copy.deepcopy(g)
        a["results"]["eigenvectors"] = [[-1, 0], [0, 1]]
        self.assertEqual(score_answer(r, a)["status"], "passed")
        a["results"]["eigenvalues"] = [1, 3]
        self.assertEqual(score_answer(r, a)["status"], "failed")
        g["results"]["eigenvalues"] = [2, 2]
        r = reference(g)
        a = copy.deepcopy(g)
        h = 2**-0.5
        a["results"]["eigenvectors"] = [[h, -h], [h, h]]
        self.assertEqual(score_answer(r, a)["status"], "passed")

    def test_pca_components_and_scores_must_transform_together(self):
        g = {
            "results": {
                "components": [[1, 0], [0, 1]],
                "features": [[1, 0], [-1, 0], [0, 0]],
                "explained_variance": [1, 0],
                "explained_variance_ratio": [1, 0],
            }
        }
        r = reference(g)
        a = copy.deepcopy(g)
        a["results"]["components"][0] = [-1, 0]
        a["results"]["features"] = [[-1, 0], [1, 0], [0, 0]]
        self.assertEqual(score_answer(r, a)["status"], "passed")
        a["results"]["features"] = g["results"]["features"]
        self.assertEqual(score_answer(r, a)["status"], "failed")

    def test_cluster_partition_requires_corresponding_centers(self):
        g = {
            "results": {
                "labels": [0, 0, 1],
                "centroids": [[1], [7]],
                "cluster_sizes": {"0": 2, "1": 1},
            }
        }
        r = reference(g, ["KMeansClustering"])
        a = {
            "results": {
                "labels": [1, 1, 0],
                "centroids": [[7], [1]],
                "cluster_sizes": {"0": 1, "1": 2},
            }
        }
        self.assertEqual(score_answer(r, a)["status"], "passed")
        a["results"]["centroids"] = [[1], [7]]
        self.assertEqual(score_answer(r, a)["status"], "failed")
        a = copy.deepcopy(g)
        a["results"]["labels"] = [0, 1, 0]
        self.assertEqual(score_answer(r, a)["status"], "failed")

    def test_unlabelled_membership_groups_allow_group_order_only(self):
        g = {
            "results": {
                "labels": [0, 0, 1],
                "centroids": [[1], [7]],
                "groups": [["M0", "M1"], ["M2"]],
            }
        }
        r = reference(g, ["KMeansClustering"])
        a = {
            "results": {
                "labels": [1, 1, 0],
                "centroids": [[7], [1]],
                "groups": [["M2"], ["M1", "M0"]],
            }
        }
        self.assertEqual(score_answer(r, a)["status"], "passed")
        a["results"]["groups"][1][0] = "M9"
        self.assertNotEqual(score_answer(r, a)["status"], "passed")

    def test_dbscan_noise_is_not_an_arbitrary_cluster_label(self):
        g = {"results": {"returned_labels": [0, 0, -1, 1]}}
        r = reference(g, ["DBSCANClustering"])
        self.assertEqual(
            score_answer(r, {"results": {"returned_labels": [7, 7, -1, 2]}})["status"],
            "passed",
        )
        self.assertEqual(
            score_answer(r, {"results": {"returned_labels": [7, 7, 2, -1]}})["status"],
            "failed",
        )

    def test_unused_centers_and_variance_pairing_are_not_filled_in(self):
        g = {"results": {"labels": [0, 0], "centroids": [[1], [7]]}}
        r = reference(g, ["KMeansClustering"])
        a = {"results": {"labels": [1, 1], "centroids": [[999], [1]]}}
        self.assertEqual(score_answer(r, a)["status"], "failed")
        g = {
            "results": {
                "components": [[1, 0], [0, 1]],
                "features": [[1, 0], [-1, 0], [0, 0]],
                "explained_variance": [1, 0],
                "explained_variance_ratio": [1, 0],
            }
        }
        r = reference(g)
        a = copy.deepcopy(g)
        a["results"]["components"][0] = [-1, 0]
        a["results"]["features"] = [[-1, 0], [1, 0], [0, 0]]
        a["results"]["explained_variance_ratio"] = [0, 1]
        self.assertEqual(score_answer(r, a)["status"], "failed")

    def test_independent_pca_branches_cannot_borrow_each_others_rotation(self):
        pca = {
            "components": [[1, 0], [0, 1]],
            "features": [[1, 0], [-1, 0], [0, 0]],
            "explained_variance": [1, 0],
            "explained_variance_ratio": [1, 0],
        }
        cluster = {"labels": [0, 0, 1], "centroids": [[1, 0], [7, 0]]}
        g = {
            "results": {
                "branches": {
                    "A": {"pca": pca, "clustering": cluster},
                    "B": {
                        "pca": copy.deepcopy(pca),
                        "clustering": copy.deepcopy(cluster),
                    },
                }
            }
        }
        r = reference(g, ["KMeansClustering"])
        a = copy.deepcopy(g)
        b = a["results"]["branches"]["B"]
        b["pca"]["components"][0] = [-1, 0]
        b["pca"]["features"] = [[-1, 0], [1, 0], [0, 0]]
        for branch in a["results"]["branches"].values():
            for row in branch["clustering"]["centroids"]:
                row[0] = -row[0]
        self.assertEqual(score_answer(r, a)["status"], "failed")

    def test_malformed_matrix_never_crashes_or_becomes_equivalent(self):
        g = {"results": {"eigenvalues": [1, 2], "eigenvectors": [[1, 0], [0, 1]]}}
        r = reference(g)
        for v in [None, [], [[1]], "unknown"]:
            a = copy.deepcopy(g)
            a["results"]["eigenvectors"] = v
            self.assertNotEqual(score_answer(r, a)["status"], "passed")


class EvidenceConditioningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = {
            r["id"]: r
            for line in (ROOT / "evaluation/references.jsonl").read_text().splitlines()
            if (r := json.loads(line))
        }

    def test_unseeded_inertia_uses_observed_same_molecule_only(self):
        r = self.refs["FLOW-0191"]
        call = {
            "tool": "CalculatePmi",
            "status": "success",
            "arguments": {"smiles": r["inputs"]["smiles"]},
            "observation_id": "o123",
            "output": "### Results\n- NPR1 (Normalized Principal Moment of Inertia 1): 0.3000\n- NPR2 (Normalized Principal Moment of Inertia 2): 0.9000\n",
        }
        conditioned, proof = condition_reference(r, [call], None)
        self.assertEqual(proof["status"], "conditioned_on_actual_observation")
        self.assertEqual(
            conditioned["expected_answer"]["results"]["native_normalized_ratios"],
            [0.3, 0.9],
        )
        self.assertEqual(
            score_answer(conditioned, conditioned["expected_answer"])["status"],
            "passed",
        )
        wrong = copy.deepcopy(conditioned["expected_answer"])
        wrong["results"]["seed42_minus_native_ratios"][0] += 0.1
        self.assertEqual(score_answer(conditioned, wrong)["status"], "failed")
        call["arguments"]["smiles"] = "different molecule"
        _, proof = condition_reference(r, [call], None)
        self.assertEqual(proof["status"], "missing_actual_evidence")

    def test_standard_identifier_and_tiny_probability_errors_cannot_pass(self):
        r = copy.deepcopy(self.refs["FLOW-0001"])
        a = copy.deepcopy(r["expected_answer"])
        a["results"]["identifiers"]["original"][
            "full_inchikey"
        ] = "AAAAAAAAAAAAAA-BBBBBBBBBB-C"
        self.assertEqual(score_answer(r, a)["status"], "failed")
        r = self.refs["FLOW-0285"]
        a = copy.deepcopy(r["expected_answer"])
        a["results"]["pearson"]["p_value"] = 0
        self.assertEqual(score_answer(r, a)["status"], "failed")
        r = self.refs["FLOW-0008"]
        a = copy.deepcopy(r["expected_answer"])
        a["results"]["analysis"]["derived"]["band_gap_joule"] = 0
        self.assertEqual(score_answer(r, a)["status"], "failed")

    def test_review_metadata_removed_but_scientific_source_hash_retained(self):
        for r in self.refs.values():
            self.assertNotIn("review_artifact_manifest", str(r["answer_contract"]))
        self.assertIn("source_sha256", str(self.refs["FLOW-0099"]["expected_answer"]))


class SelectorCountTests(unittest.TestCase):
    def test_separately_displayed_first_identifier_is_not_omitted(self):
        refs = {
            r["id"]: r
            for l in (ROOT / "evaluation/references.jsonl").read_text().splitlines()
            if (r := json.loads(l))
        }
        for identifier, key in [
            ("FLOW-0247", "num_identifiers_returned"),
            ("FLOW-0265", "material_ids_returned_count"),
            ("FLOW-0319", "resolver_identifier_count"),
        ]:
            r = refs[identifier]
            e = next(
                e
                for l in (ROOT / r["reference_trace"]).read_text().splitlines()
                if (e := json.loads(l)).get("event") == "tool_result"
                and e.get("tool") == "GetMaterialIdByFormula"
            )
            count = len(set(re.findall(r"\bmp-\d+\b", e["output"])))
            self.assertEqual(r["expected_answer"]["results"][key], count)
            a = copy.deepcopy(r["expected_answer"])
            a["results"][key] = count - 1
            self.assertEqual(score_answer(r, a)["status"], "failed")


class SourceVersionTests(unittest.TestCase):
    def test_changed_selector_is_not_confused_with_wrong_model_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = {
                "event": "tool_result",
                "tool": "SearchByBandGap",
                "arguments": {"band_gap": "0-1"},
                "status": "success",
                "observation_id": "o001",
                "output": "mp-1\nmp-2",
            }
            Path(tmp, "ref.jsonl").write_text(json.dumps(event) + "\n")
            r = {"tool_path": ["SearchByBandGap"], "reference_trace": "ref.jsonl"}
            actual = {**event, "output": "mp-3\nmp-2"}
            self.assertEqual(len(selector_drift(r, [actual], tmp, {})), 1)
            actual["arguments"] = {"band_gap": "2-3"}
            self.assertEqual(selector_drift(r, [actual], tmp, {}), [])
            actual = {**event, "output": "updated today: mp-1\nmp-2"}
            self.assertEqual(selector_drift(r, [actual], tmp, {}), [])

    def test_changed_sources_never_use_the_weak_automatic_judge(self):
        class NoRequests:
            backend = "injected"

            def request(self, *a, **k):
                raise AssertionError("Must not call model")

        with tempfile.TemporaryDirectory() as tmp:
            request = Path(tmp, "requests.json")
            request.write_text(
                json.dumps(
                    {"tasks": [{"id": "case", "requires_independent_review": True}]}
                )
            )
            result = judge_requests(
                request, Path(tmp, "reviews.json"), client=NoRequests()
            )
            self.assertFalse(result["reviews"])
            self.assertEqual(result["unresolved"][0]["id"], "case")


if __name__ == "__main__":
    unittest.main()
