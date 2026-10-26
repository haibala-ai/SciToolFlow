"""Official ESMFold v1 inference on local CPU; reported confidence is not measured accuracy."""
from src.utils.paths import local_root, artifacts_root
import json
from pathlib import Path
import uuid

ROOT = local_root()


def _prediction(sequence):
    import numpy as np
    import torch
    from transformers import EsmForProteinFolding
    from tools.runtime.config import Config
    from tools.implementations.adapters import _peptide
    sequence = _peptide(sequence)
    if len(sequence) > 1024:
        raise ValueError("This local ESMFold adapter supports at most 1024 residues per call")
    torch.set_num_threads(4)
    from tools.implementations.biology.model_cache import cached_resource, inference_lock
    def load():
        model = EsmForProteinFolding.from_pretrained(Config().ESMFOLD_MODEL_PATH, local_files_only=True)
        model.esm.float()  # Preserve original CPU precision/settings.
        model.trunk.set_chunk_size(32)
        model.eval()
        return model
    model = cached_resource("esmfold_v1", Config().ESMFOLD_MODEL_PATH, load, ("cpu", "float_encoder", 32))
    with inference_lock(model), torch.inference_mode():
        prediction = model.infer(sequence)
    # Transformers 4.57 categorical_lddt returns a mean in [0,1]. The
    # conventional pLDDT/B-factor display uses [0,100]; normalize before PDB export.
    raw_confidence = prediction["plddt"]
    if not torch.isfinite(raw_confidence).all() or bool((raw_confidence < 0).any()) or bool((raw_confidence > 1).any()):
        raise RuntimeError("Unexpected ESMFold confidence scale; expected Transformers' [0,1] categorical mean")
    prediction["plddt"] = raw_confidence * 100
    pdb = model.output_to_pdb(prediction)[0]
    residues = [line for line in pdb.splitlines() if line.startswith("ATOM  ") and line[12:16].strip() == "CA"]
    if len(residues) != len(sequence):
        raise RuntimeError("ESMFold PDB residue count does not match the sequence")
    xyz = np.asarray([[float(line[start:start + 8]) for start in [30, 38, 46]] for line in residues])
    confidence = np.asarray([float(line[60:66]) for line in residues])
    if not np.isfinite(xyz).all() or not np.isfinite(confidence).all() or ((confidence < 0) | (confidence > 100)).any():
        raise RuntimeError("ESMFold produced invalid coordinates or confidence values")
    directory = artifacts_root()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("esmfold_" + uuid.uuid4().hex + ".pdb")
    path.write_text(pdb)
    return {"source": "facebook/esmfold_v1 local official checkpoint", "sequence": sequence,
            "residues": len(residues), "pdb_path": str(path), "mean_pLDDT_confidence": float(confidence.mean()),
            "pLDDT_per_residue": confidence.tolist(), "confidence_units": "pLDDT on the 0-100 scale",
            "experimental_accuracy_measured": False, "device": "cpu"}


def sequence_to_pdb(sequence: str):
    """Predict a local ESMFold protein PDB and disclose per-residue pLDDT confidence."""
    return json.dumps(_prediction(sequence))


def residue_confidence(sequence: str):
    """Compute predicted residue pLDDT confidence from local ESMFold; not empirical residue accuracy."""
    return json.dumps(_prediction(sequence))
