"""Actual IMP NMT prediction, preserving taxonomy and cleavage choices."""
from src.utils.paths import local_root, artifacts_root
import json
from pathlib import Path
import uuid
import requests
from bs4 import BeautifulSoup

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()


def predict_myristoylation(sequence: str, fungi: bool = False, internal_glycines: bool = True):
    """IMP NMT myristoylation predictor; eukaryota/virus or fungal parameter set and explicit internal-glycine option."""
    if type(fungi) is not bool or type(internal_glycines) is not bool:
        raise ValueError("fungi and internal_glycines must be booleans")
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    sequence = canonical_sequence(sequence, maximum=10000)
    if not 1 <= len(sequence) <= 10000 or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
        raise ValueError("Require 1..10000 canonical amino acids")
    with requests.Session() as session:
        response = request_with_retries(session, "POST", "https://mendel.imp.ac.at/myristate/cgi-bin/myr_pred.cgi", data={
            "LSet": "2" if fungi else "1", "Cleavage": "3" if internal_glycines else "4",
            "Sequence": ">ToolKG_input\n" + sequence + "\n", "RSet": "movie"}, timeout=60)
    response.raise_for_status()
    directory = artifacts_root() / ("myristoylation_" + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    path = directory / "response.html"
    path.write_text(response.text)
    text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
    if "Prediction of potential Myristoylation by NMT" not in text or "Your query:" not in text:
        raise RuntimeError("Service did not return the expected prediction; raw response: " + str(path))
    if sequence not in "".join(text.split()):
        raise RuntimeError("Service report does not include the submitted amino acid sequence")
    return json.dumps({"source": "IMP NMT Myristoylation Predictor", "sequence": sequence, "completed": True,
                       "parameter_set": "fungi" if fungi else "eukaryota without fungi and their viruses",
                       "internal_glycines": internal_glycines, "source_report": text, "raw_response": str(path),
                       "experimental_modification_verified": False})
