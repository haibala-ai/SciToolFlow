"""The composite is averaged per task and cannot hide missing or pending work."""
from evaluation.suites.mini import summarize
from evaluation.workflow.efficiency import orchestration_score


def row(c,e,**kw):
    return dict(runtime_completed=True,tool_plan_correct=c==1,answer_correct=True,
                orchestration_credit=c,selection_efficiency=e,
                tool_orchestration_score=orchestration_score(c,e),**kw)


def test_composite_is_macro_average_not_harmonic_of_macro_components():
    scored=summarize([row(1,.25),row(.25,1)])
    assert scored['tool_planning_accuracy']==(orchestration_score(1,.25)+orchestration_score(.25,1))/2
    assert scored['tool_planning_accuracy']!=orchestration_score(.625,.625)
    assert scored['strict_tool_planning_accuracy']==.5


def test_missing_invalid_and_failed_tasks_remain_in_denominator():
    scored=summarize([row(1,1),dict(runtime_completed=False,tool_plan_correct=False,answer_correct=False)])
    assert scored['tool_planning_accuracy']==.5
    assert scored['runtime_completion_rate']==.5
    assert scored['answer_accuracy']==.5


def test_pending_evidence_is_diagnostic_not_a_reportable_final_score():
    scored=summarize([row(1,1),row(.5,1,planning_reportable=False)])
    assert scored['tool_planning_accuracy'] is None
    assert scored['tool_planning_reportable'] is False
    assert scored['observed_mean_tool_orchestration_score']>0
