"""
SCScore-based synthetic complexity and simplicity scoring.

Uses the pretrained SCScore model by Coley et al.
Source: https://github.com/connorcoley/scscore
License: MIT
"""

from functools import lru_cache
from typing import Optional

from scscore.standalone_model_numpy import SCScorer


# --- Global singleton (per process) -----------------------------------------

_SCORER: Optional[SCScorer] = None


def _get_scorer() -> SCScorer:
    """
    Lazily initialize and return the SCScorer singleton.

    This ensures:
    - model weights are loaded once per process
    - safe behavior in Celery workers
    """
    global _SCORER
    if _SCORER is None:
        scorer = SCScorer()
        scorer.restore()   # loads pretrained numpy weights
        _SCORER = scorer
    return _SCORER


# --- Public API -------------------------------------------------------------

@lru_cache(maxsize=100_000)
def get_scscore(smiles: str) -> float:
    """
    Return the SCScore for a molecule.

    Parameters
    ----------
    smiles : str
        Canonical (or at least valid) SMILES.

    Returns
    -------
    float
        SCScore in the range [1.0, 5.0]
    """
    if not smiles:
        return 5.0  # treat empty as maximally complex

    scorer = _get_scorer()
    _, score = scorer.get_score_from_smi(smiles)
    return float(score.item())


def simplicity_score_from_scscore(sc: float) -> float:
    """
    Convert SCScore to simplicity score.

    s(X) = 1 - (SC(X) - 1) / 4

    Maps:
        SCScore = 1 -> simplicity = 1.0 (very simple)
        SCScore = 5 -> simplicity = 0.0 (very complex)
    """
    return max(0.0, min(1.0, 1.0 - (sc - 1.0) / 4.0))


def simplicity(smiles: str) -> float:
    """
    Convenience wrapper: SMILES -> simplicity score.

    Equivalent to:
        simplicity_score_from_scscore(get_scscore(smiles))
    """
    return simplicity_score_from_scscore(get_scscore(smiles))
