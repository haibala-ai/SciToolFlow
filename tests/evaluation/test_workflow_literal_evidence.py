import pytest
from evaluation.workflow.literal_evidence import (
    decode_literal,
    literal_assignment_values,
    LiteralEvidenceError,
)
from evaluation.workflow import MissingEvidence, operand


def test_literal_lines_compare_numerical_receipts_without_executing_them():
    from evaluation.workflow.expressions import predicate

    receipt = {"operation": "python_literal_lines", "args": [{"value": "{'x': 1.000000001}\n\n[2, False, None]\n"}]}
    assert predicate({"left": receipt, "op": "eq", "right": {"value": [{"x": 1.0}, [2, False, None]]}, "atol": 1e-8}, {})
    assert not predicate({"left": receipt, "op": "eq", "right": {"value": [{"x": 1.0}, [2, 0, None]]}, "atol": 1e-8}, {})


@pytest.mark.parametrize("receipt", ["", "\n", "1\n__import__('os').getcwd()", "{'x': 1, 'x': 2}", "[1e309]", "1\n" * 1001, " " * 200001])
def test_literal_lines_reject_incomplete_unbounded_or_executable_receipts(receipt):
    with pytest.raises(MissingEvidence):
        operand({"operation": "python_literal_lines", "args": [{"value": receipt}]}, {})


def test_literal_receipt_preserves_finite_json_types_and_escaped_pointer():
    text = "{'a/b': {'~x': [1, -2.5, True, None]}, 'mass': 3.0}"
    assert decode_literal(text)["a/b"]["~x"] == [1, -2.5, True, None]
    assert (
        operand(
            {
                "operation": "python_literal_value",
                "args": [{"value": text}, {"value": "/a~1b/~0x/1"}],
            },
            {},
        )
        == -2.5
    )


@pytest.mark.parametrize(
    "text",
    [
        "{'a':1,'a':2}",
        "{1:2}",
        "{'a':float('nan')}",
        "{'a':nan}",
        "{'a':1e309}",
        "__import__('os').getcwd()",
        "(1,2)",
        "{1,2}",
        "{'a':1}; print(2)",
        "{'a': [x for x in [1]]}",
        "{**{'a':1}}",
        "1+2",
        'b"abc"',
        "1j",
        "",
        "1" * 10000,
        "[" * 100 + "0" + "]" * 100,
    ],
)
def test_code_names_nonfinite_duplicate_or_non_json_data_is_rejected(text):
    with pytest.raises(LiteralEvidenceError):
        decode_literal(text)


def test_assignment_extraction_is_variable_name_independent_and_ignores_expressions():
    code = "source=[[1,2],[3,4]]\nweights=[5,-6]\nanswer=sum(weights)\nprint(answer)"
    assert literal_assignment_values(code) == [[[1, 2], [3, 4]], [5, -6]]
    assert literal_assignment_values(
        code.replace("source", "coordinates")
    ) == literal_assignment_values(code)


@pytest.mark.parametrize(
    "code",
    [
        "x=[1,2]\nx=[3,4]",
        "x=[1,2]\nx[0]=9",
        "x=[1,2]\nx.append(9)",
        "x=[1,2]\ndel x[0]",
        "x=[1,2]\nx+=[3]",
        "x=[1,2]\nfor x in [3]:\n print(x)",
        "x=[1,2]\nif True:\n x=[3,4]",
    ],
)
def test_direct_reassignment_or_mutation_is_not_a_source_binding(code):
    assert literal_assignment_values(code) == []


def test_no_alias_or_algorithm_proof_is_inferred_from_source_presence():
    # The consumer still has to check all scientific outputs against the source.
    assert literal_assignment_values("x=[1,2]\ny=x\ny[0]=3") == [[1, 2]]


def test_source_tuples_and_unshadowed_numpy_wrappers_are_data_only():
    assert literal_assignment_values("plans=[('early',7,12),('late',9,13)]") == [
        [["early", 7, 12], ["late", 9, 13]]
    ]
    for declaration, alias in [
        ("import numpy as np", "np"),
        ("import numpy as numeric", "numeric"),
        ("import numpy", "numpy"),
    ]:
        code = declaration + "\nx=" + alias + ".array([(1,2),(3,4)], dtype=float)"
        assert literal_assignment_values(code) == [[[1, 2], [3, 4]]]


@pytest.mark.parametrize(
    "code",
    [
        "x=np.array([1,2])",
        "import numpy as np\nnp=other\nx=np.array([1,2])",
        "import numpy as np\nimport other as np\nx=np.array([1,2])",
        "import numpy as np\nnp.array=other\nx=np.array([1,2])",
        "import numpy as np\nx=np.array([1,2], dtype=object)",
        "import numpy as np\nx=np.array([1,2], ndmin=2)",
        "import numpy as np\nx=np.array([1,2], **opts)",
        "import numpy as np\nx=np.array(other())",
        "import numpy as np\nx=np.asarray([1,2])",
        "import numpy as np\nfloat=other\nx=np.array([1,2],dtype=float)",
        "import numpy as np\ndef f(np):\n return np\nx=np.array([1,2])",
    ],
)
def test_source_array_wrappers_reject_unbound_or_modified_names(code):
    # Function arguments do not reassign the top-level module binding.
    expected = [[1, 2]] if "def f(np)" in code else []
    assert literal_assignment_values(code) == expected


@pytest.mark.parametrize("pointer", ["a", "/bad~2x", "/~", None, "/" + ("x" * 1001)])
def test_receipt_pointer_fails_closed(pointer):
    with pytest.raises(MissingEvidence):
        operand(
            {
                "operation": "python_literal_value",
                "args": [{"value": "{'a':1}"}, {"value": pointer}],
            },
            {},
        )


def test_labelled_receipts_tolerate_roundoff_and_preserve_field_meanings():
    from evaluation.workflow.expressions import predicate
    from evaluation.workflow.literal_evidence import numeric_receipt_tokens

    target = numeric_receipt_tokens('g4/g1 ratio 10.0 pH [9.07, 9.16]\n')
    def compare(text):
        return predicate({'left': {'operation': 'numeric_receipt_tokens', 'args': [{'value': text}]}, 'op': 'eq', 'right': {'value': target}, 'atol': 1e-7, 'rtol': 1e-7}, {})
    assert compare('g4/g1 ratio 10.000000001 pH [9.07, 9.16]\n')
    assert not compare('g1/g4 ratio 10.0 pH [9.07, 9.16]\n')
    assert not compare('g4/g1 ratio 1000.0 pH [9.07, 9.16]\n')
    assert not compare('g4/g1 ratio 10.0 pH [9.16, 9.07]\n')
    assert not compare('g4/g1 ratio 10.0 pH [9.07, 9.16, 10.0]\n')


@pytest.mark.parametrize('text', ['', 'no numeric observations', 'x nan', 'x -Infinity', 'x 1e309', 'x ' + '1' * 257, '1 ' * 10001, 'x' * 200001])
def test_numeric_receipts_reject_nonfinite_and_excessive_evidence(text):
    with pytest.raises(MissingEvidence):
        operand({'operation': 'numeric_receipt_tokens', 'args': [{'value': text}]}, {})


def test_numeric_receipt_text_is_never_executed():
    from evaluation.workflow.literal_evidence import numeric_receipt_tokens
    decoded = numeric_receipt_tokens("__import__('missing_module').call(2)\n")
    assert decoded == {'labels': ["__import__('missing_module').call(", ')\n'], 'numbers': [2.0]}
