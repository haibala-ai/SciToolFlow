"""Local author DeepTMHMM2 replacement for an upstream KG-only DeepTMHMM tool."""
from src.utils.paths import local_root, artifacts_root
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = local_root()


def predict_deeptmhmm(sequence: str):
    """Author DeepTMHMM2 five-model ensembles with local ESM2: topology/membrane prediction; version differs from DeepTMHMM1."""
    import numpy as np
    from tools.runtime.config import Config
    sequence = "".join(sequence.split()).upper()
    if not 1 <= len(sequence) <= 1022 or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
        raise ValueError("Require 1..1022 canonical amino acids")
    source = ROOT / "external_sources/DeepTMHMM2"
    backbone = ROOT / "models/torch_cache/hub/checkpoints"
    for name in ["esm2_t33_650M_UR50D.pt", "esm2_t33_650M_UR50D-contact-regression.pt"]:
        if not (backbone / name).is_file():
            raise FileNotFoundError("Required local ESM2 resource: " + str(backbone / name))
    os.environ["TORCH_HOME"] = str(ROOT / "models/torch_cache")
    sys.path.insert(0, str(source))
    from deeptmhmm2_predictor import DeepTMHMM2
    from deeptmhmm2_predictor.constants import MEMBRANE_TYPE_NAMES
    from tools.implementations.biology.model_cache import cached_resource, checkpoint_version, inference_lock
    model = cached_resource("deeptmhmm2", Config().DEEPTMHMM_MODEL_PATH,
                            lambda: DeepTMHMM2(model_dir=Config().DEEPTMHMM_MODEL_PATH, device="cpu", num_threads=4),
                            ("cpu", 4, checkpoint_version(backbone)))
    with inference_lock(model):
        predictions = model.predict({"input": sequence}, progress_bar=False, compute_marginals=False)
    prediction = predictions[0]
    if prediction.sequence != sequence or len(prediction.topology_string) != len(sequence):
        raise RuntimeError("Prediction sequence/topology length mismatch")
    probabilities = prediction.membrane_types_probabilities
    if probabilities.ndim != 1 or len(probabilities) <= max(MEMBRANE_TYPE_NAMES) or not np.isfinite(probabilities).all() or np.any(probabilities < 0) or np.any(probabilities > 1):
        raise RuntimeError("Invalid membrane probabilities for the author's supported label indices")
    directory = artifacts_root() / ("deeptmhmm2_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    predictions.to_json(directory / "predictions.json")
    predictions.to_3line(directory / "predicted_topologies.3line")
    predictions.to_gff3(directory / "TMRs.gff3")
    predictions.to_memtype_tsv(directory / "membrane_types.tsv")
    manifest = json.loads((ROOT / "provenance/deeptmhmm2_source_weights_verified.json").read_text())
    return json.dumps({"source": "fteufel/DeepTMHMM2", "source_revision": manifest["revision"],
                       "model_version": 2, "replaces_KG_node": "DeepTMHMM", "sequence": sequence,
                       "prediction": prediction.to_dict(), "artifact_directory": str(directory),
                       "supported_membrane_probability_labels": MEMBRANE_TYPE_NAMES,
                       "segment_coordinate_convention": "one-based inclusive, author output",
                       "checkpoint_ensembles": {"topology": 5, "membrane_type": 5},
                       "backbone": "author-specified ESM2 t33 650M UR50D", "device": "cpu",
                       "experimental_accuracy_verified": False})
