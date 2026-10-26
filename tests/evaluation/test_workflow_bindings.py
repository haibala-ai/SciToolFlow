"""Alternative-specific dataflow is conjunctive with shared node bindings."""

import copy
import unittest
from evaluation.workflow import score_workflow, validate_workflow
from tests.support.workflows import fixture, run, ROWS


class AlternativeBindingTest(unittest.TestCase):
    def fixture(self):
        ref, prediction = fixture(), run()
        node = ref["evaluation"]["nodes"][2]
        # Shared audit binding must hold for either accepted source layout.
        node["bindings"] = [
            {"argument": "/audit", "source_node": "audit", "output": "/consistent"}
        ]
        original = node["alternatives"][0]
        original["bindings"] = [
            {"argument": "/rows", "source_node": "load", "output": "/rows"}
        ]
        swapped = copy.deepcopy(original)
        swapped["bindings"][0]["argument"] = "/data"
        node["alternatives"] = [original, swapped]
        prediction["calls"][2]["arguments"] = {
            "data": copy.deepcopy(ROWS),
            "audit": True,
        }
        return ref, prediction

    def test_either_layout_allowed_but_shared_and_chosen_bindings_both_required(self):
        ref, prediction = self.fixture()
        self.assertTrue(score_workflow(ref, prediction)["joint_pass"])
        prediction["calls"][2]["arguments"]["audit"] = False
        self.assertFalse(score_workflow(ref, prediction)["planning_pass"])
        prediction["calls"][2]["arguments"]["audit"] = True
        prediction["calls"][2]["arguments"]["data"] = []
        self.assertFalse(score_workflow(ref, prediction)["planning_pass"])
        prediction["calls"][2]["arguments"] = {
            "rows": copy.deepcopy(ROWS),
            "audit": True,
        }
        self.assertTrue(score_workflow(ref, prediction)["joint_pass"])

    def test_alternative_binding_requires_dependency_and_valid_pointer(self):
        ref, _ = self.fixture()
        binding = ref["evaluation"]["nodes"][2]["alternatives"][1]["bindings"][0]
        for field, bad in [
            ("source_node", "unknown"),
            ("argument", "rows"),
            ("output", "/bad~2escape"),
            ("atol", -1),
        ]:
            bad_ref = copy.deepcopy(ref)
            bad_ref["evaluation"]["nodes"][2]["alternatives"][1]["bindings"][0][
                field
            ] = bad
            with self.assertRaises(ValueError):
                validate_workflow(bad_ref["evaluation"])
        validate_workflow(ref["evaluation"])


if __name__ == "__main__":
    unittest.main()
