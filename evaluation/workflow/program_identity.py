"""Compare the full syntax tree of an already reviewed numerical program.

This does not execute, optimize or infer the correctness of new algorithms.
Comments, redundant parentheses and layout may change; names, literals,
operators, statement order and source observations must remain identical.
"""
import ast
import hashlib
from functools import lru_cache
from .values import MissingEvidence

@lru_cache(maxsize=2048)
def _identity(source):
    if not isinstance(source,str) or not 1 <= len(source) <= 64000:
        raise MissingEvidence('Reviewed program identity requires bounded Python text')
    try:
        tree=ast.parse(source,mode='exec')
        pending=[(tree,0)];count=0
        while pending:
            node,depth=pending.pop();count+=1
            if count>25000 or depth>128:
                raise MissingEvidence('Reviewed program syntax tree exceeds its bounds')
            pending.extend((child,depth+1) for child in ast.iter_child_nodes(node))
        normalized=ast.dump(tree,annotate_fields=True,include_attributes=False)
    except (SyntaxError,ValueError,TypeError,MemoryError,RecursionError) as error:
        raise MissingEvidence('Invalid or excessive reviewed Python program') from error
    return hashlib.sha256(normalized.encode()).hexdigest()

def reviewed_program_identity(value):
    if isinstance(value,str):
        return _identity(value)
    if isinstance(value,list) and 1<=len(value)<=128 and all(isinstance(x,str) for x in value) and sum(map(len,value))<=512000:
        return [_identity(source) for source in value]
    raise MissingEvidence('Require a reviewed program or bounded explicit program list')
