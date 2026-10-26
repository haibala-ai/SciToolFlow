"""Coordinate contacts and optional SASA; no MutaBind2 mutation prediction.

The old adapter uploaded a structure without submitting its mutation argument.
That route cannot support an affinity-change capability and is retired.
"""
from src.utils.paths import local_root, artifacts_root
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid

import requests

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()
RCSB = "https://files.rcsb.org/download"
SERVER = "https://lilab.jysw.suda.edu.cn/research/mutabind2/"


def _pdb_id(value):
    text = value.strip().upper()
    if not re.fullmatch(r"[0-9][A-Z0-9]{3}", text):
        raise ValueError("Require a four-character PDB identifier")
    return text


def _session():
    session = requests.Session()
    session.trust_env = os.getenv("SCITOOL_MUTABIND_USE_PROXY", "1") == "1"
    session.headers.update({"User-Agent": "SciToolAgent/1.0 (MutaBind2 interface retrieval)"})
    return session


def _fetch_structure(session, pdb_id, assembly, directory):
    """Download the experimental structure; 'bio' prefers assembly 1 when RCSB publishes it."""
    suffixes = [".pdb1", ".pdb"] if assembly == "bio" else [".pdb"]
    attempts = []
    for suffix in suffixes:
        url = f"{RCSB}/{pdb_id}{suffix}"
        try:
            response = request_with_retries(session, "GET", url, timeout=60)
        except requests.exceptions.RequestException as error:
            attempts.append({"url": url, "error": type(error).__name__})
            continue
        if response.status_code == 404:
            attempts.append({"url": url, "http_status": 404})
            continue
        response.raise_for_status()
        path = directory / (pdb_id + suffix)
        path.write_text(response.text)
        return path, url, attempts
    raise RuntimeError(f"RCSB has no downloadable structure for {pdb_id}; attempts: {json.dumps(attempts)}")


def _parse(path):
    from Bio.PDB import PDBParser
    structure = PDBParser(QUIET=True).get_structure(path.stem, str(path))
    model = next(structure.get_models())
    chains = []
    for chain in model:
        residues = [residue for residue in chain if residue.id[0] == " " and any(atom.element != "H" for atom in residue)]
        if residues:
            chains.append(chain.id)
    if len(chains) < 1:
        raise RuntimeError("Downloaded structure contains no protein chains")
    return model, chains


def _interfaces(model, cutoff, minimum_contacts):
    """Chain-chain interfaces from heavy-atom contacts; every residue pair is retained."""
    import numpy as np
    from scipy.spatial import cKDTree
    coordinates, chain_of, residue_of = [], [], []
    for chain in model:
        for residue in chain:
            if residue.id[0] != " ":
                continue
            for atom in residue:
                if atom.element in {"H", "D"}:
                    continue
                coordinates.append(atom.coord)
                chain_of.append(chain.id)
                residue_of.append(f"{chain.id}:{residue.resname}:{residue.id[1]}{residue.id[2].strip()}")
    if not coordinates:
        raise RuntimeError("No heavy atoms found in the structure")
    points = np.asarray(coordinates, dtype=float)
    tree = cKDTree(points)
    pairs = tree.query_pairs(r=float(cutoff), output_type="ndarray")
    contacts = {}
    for first, second in pairs:
        chain_a, chain_b = chain_of[first], chain_of[second]
        if chain_a == chain_b:
            continue
        key = tuple(sorted((chain_a, chain_b)))
        bucket = contacts.setdefault(key, {"atom_contacts": 0, "residue_pairs": set(),
                                           "interface_residues": {chain_a: set(), chain_b: set()}})
        bucket["atom_contacts"] += 1
        bucket["residue_pairs"].add((residue_of[first], residue_of[second]) if chain_a <= chain_b
                                    else (residue_of[second], residue_of[first]))
        bucket["interface_residues"][chain_a].add(residue_of[first])
        bucket["interface_residues"][chain_b].add(residue_of[second])
    interfaces = []
    for (chain_a, chain_b), bucket in sorted(contacts.items()):
        if bucket["atom_contacts"] < minimum_contacts:
            continue
        interfaces.append({"chains": [chain_a, chain_b], "atom_contacts": bucket["atom_contacts"],
                           "residue_pairs": len(bucket["residue_pairs"]),
                           "interface_residues": {chain: sorted(values) for chain, values in bucket["interface_residues"].items()},
                           "interface_residue_counts": {chain: len(values) for chain, values in bucket["interface_residues"].items()}})
    interfaces.sort(key=lambda row: -row["atom_contacts"])
    return interfaces


def _buried_surface(model, chain_ids):
    """Buried solvent-accessible area when the complex has a tractable number of atoms."""
    from Bio.PDB.SASA import ShrakeRupley
    atoms = sum(1 for chain in model for residue in chain if residue.id[0] == " " for atom in residue if atom.element != "H")
    if atoms > 6000:
        return {"computed": False, "reason": f"{atoms} heavy atoms exceed the 6000-atom SASA budget"}
    calculator = ShrakeRupley()
    calculator.compute(model, level="C")
    complex_area = {chain.id: float(chain.sasa) for chain in model if chain.id in chain_ids}
    # ShrakeRupley only sees the atoms of the entity it is given, so computing on a
    # single chain yields that chain's isolated (unburied) accessible area.
    isolated = {}
    for chain in model:
        if chain.id not in chain_ids:
            continue
        calculator.compute(chain, level="C")
        isolated[chain.id] = float(chain.sasa)
    calculator.compute(model, level="C")  # restore the complex values on the model
    buried = sum(isolated.values()) - sum(complex_area.values())
    return {"computed": True, "units": "angstrom^2", "buried_area": buried,
            "isolated_chain_area": isolated, "complex_chain_area": complex_area}


def pdb_interface_contacts(structure_file: str, model_id: int = 0,
                           distance_cutoff: float = 5.0, minimum_contacts: int = 10,
                           compute_buried_surface: bool = False):
    """Protein chain contacts in one explicit PDB model; optional buried SASA.

    Uses standard amino-acid ATOM residues only, selected Biopython alternate
    locations, and heavy atoms (H/D excluded). No assembly is inferred or
    downloaded. Coordinates and molecule/chain identity come from caller's
    file; contacts do not prove a physiological interaction. No mutation,
    affinity, MutaBind2 model or experimental-status inference is performed.
    Buried area is sum(isolated chain SASA)-complex SASA (no division by two).
    """
    import hashlib
    import io
    import math
    from Bio.PDB import PDBParser, is_aa
    from tools.implementations.general.research_data import _public_source_path
    if type(model_id) is not int or model_id < 0:
        raise ValueError("model_id must be a nonnegative integer")
    if type(distance_cutoff) not in (int, float) or not math.isfinite(distance_cutoff) or not 2 <= distance_cutoff <= 10:
        raise ValueError("distance_cutoff must be finite, 2..10 angstrom")
    if type(minimum_contacts) is not int or not 1 <= minimum_contacts <= 100000:
        raise ValueError("minimum_contacts must be integer1..100000")
    if type(compute_buried_surface) is not bool:
        raise ValueError("compute_buried_surface must be a strict Boolean")
    path = _public_source_path(structure_file)
    raw = path.read_bytes()
    if not raw or len(raw) > 10000000:
        raise ValueError("Require nonempty plain PDB of at most10000000bytes")
    structure = PDBParser(QUIET=True, PERMISSIVE=False).get_structure("input", io.StringIO(raw.decode("ascii")))
    if model_id not in structure:
        raise ValueError("Requested parsed model_id absent")
    model = structure[model_id]
    for chain in list(model):
        for residue in list(chain):
            if residue.id[0] != " " or not is_aa(residue, standard=True):
                chain.detach_child(residue.id)
                continue
            for atom in list(residue):
                if atom.element in {"H", "D"}:
                    residue.detach_child(atom.id)
                elif not all(math.isfinite(float(v)) for v in atom.coord):
                    raise ValueError("Nonfinite selected protein coordinates")
            if not len(residue):
                chain.detach_child(residue.id)
        if not len(chain):
            model.detach_child(chain.id)
    atoms = sum(1 for _ in model.get_atoms())
    chains = [chain.id for chain in model]
    if not atoms or atoms > 12000:
        raise ValueError("Require1..12000 selected standard protein heavy atoms")
    interfaces = _interfaces(model, distance_cutoff, minimum_contacts)
    area = _buried_surface(model, chains) if compute_buried_surface else {"computed": False, "reason": "not requested"}
    return json.dumps({"method": "heavy-atom distance contacts; optional Shrake-Rupley SASA",
                       "source_sha256": hashlib.sha256(raw).hexdigest(), "model_id": model_id,
                       "chains": chains, "selected_atom_count": atoms,
                       "distance_cutoff_angstrom": distance_cutoff, "minimum_atom_contacts": minimum_contacts,
                       "interfaces": interfaces, "interface_count": len(interfaces), "buried_surface": area,
                       "atom_scope": "standard amino-acid ATOM heavy atoms only; no H/D, hetero/water or missing-atom completion",
                       "altloc_policy": "Biopython selected highest occupancy; ties follow source order",
                       "assembly_policy": "caller-supplied model only; no biological assembly inference",
                       "binding_affinity_or_mutation_prediction": False}, allow_nan=False)


def mutabind2(pdb_id: str, chain: str = "", distance_cutoff: float = 5.0, minimum_contacts: int = 10,
              assembly: str = "bio", mutation: str = "", wait_seconds: int = 60):
    """Retired unsupported mutation-model entrypoint; use explicit contact analysis."""
    raise NotImplementedError("Mutabind2 is retired: no mutation-specific model was implemented; use PDBInterfaceContacts for coordinate geometry only")
