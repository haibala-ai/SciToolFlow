"""Assemble individually authored special studies; never generate reference answers."""
import importlib.util
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from evaluation.workflow import validate_workflow,public_answer_contract
from jsonschema import Draft202012Validator
from src.utils.io import atomic_json
BASE=Path(__file__).resolve().parents[1]


def build(base=BASE):
    base=Path(base)
    rows=[]
    existing={t["id"]:t for t in map(json.loads,(base/"questions.jsonl").read_text().splitlines())} if (base/"questions.jsonl").exists() else {}
    for name in ['chemical','material','biology','machine_learning']:
        path=BASE/'authoring'/f'{name}.py'
        if not path.exists():continue
        module_spec=importlib.util.spec_from_file_location('special_'+name,path)
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
        rows.extend(module.build())
    sys.path.insert(0,str(BASE/'authoring'))
    from revision import apply as revise
    rows=revise(rows)
    from equivalence import apply
    apply(rows,BASE)
    from revision import semantic_equivalences
    for row in rows:semantic_equivalences(row)
    extensions=[]
    for name in ['chemical','material','biology','machine_learning']:
        extensions.extend(importlib.import_module('extension.'+name).build())
    updates={r['task']['id']:r for r in extensions}
    rows=[r for r in rows if r['task']['id'] not in updates]+extensions
    rows.sort(key=lambda s:s['task']['id'])
    from publication import rewrite,adjust_criteria,REVISED_IDS as PUBLICATION_REVISIONS
    for row in rows:
        row['task']=rewrite(row['task'])
        adjust_criteria(row['task'],row['evaluation'])
    assert len({s['task']['id'] for s in rows})==len(rows)
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())['tools']
    manifest={};questions=[];criteria=[];design=[]
    workflow_schema=json.loads((ROOT/'evaluation/workflow/schema.json').read_text())
    for row in rows:
        task=row['task'];spec=row['evaluation']
        from compiler import asset_guards
        asset_guards(row,registry)
        validate_workflow(spec);Draft202012Validator(workflow_schema).validate(spec)
        for node in spec['nodes']:
            for alt in node['alternatives']:
                assert set(alt['tools'])<=set(registry),alt['tools']
        for name,data in row['assets'].items():
            assert Path(name).name==name and name.startswith(task['id'])
            text=data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)+'\n'
            path=base/'assets'/name;raw=text.encode();path.write_bytes(raw)
            manifest[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                            'provenance':row.get('asset_provenance',{}).get(name,'Individually specified synthetic scientific fixture; not empirical measurements.')}
        task['Parameter']=json.dumps(task['inputs'],ensure_ascii=False,sort_keys=True,allow_nan=False)
        if not isinstance(task.get('unit_annotations',[]),list):
            task['unit_annotations']=[{'description':json.dumps(task['unit_annotations'],ensure_ascii=False,sort_keys=True)}]
        task['unit_annotations']=[{'description':json.dumps(a,ensure_ascii=False)} if isinstance(a,dict) and 'field' in a else a for a in task.get('unit_annotations',[])]
        task['answer_schema']['x-scoring-semantics']=public_answer_contract({'evaluation':spec})
        Draft202012Validator.check_schema(task['answer_schema'])
        from revision import REVISED_IDS
        if task['id'] not in (REVISED_IDS|set(updates)|PUBLICATION_REVISIONS) and task['id'] in existing:
            previous=existing[task['id']]
            assert {k:v for k,v in task.items() if k not in {'Parameter','unit_annotations'}}=={k:v for k,v in previous.items() if k not in {'Parameter','unit_annotations'}}, 'Unchanged reference task needs an explicit scientific revision: '+task['id']
            task=previous
        questions.append(task);criteria.append({'id':task['id'],'inputs':task['inputs'],'evaluation':spec})
        design.append({'id':task['id'],'domain':task['domain'],**row['design']})
    (base/'questions.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in questions))
    (base/'evaluation/criteria.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in criteria))
    for old_asset in (base/'assets').iterdir():
        if old_asset.is_file() and old_asset.name.startswith('SMAS-') and old_asset.name not in manifest:old_asset.unlink()
    atomic_json(base/'asset_manifest.json',{'files':manifest})
    atomic_json(base/'design.json',{'studies':design})
    from collections import Counter
    atomic_json(base/'progress.json',{'phase':'authored_awaiting_clean_reference_execution','authored':len(rows),
        'target':100,'accepted_references':len((base/'evaluation/references.jsonl').read_text().splitlines()) if (base/'evaluation/references.jsonl').exists() else 0,'domains':dict(Counter(t['domain'] for t in questions))})
    print(json.dumps({'authored':len(rows),'assets':len(manifest),'cases':[d['id'] for d in design if d['case_study']]},ensure_ascii=False))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=BASE)
    build(p.parse_args().directory)
