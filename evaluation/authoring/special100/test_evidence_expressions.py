"""Reject missing/invalid evidence while supporting bounded data assembly."""
import math
import pytest
from evaluation.workflow.expressions import operand
from evaluation.workflow.values import MissingEvidence

def V(value):return {'value':value}
def E(operation,*args):return {'operation':operation,'args':list(args)}
MISSING={'source':'node','node':'unexecuted','path':'/value'}


def test_nested_json_assembly_preserves_correspondence_and_null():
    data=[[[0.,1.,2.]],{'residue_ids':['1','4'],'missing':None}]
    assert operand(E('json_array',*[V(v) for v in data]),{})==data


@pytest.mark.parametrize('value',[math.inf,math.nan,tuple([1]),{1:'bad'},'x'*2000001])
def test_json_assembly_rejects_non_json_or_excessive_values(value):
    with pytest.raises(MissingEvidence):operand(E('json_array',V(value)),{})


def test_json_assembly_structural_limits():
    nested=0
    for _ in range(17):nested=[nested]
    for value in [nested,[0]*20001]:
        with pytest.raises(MissingEvidence):operand(E('json_array',V(value)),{})


def test_observed_boolean_selection_is_lazy_but_selected_missing_still_fails():
    assert operand(E('select_if_boolean',V(True),V(3),MISSING),{})==3
    assert operand(E('select_if_boolean',V(False),MISSING,V(None)),{}) is None
    with pytest.raises(MissingEvidence):operand(E('select_if_boolean',V(True),MISSING,V(0)),{})


@pytest.mark.parametrize('value',[None,0,1,'true',[],{}])
def test_boolean_guard_never_coerces_missing_or_other_types(value):
    with pytest.raises(MissingEvidence):operand(E('select_if_boolean',V(value),V(1),V(0)),{})


def test_numeric_comparison_has_strict_finite_domain_and_inclusive_boundary():
    assert operand(E('finite_ge',V(.8),V(.8)),{}) is True
    assert operand(E('finite_ge',V(.799999999),V(.8)),{}) is False
    for value in [True,False,None,'1',math.inf,math.nan]:
        with pytest.raises(MissingEvidence):operand(E('finite_ge',V(value),V(.8)),{})


def test_crystal_amounts_preserve_occupancy_and_absent_elements():
    value={'structure':{'sites':[{'species':[{'element':'Na','occu':.45},{'element':'K','occu':.15}]},{'species':[{'element':'Cl','occu':1.}]}]}}
    assert operand(E('crystal_element_amount',V(value),V('Na')), {})==.45
    assert operand(E('crystal_element_amount',V(value),V('O')), {})==0.
    assert operand(E('crystal_element_amount',V({'element_amounts':{'Na':.45,'K':.15,'Cl':1.}}),V('Na')), {})==.45


@pytest.mark.parametrize('value',[{}, {'structure':{}}, {'structure':None}, {'structure':[]}, {'element_amounts':{'Na':True}}, {'element_amounts':{'Na':-1}}, {'structure':{'sites':[{'species':[{'element':'Na','occu':.7},{'element':'K','occu':.7}]}]}}, {'structure':{'sites':[{'species':[{'element':'Na','occu':.3},{'element':'Na','occu':.2}]}]}}])
def test_crystal_inventory_never_infers_or_repairs_invalid_observations(value):
    with pytest.raises(MissingEvidence):operand(E('crystal_element_amount',V(value),V('Na')), {})
