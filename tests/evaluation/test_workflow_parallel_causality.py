"""Observed parallel intervals and trace authentication, without trusting plan text."""
import hashlib,json
from pathlib import Path
from evaluation.integrity.traces import authenticate_prediction
from evaluation.workflow.causality import observed_before
import pytest


def test_prediction_cannot_replace_authenticated_dispatcher_timing(tmp_path):
    trace={'task_id':'T','dataset':'mini','status':'failed','final_answer':None,
           'failure_reason':'no answer','steps':[{'type':'tools','calls':[
               {'observation_id':'o1','tool':'Read','arguments':{},'status':'success',
                'output':{'x':1},'started_seconds':2,'finished_seconds':3}]}]}
    p=tmp_path/'trace.json';p.write_text(json.dumps(trace));call=dict(trace['steps'][0]['calls'][0])
    call.update(started_seconds=100,finished_seconds=200)
    pred={'id':'T','dataset':'mini','completed':False,'status':'failed','final_answer':None,
          'failure_reason':'no answer','trace_path':str(p),'trace_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'calls':[call]}
    authenticated,checked=authenticate_prediction(pred,tmp_path,tmp_path,{'tools':{'Read':{}}},dataset='mini')
    assert checked['verified']
    assert authenticated['calls'][0]['started_seconds']==2
    assert authenticated['calls'][0]['finished_seconds']==3


def test_causality_uses_finish_before_start_instead_of_collection_order():
    a={'_index':5,'started_seconds':0,'finished_seconds':2}
    b={'_index':0,'started_seconds':2,'finished_seconds':3}
    assert observed_before(a,b)
    b['started_seconds']=1
    assert not observed_before(a,b)


@pytest.mark.parametrize('baseline,timed,valid', [
    ('react',False,True), ('scitoolagent',False,True), ('scimas',True,True),
    ('react',True,True), ('scitoolagent',True,True), ('scimas',False,False),
])
def test_common_authentication_accepts_real_serial_and_parallel_forms(tmp_path,baseline,timed,valid):
    receipt={'observation_id':'o1','tool':'Read','arguments':{},'status':'success','output':{'x':1}}
    if timed:receipt.update(started_seconds=0,finished_seconds=1)
    trace={'task_id':'T','dataset':'mini','baseline':baseline,'status':'completed',
           'final_answer':{'x':1},'failure_reason':None,
           'steps':[{'type':'tools','calls':[receipt]}]}
    path=tmp_path/'trajectory.json';path.write_text(json.dumps(trace))
    pred={'id':'T','dataset':'mini','status':'completed','completed':True,
          'final_answer':{'x':1},'failure_reason':None,'trace_path':str(path),
          'trace_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'calls':[receipt]}
    _,integrity=authenticate_prediction(pred,tmp_path,tmp_path,{'tools':{'Read':{}}},dataset='mini')
    assert integrity['verified']is valid


@pytest.mark.parametrize('start,finish', [(2,1),(-1,2),(True,2),(0,float('nan')),(0,None),(None,1)])
def test_invalid_timing_is_not_a_license_to_fall_back_to_serial_order(start,finish):
    with pytest.raises(ValueError):
        observed_before({'_index':0,'started_seconds':start,'finished_seconds':finish},
                        {'_index':1,'started_seconds':3,'finished_seconds':4})
