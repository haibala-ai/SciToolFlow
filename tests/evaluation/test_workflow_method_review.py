import copy
import unittest

from evaluation.workflow.constants import compact
from evaluation.review.methods import classify, exact_programs


class MethodReviewTests(unittest.TestCase):
    def setUp(self):
        self.ref = {
            "evaluation": {
                "nodes": [
                    {
                        "id": "source",
                        "alternatives": [{"tools": ["ParseJSONDocument"]}],
                    },
                    {
                        "id": "analysis",
                        "alternatives": [
                            {
                                "tools": ["ExecuteNumericalCode"],
                                "input_rules": [
                                    {
                                        "left": {
                                            "source": "call_arguments",
                                            "path": "/code",
                                        },
                                        "op": "eq",
                                        "right": {"value": "print(1+1)"},
                                    }
                                ],
                            }
                        ],
                    },
                ]
            }
        }
        self.raw = {
            "joint_pass": False,
            "runtime_pass": True,
            "answer_only_credit": 1,
            "nodes": [
                {
                    "id": "source",
                    "required": True,
                    "matched": True,
                    "observation_id": "o1",
                },
                {"id": "analysis", "required": True, "matched": False},
            ],
        }
        self.call = {
            "tool": "ExecuteNumericalCode",
            "status": "success",
            "observation_id": "o2",
            "arguments": {"code": "print(sum([1,1]))"},
            "output": {
                "code": "print(sum([1,1]))",
                "status": "success",
                "execution_status": "completed",
                "exit_code": 0,
                "stdout_truncated": False,
                "stderr_truncated": False,
            },
        }
        self.contracts = {"ExecuteNumericalCode": {"domain": "General"}}

    def test_same_tool_new_program_is_unresolved_not_an_automatic_failure(self):
        result = classify(self.ref, {"calls": [self.call]}, self.raw, self.contracts)
        self.assertEqual(result["observations"], ["o2"])
        self.assertEqual(result["kind"], "unrecognized_computational_proof")

    def test_correct_printed_values_do_not_grant_scientific_approval(self):
        call = copy.deepcopy(self.call)
        call["arguments"]["code"] = call["output"]["code"] = "print(2)"
        result = classify(self.ref, {"calls": [call]}, self.raw, self.contracts)
        self.assertIn("never establishes scientific validity", result["reason"])
        self.assertNotIn("joint_pass", result)

    def test_wrong_answers_missing_sources_and_failed_runs_are_not_method_candidates(
        self,
    ):
        for field, value in [("answer_only_credit", 0.5), ("runtime_pass", False)]:
            raw = {**self.raw, field: value}
            self.assertIsNone(
                classify(self.ref, {"calls": [self.call]}, raw, self.contracts)
            )
        raw = copy.deepcopy(self.raw)
        raw["nodes"][0]["matched"] = False
        self.assertIsNone(
            classify(self.ref, {"calls": [self.call]}, raw, self.contracts)
        )

    def test_known_and_incomplete_programs_do_not_create_spurious_pending_reviews(self):
        call = copy.deepcopy(self.call)
        call["arguments"]["code"] = call["output"]["code"] = "print(1+1)"
        self.assertIsNone(
            classify(self.ref, {"calls": [call]}, self.raw, self.contracts)
        )
        call = copy.deepcopy(self.call)
        call["output"]["stdout_truncated"] = True
        self.assertIsNone(
            classify(self.ref, {"calls": [call]}, self.raw, self.contracts)
        )

    def test_compacted_programs_remain_recognized(self):
        ref = copy.deepcopy(self.ref)
        code = "print(1+1)" * 200
        ref["evaluation"]["nodes"][1]["alternatives"][0]["input_rules"][0]["right"][
            "value"
        ] = code
        ref["evaluation"] = compact(ref["evaluation"])
        self.assertEqual(exact_programs(ref), {code})
