"""Shared batch witnesses, exact overlap choices and honest search bounds."""
from itertools import product
import random
from evaluation.workflow.method_cover import select_methods
from evaluation.workflow import score_workflow
from tests.support.workflows import call


def footprint(groups,selected,base=0):
    result=base
    for name,route in selected.items():result|=next(mask for r,mask in groups[name]if tuple(r)==tuple(route))
    return result.bit_count()


def test_exact_cover_matches_exhaustive_small_problems():
    rng=random.Random(29)
    for trial in range(100):
        groups={str(g):[((str(g)+'_'+str(r),),rng.randrange(128))for r in range(rng.randrange(1,4))]
                for g in range(rng.randrange(1,7))}
        base=rng.randrange(128);best=128
        for options in product(*groups.values()):
            value=base
            for _,mask in options:value|=mask
            best=min(best,value.bit_count())
        selected,truncated,_=select_methods(groups,base)
        assert not truncated and footprint(groups,selected,base)==best
        reversed_groups={name:list(reversed(options))for name,options in reversed(list(groups.items()))}
        other,unresolved,_=select_methods(reversed_groups,base)
        assert not unresolved and other==selected


def test_search_improves_a_greedy_cover_and_exhaustion_is_explicit():
    masks={'A':1,'B':2,'C':4,'D':8,'E':16}
    routes=[['A','B'],['A','B'],['A','C'],['A','C'],['B','D'],['C','E']]
    groups={str(i):[((name,),masks[name])for name in names]for i,names in enumerate(routes)}
    result,unresolved,visits=select_methods(groups)
    assert not unresolved and footprint(groups,result)==2 and visits>0
    bounded,pending,_=select_methods(groups,limit=0)
    assert pending and footprint(groups,bounded)==3


def test_shared_batch_beats_two_redundant_scalar_methods_independent_of_names():
    nodes=[{'id':'source','alternatives':[{'tools':['Read'],'output_rules':[{'path':'/known','op':'eq','value':True}]}]}]
    for name,tool,field,value in [('a_x','GetX','x',2),('b_y','GetY','y',3)]:
        nodes.append({'id':name,'required':False,'depends_on':['source'],'alternatives':[{'tools':[tool],'output_rules':[{'path':'/'+field,'op':'eq','value':value}]}]})
    nodes.append({'id':'z_shared','required':False,'depends_on':['source'],
        'alternatives':[{'tools':['Batch'],'output_rules':[{'path':'/x','op':'eq','value':2},{'path':'/y','op':'eq','value':3}]}]})
    ref={'id':'batch','evaluation':{'schema_version':'workflow.v1','nodes':nodes,
        'capability_groups':[{'id':'x','alternatives':[['a_x'],['z_shared']]},{'id':'y','alternatives':[['b_y'],['z_shared']]}],
        'outcomes':[{'id':'answer','left':{'source':'answer','path':'/x'},'op':'eq','value':2,'evidence_groups':['x','y']}],
        'efficiency':{'single_route_efficiency':True,'useful_work_rules':[],'recovery_rules':[],'disambiguation_rules':[]}}}
    pred={'completed':True,'final_answer':{'x':2},'calls':[call('s','Read',{}, {'known':True}),
        call('x','GetX',{}, {'x':2}),call('y','GetY',{}, {'y':3}),call('b','Batch',{}, {'x':2,'y':3})]}
    result=score_workflow(ref,pred)
    assert result['orchestration_credit']==1 and result['selection_efficiency']==.5
    assert result['selected_efficiency_routes']=={'x':['z_shared'],'y':['z_shared']}
    for c in pred['calls']:c.update(started_seconds=0 if c['tool']=='Read'else 1,finished_seconds=1 if c['tool']=='Read'else 2)
    pred['calls'].reverse();ref['evaluation']['capability_groups'].reverse()
    assert score_workflow(ref,pred)['selection_efficiency']==.5
