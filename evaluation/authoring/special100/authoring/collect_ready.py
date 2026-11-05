"""Root review driver: gate real native references, never fabricate trajectories."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('special_review',HERE/'review.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
notes=json.loads((HERE/'review_notes.json').read_text())
actors=json.loads((HERE/'actor_records.json').read_text())
accepted=m.mapping(m.BASE/'evaluation/references.jsonl') if (m.BASE/'evaluation/references.jsonl').exists() else {}
for tid,note in notes.items():
 if tid in accepted:
  current=m.mapping(m.BASE/'evaluation/criteria.jsonl')[tid]
  if (accepted[tid]['native_provenance']['task_sha256']==m.canonical_sha256(m.mapping(m.BASE/'questions.jsonl')[tid])
      and m.canonical_sha256(accepted[tid]['evaluation'])==m.canonical_sha256(current['evaluation'])
      and accepted[tid]['native_provenance']['actor_id']==actors.get(tid,{}).get('actor_id',accepted[tid]['native_provenance']['actor_id'])):continue
 path=m.ROOT/'results/special_native_references'/tid/'attempt_1/candidate.json'
 if path.exists():
  result=m.review(tid,actors.get(tid,{}).get('actor_id','/root/native_'+tid[-4:]),note,attempt=actors.get(tid,{}).get('attempt',1))
  print(json.dumps(result,ensure_ascii=False),flush=True)
