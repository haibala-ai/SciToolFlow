"""One explicit Chroma generation primitive with optional exact CATH condition."""
import json
import uuid

from src.utils.paths import artifacts_root


def design_protein_chroma(length: int, cath_class: str | None = None,
                          steps: int = 300, seed: int | None = None):
    """Sample one chain with Chroma, optionally class-conditioned.

    cath_class is null (unconditioned), '1', '2.40' or '3.30'. These are exact
    model classifier labels; 2.40 and 3.30 are particular CATH subclasses, not
    guarantees of every beta or alpha/beta fold. Returns sequence and a new PDB
    artifact. This is a stochastic learned design, not an experimentally
    validated fold, biological function or safety claim. Requires configured
    Chroma credentials/weights. Resource and model failures propagate.
    """
    if type(length) is not int or not 1 <= length <= 1000:
        raise ValueError("length must be integer1..1000")
    if cath_class is not None and cath_class not in {"1", "2.40", "3.30"}:
        raise ValueError("cath_class must be null, '1', '2.40' or '3.30'")
    if type(steps) is not int or not 1 <= steps <= 1000:
        raise ValueError("steps must be integer1..1000")
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 2147483647):
        raise ValueError("seed must be null or integer0..2147483647")
    from tools.implementations.biology import protein_tools as backend
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    backend._load_chroma_dependencies()
    from contextlib import nullcontext
    with backend.torch.random.fork_rng(devices=[]) if seed is not None else nullcontext():
        if seed is not None:
            backend.torch.manual_seed(seed)
        model = backend.Chroma(device="cpu")
        condition = None
        if cath_class is not None:
            classifier = backend.graph_classifier.load_model("named:public", device="cpu")
            condition = backend.conditioners.ProClassConditioner("cath", cath_class, model=classifier)
        protein = model.sample(chain_lengths=[length], steps=steps, conditioner=condition)
        sequence = canonical_sequence(protein.sequence(), maximum=1000)
        if len(sequence) != length:
            raise RuntimeError("Chroma returned an unexpected sequence length")
        directory = artifacts_root() / ("chroma_" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        path = directory / "design.pdb"
        protein.to(str(path))
    return json.dumps({"method": "Chroma learned generative model", "device": "cpu",
                       "length": length, "sequence": sequence, "pdb_path": str(path),
                       "cath_condition": cath_class, "steps": steps, "seed": seed,
                       "condition_satisfied_experimentally": False,
                       "experimental_validation": False})
