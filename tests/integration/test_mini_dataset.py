"""Mini-200 source identity, public boundary and production run/score routing."""
from collections import Counter
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import cli
from tasks.datasets import load_dataset,dataset_files
from tasks.assets import load_agent_input
from evaluation.suites.mini import load_references,prediction_from_reference,three_metrics,evaluate
from evaluation.integrity.traces import canonical_sha256,read_trajectory
ROOT=Path(__file__).resolve().parents[2]


def test_balanced_selection_preserves_scientific_inputs_and_reviewed_contracts():
    dataset=load_dataset('mini');full=load_dataset('full')
    seeds={t['id']:t for t in map(json.loads,(ROOT/'evaluation/authoring/special100/questions.jsonl').read_text().splitlines())}
    fullq={t['id']:t for t in full.questions}
    selection=json.loads((dataset.asset_root/'selection.json').read_text())['tasks_review']
    assert len(dataset.questions)==200
    assert Counter(t['domain'] for t in dataset.questions)==dict.fromkeys(['Chemical','Material','Biology','MachineLearning'],50)
    _,references=load_references(ROOT,dataset)
    from evaluation.workflow import public_answer_contract
    for t,r in zip(dataset.questions,selection):
        original=deepcopy(seeds[t['id']]if r['origin']=='special100'else fullq[r['source_id']])
        assert t['inputs']==original['inputs'] and t['files']==original['files']
        for change in r.get('public_contract_clarifications',[]):
            assert set(change)=={'path','value','reason'} and change['reason'].strip()
            parts=change['path'].strip('/').split('/')
            assert parts[0]in{'question','answer_schema','unit_annotations'}
            parent=original
            for part in parts[:-1]:parent=parent[part]
            parent[parts[-1]]=deepcopy(change['value'])
        if 'orchestration_review'in r and 'x-scoring-semantics'in original['answer_schema']:
            original['answer_schema']['x-scoring-semantics']=public_answer_contract(references[t['id']])
        assert {**t,'id':r['source_id']}=={**original,'id':r['source_id']}
        assert r['public_task_sha256']==canonical_sha256(t)
    assert Counter(r['domain'] for r in selection[100:])==dict.fromkeys(['Chemical','Material','Biology','MachineLearning'],25)
    assert all(r['category']!='high_difficulty' for r in selection[100:])
    assert all(r['capability_depth']>=2 and r['capability_width']>=2 for r in selection[100:])


def test_public_loader_does_not_read_selection_or_evaluation(monkeypatch):
    original=Path.open
    def guarded(path,*a,**kw):
        if 'evaluation' in path.parts or path.name=='selection.json':raise AssertionError('Private metadata read')
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'open',guarded)
    dataset=load_dataset('mini');task=load_agent_input(dataset.select('SMAS-0103')[0],dataset.asset_root)
    assert all(Path(p).parent==dataset.asset_root/'assets' for p in task['files'])


def test_mapped_reference_keeps_its_genuine_source_identity():
    dataset=load_dataset('mini');sources,views=load_references(ROOT,dataset)
    ref=views['SMAS-0103'];source=dataset.source_id('SMAS-0103')
    assert source=='FLOW-0029' and sources[source]['id']==source
    trace=read_trajectory(ROOT/ref['reference_trace'])
    assert trace['task_id']==source
    assert ref['native_provenance']['generation_manifest']['task_id']==source
    assert ref['id']=='SMAS-0103'
    changed=deepcopy(dataset.questions[102]);changed['question']+=' Hidden scientific edit.'
    dataset.questions[102]=changed
    with pytest.raises(ValueError,match='differs'):load_references(ROOT,dataset)


@pytest.mark.parametrize('baseline',['react','scitoolagent','scimas'])
@pytest.mark.parametrize('backend',['api','vllm','local'])
def test_cli_run_and_score_share_mini_namespace(tmp_path,monkeypatch,baseline,backend):
    called=[]
    monkeypatch.setattr('baselines.react.runner.run_batch',lambda a:called.append(a))
    monkeypatch.setattr(sys,'argv',['cli.py','run','--dataset','mini','--baseline',baseline,'--backend',backend,'--tasks','SMAS-0103'])
    cli.main();assert called[0].dataset=='mini' and called[0].baseline==baseline and called[0].backend==backend
    monkeypatch.setattr('evaluation.runner.evaluate_package',lambda *a,**kw:called.append(kw) or {'summary':{}})
    monkeypatch.setattr(sys,'argv',['cli.py','score','--dataset','mini','--tasks','SMAS-0103','--predictions','unused.json','--output',str(tmp_path/'score.json')])
    with redirect_stdout(StringIO()):cli.main()
    assert called[-1]['dataset']=='mini' and called[-1]['task_ids']==['SMAS-0103']


def options(monkeypatch,tmp_path):
    captured=[]
    monkeypatch.setattr(sys,'argv',['cli.py','run','--dataset','mini','--baseline','react','--backend','api','--tasks','SMAS-0103','--output',str(tmp_path/'predictions.json')])
    with patch('baselines.react.runner.run_batch',side_effect=lambda args:captured.append(args)):cli.main()
    return vars(captured[0])


@pytest.mark.parametrize('dataset_name,task_id',[('mini','SMAS-0103'),('mini','SMAS-0131'),('mini','SMAS-0132'),('mini-100','SMAS-0103'),('full','FLOW-0029')])
def test_production_react_tools_checkpoint_and_three_metric_score(tmp_path,monkeypatch,dataset_name,task_id):
    """Deterministic client replay is an integration test, not a model experiment.

    Real registered tools, production trace/ledger and source-ID mapping execute.
    Raw reference traces stay unchanged and this run is never a new reference.
    """
    import baselines.react.runner as runner
    dataset=load_dataset(dataset_name);task=dataset.select(task_id)[0]
    if dataset_name in {'mini','mini-100'}:_,refs=load_references(ROOT,dataset)
    else:
        from src.utils.io import read_jsonl
        refs={r['id']:r for r in read_jsonl(ROOT/'evaluation/data/references.jsonl.gz')}
    source=read_trajectory(ROOT/refs[task['id']]['reference_trace'])
    def relocate(value):
        if isinstance(value,str):
            candidate=dataset.asset_root/'assets'/Path(value).name
            if value.startswith('/') and candidate.is_file():return str(candidate)
        if isinstance(value,list):return [relocate(x) for x in value]
        if isinstance(value,dict):return {k:relocate(v) for k,v in value.items()}
        return value
    decisions=[relocate(s['decision']) for s in source['steps']]
    class Client:
        backend='injected';model='scripted-integration-test';supports_response_schema=True
        def __init__(self,*a,**kw):self.i=0
        def request(self,*a,**kw):
            decision=decisions[self.i];self.i+=1
            return {'text':json.dumps(decision),'usage':{'prompt_tokens':10,'completion_tokens':10}}
        def close(self):pass
    monkeypatch.setattr(runner,'GenerationClient',Client)
    args=options(monkeypatch,tmp_path)
    # Prevent worker-set task paths from escaping the test's environment.
    monkeypatch.setenv('SCITOOLFLOW_WORK_DIR',str(tmp_path/'work'))
    monkeypatch.setenv('SCITOOLFLOW_ARTIFACTS_DIR',str(tmp_path/'artifacts'))
    args['tasks']=task_id;args['dataset']=dataset_name
    prediction=runner.run_task((task,args,str(tmp_path/'predictions.json'),'integration'))
    assert prediction['completed'],prediction.get('failure_reason')
    assert prediction['dataset']==dataset_name and prediction['public_task_sha256']==canonical_sha256(task)
    trace=read_trajectory(prediction['trace_path']);policy={
        'version':'task-resources.v1','max_model_requests':args['max_model_requests'],'task_seconds':args['task_timeout'],
        'scientific_calls':args['max_calls'],'decisions':args['max_steps'],'discovery_calls':args['max_discovery_calls'],
        'think_steps':args['max_think_steps'],'consecutive_thinks':args['max_consecutive_thinks']}
    settings={'dataset':dataset_name,'resource_policy':policy,'actor_file_hashes':{
        name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in dataset_files(dataset_name)+['tools/catalog/catalog.json']}}
    envelope={'settings':settings,'fingerprint':hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest(),'predictions':[prediction]}
    checkpoint=tmp_path/'predictions.json';checkpoint.write_text(json.dumps(envelope))
    if dataset_name=='full':
        from evaluation.runner import evaluate_package
        # Full package/reference integrity is checked separately; keep this test
        # focused on actual relocated input -> tool -> production trace -> score.
        with patch('evaluation.runner.validate_package'):
            report=evaluate_package(ROOT,checkpoint,tmp_path/'scores.json',task_ids=[task_id],dataset='full')
        assert report['summary']['joint_success_rate']==1,report
        return
    report=evaluate(ROOT,checkpoint,tmp_path/'scores.json',task_ids=[task_id],dataset=dataset_name)
    assert all(report['summary'][k]==1 for k in ['runtime_completion_rate','answer_accuracy']),report
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    reference_prediction=prediction_from_reference(ROOT,refs[task_id])
    expected=three_metrics(task,refs[task_id],reference_prediction,reference_prediction,registry)
    # Real reference errors/redundancy still cost E; correct replay need not S=1.
    assert report['summary']['tool_planning_accuracy']==pytest.approx(expected['tool_orchestration_score'])
    assert report['summary']['strict_tool_planning_accuracy']==float(expected['tool_plan_correct'])
    # A complete valid checkpoint can be scored on the whole200 denominator.
    empty={**envelope,'predictions':[]};checkpoint.write_text(json.dumps(empty))
    missing=evaluate(ROOT,checkpoint,tmp_path/'missing.json',dataset=dataset_name)
    assert missing['summary']['tasks']==len(dataset.questions) and missing['summary']['answer_accuracy']==0
    checkpoint.write_text(json.dumps(envelope));envelope['predictions'][0]['public_task_sha256']='0'*64
    checkpoint.write_text(json.dumps(envelope));bad=evaluate(ROOT,checkpoint,tmp_path/'bad.json',task_ids=[task_id],dataset=dataset_name)
    assert bad['summary']['answer_accuracy']==0


@pytest.mark.parametrize('baseline',['react','scitoolagent','scimas'])
@pytest.mark.parametrize('dataset_name',['mini','mini-100'])
def test_each_worker_receives_mini_assets_and_public_scope(tmp_path,monkeypatch,baseline,dataset_name):
    import importlib,inspect
    import baselines.react.runner as runner
    from baselines.scimas.assets import asset_previews
    options_row=options(monkeypatch,tmp_path);options_row.update(baseline=baseline,dataset=dataset_name)
    dataset=load_dataset(dataset_name);task=dataset.select('SMAS-0103')[0]
    module=importlib.import_module('baselines.'+baseline+'.runtime');original=getattr(module,'run_'+baseline)
    class Client:
        model='adapter-test';backend='injected'
        def __init__(self,*a,**kw):pass
        def close(self):pass
    def runtime(question,**kwargs):
        inspect.signature(original).bind(question,**kwargs)
        assert kwargs['dataset']==dataset_name and kwargs['case_id']=='SMAS-0103'
        assert Path(kwargs['files'][0]).parent==dataset.asset_root/'assets'
        assert asset_previews({'files':kwargs['files']},ROOT/'tasks')
        p=tmp_path/'trace.json';p.write_text('{}')
        return {'status':'stopped','calls':[],'final_answer':None,'failure_reason':'adapter_test',
          'trace_path':str(p),'stats':{},'duration_seconds':0,'resource_usage':{}}
    if baseline=='react':monkeypatch.setattr(runner,'run_react',runtime)
    else:monkeypatch.setattr(module,'run_'+baseline,runtime)
    monkeypatch.setattr(runner,'GenerationClient',Client)
    monkeypatch.setenv('SCITOOLFLOW_WORK_DIR',str(tmp_path/'work'))
    monkeypatch.setenv('SCITOOLFLOW_ARTIFACTS_DIR',str(tmp_path/'artifacts'))
    result=runner.run_task((task,options_row,str(tmp_path/'p.json'),'adapter'))
    assert result['failure_reason']=='adapter_test'


def test_planning_entrypoint_uses_mini_public_asset_scope(tmp_path,monkeypatch):
    import baselines.scimas.runner as runner
    from baselines.scimas.assets import asset_previews
    seen=[];monitors=[]
    class Client:
        model='test'
        def __init__(self,**kw):pass
        def close(self):pass
    class Planner:
        def __init__(self,*a,**kw):pass
        def plan(self,public,**kwargs):
            assert kwargs['dataset']=='mini'
            assert asset_previews(public,ROOT/'tasks')
            seen.append(public['id']);return {'status':'planned','steps':[]}
    monkeypatch.setattr(runner,'Planner',Planner);monkeypatch.setattr(runner,'GenerationClient',Client)
    monkeypatch.setattr(runner,'ToolKnowledge',lambda:object())
    monkeypatch.setattr(runner,'start_monitor',lambda path:monitors.append(path))
    report=runner.run_planning(SimpleNamespace(dataset='mini',tasks='SMAS-0103',output=str(tmp_path/'plan'),backend='api',model='test',max_model_requests=3,max_output_tokens=1024,task_timeout=30))
    assert report['planned']==1 and seen==['SMAS-0103']
    assert monitors==[tmp_path/'plan']
    progress=json.loads((tmp_path/'plan/progress.json').read_text())
    assert progress['stage']=='graph_planning' and progress['status']=='finished'
