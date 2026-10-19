"""Direct CPU calls to the official RXN Sandbox, without a hosted account or broker."""

from scitoolflow.paths import local_root, artifacts_root
import json
from pathlib import Path
import sys

ROOT = local_root()


def _runtime():
    import torch

    torch.set_num_threads(4)
    sys.path.insert(0, str(ROOT / "external_sources/rxn-sandbox/worker"))
    from tasks import product_prediction_body, retro_prediction_tree_body

    weights = ROOT / "models/rxn-sandbox/models"
    options = {
        "ckpt_forward_path": str(weights / "forward/Pistachio2025Q2-Forward.ckpt"),
        "ckpt_retro_path": str(weights / "retrosynthesis/Pistachio2025Q2-Retro.ckpt"),
        "vocab_path": str(
            ROOT / "external_sources/rxn-sandbox/vocab/Pistachio2025Q2.txt"
        ),
        "device": "cpu",
    }
    return product_prediction_body, retro_prediction_tree_body, options


def predict_reaction(reactants: str):
    """Predict products locally with the official 2025Q2 RXN forward model."""
    forward, _, options = _runtime()
    predictions = forward([reactants], topn=1, num_beams=3, **options)
    if not predictions:
        raise ValueError("RXN returned no forward prediction")
    return json.dumps(
        {
            "provider": "official RXN Sandbox",
            "model": "Pistachio2025Q2-Forward",
            "input": reactants,
            "predictions": predictions,
        }
    )


def predict_retrosynthetic_pathway(product: str, max_depth: int = 3):
    """Return locally predicted multi-step routes; an empty result is labelled explicitly."""
    if not 1 <= max_depth <= 4:
        raise ValueError("max_depth must be between 1 and 4")
    _, retro, options = _runtime()
    routes = retro(
        product, topn=3, num_beams=3, max_depth=max_depth, beam_width=2, **options
    )
    expanded = [
        route for route in routes if route.get("steps", 0) > 0 and route.get("arcs")
    ]
    return json.dumps(
        {
            "provider": "official RXN Sandbox",
            "model": "Pistachio2025Q2-Retro",
            "input": product,
            "max_depth": max_depth,
            "routes": expanded,
            "diagnostic_search_states": routes,
            "prediction_status": (
                "routes_generated" if expanded else "no_accepted_routes"
            ),
        }
    )


def predict_reaction_properties(reactions: list):
    """Compute local RXNMapper atom mappings and confidence; the upstream tool also fixed atom-mapping mode."""
    if (
        not isinstance(reactions, list)
        or not reactions
        or any(not isinstance(item, str) or ">>" not in item for item in reactions)
    ):
        raise ValueError("reactions must be a non-empty list of reaction SMILES")
    import torch

    torch.set_num_threads(4)
    from rxnmapper import RXNMapper

    mappings = RXNMapper().get_attention_guided_atom_maps(reactions)
    return json.dumps(
        {
            "provider": "local RXNMapper",
            "property_type": "atom_to_atom_mapping",
            "input": reactions,
            "mappings": mappings,
        }
    )
