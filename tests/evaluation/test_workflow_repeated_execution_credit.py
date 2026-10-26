"""Repeated feedback cannot earn efficiency credit through overlapping routes."""

import copy
import unittest

from evaluation.workflow import score_workflow


def observation(identifier, tool="T", output=None, status="success"):
    return dict(
        observation_id=identifier,
        tool=tool,
        arguments=dict(query="same"),
        status=status,
        output=output if output is not None else dict(ok=True),
    )


def reference(nodes=None, efficiency=None):
    nodes = nodes or [
        dict(
            id=name,
            required=False,
            alternatives=[
                dict(tools=["T"], output_rules=[dict(path="/ok", op="eq", value=True)])
            ],
        )
        for name in ("a", "b")
    ]
    return dict(
        evaluation=dict(
            schema_version="workflow.v1",
            nodes=nodes,
            capability_groups=[dict(id="g", alternatives=[[nodes[-1]["id"]]])],
            outcomes=[
                dict(
                    id="answer",
                    left=dict(source="answer", path="/x"),
                    op="eq",
                    value=1,
                    evidence_groups=["g"],
                )
            ],
            efficiency=efficiency or {},
        )
    )


def score(ref, calls):
    return score_workflow(
        ref, dict(completed=True, calls=calls, final_answer=dict(x=1))
    )


class RepeatedExecutionCreditTests(unittest.TestCase):
    def numerical_call(self, identifier, *, stdout="1\n", plot="result.png"):
        call = observation(
            identifier,
            tool="ExecuteNumericalCode",
            output=dict(
                stdout=stdout,
                stderr="",
                exit_code=0,
                artifact_directory="/runs/" + identifier,
                plots=["/runs/" + identifier + "/" + plot],
            ),
        )
        call["arguments"] = {"code": "print(1)"}
        return call

    def numerical_reference(self):
        return reference(
            [
                dict(
                    id=name,
                    required=False,
                    alternatives=[
                        dict(
                            tools=["ExecuteNumericalCode"],
                            output_rules=[dict(path="/exit_code", op="eq", value=0)],
                        )
                    ],
                )
                for name in ("a", "b")
            ]
        )

    def test_numerical_worker_uuid_is_not_new_scientific_credit(self):
        calls = [self.numerical_call("one"), self.numerical_call("two")]
        before = copy.deepcopy(calls)
        r = score(self.numerical_reference(), calls)
        self.assertTrue(r["joint_pass"])
        self.assertEqual(r["matched_scientific_calls"], 1)
        self.assertEqual(r["charged_scientific_calls"], 2)
        self.assertEqual(r["selection_efficiency"], 0.5)
        self.assertEqual(r["redundant_calls"], 1)
        self.assertEqual(calls, before)

    def test_changed_numerical_feedback_keeps_distinct_credit(self):
        for field, value in (("stdout", "2\n"), ("stderr", "warning")):
            with self.subTest(field=field):
                calls = [self.numerical_call("one"), self.numerical_call("two")]
                calls[-1]["output"][field] = value
                r = score(self.numerical_reference(), calls)
                self.assertEqual(r["matched_scientific_calls"], 2)
                self.assertEqual(r["redundant_calls"], 0)

    def test_different_plot_names_are_not_merged(self):
        r = score(
            self.numerical_reference(),
            [
                self.numerical_call("one"),
                self.numerical_call("two", plot="other.png"),
            ],
        )
        self.assertEqual(r["matched_scientific_calls"], 2)

    def test_external_plot_paths_are_not_relativized(self):
        calls = [self.numerical_call("one"), self.numerical_call("two")]
        calls[0]["output"]["plots"] = ["/external/one/result.png"]
        calls[1]["output"]["plots"] = ["/external/two/result.png"]
        r = score(self.numerical_reference(), calls)
        self.assertEqual(r["matched_scientific_calls"], 2)

    def test_identical_matched_observations_earn_one_credit(self):
        r = score(reference(), [observation("one"), observation("two")])
        self.assertTrue(r["joint_pass"])
        self.assertEqual(r["matched_scientific_calls"], 1)
        self.assertEqual(r["charged_scientific_calls"], 2)
        self.assertEqual(r["selection_efficiency"], 0.5)
        self.assertEqual(r["raw_selection_efficiency"], 0.5)
        self.assertEqual(r["redundant_calls"], 1)

    def test_same_query_with_new_actual_data_retains_credit(self):
        nodes = [
            dict(
                id=str(i),
                alternatives=[
                    dict(
                        tools=["T"],
                        output_rules=[dict(path="/value", op="eq", value=i)],
                    )
                ],
            )
            for i in (1, 2)
        ]
        r = score(
            reference(nodes),
            [
                observation("old", output=dict(value=1)),
                observation("new", output=dict(value=2)),
            ],
        )
        self.assertTrue(r["joint_pass"])
        self.assertEqual(r["matched_scientific_calls"], 2)
        self.assertEqual(r["selection_efficiency"], 1)
        self.assertEqual(r["redundant_calls"], 0)

    def test_error_then_success_is_recovery_not_duplicate(self):
        failed = observation("failure", status="error")
        failed.update(output=None, error_type="Timeout", error="Retry may recover")
        r = score(
            reference(efficiency=dict(free_recovery_calls=1)),
            [failed, observation("success")],
        )
        self.assertTrue(r["joint_pass"])
        self.assertEqual(r["recovery_exempt_calls"], 1)
        self.assertEqual(r["redundant_calls"], 0)
        self.assertEqual(r["raw_selection_efficiency"], 0.5)
        self.assertEqual(r["selection_efficiency"], 1)

    def test_earlier_copy_of_later_witness_has_no_exploration_allowance(self):
        nodes = [
            dict(
                id="source",
                alternatives=[
                    dict(
                        tools=["Source"],
                        output_rules=[dict(path="/ok", op="eq", value=True)],
                    )
                ],
            ),
            dict(
                id="dependent",
                depends_on=["source"],
                alternatives=[
                    dict(
                        tools=["T"],
                        output_rules=[dict(path="/ok", op="eq", value=True)],
                    )
                ],
            ),
        ]
        r = score(
            reference(
                nodes, dict(free_disambiguation_calls=3, disambiguation_tools=["T"])
            ),
            [
                observation("early"),
                observation("source", tool="Source"),
                observation("later"),
            ],
        )
        self.assertTrue(r["joint_pass"])
        self.assertEqual(r["exploration_exempt_calls"], 0)
        self.assertEqual(r["charged_scientific_calls"], 3)
        self.assertEqual(r["matched_scientific_calls"], 2)
        self.assertEqual(r["selection_efficiency"], 2 / 3)
        self.assertEqual(r["redundant_calls"], 1)

    def test_identical_failed_retries_are_charged_after_first_allowance(self):
        failed = observation("failure", status="error")
        failed.update(output=None, error_type="Timeout", error="Same failure")
        repeated = copy.deepcopy(failed)
        repeated["observation_id"] = "retry"
        r = score(
            reference(efficiency=dict(free_recovery_calls=5)),
            [failed, repeated, observation("success")],
        )
        self.assertEqual(r["recovery_exempt_calls"], 1)
        self.assertEqual(r["charged_scientific_calls"], 2)
        self.assertEqual(r["selection_efficiency"], 0.5)
        self.assertEqual(r["raw_selection_efficiency"], 1 / 3)
        self.assertEqual(r["redundant_calls"], 1)


if __name__ == "__main__":
    unittest.main()
