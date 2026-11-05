"""Hash the delivered special suite, excluding its own manifest and caches."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parents[1]

def freeze():
    files={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(BASE.rglob('*'))
        if p.is_file() and p!=BASE/'manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc' and not any(x.startswith('.') for x in p.relative_to(BASE).parts)}
    (BASE/'manifest.json').write_text(json.dumps({'suite':'scimas-special-100-v2','files':files},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'suite':'scimas-special-100-v2','hashed_files':len(files)}))
if __name__=='__main__':freeze()
