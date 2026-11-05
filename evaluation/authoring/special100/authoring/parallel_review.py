"""Review local scientific operations in two isolated production workers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import hashlib,importlib,inspect,json,sys,time
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tools import ToolCatalog,execute
from src.utils.paths import CALL_DIRECTORIES
from src.utils.io import atomic_json
from baselines.scimas.task_graph import digest
from evaluation.integrity.traces import read_trajectory,execution_calls

PARSERS=['ReadQChemFrequencyModes','ReadQChemIRIntensities','ReadQChemNBOPopulations',
 'ReadQChemTranslationalEnthalpy','ReadQChemTranslationalEntropy','ReadQChemRotationalEnthalpy',
 'ReadQChemRotationalEntropy','ReadQChemVibrationalEnthalpy','ReadQChemVibrationalEntropy']

LOCAL_OPERATIONS=['GetEEMCharges','MolecularFormalCharges','CountMolecularAtoms','CalculatePMI1','CalculatePMI2','CalculatePMI3','NormalizedPrincipalMoments','CompareMolecularShapes','SummarizeNumericTable']

def run():
    catalog=ToolCatalog(ROOT);folder=ROOT/'results/special100_parallel_acceptance';checks=[]
    inputs=ROOT/'evaluation/authoring/special100/assets'
    manifest=json.loads((inputs.parent/'asset_manifest.json').read_text())['files']
    def public_arguments(value):
        if isinstance(value,str) and value.startswith('/') and Path(value).name in manifest:
            name=Path(value).name;current=inputs/name
            assert hashlib.sha256(current.read_bytes()).hexdigest()==manifest[name]['sha256']
            return str(current.resolve())
        if isinstance(value,list):return [public_arguments(v) for v in value]
        if isinstance(value,dict):return {k:public_arguments(v) for k,v in value.items()}
        return value
    samples={}
    for line in (ROOT/'evaluation/authoring/special100/evaluation/references.jsonl').read_text().splitlines():
        ref=json.loads(line)
        for observation in execution_calls(read_trajectory(ROOT/ref['reference_trace'])):
            if observation['tool'] in LOCAL_OPERATIONS and observation['status']=='success':samples.setdefault(observation['tool'],public_arguments(observation['arguments']))
    def call(tool,index,arguments,files):
        directory=folder/tool/f'call_{index:04d}'
        for name in ('work','artifacts'):(directory/name).mkdir(parents=True,exist_ok=True)
        token=CALL_DIRECTORIES.set({name:str((directory/name).resolve()) for name in ('work','artifacts')})
        try:
            start=time.monotonic();result=execute(tool,arguments,files=files,timeout=180,catalog=catalog);end=time.monotonic()
        finally:CALL_DIRECTORIES.reset(token)
        atomic_json(directory/'result.json',result)
        return start,end,result
    for tool in PARSERS+LOCAL_OPERATIONS:
        source=inputs/('SMAS-0073_nbo_source.qout' if tool=='ReadQChemNBOPopulations' else 'SMAS-0070_water_source.qout')
        arguments={'qchem_file':str(source)} if tool in PARSERS else samples[tool]
        def paths(value):
            if isinstance(value,str) and value.startswith('/') and Path(value).is_file():yield value
            elif isinstance(value,list):
                for item in value:yield from paths(item)
            elif isinstance(value,dict):
                for item in value.values():yield from paths(item)
        files=sorted(set(paths(arguments)));original={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(call,tool,index,arguments,files) for index in [1,2]];results=[f.result() for f in futures]
        assert all(r[2]['status']=='success' for r in results),(tool,results)
        assert results[0][2]['output']==results[1][2]['output'],tool
        assert max(r[0] for r in results)<min(r[1] for r in results),tool
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in original.items())
        spec=catalog.tools[tool]
        checks.append({'tool':tool,'status':'passed','two_real_process_calls':2,'overlapping_dispatch_windows':True,
         'outputs_equivalent':True,'input_immutable':True,'contract_sha256':digest(spec),'source':spec['source'],
         'function_sha256':hashlib.sha256(inspect.getsource(getattr(importlib.import_module(spec['execution']['module']),spec['execution']['function'])).encode()).hexdigest(),'scope':'Local scientific calculation or read-only parser; independently isolated production workers/directories. Exact method/seed/source retained; no thread-safety or latency claim.'})
    report_path=ROOT/'tools/graph/scimas/parallel_review.json';report=json.loads(report_path.read_text())
    by_tool={r['tool']:r for r in report['checks']};by_tool.update({r['tool']:r for r in checks});report.update(status='passed',tools=len(by_tool),checks=[by_tool[k] for k in sorted(by_tool)])
    atomic_json(report_path,report)
    path=ROOT/'tools/graph/scimas/annotations.json';annotations=json.loads(path.read_text());template=annotations['tools']['CalculateDensity']
    for tool in PARSERS+LOCAL_OPERATIONS:
        spec=catalog.tools[tool];ann=deepcopy(template);ann['contract_sha256']=digest(spec);ann['evidence']['source']=spec['source'];ann['operation']='read_only_completed_qchem_parser' if tool in PARSERS else 'local_scientific_computation_or_readonly_input'
        ann['constraints'].append({'kind':'scientific_scope','description':('Only immutable supplied completed Q-Chem bytes; component fields share source hash and printed context; no new calculation or remote substitution.' if tool in PARSERS else 'Local deterministic molecular geometry/inventory or finite table arithmetic; retain coordinate, hydrogen, record, random-seed and normalization protocol. No external experimental claim. Process-local caches are not shared state.')})
        annotations['tools'][tool]=ann
    atomic_json(path,annotations)
    print(json.dumps({'source_reviewed_operations':len(checks),'new_successful_calls':len(checks)*2,'total_paired_tools':len(by_tool)}))

if __name__=='__main__':run()
