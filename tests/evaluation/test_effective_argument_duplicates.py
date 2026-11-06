"""Syntactic parameter differences cannot manufacture additional scientific work.

These are offline grading controls. No tools or model are executed here.
"""
from copy import deepcopy
import pytest
from evaluation.workflow import score_workflow
from evaluation.workflow.matching import _execution_signature
from evaluation.workflow.program_identity import reviewed_program_identity
from tests.evaluation.test_mini_orchestration_design import reference, rule
from tests.evaluation.test_workflow_capability_groups import prediction
from tests.support.workflows import call


def scenario(first, second, *, outputs=None):
    ref = reference()
    ref['evaluation']['efficiency']['useful_work_rules'] = [rule(max_calls=2)]
    pred = prediction('difference')
    outputs = outputs or [{'residual': 0}, {'residual': 0}]
    pred['calls'].extend([
        call('diagnostic-a', 'Diagnostic', {'target': 'same-source', **first}, outputs[0]),
        call('diagnostic-b', 'Diagnostic', {'target': 'same-source', **second}, outputs[1]),
    ])
    contracts = {'Diagnostic': {'parameters': [
        {'name': 'mode', 'required': False, 'default_value': 'standard'},
    ]}}
    return ref, pred, contracts


def grade(first, second, **kwargs):
    ref, pred, contracts = scenario(first, second, **kwargs)
    before = deepcopy(pred)
    scored = score_workflow(ref, pred, tool_contracts=contracts)
    assert pred == before, 'Identity normalization must not rewrite authenticated evidence'
    return scored


def test_omitted_and_explicit_trusted_default_are_the_same_executed_work():
    scored = grade({}, {'mode': 'standard'})
    assert scored['orchestration_credit'] == 1
    assert scored['selection_efficiency'] == .75
    assert scored['matched_scientific_calls'] == 3
    assert scored['redundant_calls'] == 1


def test_explicit_null_is_not_replaced_with_a_published_default():
    scored = grade({}, {'mode': None})
    assert scored['selection_efficiency'] == 1
    assert scored['redundant_calls'] == 0


@pytest.mark.parametrize('left,right', [(1, 1.0), (0, -0.0), ([1, [2.0]], [1.0, [2]])])
def test_equal_json_numbers_have_one_work_identity(left, right):
    scored = grade({'values': left}, {'values': right})
    assert scored['selection_efficiency'] == .75
    assert scored['redundant_calls'] == 1


@pytest.mark.parametrize('left,right', [
    (True, 1), (False, 0), (1, 2), ('1', 1),
    (9007199254740993, float(9007199254740993)),
])
def test_boolean_string_and_actual_numeric_changes_remain_distinct(left, right):
    scored = grade({'values': left}, {'values': right})
    assert scored['selection_efficiency'] == 1
    assert scored['redundant_calls'] == 0


def test_equivalent_numeric_feedback_is_not_a_second_measurement():
    scored = grade({}, {}, outputs=[{'residual': 0}, {'residual': 0.0}])
    assert scored['selection_efficiency'] == .75
    assert scored['redundant_calls'] == 1


def test_actual_changed_feedback_is_preserved_as_a_distinct_observation():
    ref, pred, contracts = scenario({}, {})
    ref['evaluation']['efficiency']['useful_work_rules'][0]['output_rules'] = [
        {'path': '/residual', 'op': 'finite'}
    ]
    pred['calls'][-1]['output']['residual'] = .1
    scored = score_workflow(ref, pred, tool_contracts=contracts)
    assert scored['selection_efficiency'] == 1
    assert scored['redundant_calls'] == 0


def test_caller_cannot_spoof_effective_arguments_to_gain_scientific_credit():
    ref, pred, contracts = scenario({}, {})
    pred['calls'] = pred['calls'][:-1]
    pred['calls'][-1]['arguments']['target'] = 'wrong-source'
    pred['calls'][-1]['_effective_arguments'] = {'target': 'same-source', 'mode': 'standard'}
    scored = score_workflow(ref, pred, tool_contracts=contracts)
    assert scored['selection_efficiency'] == 2/3
    assert scored['matched_scientific_calls'] == 2


def numerical_receipt(identifier, code, stdout='1\n'):
    """An explicitly synthetic receipt for identity tests, not actor evidence."""
    return call(identifier, 'ExecuteNumericalCode', {'code': code}, {
        'status': 'success', 'exit_code': 0, 'execution_status': 'completed',
        'stdout': stdout, 'stderr': '', 'code': code, 'plots': [],
        'artifact_directory': '/test/worker-'+identifier,
    })


def test_code_layout_and_comments_do_not_create_additional_scientific_work():
    original = 'value = 1\nprint(value)\n'
    layout = '# Only whitespace and a comment change.\nvalue=1\nprint( value )\n'
    first = numerical_receipt('first', original)
    second = numerical_receipt('second', layout)
    before = deepcopy([first, second])
    assert _execution_signature(first) == _execution_signature(second)
    assert [first, second] == before
    ref = reference()
    ref['evaluation']['efficiency']['useful_work_rules'] = [{
        'id': 'audited-program', 'tools': ['ExecuteNumericalCode'],
        'max_calls': 2, 'depends_on': ['source'],
        'input_rules': [{'left': {'operation': 'reviewed_program_identity', 'args': [
            {'source': 'call_arguments', 'path': '/code'}]},
            'op': 'eq', 'value': reviewed_program_identity(original)}],
        'output_rules': [{'path': '/stdout', 'op': 'eq', 'value': '1\n'}],
    }]
    pred = prediction('difference'); pred['calls'].extend([first, second])
    result = score_workflow(ref, pred)
    assert result['orchestration_credit'] == 1
    assert result['selection_efficiency'] == .75
    assert result['redundant_calls'] == 1


@pytest.mark.parametrize('other,stdout', [
    ('value = 2\nprint(value)\n', '2\n'),
    ('value = 2\nprint(value-1)\n', '1\n'),
    ('value = 1\nprint("value")\n', 'value\n'),
])
def test_distinct_programs_and_string_literals_are_not_semantically_guessed(other, stdout):
    original = numerical_receipt('first', 'value = 1\nprint(value)\n')
    changed = numerical_receipt('second', other, stdout)
    assert _execution_signature(original) != _execution_signature(changed)


def test_invalid_programs_remain_distinct_and_do_not_crash_identity_matching():
    first = numerical_receipt('first', 'value = (')
    second = numerical_receipt('second', 'value = [')
    assert _execution_signature(first) != _execution_signature(second)
