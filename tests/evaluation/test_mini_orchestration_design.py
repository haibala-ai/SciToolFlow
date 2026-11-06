"""C/E scientific-route invariance, bounded useful work and composite boundaries."""
from copy import deepcopy
import pytest
from evaluation.workflow import score_workflow, validate_workflow
from evaluation.workflow.efficiency import orchestration_score
from tests.evaluation.test_workflow_capability_groups import fixture, prediction
from tests.support.workflows import call


def reference():
    ref = fixture()
    ref['evaluation']['efficiency'] = {
        'single_route_efficiency': True, 'free_recovery_calls': 1,
        'free_disambiguation_calls': 1, 'useful_work_rules': [],
        'recovery_rules': [], 'disambiguation_rules': [],
    }
    return ref


def rule(kind='useful', **changes):
    r = {'id':kind, 'tools':['Diagnostic'], 'statuses':['success'], 'depends_on':['source'],
         'input_rules':[{'path':'/target','op':'eq','value':'same-source'}],
         'output_rules':[{'path':'/residual','op':'eq','value':0}], 'max_calls':1}
    r.update(changes)
    return r


def test_equivalent_route_granularity_does_not_change_completion_or_efficiency():
    for route in [('difference',), ('gas','liquid')]:
        scored = score_workflow(reference(), prediction(*route))
        assert scored['orchestration_credit'] == 1
        assert scored['selection_efficiency'] == 1
        assert scored['tool_orchestration_score'] == 1


def test_two_equivalent_routes_are_not_both_useful_just_because_their_args_differ():
    scored = score_workflow(reference(), prediction('difference','gas','liquid'))
    assert scored['orchestration_credit'] == 1
    assert scored['selection_efficiency'] == .5
    assert scored['selected_efficiency_routes']['correction'] == ['net']
    assert len(scored['redundant_semantic_observations']) == 2


@pytest.mark.parametrize('grouped',[False,True])
def test_optional_descendant_cannot_launder_an_unused_equivalent_route(grouped):
    ref=reference();ref['evaluation']['nodes'].append({'id':'phase-detail','required':False,
        'depends_on':['gas'],'alternatives':[{'tools':['Diagnostic'],
            'output_rules':[{'path':'/residual','op':'eq','value':0}]}]})
    if grouped:ref['evaluation']['capability_groups'].append({'id':'optional-phase-check','required':False,'alternatives':[['phase-detail']]})
    pred=prediction('difference','gas','liquid')
    pred['calls'].append(call('detail','Diagnostic',{}, {'residual':0}))
    result=score_workflow(ref,pred)
    assert result['orchestration_credit']==1
    assert result['selection_efficiency']==2/5
    check=ref['evaluation']['nodes'][-1]
    check.update(independent_check=True,check_reason='Task-required independent gas-phase cross-check with a bounded residual witness.')
    assert score_workflow(ref,pred)['selection_efficiency']==4/5


def test_unused_route_preparation_is_not_automatically_free_work():
    ref=reference();nodes=ref['evaluation']['nodes']
    nodes.append({'id':'gas-preparation','required':False,'depends_on':['source'],
        'alternatives':[{'tools':['Prepare'],'output_rules':[{'path':'/ready','op':'eq','value':True}]}]})
    next(n for n in nodes if n['id']=='gas')['depends_on']=['gas-preparation']
    pred=prediction('difference','gas','liquid')
    pred['calls'].insert(2,call('prep','Prepare',{}, {'ready':True}))
    assert score_workflow(ref,pred)['selection_efficiency']==2/5


def test_extra_work_certificate_is_bound_to_actual_source_and_numeric_check():
    ref = reference();ref['evaluation']['efficiency']['useful_work_rules'] = [rule()]
    pred = prediction('difference')
    pred['calls'].append(call('check','Diagnostic',{'target':'same-source'},{'residual':0}))
    good = score_workflow(ref,pred)
    assert good['selection_efficiency'] == 1 and good['orchestration_credit'] == 1
    for field,value in [('target','other-source'), ('residual',10)]:
        bad = deepcopy(pred)
        bad['calls'][-1]['arguments' if field=='target' else 'output'][field] = value
        scored = score_workflow(ref,bad)
        assert scored['selection_efficiency'] == 2/3
        assert scored['orchestration_credit'] == 1


def test_useful_work_count_is_bounded_and_exact_repeats_are_charged():
    ref = reference();ref['evaluation']['efficiency']['useful_work_rules'] = [rule()]
    pred = prediction('difference')
    pred['calls'] += [call('c1','Diagnostic',{'target':'same-source'},{'residual':0}),
                      call('c2','Diagnostic',{'target':'same-source'},{'residual':0})]
    scored = score_workflow(ref,pred)
    assert scored['selection_efficiency'] == 3/4
    assert scored['redundant_calls'] == 1


def test_recovery_is_transient_and_same_input_not_a_free_invalid_attempt():
    ref = reference()
    ref['evaluation']['efficiency']['recovery_rules'] = [rule('recovery',
        tools=['Integrate'],statuses=['error'],input_rules=[{'path':'/curve','op':'eq','value':'difference'}],
        output_rules=[{'path':'','op':'eq','value':None}])]
    pred = prediction('difference')
    failed = call('failed','Integrate',{'curve':'difference'},None,'error')
    failed['error_type'] = 'Timeout'
    pred['calls'].insert(1,failed)
    assert score_workflow(ref,pred)['selection_efficiency'] == 1
    for key,value in [('error_type','InvalidInput'), ('curve','unrelated')]:
        bad = deepcopy(pred)
        if key=='curve':bad['calls'][1]['arguments'][key]=value
        else:bad['calls'][1][key]=value
        assert score_workflow(ref,bad)['selection_efficiency'] == 2/3


def test_a_stipulated_corrupt_public_record_can_have_one_bounded_parse_check():
    ref=reference();policy=ref['evaluation']['efficiency']
    policy['disambiguation_rules']=[rule('public-parse-check',tools=['Parse'],statuses=['error'],
        error_types=['InvalidInput'],input_rules=[{'path':'/text','op':'eq','value':'corrupt-public-record'}],
        output_rules=[{'left':{'source':'call_error'},'op':'eq','value':'invalid public serialization'}])]
    pred=prediction('difference')
    failed=call('parse','Parse',{'text':'corrupt-public-record'},None,'error')
    failed.update(error_type='InvalidInput',error='invalid public serialization')
    pred['calls'].append(failed)
    assert score_workflow(ref,pred)['selection_efficiency']==1
    for change in [('arguments',{'text':'invented-invalid-record'}),('error','different failure'),('error_type','Timeout')]:
        wrong=deepcopy(pred);wrong['calls'][-1][change[0]]=change[1]
        assert score_workflow(ref,wrong)['selection_efficiency']==2/3
    repeat=deepcopy(failed);repeat['observation_id']='again';pred['calls'].append(repeat)
    assert score_workflow(ref,pred)['selection_efficiency']==2/3


def test_inactive_method_group_has_no_completion_penalty():
    ref = reference();spec=ref['evaluation']
    spec['branches']=[{'id':'eligible','when':{'left':{'source':'inputs','path':'/eligible'},'op':'eq','value':True}}]
    spec['capability_groups'][0]['branch']='eligible'
    ref['inputs']={'eligible':False}
    # The unconditional result here only certifies the source eligibility read.
    spec['outcomes']=[{'id':'read','left':{'source':'answer','path':'/correction'},'op':'eq','value':-10,'evidence_nodes':['source']}]
    pred=prediction();scored=score_workflow(ref,pred)
    assert scored['planning_pass'] and scored['orchestration_credit']==1
    assert scored['capability_groups'][0]['applicable'] is False
    ref['inputs']['eligible']=True
    scored=score_workflow(ref,pred)
    assert not scored['planning_pass'] and scored['orchestration_credit']==.5


def test_efficiency_cannot_read_the_submitted_answer_or_unbounded_tool_whitelist():
    for change in [{'max_calls':0}, {'input_rules':[]},
                   {'input_rules':[{'left':{'source':'answer','path':'/x'},'op':'eq','value':1}]}]:
        ref=reference();ref['evaluation']['efficiency']['useful_work_rules']=[rule(**change)]
        with pytest.raises(ValueError):validate_workflow(ref['evaluation'])


def test_composite_is_per_task_and_does_not_average_components_first():
    a,b=orchestration_score(1,.1),orchestration_score(.1,1)
    assert (a+b)/2 < orchestration_score(.55,.55)
    assert orchestration_score(1,.5)>.7
    assert orchestration_score(.5,1)<.7
    assert orchestration_score(0,1)==orchestration_score(1,0)==0


def test_reordering_independent_equivalent_routes_cannot_change_any_score():
    ref=reference()
    scores=[score_workflow(ref,prediction(*route))for route in
            [('difference','gas','liquid'),('gas','liquid','difference'),
             ('gas','difference','liquid'),('liquid','gas','difference')]]
    for field in ['orchestration_credit','selection_efficiency','tool_orchestration_score']:
        assert len({row[field]for row in scores})==1
    assert all(row['selected_efficiency_routes']['correction']==['net']for row in scores)


def test_unknown_eligibility_cannot_improve_C_by_removing_a_group_denominator():
    ref=reference();spec=ref['evaluation']
    spec['branches']=[{'id':'eligible','when':{'left':{'source':'node','node':'source','path':'/known'},'op':'eq','value':True}}]
    spec['capability_groups'][0]['branch']='eligible'
    present=score_workflow(ref,prediction())
    missing=prediction();missing['calls']=[]
    absent=score_workflow(ref,missing)
    assert present['orchestration_credit']==.5
    assert absent['orchestration_credit']==0
    assert not absent['planning_pass']


def test_overlapping_helper_rules_use_optimal_assignment_not_log_order():
    ref=reference()
    broad=rule('broad',input_rules=[{'path':'/target','op':'one_of','value':['A','B']}])
    narrow=rule('narrow',input_rules=[{'path':'/target','op':'eq','value':'A'}])
    ref['evaluation']['efficiency']['useful_work_rules']=[broad,narrow]
    for targets in [('A','B'),('B','A')]:
        pred=prediction('difference')
        pred['calls'] += [call('check'+t,'Diagnostic',{'target':t},{'residual':0})for t in targets]
        scored=score_workflow(ref,pred)
        assert scored['selection_efficiency']==1
        assert len(scored['supporting_work_observations'])==2


def test_useful_work_assignment_leaves_exploration_allowance_for_other_calls():
    ref=reference();policy=ref['evaluation']['efficiency']
    policy['useful_work_rules']=[rule('helper',input_rules=[{'path':'/target','op':'one_of','value':['A','B']}])]
    policy['disambiguation_rules']=[rule('explore',input_rules=[{'path':'/target','op':'eq','value':'A'}])]
    for targets in [('A','B'),('B','A')]:
        pred=prediction('difference')
        pred['calls'] += [call('check'+t,'Diagnostic',{'target':t},{'residual':0})for t in targets]
        scored=score_workflow(ref,pred)
        assert scored['selection_efficiency']==1
        assert scored['exploration_exempt_calls']==1
        assert scored['supporting_work_observations'][0]['observation_id']=='checkB'


def test_parallel_completion_logs_do_not_impose_a_false_serial_order():
    ref=reference();pred=prediction('gas','liquid')
    intervals={'Read':(0,1),'gas':(1,3),'liquid':(1,2)}
    for c in pred['calls']:
        start,finish=intervals[c['arguments'].get('curve','Read')]
        c.update(started_seconds=start,finished_seconds=finish)
    expected=score_workflow(ref,pred)
    pred['calls']=[pred['calls'][2],pred['calls'][1],pred['calls'][0]]
    actual=score_workflow(ref,pred)
    for key in ['orchestration_credit','selection_efficiency','tool_orchestration_score']:
        assert actual[key]==expected[key]==1


def test_a_real_consumer_cannot_start_before_its_required_source_exists():
    ref=reference();pred=prediction('difference')
    pred['calls'][0].update(started_seconds=0,finished_seconds=2)
    pred['calls'][1].update(started_seconds=1,finished_seconds=3)
    scored=score_workflow(ref,pred)
    assert not scored['planning_pass'] and scored['orchestration_credit']==.5


def test_ambiguous_reusable_source_witness_is_independent_of_result_collection_order():
    ref=reference();source=ref['evaluation']['nodes'][0]
    source['observation_reuse_group']='source-alternatives'
    ref['evaluation']['nodes'].append({'id':'optional-source-check','required':False,
        'observation_reuse_group':'source-alternatives',
        'alternatives':[{'tools':['Read'],'input_rules':[{'path':'/format','op':'eq','value':'A'}],
                         'output_rules':[{'path':'/known','op':'eq','value':True}]}]})
    pred=prediction('difference');pred['calls'][0]['arguments']={'format':'A'}
    other=deepcopy(pred['calls'][0]);other.update(observation_id='other',arguments={'format':'B'})
    pred['calls'].insert(1,other)
    for i,c in enumerate(pred['calls']):c.update(started_seconds=2*i,finished_seconds=2*i+1)
    expected=score_workflow(ref,pred)
    pred['calls'].reverse();actual=score_workflow(ref,pred)
    assert all(actual[k]==expected[k]for k in ['orchestration_credit','selection_efficiency','tool_orchestration_score'])
