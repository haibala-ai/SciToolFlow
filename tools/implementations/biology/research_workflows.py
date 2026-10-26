"""Bounded CPU-only sequence, coordinate and ecological analysis primitives.

No sequence design, laboratory execution, learned models or network access.
"""

import hashlib
import math
import re
from collections import Counter
from io import StringIO


def _sequence(sequence, molecule_type):
    if not isinstance(sequence, str) or not sequence.strip():
        raise ValueError("sequence must be a nonempty string")
    if molecule_type not in {"DNA", "RNA", "protein"}:
        raise ValueError("molecule_type must be DNA, RNA or protein")
    seq = "".join(sequence.split()).upper()
    if len(seq) > 100000:
        raise ValueError("sequence exceeds100000 symbols")
    canonical = {"DNA": "ACGT", "RNA": "ACGU", "protein": "ACDEFGHIKLMNPQRSTVWY"}[
        molecule_type
    ]
    permitted = {
        "DNA": "ACGTRYSWKMBDHVN-",
        "RNA": "ACGURYSWKMBDHVN-",
        "protein": "ACDEFGHIKLMNPQRSTVWYBXZJUO*-",
    }[molecule_type]
    return seq, canonical, permitted


def parse_fasta_records(fasta_text: str, molecule_type: str = "protein") -> dict:
    """Parse1..1000 FASTA records, preserving IDs and full descriptions.

    Duplicate IDs are reported, never merged. Wrapped lines and whitespace are
    normalized. Sequence symbols are reported by sequence_quality_metrics, not
    silently repaired. Empty records or sequence before first header are errors.
    """
    if (
        not isinstance(fasta_text, str)
        or not fasta_text.strip()
        or len(fasta_text) > 2000000
    ):
        raise ValueError("fasta_text must contain1..2000000 characters")
    records = []
    header = None
    parts = []

    def append():
        if header is None:
            return
        seq, _, _ = _sequence("".join(parts), molecule_type)
        records.append(
            {
                "id": header.split()[0],
                "description": header,
                "sequence": seq,
                "length": len(seq),
            }
        )

    for line in fasta_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            append()
            header = line[1:].strip()
            parts = []
            if not header:
                raise ValueError("FASTA header must have an identifier")
        else:
            if header is None:
                raise ValueError("Sequence appears before FASTA header")
            parts.append(line)
    append()
    if not 1 <= len(records) <= 1000:
        raise ValueError("Require1..1000 records")
    counts = Counter(x["id"] for x in records)
    return {
        "records": records,
        "record_count": len(records),
        "duplicate_ids": sorted(k for k, v in counts.items() if v > 1),
        "molecule_type": molecule_type,
        "normalization": "whitespace removed; uppercase; no gap/ambiguity/stop repair",
    }


def sequence_quality_metrics(sequence: str, molecule_type: str = "protein") -> dict:
    """Count canonical, ambiguous, gap, stop and invalid symbols with exact scope.

    Positions are1-based. GC bounds concern nongap nucleotide positions including
    IUPAC ambiguity; midpoint is not imputed. Protein GC bounds are null.
    """
    seq, canonical, permitted = _sequence(sequence, molecule_type)
    counts = Counter(seq)
    invalid = sorted(set(seq) - set(permitted))
    noncanonical = [
        i + 1 for i, s in enumerate(seq) if s not in canonical and s not in "-*"
    ]
    nongap = len(seq) - counts["-"]
    gc_count = sum(counts[s] for s in "GC")
    if molecule_type == "protein":
        gc = None
        bounds = None
    else:
        possibilities = {
            "A": "A",
            "C": "C",
            "G": "G",
            "T": "T",
            "U": "U",
            "R": "AG",
            "Y": "CT",
            "S": "GC",
            "W": "AT",
            "K": "GT",
            "M": "AC",
            "B": "CGT",
            "D": "AGT",
            "H": "ACT",
            "V": "ACG",
            "N": "ACGT",
        }
        if invalid or "*" in counts or nongap == 0:
            bounds = None
        else:
            sets = [set(possibilities[s]) for s in seq if s != "-"]
            bounds = [
                100 * sum(v <= set("GC") for v in sets) / nongap,
                100 * sum(bool(v & set("GC")) for v in sets) / nongap,
            ]
        n = sum(counts[s] for s in canonical)
        gc = 100 * gc_count / n if n else None
    return {
        "length": len(seq),
        "nongap_length": nongap,
        "counts": dict(sorted(counts.items())),
        "canonical_count": sum(counts[s] for s in canonical),
        "noncanonical_positions": noncanonical,
        "ambiguous_positions": [
            i + 1
            for i, symbol in enumerate(seq)
            if symbol in ("BXZJ" if molecule_type == "protein" else "RYSWKMBDHVN")
        ],
        "gap_positions": [i + 1 for i, s in enumerate(seq) if s == "-"],
        "stop_positions": [i + 1 for i, s in enumerate(seq) if s == "*"],
        "invalid_symbols": invalid,
        "canonical_fraction": sum(counts[s] for s in canonical) / len(seq),
        "gc_percent_known_bases": gc,
        "gc_percent_bounds_all_nongap": bounds,
        "molecule_type": molecule_type,
        "coordinate_convention": "1-based positions; GC bounds include IUPAC ambiguity, ignore gaps",
        "valid_alphabet": not invalid,
    }


def inspect_pdb_quality(file_name: str, mse_to_m: bool = False) -> dict:
    """Inspect a public uploaded PDB/mmCIF; never repair or infer missing atoms.

    Counts first and subsequent models separately. Protein residue identity keeps
    chain, residue number and insertion code. Backbone expectation N/CA/C/O is
    structural completeness only. SEQRES missing residues are not inferred.
    mse_to_m optionally maps observed selenomethionine MSE to M; otherwise
    nonstandard residue names unresolved by seq1 are reported as X.
    """
    from tools.implementations.general.research_data import _public_source_path
    from Bio.PDB import PDBParser, MMCIFParser
    from Bio.PDB.Polypeptide import is_aa
    from Bio.SeqUtils import seq1
    import io

    if type(mse_to_m) is not bool:
        raise ValueError("mse_to_m must be a strict Boolean")
    p = _public_source_path(file_name)
    raw = p.read_bytes()
    if not raw or len(raw) > 10000000:
        raise ValueError("coordinate file must be nonempty and at most10000000bytes")
    parser = (
        MMCIFParser(QUIET=True)
        if p.suffix.lower() in {".cif", ".mmcif"}
        else PDBParser(QUIET=True, PERMISSIVE=False)
    )
    structure = parser.get_structure("public", io.StringIO(raw.decode("utf-8")))
    models = []
    for model in structure:
        chains = []
        for chain in model:
            residues = [r for r in chain if is_aa(r, standard=False)]
            if not residues:
                continue
            missing = []
            alts = []
            for r in residues:
                if any(
                    not all(math.isfinite(float(v)) for v in a.coord)
                    for a in r.get_unpacked_list()
                ):
                    raise ValueError(
                        "Nonfinite coordinate encountered in protein atoms"
                    )
                key = f"{r.id[1]}{r.id[2].strip()}"
                absent = [a for a in ["N", "CA", "C", "O"] if a not in r]
                if absent:
                    missing.append({"residue_id": key, "missing_atoms": absent})
                for a in r.get_unpacked_list():
                    if a.get_altloc().strip():
                        alts.append(
                            {
                                "residue_id": key,
                                "atom": a.get_name(),
                                "altloc": a.get_altloc(),
                                "occupancy": a.get_occupancy(),
                            }
                        )
            chains.append(
                {
                    "chain_id": chain.id,
                    "residue_count": len(residues),
                    "sequence": "".join(
                        seq1(r.resname, undef_code="X", custom_map={"MSE": "M"} if mse_to_m else {}) for r in residues
                    ),
                    "residue_ids": [f"{r.id[1]}{r.id[2].strip()}" for r in residues],
                    "missing_backbone": missing,
                    "altloc_atoms": alts,
                    "coordinate_atom_count": sum(
                        1 for r in residues for a in r.get_unpacked_list()
                    ),
                }
            )
        models.append({"model_id": int(model.id), "chains": chains})
    if not models or not any(m["chains"] for m in models):
        raise ValueError("No protein coordinate residues found")
    return {
        "source_file": p.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "mse_to_m": mse_to_m,
        "model_count": len(models),
        "models": models,
        "scope": "coordinate protein residues only; no SEQRES completeness inference; selected atoms may follow Biopython highest-occupancy convention",
        "coordinate_units": "angstrom",
    }


def extract_pdb_coordinates(
    file_name: str,
    chain_id: str,
    model_id: int = 0,
    atom_name: str = "CA",
    residue_ids: list | None = None,
) -> dict:
    """Extract ordered selected coordinates from public PDB/mmCIF.

    atom_name is one exact case-sensitive PDB atom name of1..4 characters:
    uppercase ASCII letters/digits with optional apostrophe/asterisk, never an
    expression or multi-atom selector. CA/N/C/O remain valid; SG supports
    observed cysteine geometry without changing residue scope. residue_ids is
    an exact list such as23 or23A; null requests every observed amino-acid
    residue, so atoms missing in any requested residue explicitly fail. Model
    IDs are zero-based Biopython IDs. Altloc selection is highest occupancy,
    with equal-occupancy ties following source order. SHA256 identifies the
    exact bytes parsed, not a second later read. Missing atoms are not imputed.
    """
    import io
    import re
    from tools.implementations.general.research_data import _public_source_path
    from Bio.PDB import PDBParser, MMCIFParser
    from Bio.PDB.Polypeptide import is_aa

    if type(model_id) is not int or model_id < 0:
        raise ValueError("model_id must be a nonnegative integer")
    if not isinstance(chain_id, str) or not chain_id:
        raise ValueError("chain_id must be nonempty")
    if not isinstance(atom_name, str) or not re.fullmatch(
        r"[A-Z0-9][A-Z0-9'*]{0,3}", atom_name
    ):
        raise ValueError(
            "atom_name must be one exact1..4character uppercase PDB atom name, not a selection expression"
        )
    p = _public_source_path(file_name)
    raw = p.read_bytes()
    if not raw or len(raw) > 10000000:
        raise ValueError("file must be nonempty and at most10000000bytes")
    parser = (
        MMCIFParser(QUIET=True)
        if p.suffix.lower() in {".cif", ".mmcif"}
        else PDBParser(QUIET=True, PERMISSIVE=False)
    )
    s = parser.get_structure("public", io.StringIO(raw.decode("utf-8")))
    if model_id not in s or chain_id not in s[model_id]:
        raise ValueError("Requested model/chain absent")
    residues = {
        f"{r.id[1]}{r.id[2].strip()}": r
        for r in s[model_id][chain_id]
        if is_aa(r, standard=False)
    }
    ids = list(residues) if residue_ids is None else residue_ids
    if (
        not isinstance(ids, list)
        or not ids
        or len(ids) > 10000
        or len(set(ids)) != len(ids)
        or not all(isinstance(i, str) for i in ids)
    ):
        raise ValueError("residue_ids must be1..10000 unique strings")
    if any(i not in residues or atom_name not in residues[i] for i in ids):
        raise ValueError("Requested residue/atom absent; inspect completeness first")
    if any(
        not all(math.isfinite(float(v)) for v in residues[i][atom_name].coord)
        for i in ids
    ):
        raise ValueError("Selected coordinates must be finite")
    return {
        "residue_ids": ids,
        "coordinates": [[float(v) for v in residues[i][atom_name].coord] for i in ids],
        "chain_id": chain_id,
        "model_id": model_id,
        "atom_name": atom_name,
        "units": "angstrom",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "altloc_policy": "Biopython highest occupancy; ties follow source order",
    }

def diversity_indices(counts: list) -> dict:
    """Compute observed richness, entropy, Simpson indices and Pielou evenness.

    Counts are finite nonnegative, length1..10000; zero-total diversity/evenness
    are null. Simpson concentration is sum(p^2), Gini-Simpson is 1-sum(p^2),
    and inverse Simpson is 1/sum(p^2), using observed relative abundances.
    No finite-sample, rarefaction, detection or ecological causality correction.
    """
    if (
        not isinstance(counts, list)
        or not 1 <= len(counts) <= 10000
        or any(
            type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in counts
        )
    ):
        raise ValueError("counts must be1..10000 finite nonnegative numbers")
    try:
        total = math.fsum(counts)
    except OverflowError as error:
        raise ValueError("Total abundance exceeds finite floating-point range") from error
    if not math.isfinite(total):
        raise ValueError("Total abundance must be finite")
    rich = sum(x > 0 for x in counts)
    p = [x / total for x in counts if x > 0] if total else []
    if any(v == 0 for v in p):
        raise ValueError("Positive abundance probabilities underflow; the dynamic range exceeds floating-point resolution")
    h = -math.fsum(v * math.log(v) for v in p) if p else None
    concentration = math.fsum(v * v for v in p) if p else None
    return {
        "total": total,
        "richness": rich,
        "shannon_nats": h,
        "simpson_concentration": concentration,
        "gini_simpson": 1 - concentration if p else None,
        "inverse_simpson": 1 / concentration if p else None,
        "pielou_evenness": h / math.log(rich) if rich > 1 else None,
        "scope": "sample composition only; Pielou null for richness<2; no rarefaction or effort/detection correction",
    }


def traverse_ontology_relations(
    edges: list, term: str, direction: str = "ancestors"
) -> dict:
    """Traverse supplied child->parent is_a graph; no online ontology assumptions.

    Edges are objects child,parent. Cycles reachable from queried term are errors.
    Only is_a semantics are represented; other relations must not be inferred.
    """
    if (
        not isinstance(edges, list)
        or len(edges) > 10000
        or not isinstance(term, str)
        or not term
        or direction not in {"ancestors", "descendants"}
    ):
        raise ValueError("Bounded edge list, term and valid direction required")
    graph = {}
    for e in edges:
        if (
            not isinstance(e, dict)
            or set(e) != {"child", "parent"}
            or any(not isinstance(e[k], str) or not e[k] for k in e)
            or e["child"] == e["parent"]
        ):
            raise ValueError("Edges require distinct child,parent string IDs")
        a, b = (
            (e["child"], e["parent"])
            if direction == "ancestors"
            else (e["parent"], e["child"])
        )
        graph.setdefault(a, set()).add(b)
    visited = set()
    active = set()
    stack = [(term, False)]
    while stack:
        x, exiting = stack.pop()
        if exiting:
            active.discard(x)
            visited.add(x)
            continue
        if x in active:
            raise ValueError("Reachable ontology relation cycle")
        if x in visited:
            continue
        active.add(x)
        stack.append((x, True))
        stack.extend((y, False) for y in graph.get(x, []))
    visited.remove(term)
    return {
        "term": term,
        "direction": direction,
        "related_terms": sorted(visited),
        "relation": "is_a only; supplied graph only",
        "graph_edge_count": len(edges),
    }
