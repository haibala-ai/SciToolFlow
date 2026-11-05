"""Compile public file identities into portable observation guards."""
import hashlib,json
from evaluation.workflow.expressions import operand
from evaluation.workflow.values import MissingEvidence


def hash_port(schema,path='',field='source_sha256'):
    if field in schema.get('properties',{}):return path+'/'+field
    for key,child in schema.get('properties',{}).items():
        result=hash_port(child,path+'/'+key,field)
        if result:return result
    for union in ('anyOf','oneOf','allOf'):
        for child in schema.get(union,[]):
            result=hash_port(child,path,field)
            if result:return result
    return None


def asset_guards(row,registry):
    for node in row['evaluation']['nodes']:
        for alt in node['alternatives']:
            kept=[]
            for rule in alt.get('input_rules',[]):
                try:value=operand(rule.get('right',{}),{'inputs':row['task']['inputs']})
                except (MissingEvidence,ValueError,TypeError,KeyError):value=None
                # Missing node evidence is expected during source compilation.
                # Only literal/public-input asset identities are rewritten.
                if isinstance(value,str) and value.startswith('asset://'):
                    data=row['assets'].get(value[8:])
                    if data is not None:
                        raw=(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
                        argument=rule.get('path','').lstrip('/')
                        field=argument.removesuffix('_file')+'_source_sha256' if argument in ('reference_file','mobile_file') else 'source_sha256'
                        port=hash_port(registry[alt['tools'][0]]['output_schema'],field=field)
                        if port:
                            guard={'path':port,'op':'eq','value':hashlib.sha256(raw).hexdigest()}
                            if guard not in alt['output_rules']:alt['output_rules'].append(guard)
                            continue
                kept.append(rule)
            if 'input_rules' in alt or kept:alt['input_rules']=kept
