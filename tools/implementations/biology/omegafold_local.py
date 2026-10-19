"""Invoke version-pinned author OmegaFold code and weights locally with bounded resources."""
from scitoolflow.paths import local_root, artifacts_root
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = local_root()


def fold_protein(sequence: str, num_cycle: int = 10):
    """Predict a PDB with official OmegaFold model 1; default ten cycles, small subbatches, local checkpoint."""
    from tools.implementations.adapters import _peptide
    sequence = _peptide(sequence)
    if len(sequence) > 1024 or not 1 <= num_cycle <= 20:
        raise ValueError("Local OmegaFold supports at most 1024 residues and 1-20 cycles")
    os.environ["CUDA_VISIBLE_DEVICES"] = os.getenv("SCITOOL_FOLD_GPU", "7")
    import torch
    torch.set_num_threads(4)
    device = "cpu"
    if torch.cuda.is_available():
        free, _ = torch.cuda.mem_get_info(0)
        if free >= 6 * 1024**3:
            device = "cuda:0"
    directory = artifacts_root() / ("omegafold_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    fasta = directory / "input.fasta"
    fasta.write_text(">prediction\n" + sequence + "\n")
    source = ROOT / "external_sources/OmegaFold"
    from tools.runtime.config import Config
    checkpoint = Path(Config().OMEGAFOLD_MODEL_PATH) / "release1.pt"
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="4", MKL_NUM_THREADS="4", PYTHONPATH=str(source))
    command = [sys.executable, str(source / "main.py"), str(fasta), str(directory),
               "--weights_file", str(checkpoint), "--model", "1", "--num_cycle", str(num_cycle),
               "--subbatch_size", "16", "--device", device]
    with (directory / "inference.log").open("w") as log:
        completed = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
    if completed.returncode:
        raise RuntimeError("OmegaFold inference failed; diagnostic log: " + str(directory / "inference.log"))
    pdb = directory / "prediction.pdb"
    if not pdb.is_file():
        raise RuntimeError("OmegaFold produced no PDB; diagnostic log: " + str(directory / "inference.log"))
    import numpy as np
    residues = [line for line in pdb.read_text().splitlines() if line.startswith("ATOM  ") and line[12:16].strip() == "CA"]
    coords = np.asarray([[float(line[start:start + 8]) for start in [30, 38, 46]] for line in residues])
    if len(residues) != len(sequence) or not np.isfinite(coords).all():
        raise RuntimeError("OmegaFold PDB contains an incorrect residue count or invalid coordinates")
    confidence = [float(line[60:66]) for line in residues]
    if any(not np.isfinite(value) or not 0 <= value <= 100 for value in confidence):
        raise RuntimeError("Invalid OmegaFold confidence values")
    return json.dumps({"source": "HeliXonProtein/OmegaFold official model 1", "sequence": sequence,
                       "pdb_path": str(pdb), "residues": len(residues), "num_cycle": num_cycle,
                       "subbatch_size": 16, "device": device, "mean_confidence_0_to_100": float(np.mean(confidence)),
                       "experimental_accuracy_measured": False, "inference_log": str(directory / "inference.log")})
