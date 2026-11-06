"""Regrade verified historical evidence with the current Mini scientific rules.

This is an explicit retrospective assessment, not a current-release model run.
Original fingerprints, answers, statuses, traces and timing ledgers are retained.
The ordinary production scorer and its release gate are not relaxed.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from evaluation.integrity.resources import check_resources, validate_policy
from evaluation.integrity.traces import (
    authenticate_prediction, canonical_sha256, read_trajectory, trajectory_bytes,
)
from evaluation.suites.mini import load_references, prediction_from_reference, summarize, three_metrics
from evaluation.workflow import public_answer_contract
from src.utils.io import atomic_json
from tasks.datasets import dataset_files, load_dataset
from tasks.schema import validation_errors

ARCHIVE = ROOT / 'exp/main_scimas'
OUTPUT = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_digest(path):
    return digest(path.read_bytes())


def json_file(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def checked_path(root, name):
    path = (root / name).resolve()
    if Path(name).is_absolute() or root.resolve() not in path.parents:
        raise ValueError('Archive path escapes its root: ' + name)
    return path


def verify_original():
    manifest = json_file(ARCHIVE / 'manifest.json')
    for item in manifest['files']:
        path = checked_path(ARCHIVE, item['path'])
        raw = path.read_bytes()
        if len(raw) != item['stored_bytes'] or digest(raw) != item['stored_sha256']:
            raise ValueError('Archive stored identity differs: ' + item['path'])
        if item.get('role') != 'derived_index':
            original = gzip.decompress(raw) if item['encoding'] == 'gzip' else raw
            if len(original) != item['source_bytes'] or digest(original) != item['source_sha256']:
                raise ValueError('Archive original identity differs: ' + item['path'])
    original = json_file(ARCHIVE / 'predictions.json.gz')
    portable = json_file(ARCHIVE / 'predictions.portable.json')
    settings = original['settings']
    fingerprint = digest(json.dumps(settings, sort_keys=True).encode())
    if original['fingerprint'] != fingerprint or portable['fingerprint'] != fingerprint:
        raise ValueError('Original settings fingerprint differs')
    if portable['settings'] != settings or settings.get('dataset') != 'mini':
        raise ValueError('Archive settings or dataset differs')
    hashes = settings['actor_file_hashes']
    if not set(dataset_files('mini') + ['tools/catalog/catalog.json']) <= set(hashes):
        raise ValueError('Original release hash inventory is incomplete')
    if json_file(ARCHIVE / 'metadata/actor_file_hashes.json') != hashes:
        raise ValueError('Archived actor hash inventory differs')
    commit = manifest['actor_commit']
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Require an exact historical actor commit')
    actor_checks = {}
    for name, expected in hashes.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe actor source path')
        blob = subprocess.run(['git', 'show', commit + ':' + name], cwd=ROOT,
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        if digest(blob) != expected:
            raise ValueError('Historical commit does not match actor file: ' + name)
        actor_checks[name] = expected
    for name in ['questions.jsonl', 'metadata.json']:
        if file_digest(ARCHIVE / 'metadata/dataset_snapshot' / name) != hashes['tasks/mini/' + name]:
            raise ValueError('Historical public-task snapshot differs: ' + name)
    original_by_id = {p['id']: p for p in original['predictions']}
    portable_by_id = {p['id']: p for p in portable['predictions']}
    if (len(original_by_id) != len(original['predictions']) or len(portable_by_id) != 200
            or len(portable['predictions']) != 200 or set(original_by_id) != set(portable_by_id)):
        raise ValueError('Archive must have 200 unique aligned predictions')
    for tid, row in portable_by_id.items():
        if ({k:v for k,v in row.items() if k not in {'trace_path','trace_sha256'}} !=
                {k:v for k,v in original_by_id[tid].items() if k not in {'trace_path','trace_sha256'}}):
            raise ValueError('Portable prediction changed scientific content: ' + tid)
        path = checked_path(ARCHIVE, row['trace_path'])
        if digest(trajectory_bytes(path)) != original_by_id[tid]['trace_sha256']:
            raise ValueError('Decompressed trace is not the original evidence: ' + tid)
    return portable, dict(
        archive_files_verified=len(manifest['files']), actor_commit=commit,
        historical_actor_files_verified=len(actor_checks),
        original_run_fingerprint=fingerprint,
        original_predictions_sha256=file_digest(ARCHIVE / 'predictions.json.gz'),
        portable_predictions_sha256=file_digest(ARCHIVE / 'predictions.portable.json'),
        original_archive_manifest_sha256=file_digest(ARCHIVE / 'manifest.json'),
        original_scores_sha256=file_digest(ARCHIVE / 'scores.json'),
    )


def verify_migration(envelope, dataset, refs):
    hashes = envelope['settings']['actor_file_hashes']
    for name in ['tools/catalog/catalog.json','tasks/mini/ids.tsv','tasks/mini/asset_manifest.json']:
        if file_digest(ROOT / name) != hashes[name]:
            raise ValueError('Scientific tools, task mapping or assets changed: ' + name)
    old_rows = [json.loads(line) for line in (ARCHIVE / 'metadata/dataset_snapshot/questions.jsonl').read_text().splitlines() if line.strip()]
    old = {q['id']:q for q in old_rows}
    if len(old) != len(old_rows) or set(old) != {q['id'] for q in dataset.questions}:
        raise ValueError('Historical and current tasks are not aligned')
    selection = {r['id']:r for r in json_file(ROOT / 'tasks/mini/selection.json')['tasks_review']}
    changes = []
    for current in dataset.questions:
        tid = current['id']
        if any(current.get(k) != old[tid].get(k) for k in ['inputs','files','domain','parameter']):
            raise ValueError('Scientific inputs changed: ' + tid)
        expected = deepcopy(old[tid])
        for change in selection[tid].get('public_contract_clarifications', []):
            if set(change) != {'path','value','reason'} or not change['reason'].strip():
                raise ValueError('Public clarification has no reviewed basis')
            parts = change['path'].strip('/').split('/')
            if parts[0] not in {'question','answer_schema','unit_annotations'}:
                raise ValueError('Unapproved public-task migration')
            parent = expected
            for part in parts[:-1]:
                parent = parent[part]
            parent[parts[-1]] = deepcopy(change['value'])
        if 'x-scoring-semantics' in expected['answer_schema']:
            expected['answer_schema']['x-scoring-semantics'] = public_answer_contract(refs[tid])
        if expected != current:
            raise ValueError('Difference is not covered by reviewed public clarifications: ' + tid)
        fields = sorted(k for k in set(current) | set(old[tid]) if current.get(k) != old[tid].get(k))
        changes.append(dict(id=tid, changed_public_fields=fields,
            historical_public_task_sha256=canonical_sha256(old[tid]),
            current_public_task_sha256=canonical_sha256(current),
            question_changed='question' in fields, answer_contract_changed='answer_schema' in fields,
            scientific_inputs_unchanged=True,
            approved_clarification_paths=[c['path'] for c in selection[tid].get('public_contract_clarifications', [])]))
    return old, changes


def scorer_hashes():
    paths = set((ROOT / 'evaluation/workflow').glob('*.py'))
    paths |= set((ROOT / 'evaluation/integrity').glob('*.py'))
    paths |= {ROOT / name for name in ['evaluation/workflow/schema.json','evaluation/suites/mini.py','evaluation/suites/reference_context.py',
        'tasks/schema.py','tasks/datasets.py','src/utils/io.py','tools/catalog/catalog.json']}
    return {str(p.relative_to(ROOT)):file_digest(p) for p in sorted(paths)}


def write_snapshot(code_hashes, contexts):
    """Keep the reproducibility snapshot in one archive, without loose copies."""
    prefix = str((OUTPUT / 'scoring_snapshot').relative_to(ROOT))
    temporary = OUTPUT / '.scoring_snapshot.tar.gz.tmp'
    target = OUTPUT / 'scoring_snapshot.tar.gz'
    members = {}
    for name in ['questions.jsonl','metadata.json','selection.json','evaluation/references.jsonl.gz','evaluation/orchestration_review.json']:
        members[prefix+'/'+name] = (ROOT/'tasks/mini'/name).read_bytes()
    for name, expected in code_hashes.items():
        content = (ROOT/name).read_bytes()
        if digest(content) != expected:
            raise ValueError('Snapshot implementation changed: '+name)
        members[prefix+'/scorer_code/'+name] = content
    members[prefix+'/answer_reference_contexts.jsonl.gz'] = gzip.compress(
        ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n' for row in contexts).encode(), mtime=0)
    with tarfile.open(temporary, 'w:gz') as archive:
        for name, content in sorted(members.items()):
            info = tarfile.TarInfo(name);info.size = len(content);info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    # Re-running an identical assessment must not change a frozen archive just
    # because gzip/tar metadata differ. Compare every member's actual content.
    existing = {}
    if target.exists():
        with tarfile.open(target, 'r:gz') as archive:
            for member in archive:
                if member.isfile():
                    if member.name in existing:
                        raise ValueError('Duplicate snapshot member')
                    existing[member.name] = digest(archive.extractfile(member).read())
    if existing == {name:digest(content) for name,content in members.items()}:
        temporary.unlink()
    else:
        temporary.replace(target)
    return dict(path=target.name, sha256=file_digest(target), files=len(members))


def run():
    OUTPUT.mkdir(exist_ok=True)
    started = time.perf_counter()
    atomic_json(OUTPUT / 'progress.json', dict(status='verifying', completed=0, total=200))
    original_files = {str(p.relative_to(ARCHIVE)):file_digest(p)
        for p in ARCHIVE.rglob('*') if p.is_file() and OUTPUT not in p.parents}
    envelope, original_check = verify_original()
    dataset = load_dataset('mini', ROOT)
    _, refs = load_references(ROOT, dataset)
    old_tasks, migrations = verify_migration(envelope, dataset, refs)
    migration_by_id = {r['id']:r for r in migrations}
    policy = validate_policy(envelope['settings']['resource_policy'])
    registry = json_file(ROOT / 'tools/catalog/catalog.json')
    by_id = {p['id']:p for p in envelope['predictions']}
    old_scores = {r['id']:r for r in json_file(ARCHIVE / 'scores.json')['tasks']}
    current_meta = json_file(ROOT / 'tasks/mini/metadata.json')
    code_hashes = scorer_hashes()
    identity = dict(schema_version='scitoolflow.historical_mini_rescore.v1',
        **original_check, current_scoring_revision=current_meta.get('orchestration_revision'),
        current_scoring_files_sha256=code_hashes,
        current_release_files_sha256={n:file_digest(ROOT / 'tasks/mini' / n) for n in
            ['questions.jsonl','metadata.json','selection.json','evaluation/references.jsonl.gz','evaluation/orchestration_review.json']},
        historical_run_identity_preserved=True, production_release_gate_changed=False,
        new_model_calls=0, new_scientific_tool_calls=0, llm_judge_used=False,
        resource_timing_policy='Use original authenticated task-resources.v1 ledger; no counterfactual retiming',
        historical_public_task_changes=migrations)
    atomic_json(OUTPUT / 'validation.json', {**identity, 'status':'verified_inputs_scoring_in_progress'})
    # Preserve the actual scientific observations used to judge answer values.
    # These are extracted contexts, not newly executed reference trajectories.
    contexts = []
    rows = []
    for index, task in enumerate(dataset.questions, 1):
        tid = task['id']
        prediction = by_id[tid]
        migration = migration_by_id[tid]
        if prediction.get('public_task_sha256') != canonical_sha256(old_tasks[tid]):
            raise ValueError('Prediction does not match the historical public task: ' + tid)
        authenticated, integrity = authenticate_prediction(prediction, ROOT, ARCHIVE, registry, dataset='mini')
        if not integrity['verified']:
            raise ValueError('Archived trajectory failed current evidence authentication: ' + tid + ': ' + integrity.get('reason',''))
        resource = check_resources(authenticated, policy)
        reference = refs[tid]
        reference_path = ROOT / reference['reference_trace']
        if digest(trajectory_bytes(reference_path)) != reference['native_provenance']['trace_sha256']:
            raise ValueError('Current answer-reference evidence differs: ' + tid)
        reference_prediction = prediction_from_reference(ROOT, reference)
        contexts.append(dict(id=tid, source_trace_sha256=reference['native_provenance']['trace_sha256'],
                             prediction=reference_prediction))
        scored = three_metrics(task, reference, authenticated, reference_prediction, registry)
        scored.update(domain=task['domain'], source_id=dataset.source_id(tid),
            evidence_integrity=integrity, resource_usage=resource,
            historical_task_identity_verified=True,
            historical_public_task_sha256=migration['historical_public_task_sha256'],
            current_public_task_sha256=migration['current_public_task_sha256'],
            public_contract_changed=bool(migration['changed_public_fields']),
            question_changed=migration['question_changed'],
            historical_answer_schema_valid=not validation_errors(prediction.get('final_answer'), old_tasks[tid]['answer_schema']),
            current_answer_schema_valid=not validation_errors(prediction.get('final_answer'), task['answer_schema']),
            original_score={k:old_scores[tid][k] for k in ['runtime_completed','tool_plan_correct','answer_correct']})
        rows.append(scored)
        atomic_json(OUTPUT / 'progress.json', dict(status='scoring', completed=index, total=200,
            last_task=tid, elapsed_scoring_seconds=time.perf_counter()-started,
            partial_summary=summarize(rows)))
        print(tid, 'C', scored['orchestration_credit'], 'E', scored['selection_efficiency'],
              'S', scored['tool_orchestration_score'], 'answer', scored['answer_correct'],
              'pending', scored['pending_review'], flush=True)
    if scorer_hashes() != code_hashes:
        raise ValueError('Scoring implementation changed during retrospective assessment')
    for name, expected in identity['current_release_files_sha256'].items():
        if file_digest(ROOT / 'tasks/mini' / name) != expected:
            raise ValueError('Current task/criterion release changed while scoring')
    for name, expected in original_files.items():
        if file_digest(ARCHIVE / name) != expected:
            raise ValueError('Original experiment file changed: ' + name)
    snapshot = write_snapshot(code_hashes, contexts)
    summary = summarize(rows)
    report = dict(schema_version='scitoolflow.mini.three_metrics.v3',
        metric_definition_version='independent-runtime-answer.v2',
        assessment='historical_run_rescored_with_current_criteria', dataset='mini', summary=summary,
        primary_metrics=['runtime_completion_rate','tool_planning_accuracy','answer_accuracy'],
        tool_planning_definition='Macro mean of per-task 3*C*E/(2*E+C), zero when C or E is zero; pending search is not a reportable score.',
        original_run_fingerprint=envelope['fingerprint'],
        original_summary=json_file(ARCHIVE / 'scores.json')['summary'],
        current_scoring_revision=identity['current_scoring_revision'], tasks=rows,
        domains={d:summarize([r for r in rows if r['domain']==d]) for d in sorted({r['domain'] for r in rows})},
        llm_judge_used=False, new_model_calls=0, new_scientific_tool_calls=0)
    atomic_json(OUTPUT / 'scores.json', report)
    atomic_json(OUTPUT / 'validation.json', {**identity, 'status':'passed',
        'scoring_snapshot_archive':snapshot,
        'authenticated_original_trajectories':200, 'original_experiment_files_unchanged':len(original_files),
        'public_contract_changed_tasks':sum(r['public_contract_changed'] for r in rows),
        'question_changed_tasks':sum(r['question_changed'] for r in rows),
        'completed_utc':datetime.now(timezone.utc).isoformat()})
    atomic_json(OUTPUT / 'progress.json', dict(status='complete', completed=200, total=200,
        elapsed_scoring_seconds=time.perf_counter()-started, summary=summary))
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
