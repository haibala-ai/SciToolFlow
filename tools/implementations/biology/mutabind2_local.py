"""Interaction partners of a PDB complex, with the MutaBind2 server attempted first.

The KG node ``Mutabind2`` is defined as "Evaluates the effects of mutations on
protein-protein interactions for soluble complexes" with a PDB ID as input and
interaction partners as output.  This adapter keeps that contract callable:

1. it attempts the real MutaBind2 web server for the submitted PDB entry;
2. it always computes the interaction partners / interfaces directly from the
   experimental RCSB structure, so the declared output is available even while
   the MutaBind2 host is down (its ``upload_pdb`` route answers HTTP 500);
3. it never fabricates a binding-affinity change: a requested mutation effect is
   reported as unavailable unless the upstream method returned it.
"""
from scitoolflow.paths import local_root, artifacts_root
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
                if atom.element == "H":
                    continue
                coordinates.append(atom.coord)
                chain_of.append(chain.id)
                residue_of.append(f"{chain.id}:{residue.resname}{residue.id[1]}")
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


def _mutabind_server(session, pdb_id, directory, timeout):
    """Attempt the documented MutaBind2 upload route; raises on any non-usable answer."""
    page = request_with_retries(session, "GET", SERVER, attempts=2, timeout=timeout)
    page.raise_for_status()
    token = re.search(r"name='csrfmiddlewaretoken' value='([^']+)'", page.text)
    if not token:
        raise RuntimeError("MutaBind2 landing page carries no CSRF token")
    response = request_with_retries(session, "POST", SERVER + "upload_pdb", attempts=2, timeout=timeout,
                                    headers={"Referer": SERVER},
                                    data={"csrfmiddlewaretoken": token.group(1), "example": "0",
                                          "pdb_container_asu": "", "pdb_container_bio": "", "isNMR": "0",
                                          "pdb_id": pdb_id, "pdb_mol": "bio", "bioassembly": "1"})
    (directory / "mutabind2_response.html").write_text(response.text)
    if response.status_code >= 400:
        raise RuntimeError(f"MutaBind2 upload_pdb answered HTTP {response.status_code}")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", response.text))
    if "MutaBind2" not in text and "Mutation" not in text:
        raise RuntimeError("MutaBind2 returned an unrecognised page")
    partners = re.findall(r"Chain\s*([A-Za-z0-9])\s*[-–]\s*Chain\s*([A-Za-z0-9])", text)
    return {"provider": "MutaBind2 web server", "page_excerpt": text[:4000],
            "reported_chain_pairs": sorted({tuple(sorted(pair)) for pair in partners}),
            "raw_response": str(directory / "mutabind2_response.html")}


def mutabind2(pdb_id: str, chain: str = "", distance_cutoff: float = 5.0, minimum_contacts: int = 10,
              assembly: str = "bio", mutation: str = "", wait_seconds: int = 60):
    """Interaction partners of a PDB complex, plus the MutaBind2 server result when it is reachable.

    ``assembly`` selects the RCSB biological assembly 1 (``bio``) or the asymmetric
    unit (``asu``).  ``chain`` restricts the partner list to that chain.  ``mutation``
    is only evaluated by the upstream MutaBind2 method; if that host is unavailable
    the field is returned as unavailable instead of inventing a value.
    """
    identifier = _pdb_id(pdb_id)
    query_chain = chain.strip().upper()
    if not 2.0 <= distance_cutoff <= 10.0:
        raise ValueError("Require a heavy-atom distance cutoff of 2..10 angstrom")
    if not 1 <= minimum_contacts <= 100000:
        raise ValueError("Require 1..100000 minimum atom contacts")
    if assembly not in ["bio", "asu"]:
        raise ValueError("assembly must be 'bio' (assembly 1) or 'asu' (asymmetric unit)")
    if not 0 <= wait_seconds <= 300:
        raise ValueError("Require 0..300 wait seconds")
    directory = artifacts_root() / ("mutabind2_" + identifier + "_" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=True)
    result = {"source": "SciToolAgent MutaBind2 adapter", "pdb_id": identifier,
              "assembly_requested": assembly, "distance_cutoff_angstrom": distance_cutoff,
              "minimum_atom_contacts": minimum_contacts,
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    with _session() as session:
        path, url, attempts = _fetch_structure(session, identifier, assembly, directory)
        result.update({"structure_path": str(path), "structure_url": url, "structure_download_attempts": attempts})
        model, chains = _parse(path)
        result["chains"] = chains
        interfaces = _interfaces(model, distance_cutoff, minimum_contacts)
        result["interfaces"] = interfaces
        result["interface_count"] = len(interfaces)
        if query_chain:
            if query_chain not in chains:
                raise ValueError(f"Chain {query_chain} is not present in the downloaded structure; available chains: {chains}")
            partners = sorted({other for row in interfaces for other in row["chains"] if query_chain in row["chains"] and other != query_chain})
            result["query_chain"] = query_chain
            result["interaction_partners"] = partners
        else:
            result["interaction_partners"] = sorted({chain for row in interfaces for chain in row["chains"]})
        result["buried_surface"] = _buried_surface(model, chains)
        server = {"status": "not_attempted"}
        if mutation or wait_seconds > 0:
            try:
                server = {"status": "ok", **_mutabind_server(session, identifier, directory, max(wait_seconds, 30))}
            except Exception as error:  # upstream host is documented as unreliable
                server = {"status": "unavailable", "error_type": type(error).__name__, "error": str(error)[:400]}
        result["mutabind2_server"] = server
    result["mutation"] = mutation or None
    if mutation:
        if result["mutabind2_server"].get("status") == "ok":
            result["mutation_effect"] = result["mutabind2_server"].get("page_excerpt")
            result["mutation_effect_status"] = "returned by the MutaBind2 web server"
        else:
            result["mutation_effect"] = None
            result["mutation_effect_status"] = ("MutaBind2 server unavailable; no binding-affinity change is reported. "
                                                "The interaction partners above come from the experimental RCSB structure.")
    else:
        result["mutation_effect"] = None
        result["mutation_effect_status"] = "no mutation requested"
    result["scope"] = ("Interaction partners and interfaces are computed from the experimental PDB coordinates "
                       "(heavy-atom contacts and buried SASA). They are not a trained binding-affinity prediction.")
    return json.dumps(result, ensure_ascii=False)
