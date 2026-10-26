"""Independent exact vertices and certificate checks for the LP primitive."""

from fractions import Fraction as F
import itertools
import math
import json
from pathlib import Path
import unittest
from tools.implementations.machine_learning.linear_program import solve_linear_program


class LinearProgramTests(unittest.TestCase):
    def test_near_boundary_diagnostics_are_plain_finite_json(self):
        fixture = Path(__file__).parents[1] / 'fixtures/linear_program_near_boundary.json'
        result = solve_linear_program(**json.loads(fixture.read_text())['arguments'])
        self.assertEqual(result['status'], 'optimal')
        self.assertAlmostEqual(result['objective_value'], 1.8892294051167, places=10)

        def plain(value):
            if isinstance(value, dict):
                self.assertTrue(all(type(key) is str for key in value))
                for child in value.values():
                    plain(child)
            elif isinstance(value, list):
                for child in value:
                    plain(child)
            else:
                self.assertIn(type(value), (int, float, str, bool, type(None)))
                if type(value) is float:
                    self.assertTrue(math.isfinite(value))

        plain(result)
        json.dumps(result, allow_nan=False)

    def certificate(self, result, c, bounds, au=(), bu=(), ae=(), be=()):
        self.assertEqual(result["status"], "optimal")
        self.assertIsNone(result["validation_error"])
        x = list(map(F.from_float, result["solution"]))
        # Verify the actual float64 model received by the worker; decimal
        # spellings are not exact binary coefficients at extreme scales.
        q = lambda v: F.from_float(float(v))
        d = result["diagnostics"]
        yu = list(map(F.from_float, d["inequality_marginals"]))
        ye = list(map(F.from_float, d["equality_marginals"]))
        yl = list(map(F.from_float, d["lower_bound_marginals"]))
        yh = list(map(F.from_float, d["upper_bound_marginals"]))
        value = sum(q(a) * v for a, v in zip(c, x))
        self.assertAlmostEqual(float(value), result["objective_value"], places=11)
        dual = sum(q(b) * v for b, v in zip(bu, yu)) + sum(
            q(b) * v for b, v in zip(be, ye)
        )
        for i, (lower, upper) in enumerate(bounds):
            if lower is not None:
                self.assertGreaterEqual(float(x[i] - q(lower)), -1e-10)
                dual += q(lower) * yl[i]
            else:
                self.assertAlmostEqual(float(yl[i]), 0, places=11)
            if upper is not None:
                self.assertGreaterEqual(float(q(upper) - x[i]), -1e-10)
                dual += q(upper) * yh[i]
            else:
                self.assertAlmostEqual(float(yh[i]), 0, places=11)
        for row, b in zip(au, bu):
            self.assertLessEqual(
                float(sum(q(a) * v for a, v in zip(row, x)) - q(b)), 1e-10
            )
        for row, b in zip(ae, be):
            self.assertAlmostEqual(
                float(sum(q(a) * v for a, v in zip(row, x)) - q(b)), 0, places=10
            )
        for j in range(len(c)):
            stationary = (
                q(c[j])
                - sum(q(row[j]) * v for row, v in zip(au, yu))
                - sum(q(row[j]) * v for row, v in zip(ae, ye))
                - yl[j]
                - yh[j]
            )
            magnitude = (
                abs(q(c[j]))
                + sum(abs(q(row[j]) * v) for row, v in zip(au, yu))
                + sum(abs(q(row[j]) * v) for row, v in zip(ae, ye))
                + abs(yl[j])
                + abs(yh[j])
            )
            self.assertLessEqual(abs(stationary), F(64, 2**52) * magnitude)
        self.assertAlmostEqual(float(dual), float(value), places=10)
        sign = 1 if result["direction"] == "min" else -1
        self.assertTrue(all(float(v) * sign <= 1e-10 for v in yu + yh))
        self.assertTrue(all(float(v) * sign >= -1e-10 for v in yl))
        self.assertTrue(math.isfinite(result["objective_value"]))

    def test_free_signed_variables_and_maximum_marginals(self):
        au = [[-3, 1], [1, 2]]
        bu = [6, 4]
        bounds = [[None, None], [-3, None]]
        for c, direction, optimum in [([-1, 4], "min", -22), ([1, -4], "max", 22)]:
            r = solve_linear_program(c, bounds, au, bu, direction=direction)
            self.certificate(r, c, bounds, au, bu)
            self.assertAlmostEqual(r["objective_value"], optimum, places=11)
            self.assertEqual(r["solution"], [10, -3])

    def test_equalities_redundancy_and_direction(self):
        ae = [[1, 1, 1], [2, 2, 2]]
        be = [1, 2]
        bounds = [[0, 1]] * 3
        c = [1, 2, 3]
        for direction, expected in [("min", 1), ("max", 3)]:
            r = solve_linear_program(
                c, bounds, equality_matrix=ae, equality_rhs=be, direction=direction
            )
            self.certificate(r, c, bounds, ae=ae, be=be)
            self.assertAlmostEqual(r["objective_value"], expected, places=11)

    def test_exact_vertex_enumeration_for_bounded_models(self):
        au = [[1, 1], [-1, 2]]
        bu = [1.3, 0.8]
        bounds = [[0, 1], [0, 1]]
        lines = [([F(str(v)) for v in row], F(str(b))) for row, b in zip(au, bu)]
        lines += [
            ([F(1), F(0)], F(0)),
            ([F(1), F(0)], F(1)),
            ([F(0), F(1)], F(0)),
            ([F(0), F(1)], F(1)),
        ]
        vertices = []
        for (a, b), (e, f) in itertools.combinations(lines, 2):
            det = a[0] * e[1] - a[1] * e[0]
            if det == 0:
                continue
            x = [(b * e[1] - a[1] * f) / det, (a[0] * f - b * e[0]) / det]
            if all(0 <= v <= 1 for v in x) and all(
                sum(u * v for u, v in zip(row, x)) <= bound for row, bound in lines[:2]
            ):
                vertices.append(x)
        self.assertGreater(len(vertices), 2)
        for c in [[-3, 2], [2, -1], [1, 1], [-2, -3], [0, 1], [1, 0]]:
            objectives = [sum(F(a) * v for a, v in zip(c, x)) for x in vertices]
            for direction, target in [
                ("min", min(objectives)),
                ("max", max(objectives)),
            ]:
                r = solve_linear_program(c, bounds, au, bu, direction=direction)
                self.certificate(r, c, bounds, au, bu)
                self.assertAlmostEqual(r["objective_value"], float(target), places=10)

    def test_infeasibility_not_unbounded_presolve_shortcut(self):
        r = solve_linear_program(
            [-1], [[None, None]], equality_matrix=[[0]], equality_rhs=[1]
        )
        self.assertEqual(r["status"], "infeasible")
        for key in ["solution", "objective_value", "diagnostics"]:
            self.assertIsNone(r[key])

    def test_unbounded_does_not_supply_numeric_optimum(self):
        r = solve_linear_program([-1], [[0, None]])
        self.assertEqual(r["status"], "unbounded")
        self.assertIsNone(r["solution"])
        self.assertIsNone(r["objective_value"])

    def test_fixed_and_zero_objective_variables(self):
        for c, bounds in [([1], [[-2, -2]]), ([0], [[None, None]])]:
            r = solve_linear_program(c, bounds, [], [])
            self.certificate(r, c, bounds)
        self.assertEqual(solve_linear_program([1], [[-2, -2]])["objective_value"], -2)

    def test_invalid_shapes_domains_and_resource_limits(self):
        bad = [
            dict(objective=[], bounds=[]),
            dict(objective=[1], bounds=None),
            dict(objective=[True], bounds=[[0, 1]]),
            dict(objective=["1"], bounds=[[0, 1]]),
            dict(objective=[None], bounds=[[0, 1]]),
            dict(objective=[float("nan")], bounds=[[0, 1]]),
            dict(objective=[float("inf")], bounds=[[0, 1]]),
            dict(objective=[10**10000], bounds=[[0, 1]]),
            dict(objective=[1], bounds=[[2, 1]]),
            dict(objective=[1], bounds=[[False, 1]]),
            dict(objective=[1], bounds=[[0, float("inf")]]),
            dict(objective=[1], bounds=[[0]]),
            dict(objective=[1], bounds=[[0, 1]], inequality_matrix=[[1]]),
            dict(
                objective=[1],
                bounds=[[0, 1]],
                equality_matrix=[[1, 2]],
                equality_rhs=[1],
            ),
            dict(objective=[1], bounds=[[0, 1]], direction="minimum"),
            dict(
                objective=[1],
                bounds=[[0, 1]],
                inequality_matrix=[[1]] * 2001,
                inequality_rhs=[1] * 2001,
            ),
            dict(
                objective=[1] * 500,
                bounds=[[0, 1]] * 500,
                inequality_matrix=[[1] * 500] * 201,
                inequality_rhs=[1] * 201,
            ),
        ]
        for i, args in enumerate(bad):
            with self.subTest(case=i), self.assertRaises(ValueError):
                solve_linear_program(**args)

    def test_positive_model_scaling_preserves_optima_and_requested_marginals(self):
        for scale in (1e-300, 1e-12, 1.0, 1e12, 1e300):
            result = solve_linear_program([-scale], [[0, 1]])
            self.assertEqual(result["status"], "optimal")
            self.assertAlmostEqual(result["solution"][0], 1, places=12)
            self.assertAlmostEqual(result["objective_value"] / scale, -1, places=12)
            self.assertAlmostEqual(
                result["diagnostics"]["upper_bound_marginals"][0] / scale, -1, places=12
            )
            result = solve_linear_program(
                [-1],
                [[0, 1]],
                inequality_matrix=[[scale]],
                inequality_rhs=[scale * 0.5],
            )
            self.assertEqual(result["status"], "optimal")
            self.assertAlmostEqual(result["solution"][0], 0.5, places=12)
            self.assertAlmostEqual(result["objective_value"], -0.5, places=12)
            self.assertAlmostEqual(
                result["diagnostics"]["inequality_marginals"][0] * scale, -1, places=12
            )
        for args in [
            dict(objective=[1, 1e-12], bounds=[[0, 1]] * 2),
            dict(objective=[1], bounds=[[0, 1e30]]),
            dict(
                objective=[1, 1],
                bounds=[[0, 1]] * 2,
                inequality_matrix=[[1, 1e-12]],
                inequality_rhs=[1],
            ),
            dict(objective=[1e300, 1e-300], bounds=[[0, 1]] * 2),
            dict(
                objective=[1, 1],
                bounds=[[0, 1]] * 2,
                inequality_matrix=[[1e300, 1e-300]],
                inequality_rhs=[1e300],
            ),
            dict(
                objective=[1],
                bounds=[[0, 1]],
                inequality_matrix=[[1e300]],
                inequality_rhs=[1e-300],
            ),
        ]:
            with self.assertRaisesRegex(ValueError, "rescale"):
                solve_linear_program(**args)


if __name__ == "__main__":
    unittest.main()
