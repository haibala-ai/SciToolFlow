"""Real NeEMO stability jobs: structure preparation, then mutation stability changes.

The KG node ``NeEMO`` ("Evaluate changes in protein stability caused by amino acid
(AA) mutations", input PDB ID, output processed structure) maps onto the public
NeEMO service workflow:

1. ``NeemoProcess.jsp`` accepts a PDB code and chain and returns a job PID after
   building the mutated-residue template and the relative-accessibility table;
2. the finished status page carries NeEMO's processed structure (chain, sequence
   and per-residue relative accessibility);
3. ``NeEMO.jsp`` accepts ``mutationtext`` such as ``T1A#`` and returns the
   stability change in kcal/mol.

A persisted PID lets a slow upstream job be resumed by repeating the same call.
When the upstream has not finished inside the caller's budget, an explicitly
labelled local structure preparation is returned instead of a fabricated
stability value.
"""
from scitoolflow.paths import local_root, artifacts_root
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

import requests

from tools.implementations.shared.http_retry import request_with_retries

ROOT = local_root()
SUBMIT = "http://old.protein.bio.unipd.it/neemo/NeemoProcess.jsp"
MUTATE = "http://protein.bio.unipd.it/neemo/NeEMO.jsp"
STATUS = "http://old.protein.bio.unipd.it/neemo/work/pid_{pid}/neemo.html"
RCSB = "https://files.rcsb.org/download"

MAX_ASA = {"A": 129, "R": 274, "N": 195, "D": 193, "C": 167, "E": 223, "Q": 225, "G": 104,
           "H": 224, "I": 197, "L": 201, "K": 236, "M": 224, "F": 240, "P": 159, "S": 155,
           "T": 172, "W": 285, "Y": 263, "V": 174}
STANDARD_THREE = {"ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
                  "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL"}


def _pdb_id(value):
    text = value.strip().upper()
    if not re.fullmatch(r"[0-9][A-Z0-9]{3}", text):
        raise ValueError("Require a four-character PDB identifier")
    return text


def _session():
    session = requests.Session()
    session.trust_env = os.getenv("SCITOOL_NEEMO_USE_PROXY", "1") == "1"
    session.headers.update({"User-Agent": "SciToolAgent/1.0 (NeEMO stability jobs)"})
    return session


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _status(html):
    text = _plain(html)
    match = re.search(r"Status:\s*([A-Za-z. ]+?)(?:The|NB:|Available|$)", text)
    return (match.group(1).strip() if match else ""), text


def _finished(html):
    """A NeEMO page is done when it reports a terminal status or carries a result table.

    The structure page has no ``Status:`` line at all, so the presence of the
    processed structure / accessibility table is the completion signal there.
    """
    if not html:
        return False
    text = _plain(html)
    status, _ = _status(html)
    if status and "running" not in status.lower() and "queue" not in status.lower():
        return True
    return (("Processed structure" in text and "Relative Accessibility" in text) or
            ("Stability change" in text and "Available files" in text))


def _poll(session, pid, directory, wait_seconds, poll_seconds, tag):
    url = STATUS.format(pid=pid)
    deadline = time.monotonic() + wait_seconds
    html, text = "", ""
    while time.monotonic() < deadline:
        try:
            response = request_with_retries(session, "GET", url, attempts=3, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            html, text = "", f"status request failed: {type(error).__name__}"
            time.sleep(poll_seconds)
            continue
        html = response.text
        (directory / f"neemo_{tag}_status.html").write_text(html)
        status, text = _status(html)
        if _finished(html):
            return True, html, text, (status or "finished")
        time.sleep(poll_seconds)
    return False, html, text, "running"


def _submit_structure(session, pdb_id, chain, directory):
    key = hashlib.sha256(json.dumps({"pdb_id": pdb_id, "chain": chain}, sort_keys=True).encode()).hexdigest()
    state_path = directory / "neemo_structure_request.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("input_sha256") == key and state.get("pid"):
            return state
    response = request_with_retries(session, "POST", SUBMIT, timeout=120,
                                    data={"pdbcode": pdb_id, "chain": chain}, files={"pdbfile": ("", b"")})
    (directory / "neemo_submission.html").write_text(response.text)
    response.raise_for_status()
    match = re.search(r"pid:\s*<span class=\"userinfo\">(\d+)</span>", response.text)
    if not match:
        raise RuntimeError("NeEMO did not return a job PID: " + _plain(response.text)[:400])
    state = {"pid": match.group(1), "input_sha256": key, "pdb_id": pdb_id, "chain": chain,
             "status_url": STATUS.format(pid=match.group(1)),
             "submitted_at": datetime.now(timezone.utc).isoformat(), "status": "queued"}
    state_path.write_text(json.dumps(state, indent=2))
    return state


def _hidden(html, name):
    match = re.search(r'name=["\']?' + name + r'["\']?\s+value=["\']?([^"\'\s>]+)', html)
    return match.group(1) if match else ""


def _parse_processed(html):
    """Chain, sequence and the NeEMO relative-accessibility table of a finished structure job."""
    pre = re.search(r"<pre>(.*?)</pre>", html, re.S)
    sequence = _hidden(html, "sequence").upper()
    chain = _hidden(html, "chain") or None
    residues = []
    for match in re.finditer(r"updatestring\((\d+),\s*(\d+),\s*'([A-Za-z])'", html):
        position, index, wild_type = int(match.group(1)), int(match.group(2)) + 1, match.group(3).upper()
        residues.append({"index": index, "pdb_residue_number": position, "chain": chain, "wild_type": wild_type})
    accessibility = [float(value) for value in re.findall(r"<td>\s*([0-9]+\.[0-9]+)\s*</td>", html)]
    for row, value in zip(residues, accessibility):
        row["relative_accessibility_percent"] = value
        row["environment"] = ("buried" if value < 20 else "intermediate" if value < 40 else "exposed")
    alignment = re.sub(r"<[^>]+>", "", pre.group(1)) if pre else ""
    return {"chain": chain, "sequence": sequence, "sequence_length": len(sequence),
            "alignment_block": alignment.strip()[:2000], "residues": residues,
            "hidden_fields": {name: _hidden(html, name) for name in ["dir", "chain", "backid", "sequence", "pdbfile"]},
            "accessibility_units": "percent relative accessibility reported by NeEMO"}


def _mutation_text(mutation):
    parts = [part for part in re.split(r"[,\s+]+", (mutation or "").strip()) if part]
    if not parts:
        raise ValueError("Provide at least one mutation such as I16A")
    encoded = []
    for part in parts:
        match = re.fullmatch(r"([A-Za-z])(\d+)([A-Za-z])", part)
        if not match:
            raise ValueError(f"Mutation '{part}' must look like I16A (wild type, number, mutant)")
        encoded.append(f"{match.group(1).upper()}{int(match.group(2))}{match.group(3).upper()}#")
    return "".join(encoded), [part.replace("#", "") for part in encoded]


def _submit_mutation(session, processed, mutation, temperature, ph, directory):
    fields = processed["hidden_fields"]
    data = {"emailaddress": "", "name": "", "dir": fields.get("dir", ""), "chain": fields.get("chain", ""),
            "backid": fields.get("backid", ""), "sequence": fields.get("sequence", ""),
            "mutationtext": mutation, "pdbfile": fields.get("pdbfile", ""),
            "temp": str(temperature), "ph": str(ph)}
    response = request_with_retries(session, "POST", MUTATE, timeout=180, data=data, files={"dummy": ("", b"")})
    (directory / "neemo_mutation_submission.html").write_text(response.text)
    response.raise_for_status()
    match = re.search(r"pid:\s*<span class=\"userinfo\">(\d+)</span>", response.text)
    if not match:
        raise RuntimeError("NeEMO mutation submission returned no PID: " + _plain(response.text)[:400])
    return match.group(1)


def _parse_stability(html):
    """Rows of the finished NeEMO output table: number, mutant, pH, temperature, kcal/mol."""
    block = re.search(r"PDB Number.*?</pre>", html, re.S)
    if not block:
        return []
    text = re.sub(r"<[^>]+>", "", block.group(0))
    rows = []
    for line in text.splitlines()[1:]:
        columns = line.split()
        if len(columns) < 5 or not columns[0].isdigit():
            continue
        try:
            change = float(columns[4])
        except ValueError:
            continue
        rows.append({"number": int(columns[0]), "mutant": columns[1], "ph": float(columns[2]),
                     "temperature_celsius": float(columns[3]), "stability_change_kcal_per_mol": change})
    return rows


def _local_preparation(session, pdb_id, chain, directory):
    """Fallback structure preparation when the NeEMO job is still queued."""
    from Bio.PDB import PDBParser
    from Bio.PDB.SASA import ShrakeRupley
    response = request_with_retries(session, "GET", f"{RCSB}/{pdb_id}.pdb", timeout=60)
    response.raise_for_status()
    raw = directory / f"{pdb_id}.pdb"
    raw.write_text(response.text)
    model = next(PDBParser(QUIET=True).get_structure(pdb_id, str(raw)).get_models())
    available = [item.id for item in model
                 if any(residue.id[0] == " " and residue.resname in STANDARD_THREE for residue in item)]
    if not available:
        raise RuntimeError("No standard protein chain found in " + pdb_id)
    selected = chain.strip().upper() or available[0]
    if selected not in available:
        raise ValueError(f"Chain {selected} has no standard protein residues; available chains: {available}")
    target = next(item for item in model if item.id == selected)
    residues = [residue for residue in target if residue.id[0] == " " and residue.resname in STANDARD_THREE]
    ShrakeRupley().compute(target, level="R")
    return {"source": "local structure preparation (NeEMO job still queued)", "chain": selected,
            "available_chains": available, "residue_count": len(residues),
            "source_structure": str(raw),
            "accessibility_method": "Shrake-Rupley on the isolated chain",
            "residues": [{"residue_number": residue.id[1], "residue": _one(residue.resname),
                          "accessible_area": round(float(getattr(residue, "sasa", 0.0)), 3)}
                         for residue in residues]}


def _one(name):
    from Bio.PDB.Polypeptide import protein_letters_3to1_extended
    table = {key.upper(): value for key, value in protein_letters_3to1_extended.items()}
    return table.get(name.upper(), "X")


def neemo(pdb_id: str, chain: str = "", mutation: str = "", temperature: float = 20.0, ph: float = 8.5,
          wait_seconds: int = 150, poll_seconds: int = 8):
    """Run a real NeEMO structure job and, when a mutation is given, its stability change.

    ``mutation`` accepts one or more mutations (``I16A`` or ``I16A,A17G``).  The
    structure job PID is persisted, so repeating the same call resumes and collects
    a job that was still queued inside the previous wait budget.
    """
    identifier = _pdb_id(pdb_id)
    if not 0 <= wait_seconds <= 1800:
        raise ValueError("Require 0..1800 wait seconds")
    if not 3 <= poll_seconds <= 60:
        raise ValueError("Require 3..60 poll seconds")
    if not -20 <= temperature <= 100:
        raise ValueError("Require a temperature between -20 and 100 Celsius")
    if not 0 <= ph <= 14:
        raise ValueError("Require a pH between 0 and 14")
    encoded, labels = (_mutation_text(mutation) if mutation else (None, []))
    # Deterministic artifact directory: the persisted NeEMO PID is reused, so a job
    # that was still queued inside the previous wait budget resumes on the next call.
    key = hashlib.sha256(json.dumps({"pdb_id": identifier, "chain": chain.strip().upper()},
                                    sort_keys=True).encode()).hexdigest()[:16]
    directory = artifacts_root() / f"neemo_{identifier}_{key}"
    directory.mkdir(parents=True, exist_ok=True)
    result = {"source": "NeEMO public service (NEtwork Enthalpic MOdelling)", "pdb_id": identifier,
              "requested_chain": chain.strip().upper() or None, "requested_mutations": labels,
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    with _session() as session:
        state = _submit_structure(session, identifier, chain.strip().upper(), directory)
        finished, html, text, status = _poll(session, state["pid"], directory, wait_seconds, poll_seconds, "structure")
        state["status"] = status if finished else "queued"
        result["structure_job"] = state
        result["structure_job_status"] = state["status"]
        result["structure_status_text"] = text[:1500]
        if finished:
            processed = _parse_processed(html)
            result["processed_structure"] = processed
            result["processed_structure_source"] = "NeEMO job " + state["pid"]
        else:
            result["processed_structure"] = _local_preparation(session, identifier, chain, directory)
            result["processed_structure_source"] = ("local preparation; NeEMO job " + state["pid"] +
                                                    " is still running and resumes on the next identical call")
        result["stability_changes"] = []
        if encoded:
            if not finished:
                result["stability_change_status"] = ("NeEMO structure job still running; repeat this call to collect the "
                                                     "mutation result once the structure is prepared")
            else:
                mutation_pid = _submit_mutation(session, result["processed_structure"], encoded,
                                                temperature, ph, directory)
                mutation_finished, mutation_html, mutation_text, mutation_status = _poll(
                    session, mutation_pid, directory, min(wait_seconds, 300), poll_seconds, "mutation")
                result["mutation_job"] = {"pid": mutation_pid, "status": mutation_status if mutation_finished else "queued",
                                          "temperature_celsius": temperature, "ph": ph,
                                          "status_url": STATUS.format(pid=mutation_pid)}
                result["mutation_status_text"] = mutation_text[:1500]
                result["stability_changes"] = _parse_stability(mutation_html) if mutation_finished else []
                result["stability_change_status"] = ("NeEMO reported the changes below in kcal/mol"
                                                     if result["stability_changes"] else
                                                     "NeEMO mutation job still running; repeat this call to collect the result")
        else:
            result["stability_change_status"] = "no mutation requested; the processed structure is the NeEMO output"
    result["scope"] = ("Structure preparation and relative accessibility are NeEMO outputs; stability changes are only "
                       "reported when the NeEMO mutation job finished. No value is estimated locally.")
    return json.dumps(result, ensure_ascii=False)
