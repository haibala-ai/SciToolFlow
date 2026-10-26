"""Explicit fused-observation evidence cannot manufacture missing computations."""

import copy
import unittest
from evaluation.workflow import score_workflow, validate_workflow


def reference(groups=("fused", "fused"), dependency=False):
    nodes = []
    for i, (name, key) in enumerate([("a", "first"), ("b", "second")]):
        n = dict(
            id=name,
            alternatives=[
                dict(
                    tools=["Projection"],
                    output_rules=[dict(path="/" + key, op="eq", value=i + 1)],
                )
            ],
        )
        if groups[i] is not None:
            n["observation_reuse_group"] = groups[i]
        if dependency and i:
            n["depends_on"] = ["a"]
        nodes.append(n)
    return dict(
        evaluation=dict(
            schema_version="workflow.v1",
            nodes=nodes,
            outcomes=[
                dict(
                    id="answer",
                    left=dict(source="answer", path="/ok"),
                    op="eq",
                    value=True,
                    evidence_nodes=["a", "b"],
                )
            ],
        )
    )


def call(ident="one", output=None):
    return dict(
        observation_id=ident,
        tool="Projection",
        arguments=dict(matrix=[[1, 2]]),
        status="success",
        output=output if output is not None else dict(first=1, second=2),
    )


def score(r, calls):
    return score_workflow(
        r, dict(completed=True, calls=calls, final_answer=dict(ok=True))
    )


class ObservationReuseTests(unittest.TestCase):
    def test_explicit_same_group_fulfils_independent_nodes(self):
        result = score(reference(), [call()])
        self.assertTrue(result["joint_pass"])
        self.assertTrue(all(n["matched"] for n in result["nodes"]))
        self.assertEqual(result["matched_scientific_calls"], 1)
        self.assertEqual(result["charged_scientific_calls"], 1)
        self.assertEqual(result["selection_efficiency"], 1)

    def test_absent_or_different_groups_keep_one_observation_per_node(self):
        for groups in [(None, None), ("x", "y"), (None, "x"), ("x", None)]:
            with self.subTest(groups=groups):
                self.assertFalse(score(reference(groups), [call()])["joint_pass"])

    def test_missing_or_wrong_cell_is_not_accepted_through_reuse(self):
        for output in [
            dict(first=1),
            dict(first=1, second=99),
            dict(first=99, second=2),
        ]:
            with self.subTest(output=output):
                self.assertFalse(
                    score(reference(), [call(output=output)])["joint_pass"]
                )

    def test_strict_dependency_order_still_requires_later_execution(self):
        ref = reference(dependency=True)
        self.assertFalse(score(ref, [call()])["joint_pass"])
        self.assertTrue(score(ref, [call("one"), call("two")])["joint_pass"])

    def test_repeated_actual_computation_is_still_charged_twice(self):
        result = score(reference(), [call("one"), call("two")])
        self.assertTrue(result["joint_pass"])
        self.assertEqual(result["matched_scientific_calls"], 1)
        self.assertEqual(result["charged_scientific_calls"], 2)
        self.assertEqual(result["selection_efficiency"], 0.5)

    def test_cross_group_competition_cannot_steal_used_observation(self):
        ref = reference()
        third = copy.deepcopy(ref["evaluation"]["nodes"][1])
        third["id"] = "c"
        third["observation_reuse_group"] = "other"
        ref["evaluation"]["nodes"].append(third)
        ref["evaluation"]["outcomes"][0]["evidence_nodes"].append("c")
        self.assertFalse(score(ref, [call()])["joint_pass"])
        second = call("two")
        second["arguments"]["matrix"] = [[3, 4]]
        self.assertTrue(score(ref, [call(), second])["joint_pass"])

    def test_optional_reuse_does_not_hide_required_science(self):
        ref = reference()
        ref["evaluation"]["nodes"][1]["required"] = False
        ref["evaluation"]["capability_groups"] = [
            dict(id="both", alternatives=[["a", "b"]])
        ]
        self.assertFalse(score(ref, [call(output=dict(first=1))])["joint_pass"])
        self.assertTrue(score(ref, [call()])["joint_pass"])

    def test_empty_and_nonstring_reuse_groups_fail_schema(self):
        for group in ["", False, 1, None, "a" * 129]:
            ref = reference()
            ref["evaluation"]["nodes"][0]["observation_reuse_group"] = group
            with self.subTest(group=group):
                with self.assertRaises(ValueError):
                    validate_workflow(ref["evaluation"])


if __name__ == "__main__":
    unittest.main()
