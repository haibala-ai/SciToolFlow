"""Versioned local RXN inference; bounded inputs and process-local model reuse."""

from functools import lru_cache
from pathlib import Path
import sys

from src.utils.paths import local_root


@lru_cache(maxsize=1)
def _worker():
    import torch
    torch.set_num_threads(4)
    path = str(local_root() / 'external_sources/rxn-sandbox/worker')
    if path not in sys.path:
        sys.path.insert(0, path)
    import model_loading
    import prediction
    import tasks
    return model_loading, prediction, tasks


@lru_cache(maxsize=4)
def _model(kind, checkpoint, checkpoint_mtime, vocab, vocab_mtime, beams, topn):
    # mtime is part of the cache key: replacing local weights invalidates reuse.
    loading, _, _ = _worker()
    loader = loading.load_forward_model if kind == 'forward' else loading.load_retro_model
    return loader(ckpt_path=checkpoint, vocab_path=vocab, num_beams=beams, topn=topn, device='cpu')


def _load(kind, beams, topn):
    root = local_root()
    folder = 'forward' if kind == 'forward' else 'retrosynthesis'
    label = 'Forward' if kind == 'forward' else 'Retro'
    checkpoint = root / f'models/rxn-sandbox/models/{folder}/Pistachio2025Q2-{label}.ckpt'
    vocab = root / 'external_sources/rxn-sandbox/vocab/Pistachio2025Q2.txt'
    for path in [checkpoint, vocab]:
        if not path.is_file():
            raise FileNotFoundError('Required RXN resource is absent: ' + str(path))
    return _model(kind, str(checkpoint), checkpoint.stat().st_mtime_ns,
                  str(vocab), vocab.stat().st_mtime_ns, beams, topn)


def _validate_smiles(smiles):
    from .core import molecule
    molecule(smiles, 'remove')


def _validate_tokens(model, records):
    # Worker prediction otherwise truncates encoder input silently at 278 tokens.
    encoded = model.tokenizer(records, truncation=False, padding=False, return_attention_mask=False)
    ids = encoded['input_ids']
    if any(len(row) > 278 for row in ids):
        raise ValueError('RXN encoder input exceeds 278 tokens; it will not be silently truncated')


def predict_reaction_products(reactants: list[str]) -> dict:
    """Predict a batch of 1-32 product records with local Pistachio2025Q2-Forward.

    Every reactant entry is a separate dot-disconnected SMILES record; parse and
    token-length checks precede inference. CPU, num_beams=3, topn=1, worker seed42.
    A single model is loaded/reused per process and the batch is inferred together.
    Returns the actual model predictions, never a reference or fabricated product.
    This differs in model version from the retired hosted IBM RXN service.
    """
    if not isinstance(reactants, list) or not 1 <= len(reactants) <= 32:
        raise ValueError('reactants must contain 1-32 SMILES strings')
    for value in reactants:
        _validate_smiles(value)
    model = _load('forward', 3, 1)
    _validate_tokens(model, reactants)
    _, prediction, _ = _worker()
    predictions = prediction.forward_reaction(smiles_list=reactants, lit=model)
    if not predictions:
        raise ValueError('RXN returned no product predictions')
    return {'provider': 'official RXN Sandbox', 'model': 'Pistachio2025Q2-Forward',
            'inputs': reactants, 'predictions': predictions,
            'protocol': {'device': 'cpu', 'num_beams': 3, 'topn': 1, 'worker_seed': 42},
            'operation_counts': {'batch_records': len(reactants), 'forward_model_instances': 1}}


def predict_reaction(reactants: str):
    'RXNPredict retired: Forward inference is one explicit batch primitive with one loaded model per batch. Use PredictReactionProducts. See the catalog migration feedback for explicit arguments.'
    raise ValueError('RXNPredict retired: Forward inference is one explicit batch primitive with one loaded model per batch. Use PredictReactionProducts. See the catalog migration feedback for explicit arguments.')


def predict_retrosynthetic_pathway(product: str, max_depth: int = 3) -> dict:
    """Search local Pistachio2025Q2-Retro routes with forward-model acceptance evidence.

    CPU, retro topn/beams=3, forward topn/beams=2, beam_width=2, fap=0.6,
    fld=0.2. max_depth is 1-4. Empty accepted routes are reported explicitly,
    including actual diagnostic search states. This is predicted computational
    evidence, not a synthesis execution, feasibility guarantee or dominant route.
    """
    if type(max_depth) is not int or not 1 <= max_depth <= 4:
        raise ValueError('max_depth must be an integer in [1,4]')
    _validate_smiles(product)
    retro = _load('retro', 3, 3)
    forward = _load('forward', 2, 2)
    _validate_tokens(retro, [product])
    _, _, tasks = _worker()
    routes = tasks.retrosynthesis_beam_search(product=product, retro_lit=retro,
            forward_lit=forward, max_steps=max_depth, beam_width=2, fap=0.6, fld=0.2)
    expanded = [route for route in routes if route.get('steps', 0) > 0 and route.get('arcs')]
    return {'provider': 'official RXN Sandbox', 'model': 'Pistachio2025Q2-Retro',
            'input': product, 'max_depth': max_depth, 'routes': expanded,
            'diagnostic_search_states': routes,
            'prediction_status': 'routes_generated' if expanded else 'no_accepted_routes',
            'protocol': {'retro_beams': 3, 'retro_topn': 3, 'forward_beams': 2,
                         'forward_topn': 2, 'beam_width': 2, 'fap': 0.6, 'fld': 0.2}}


@lru_cache(maxsize=1)
def _mapper():
    import torch
    from rxnmapper import RXNMapper
    torch.set_num_threads(4)
    return RXNMapper()


def predict_reaction_properties(reactions: list[str]) -> dict:
    """Return local RXNMapper attention-guided atom maps/confidence for 1-32 explicit reactions.

    Inputs require nonempty parseable reactant and product SMILES separated by one
    >>. This tool reports atom correspondence, not arbitrary physical reaction
    properties, yield or forward product predictions. One mapper is reused per
    process. Missing weights/dependencies or invalid reactions raise errors.
    """
    if not isinstance(reactions, list) or not 1 <= len(reactions) <= 32:
        raise ValueError('reactions must contain 1-32 reaction SMILES strings')
    for reaction in reactions:
        if not isinstance(reaction, str) or reaction.count('>>') != 1:
            raise ValueError('Each reaction must contain exactly one >> separator')
        for side in reaction.split('>>'):
            _validate_smiles(side)
    mappings = _mapper().get_attention_guided_atom_maps(reactions)
    if len(mappings) != len(reactions):
        raise RuntimeError('RXNMapper did not return one mapping per reaction')
    from math import isfinite
    if any(not isfinite(float(m.get('confidence', float('nan')))) for m in mappings):
        raise ValueError('RXNMapper returned a missing/nonfinite confidence')
    return {'provider': 'local RXNMapper', 'property_type': 'atom_to_atom_mapping',
            'input': reactions, 'mappings': mappings,
            'operation_counts': {'batch_records': len(reactions), 'mapper_instances': 1}}
