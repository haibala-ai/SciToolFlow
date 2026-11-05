"""The public interface is Mini by default, with an explicit Full source suite."""
import hashlib,json,sys
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout
from unittest.mock import patch
import pytest
import cli
from tasks.datasets import DATASETS,load_dataset
from baselines.react.runner import actor_file_hashes,resume_rows
ROOT=Path(__file__).resolve().parents[2]


def test_public_namespaces_and_default():
    assert DATASETS==('mini','full')
    assert load_dataset().name=='mini' and len(load_dataset().questions)==200
    assert len(load_dataset('full').questions)==500
    with pytest.raises(ValueError):load_dataset('special')
    with pytest.raises(ValueError):load_dataset('mini').select('FLOW-0001')
    with pytest.raises(ValueError):load_dataset('full').select('SMAS-0001')


@pytest.mark.parametrize('command,args',[
 ('task',[]),('run',[]),('score',['--predictions','unused.json']),
 ('plan',['--tasks','SMAS-0103','--output','unused'])])
def test_removed_special_namespace_is_not_aliased(command,args):
    with patch.object(sys,'argv',['cli.py',command,'--dataset','special']+args):
        with pytest.raises(SystemExit) as result:cli.main()
    assert result.value.code==2


def test_task_command_defaults_to_mini():
    stream=StringIO()
    with patch.object(sys,'argv',['cli.py','task','SMAS-0103']),redirect_stdout(stream):cli.main()
    assert json.loads(stream.getvalue())['id']=='SMAS-0103'
    stream=StringIO()
    with patch.object(sys,'argv',['cli.py','task','FLOW-0001','--dataset','full']),redirect_stdout(stream):cli.main()
    assert json.loads(stream.getvalue())['id']=='FLOW-0001'


def test_mapping_and_actor_source_participate_in_checkpoint_identity():
    full=actor_file_hashes(ROOT,'full');mini=actor_file_hashes(ROOT,'mini')
    for name in ['tasks/mini/questions.jsonl','tasks/mini/ids.tsv','tasks/mini/metadata.json']:
        assert name in mini and name not in full
    assert not any(name.startswith('evaluation/') or '/authoring/' in name for name in mini)
    assert 'tasks/full/questions.jsonl' not in mini
    key=lambda dataset,hashes:hashlib.sha256(json.dumps({'dataset':dataset,'actor_file_hashes':hashes},sort_keys=True).encode()).hexdigest()
    with pytest.raises(ValueError):resume_rows({'fingerprint':key('full',full),'predictions':[]},key('mini',mini))
