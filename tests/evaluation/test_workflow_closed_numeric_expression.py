"""Closed arithmetic evidence decoding must never become general execution."""

import math
import unittest
from evaluation.workflow.numeric_expression import (
    decode_numeric_expression as decode,
    NumericExpressionError,
)
from evaluation.workflow import operand, MissingEvidence


class ClosedNumericExpressionTests(unittest.TestCase):
    def test_calculator_query_and_result_text(self):
        query = "N[{-Log[72/82]/100, (72/82)^6, 1-72/82, (10/(100*1+200*1+300*3+400*5+500*10))/(-Log[72/82]/100)-1}, 16]"
        values = decode(query)
        for v, w in zip(
            values,
            [
                0.0013005312824819779,
                0.4582599087429164,
                0.12195121951219512,
                -0.06229691546166205,
            ],
        ):
            self.assertAlmostEqual(v, w, places=14)
        self.assertEqual(decode("1.0e-2, -3, +2/4"), [0.01, -3, 0.5])
        self.assertEqual(decode("[1,2]"), [1.0, 2.0])
        self.assertEqual(decode("N[{1,2}]"), [1.0, 2.0])

    def test_arithmetic_precedence_and_explicit_float64_scope(self):
        for text, value in [
            ("2+3*4", 14),
            ("-2^2", -4),
            ("(-2)^2", 4),
            ("2^3^2", 512),
            ("exp(log(2))", 2),
            ("Sqrt[4]+1/2", 2.5),
            ("N[1/3,16]", 1 / 3),
        ]:
            with self.subTest(text=text):
                self.assertAlmostEqual(decode(text), value)

    def test_reject_code_and_non_numeric_language(self):
        for text in [
            '__import__("os")',
            'open("x")',
            "x+1",
            "a.b",
            "(1).__class__",
            "[x for x in [1]]",
            "1;2",
            "1=2",
            "True",
            "NaN",
            "Infinity",
            "1 hour",
            "N[1,50]",
            "N[N[1],16]",
            "Log[2,10]",
            "{1,{2}}",
            "[]",
            "{}",
            "1,",
            "{1,2} garbage",
            "2**3",
            "Sin[1]",
            '"1"',
        ]:
            with self.subTest(text=text), self.assertRaises(NumericExpressionError):
                decode(text)

    def test_reject_nonfinite_domains_and_bound_resources(self):
        for text in [
            "1/0",
            "0^-1",
            "(-1)^0.5",
            "Log[0]",
            "Sqrt[-1]",
            "Exp[1000]",
            "Exp[-1000]",
            "1e-300*1e-300",
            "1e-300/1e300",
            "1e-300^100",
            "1e301",
            "1e300*1e300",
            "10^101",
            "-" * 200 + "1",
            "(" * 100 + "1" + ")" * 100,
            "{" + ",".join(["1"] * 101) + "}",
            "+".join(["1"] * 600),
            "1" * 65,
            " ",
        ]:
            with (
                self.subTest(text=text[:50]),
                self.assertRaises(NumericExpressionError),
            ):
                decode(text)

    def test_workflow_expression_requires_bounded_closed_text(self):
        expression = lambda v: {
            "operation": "closed_numeric_expression",
            "args": [{"value": v}],
        }
        self.assertEqual(operand(expression("1/2"), {}), 0.5)
        for value in [None, 1, [], {}, "Log[-1]"]:
            with self.subTest(value=value), self.assertRaises(MissingEvidence):
                operand(expression(value), {})
        with self.assertRaises(MissingEvidence):
            operand({"operation": "closed_numeric_expression", "args": []}, {})


if __name__ == "__main__":
    unittest.main()
