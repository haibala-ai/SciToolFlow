"""Equivalent routes provide observations, never an answer or literal fallback."""
import pytest
from evaluation.workflow.expressions import operand
from evaluation.workflow.values import MissingEvidence
from evaluation.workflow import validate_workflow
from tests.evaluation.test_workflow_capability_groups import fixture


def expression():
    return {'operation':'observed_route_value','args':[{'source':'node','node':n,'path':'/x'}for n in ['a','b']]}


def test_absent_alternative_is_ignored_but_requires_one_executed_route():
    expr=expression()
    assert operand(expr,{'nodes':{'a':{'output':{'x':[1,2]}}}})==[1,2]
    assert operand(expr,{'nodes':{'b':{'output':{'x':[1,2]}}}})==[1,2]
    with pytest.raises(MissingEvidence):operand(expr,{'nodes':{}})


def test_present_malformed_or_contradictory_receipt_is_not_silently_discarded():
    expr=expression()
    for other in [{},{'x':[9,2]},{'x':[float('nan'),2]}]:
        with pytest.raises(MissingEvidence):
            operand(expr,{'nodes':{'a':{'output':{'x':[1,2]}},'b':{'output':other}}})
    assert operand(expr,{'nodes':{'a':{'output':{'x':[1,2]}},'b':{'output':{'x':[1+1e-10,2]}}}})==[1,2]


def test_nested_equivalent_routes_do_not_require_unexecuted_inner_alternatives():
    inner=expression()
    expr={'operation':'observed_route_value','args':[inner,{'source':'node','node':'program','path':'/x'}]}
    assert operand(expr,{'nodes':{'a':{'output':{'x':[1,2]}}}})==[1,2]
    assert operand(expr,{'nodes':{'program':{'output':{'x':[1,2]}}}})==[1,2]
    with pytest.raises(MissingEvidence):
        operand(expr,{'nodes':{'a':{'output':{'x':[1,2]}},'program':{'output':{'x':[3,4]}}}})


@pytest.mark.parametrize('fallback',[{'value':42},{'source':'inputs','path':'/x'},{'source':'answer','path':'/x'}])
def test_literal_input_and_answer_fallbacks_rejected_in_schema_and_runtime(fallback):
    expr={'operation':'observed_route_value','args':[{'source':'node','node':'source','path':'/known'},fallback]}
    ref=fixture();ref['evaluation']['outcomes'][0]['right']=expr
    with pytest.raises(ValueError):validate_workflow(ref['evaluation'])
    with pytest.raises(MissingEvidence):operand(expr,{'nodes':{},'inputs':{'x':42},'answer':{'x':42}})
