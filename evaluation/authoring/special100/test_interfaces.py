"""Targeted public-boundary checks; run explicitly, without any model calls."""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
BASE=Path(__file__).resolve().parent


def load(module):
    spec=importlib.util.spec_from_file_location('special_'+module,BASE/(module+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_public_loader_reads_no_evaluator(monkeypatch):
    original=Path.read_text
    def checked(path,*a,**kw):
        if '/evaluation/' in str(path) or str(path).endswith('design.json'):raise AssertionError('Private read')
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'read_text',checked)
    rows=load('data').load_tasks('SMAS-0001')
    assert rows[0]['id']=='SMAS-0001'
    assert Path(rows[0]['files'][0]).exists()


def test_asset_scope_is_explicit_and_resets():
    from baselines.scimas.assets import public_asset_scope,asset_previews
    task=load('data').load_tasks('SMAS-0001')[0]
    with pytest.raises(ValueError,match='outside'):asset_previews(task,ROOT/'tasks')
    with public_asset_scope(BASE):
        previews=asset_previews(task,ROOT/'tasks')
        assert previews[0]['sha256']
    with pytest.raises(ValueError,match='outside'):asset_previews(task,ROOT/'tasks')


def test_asset_hash_tampering_still_rejected(tmp_path):
    from baselines.scimas.assets import public_asset_scope,asset_previews
    import json
    (tmp_path/'assets').mkdir();(tmp_path/'assets/source.json').write_text('{}')
    (tmp_path/'asset_manifest.json').write_text(json.dumps({'files':{'source.json':{'sha256':'0'*64}}}))
    with public_asset_scope(tmp_path):
        with pytest.raises(ValueError,match='changed'):asset_previews({'files':[str(tmp_path/'assets/source.json')]},ROOT/'tasks')


@pytest.mark.parametrize('baseline',['react','scitoolagent','scimas'])
def test_run_adapter_forwards_public_inputs_to_each_baseline(tmp_path,monkeypatch,baseline):
    import importlib,json,inspect
    from types import SimpleNamespace
    module=load('run');runtime=importlib.import_module('baselines.'+baseline+'.runtime')
    original=getattr(runtime,'run_'+baseline);observed=[]
    class Client:
        def __init__(self,backend):self.backend=backend;self.model='test'
        def close(self):pass
    def control(question,**kwargs):
        inspect.signature(original).bind(question,**kwargs)
        assert kwargs['case_id']=='SMAS-0001'
        assert Path(kwargs['files'][0]).parent==BASE/'assets'
        from baselines.scimas.assets import asset_previews
        assert asset_previews({'files':kwargs['files']},ROOT/'tasks')
        observed.append(question)
        path=tmp_path/'control_trace.json';path.write_text('{}')
        return {'dataset':'full','status':'stopped','final_answer':None,'failure_reason':'adapter_test_control',
                'calls':[],'trace_path':str(path)}
    monkeypatch.setattr(runtime,'run_'+baseline,control);monkeypatch.setattr(module,'GenerationClient',Client)
    args=SimpleNamespace(tasks='SMAS-0001',output=tmp_path/'predictions.json',baseline=baseline,backend='api',model='test',
                         task_timeout=10,max_model_requests=2)
    result=module.run(args)
    assert result['tasks']==1 and observed
    data=json.loads(args.output.read_text())
    assert data['suite']=='scimas-special-100-v2'
    assert data['predictions'][0]['public_task_sha256']
