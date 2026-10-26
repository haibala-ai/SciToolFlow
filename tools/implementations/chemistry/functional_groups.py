"""Fixed, cached SMARTS functional-group inspection without service/model imports."""

from functools import lru_cache
from rdkit import Chem

_FUNCTIONAL_GROUP_PATTERNS = {'furan': 'o1cccc1', 'aldehydes': ' [CX3H1](=O)[#6]', 'esters': ' [#6][CX3](=O)[OX2H0][#6]', 'ketones': ' [#6][CX3](=O)[#6]', 'amides': ' C(=O)-N', 'thiol groups': ' [SH]', 'alcohol groups': '[CX4][OX2H]', 'methylamide': '*-[N;D2]-[C;D3](=O)-[C;D1;H3]', 'carboxylic acids': '[CX3](=O)[OX2H1]', 'carbonyl methylester': '*-C(=O)[O;D2]-[C;D1;H3]', 'terminal aldehyde': '[CX3H1](=O)[#6]', 'amide': '*-C(=O)-[N;D1]', 'carbonyl methyl': '*-C(=O)-[C;D1;H3]', 'isocyanate': '*-[N;D2]=[C;D2]=[O;D1]', 'isothiocyanate': '*-[N;D2]=[C;D2]=[S;D1]', 'nitro': '*-[N;D3](=[O;D1])[O;D1]', 'nitroso': '*-[N;R0]=[O;D1]', 'oximes': '*=[N;R0]-[O;D1]', 'Imines': '*-[N;R0]=[C;D1;H2]', 'terminal azo': '*-[N;D2]=[N;D2]-[C;D1;H3]', 'hydrazines': '[NX3][NX3]', 'diazo': '[C]=[N+]=[N-]', 'cyano': '*-[C;D2]#[N;D1]', 'primary sulfonamide': '*-[S;D4](=[O;D1])(=[O;D1])-[N;D1]', 'methyl sulfonamide': '*-[N;D2]-[S;D4](=[O;D1])(=[O;D1])-[C;D1;H3]', 'sulfonic acid': '*-[S;D4](=O)(=O)-[O;D1]', 'methyl ester sulfonyl': '*-[S;D4](=O)(=O)-[O;D2]-[C;D1;H3]', 'methyl sulfonyl': '*-[S;D4](=O)(=O)-[C;D1;H3]', 'sulfonyl chloride': '*-[S;D4](=O)(=O)-[Cl]', 'methyl sulfinyl': '*-[S;D3](=O)-[C;D1]', 'methyl thio': '*-[S;D2]-[C;D1;H3]', 'thiols': '*-[S;D1]', 'thio carbonyls': '*=[S;D1]', 'halogens': '*-[#9,#17,#35,#53]', 't-butyl': '*-[C;D4]([C;D1])([C;D1])-[C;D1]', 'tri fluoromethyl': '*-[C;D4](F)(F)F', 'acetylenes': '*-[C;D2]#[C;D1;H]', 'cyclopropyl': '*-[C;D3]1-[C;D2]-[C;D2]1', 'ethoxy': '*-[O;D2]-[C;D2]-[C;D1;H3]', 'methoxy': '*-[O;D2]-[C;D1;H3]', 'side-chain hydroxyls': '[CX4][OX2H]', 'carbonyl groups': '[CX3]=[OX1]', 'primary amines': '[NX3H2;!$(N-C(=O));!$(N-S(=O)(=O))][#6]', 'nitriles': '*#[N;D1]'}

@lru_cache(maxsize=1)
def _functional_group_queries():
    by_pattern = {}
    for label, smarts in _FUNCTIONAL_GROUP_PATTERNS.items():
        smarts = smarts.strip()
        if smarts not in by_pattern:
            pattern = Chem.MolFromSmarts(smarts)
            if pattern is None:
                raise RuntimeError('Invalid internal functional-group SMARTS: ' + label)
            by_pattern[smarts] = [label, [], pattern]
        else:
            by_pattern[smarts][1].append(label)
    return tuple(((name, tuple(aliases), smarts, pattern) for smarts, (name, aliases, pattern) in by_pattern.items()))

def list_functional_groups(smiles: str) -> dict:
    """Return a nonexhaustive named SMARTS functional-group screen with indexed evidence.

    Parse the molecule once and compile/cache the fixed query library once.
    Exact duplicate SMARTS labels are aliases within one group; different patterns
    remain separate and can overlap. No fragment removal or reaction inference.
    Atom indices use the hydrogen-suppressed graph; matching is chirality-agnostic.
    An empty group list is a successful negative screen, not proof of absence of
    all chemically possible functional groups.
    """
    from .core import molecule
    import hashlib
    import json
    mol = molecule(smiles, 'remove')
    groups = []
    for name, aliases, smarts, pattern in _functional_group_queries():
        matches = mol.GetSubstructMatches(pattern, uniquify=True, useChirality=False)
        if matches:
            groups.append({'name': name, 'aliases': list(aliases), 'smarts': smarts, 'matches': [list(m) for m in matches], 'match_count': len(matches)})
    return {'groups': groups, 'canonical_smiles': Chem.MolToSmiles(mol), 'library_sha256': hashlib.sha256(json.dumps(_FUNCTIONAL_GROUP_PATTERNS, sort_keys=True).encode()).hexdigest(), 'operation_counts': {'molecule_parses': 1, 'unique_patterns': len(_functional_group_queries())}, 'limitations': ['Fixed nonexhaustive overlapping SMARTS library', 'No assay evidence']}
