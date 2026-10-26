"""Mathematically valid nonunique witnesses pass; forged scalar-only outputs fail."""

import copy
import numpy as np
from evaluation.workflow.witnesses import witness_certificate, add_witness_rules
from evaluation.workflow.expressions import operand
from tools.implementations.machine_learning.linear_program import solve_linear_program


def test_eigenbasis_signs_and_degenerate_rotations():
    a = {"values": [[2.0, 0, 0], [0, 2, 0], [0, 0, 5]]}
    q = np.array([[0.6, -0.8, 0], [0.8, 0.6, 0], [0, 0, -1.0]])
    o = {"eigenvalues": [2.0, 2.0, 5.0], "eigenvectors": q.tolist()}
    assert witness_certificate("SymmetricEigenDecomposition", a, o)
    bad = copy.deepcopy(o)
    bad["eigenvectors"][0][0] += 0.2
    assert not witness_certificate("SymmetricEigenDecomposition", a, bad)
    bad = copy.deepcopy(o)
    bad["eigenvectors"] = [[0.0] * 3] * 3
    assert not witness_certificate("SymmetricEigenDecomposition", a, bad)
    bad = copy.deepcopy(o)
    bad["eigenvalues"] = [2.0, 5.0, 2.0]
    assert not witness_certificate("SymmetricEigenDecomposition", a, bad)


def test_svd_equivalent_sign_and_reconstruction():
    a = {"values": [[1.0, 2.0, 0], [0, 3.0, 4.0]]}
    u, s, vt = np.linalg.svd(a["values"], full_matrices=False)
    u[:, 0] *= -1
    vt[0, :] *= -1
    o = {
        "u": u.tolist(),
        "singular_values": s.tolist(),
        "vt": vt.tolist(),
        "reconstruction_error": float(np.linalg.norm((u * s) @ vt - a["values"])),
    }
    assert witness_certificate("MatrixSVD", a, o) is True
    bad = copy.deepcopy(o)
    bad["u"][0][0] += 0.1
    assert not witness_certificate("MatrixSVD", a, bad)
    bad = copy.deepcopy(o)
    bad["vt"] = []
    assert not witness_certificate("MatrixSVD", a, bad)


def test_nonunique_lp_optima_and_real_original_constraints():
    a = dict(
        objective=[1.0, 1.0],
        bounds=[[0, 1], [0, 1]],
        equality_matrix=[[1.0, 1.0]],
        equality_rhs=[1.0],
        direction="max",
    )
    o = solve_linear_program(**a)
    assert witness_certificate("SolveLinearProgram", a, o) is True
    # Every point on the optimal face is feasible; the same zero equality slack
    # and valid equality dual can certify either endpoint or an interior point.
    alt = copy.deepcopy(o)
    alt["solution"] = [0.4, 0.6]
    alt["diagnostics"]["lower_bound_slack"] = [0.4, 0.6]
    alt["diagnostics"]["upper_bound_slack"] = [0.6, 0.4]
    assert witness_certificate("SolveLinearProgram", a, alt)
    bad = copy.deepcopy(o)
    bad["solution"] = [2.0, -1.0]
    assert not witness_certificate("SolveLinearProgram", a, bad)
    bad = copy.deepcopy(o)
    bad["solution"] = [0.0, 0.0]
    assert not witness_certificate("SolveLinearProgram", a, bad)
    bad = copy.deepcopy(o)
    bad["diagnostics"]["equality_marginals"] = [0.0]
    assert not witness_certificate("SolveLinearProgram", a, bad)


def test_nonoptimal_is_not_a_fabricated_numeric_solution():
    a = dict(
        objective=[1.0], bounds=[[0, 1]], equality_matrix=[[1.0]], equality_rhs=[2.0]
    )
    o = solve_linear_program(**a)
    assert o["status"] == "infeasible" and witness_certificate(
        "SolveLinearProgram", a, o
    )
    bad = copy.deepcopy(o)
    bad["solution"] = [0.0]
    assert not witness_certificate("SolveLinearProgram", a, bad)


def test_expression_and_idempotent_rule():
    a = {"values": [[1.0, 0], [0, 1.0]]}
    o = {"eigenvalues": [1.0, 1.0], "eigenvectors": [[1.0, 0], [0, 1.0]]}
    spec = {
        "nodes": [
            {
                "alternatives": [
                    {"tools": ["SymmetricEigenDecomposition"], "output_rules": []}
                ]
            }
        ]
    }
    add_witness_rules(spec)
    add_witness_rules(spec)
    rules = spec["nodes"][0]["alternatives"][0]["output_rules"]
    assert len(rules) == 1
    assert operand(rules[0]["left"], {"call_arguments": a, "call_output": o}) is True
    o["eigenvectors"][0][0] = False
    assert operand(rules[0]["left"], {"call_arguments": a, "call_output": o}) is False
