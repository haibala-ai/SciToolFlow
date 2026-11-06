"""Identical scientific rules apply to independent completion and answer metrics."""
from copy import deepcopy
import pytest
from evaluation.suites.mini import three_metrics
from evaluation.authoring.special100.evaluate import three_metrics as special_metrics
from evaluation.workflow import score_workflow
from tests.support.workflows import fixture, run


@pytest.mark.parametrize('metric', [three_metrics, special_metrics])
@pytest.mark.parametrize('completed', [True, False])
@pytest.mark.parametrize('correct', [True, False])
def test_answer_is_independent_of_execution_and_unrelated_format_diagnostics(metric, completed, correct):
    ref = fixture(); trusted = run(); actor = deepcopy(trusted)
    # Deliberately impossible schema: format remains a diagnostic. Scientific
    # predicates and the reviewed actual observations determine correctness.
    task = {'id': ref['id'], 'answer_schema': {'type': 'string'}}
    if not correct:
        actor['final_answer'] = None
    actor.update(completed=completed, status='completed' if completed else 'failed',
                 failure_reason=None if completed else 'TransportError', calls=[])
    registry = {'tools': {}, 'aliases': {}}
    result = metric(task, ref, actor, trusted, registry)
    assert result['runtime_completed'] is completed
    assert result['answer_correct'] is correct
    assert result['tool_plan_correct'] is False
    assert result['answer_schema_valid'] is False


@pytest.mark.parametrize('answer', [None, {}, [], '', 0, False])
def test_completion_never_requires_a_nonempty_or_correct_answer(answer):
    actor = run(); actor['final_answer'] = answer
    assert score_workflow(fixture(), actor)['runtime_pass'] is True
