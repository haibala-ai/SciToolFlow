"""Small, separately registered chemical capabilities with typed failures/results."""

import csv
import hashlib
import io
import json
import random
import re
import uuid

from .core import molecule, finite, source_bytes, coordinate_inventory


def smiles_to_inchi(smiles: str) -> dict:
    """Convert a valid SMILES to standard RDKit InChI; preserve salts/isotopes/encoded stereo.

    No fragment, tautomer or protonation policy is inferred. Return standard InChI
    and canonical input SMILES; invalid structures or an empty converter result fail.
    """
    from rdkit import Chem, rdBase
    mol = molecule(smiles, "remove")
    value = Chem.MolToInchi(mol)
    if not value or not value.startswith("InChI="):
        raise ValueError("RDKit InChI conversion produced no identifier")
    return {"inchi": value, "canonical_smiles": Chem.MolToSmiles(mol), "rdkit_version": rdBase.rdkitVersion}


def inchi_to_smiles(inchi: str) -> dict:
    """Convert a complete InChI string to RDKit canonical isomeric SMILES locally.

    Requires the InChI= prefix. Invalid/empty InChI raises an error; no database
    lookup, guessed prefix, salt removal or pH-dependent protonation is performed.
    """
    from rdkit import Chem, rdBase
    if not isinstance(inchi, str) or not inchi.startswith("InChI=") or len(inchi) > 10000:
        raise ValueError("inchi must be a complete InChI= identifier of at most 10000 characters")
    mol = Chem.MolFromInchi(inchi)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError("Invalid InChI")
    return {"smiles": Chem.MolToSmiles(mol), "inchi": inchi, "rdkit_version": rdBase.rdkitVersion}


def inchi_to_inchikey(inchi: str) -> dict:
    """Hash the supplied complete InChI directly with RDKit InchiToInchiKey.

    This preserves the supplied InChI hash input rather than reconstructing a graph
    and re-serializing it. It is not an InChIKey database-resolution operation.
    """
    from rdkit.Chem import inchi as backend
    inchi_to_smiles(inchi)
    key = backend.InchiToInchiKey(inchi)
    if not key:
        raise ValueError("RDKit could not hash the supplied InChI")
    return {"inchikey": key, "inchi": inchi, "method": "RDKit InchiToInchiKey"}


def is_valid_inchikey(inchikey: str) -> dict:
    """Check only the standard InChIKey letter/hyphen syntax, without resolution.

    A format-valid key need not identify a known database record or a valid
    molecule. No checksum, structure, membership or identity claim is made.
    """
    if not isinstance(inchikey, str):
        raise ValueError("inchikey must be a string")
    return {"format_valid": bool(re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", inchikey)),
            "validation_scope": "letter/hyphen syntax only"}


def smiles_to_selfies(smiles: str) -> dict:
    """Encode one valid SMILES as SELFIES with the installed encoder's semantic constraints."""
    import selfies as sf
    molecule(smiles, "remove")
    return {"selfies": sf.encoder(smiles), "source_smiles": smiles, "selfies_version": sf.__version__}


def selfies_to_smiles(selfies: str) -> dict:
    """Decode one bounded nonempty SELFIES string; reject invalid/empty decoded molecules."""
    import selfies as sf
    if not isinstance(selfies, str) or not selfies or len(selfies) > 20000:
        raise ValueError("selfies must contain 1-20000 characters")
    value = sf.decoder(selfies)
    molecule(value)
    return {"smiles": value, "selfies": selfies, "selfies_version": sf.__version__}


def generate_random_selfies(length: int, seed: int = 42) -> dict:
    """Sample 1-256 semantic-robust SELFIES symbols uniformly with replacement.

    A sorted installed alphabet and local seeded RNG make the procedure auditable.
    Repetition is allowed; requested length is a token-sampling length, not a
    heavy-atom count or a claim of synthesizability, novelty or physical stability.
    The decoded molecule must be nonempty and parseable.
    """
    import selfies as sf
    if type(length) is not int or not 1 <= length <= 256 or type(seed) is not int:
        raise ValueError("length must be an integer in [1,256]; seed must be an integer")
    alphabet = sorted(sf.get_semantic_robust_alphabet())
    value = "".join(random.Random(seed).choices(alphabet, k=length))
    decoded = sf.decoder(value)
    molecule(decoded)
    return {"selfies": value, "smiles": decoded, "sampled_symbol_count": length,
            "seed": seed, "alphabet_sha256": hashlib.sha256("\n".join(alphabet).encode()).hexdigest(),
            "sampling": "uniform symbols with replacement", "selfies_version": sf.__version__}


def average_molecular_weight(smiles: str) -> dict:
    """Compute RDKit isotope-averaged molar mass (g/mol), respecting explicit isotope labels.

    This differs from exact/monoisotopic mass and ion-adduct m/z. Implicit hydrogen
    contributes through RDKit's molecular-weight convention; salts are retained.
    """
    from rdkit.Chem import Descriptors
    return {"molar_mass": finite(Descriptors.MolWt(molecule(smiles, "remove"))),
            "unit": "g/mol", "method": "RDKit average atomic weights; explicit isotope labels respected"}


def molecule_consistency(smiles: str) -> dict:
    """Parse/sanitize a graph and check canonical SMILES invariance under reversed atom order.

    This is a local software consistency check, not an experimental molecular
    identity, stability, synthetic feasibility or stereoisomer validation assay.
    """
    from rdkit import Chem
    mol = molecule(smiles, "remove")
    canonical = Chem.MolToSmiles(mol)
    reverse = Chem.RenumberAtoms(mol, list(reversed(range(mol.GetNumAtoms()))))
    consistent = canonical == Chem.MolToSmiles(reverse)
    if not consistent:
        raise RuntimeError("Canonical SMILES changed after atom-order reversal")
    return {"parsed_and_sanitized": True, "canonicalization_order_check": True,
            "canonical_smiles": canonical, "atom_count": mol.GetNumAtoms()}


def show_molecule(smiles: str) -> dict:
    """Draw a 2D RDKit SVG depiction of the supplied molecular graph.

    Returns complete SVG text. This is a 2D depiction, not a 3D conformer,
    experimental structure or structure identity validation.
    """
    from rdkit.Chem.Draw import rdMolDraw2D
    mol = molecule(smiles, "remove")
    drawer = rdMolDraw2D.MolDraw2DSVG(500, 400)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return {"svg": drawer.GetDrawingText(), "media_type": "image/svg+xml", "dimensions": [500, 400]}


def sln_to_smiles(sln: str) -> dict:
    """Parse one Sybyl Line Notation (SLN) string and return canonical isomeric SMILES."""
    from rdkit import Chem
    from rdkit.Chem import rdSLNParse
    if not isinstance(sln, str) or not sln or len(sln) > 10000:
        raise ValueError("sln must contain 1-10000 characters in SLN syntax")
    mol = rdSLNParse.MolFromSLN(sln)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError("Invalid SLN")
    return {"smiles": Chem.MolToSmiles(mol), "source_sln": sln}


def estate_vsa(smiles: str) -> dict:
    """Return all 11 RDKit EState_VSA bins: atomic surface contributions grouped by EState.

    This surface-bin descriptor differs from atomic EState indices and type-count/
    sum fingerprints. Return full finite values on the H-suppressed parsed graph.
    """
    from rdkit.Chem.EState import EState_VSA
    mol = molecule(smiles, "remove")
    return {"estate_vsa": {f"EState_VSA{i}": finite(getattr(EState_VSA, f"EState_VSA{i}")(mol))
                           for i in range(1, 12)}, "unit": "angstrom^2", "hydrogen_policy": "remove"}


def molecular_invariants(smiles, kind):
    from rdkit.Chem import rdMolDescriptors
    mol = molecule(smiles, "remove")
    fn = rdMolDescriptors.GetConnectivityInvariants if kind == "connectivity" else rdMolDescriptors.GetFeatureInvariants
    return {"kind": kind, "atom_invariants": [int(x) for x in fn(mol)],
            "atom_indices": list(range(mol.GetNumAtoms())), "hydrogen_policy": "remove"}


def connectivity_invariants(smiles: str) -> dict:
    """Return RDKit connectivity atom invariants (the circular-connectivity initialization).

    Indexed atom invariants differ from the final neighborhood-hashed Morgan
    fingerprint and from pharmacophore-feature invariants. No feature hashing.
    """
    return molecular_invariants(smiles, "connectivity")


def feature_invariants(smiles: str) -> dict:
    """Return RDKit pharmacophore-feature atom invariants on the H-suppressed graph.

    These differ from connectivity invariants and from final neighborhood-hashed
    fingerprints. Return one integer per indexed atom without aggregation.
    """
    return molecular_invariants(smiles, "feature")


def create_shingling(smiles: str) -> dict:
    """Return RDKit MHFP's default unhashed molecular shingles as complete strings.

    These are fragment strings before minhash/SECFP projection, not a hashed
    fingerprint. Backend defaults are retained; no chemical normalization.
    """
    from rdkit.Chem import rdMHFPFingerprint
    values = list(rdMHFPFingerprint.MHFPEncoder().CreateShinglingFromMol(molecule(smiles, "remove")))
    return {"shingles": values, "count": len(values), "method": "RDKit MHFP CreateShinglingFromMol defaults"}


def explain_atom_pair_score(smiles: str, atom_idx1: int, atom_idx2: int) -> dict:
    """Encode two atoms using their actual graph shortest-path distance and decode the pair code.

    Atom indices are zero-based in the H-suppressed graph. Distinct atoms in the
    same connected component are required; disconnected pairs are errors. The
    distance is computed, never hard-coded to 1 for a nonadjacent pair.
    """
    from rdkit import Chem
    from rdkit.Chem.AtomPairs.Pairs import pyScorePair, ExplainPairScore
    mol = molecule(smiles, "remove")
    if any(type(i) is not int or not 0 <= i < mol.GetNumAtoms() for i in [atom_idx1, atom_idx2]) or atom_idx1 == atom_idx2:
        raise ValueError("Indices must identify two distinct valid atoms")
    path = Chem.GetShortestPath(mol, atom_idx1, atom_idx2)
    if not path:
        raise ValueError("Selected atoms are in disconnected components")
    distance = len(path) - 1
    code = pyScorePair(mol.GetAtomWithIdx(atom_idx1), mol.GetAtomWithIdx(atom_idx2), dist=distance)
    return {"atom_indices": [atom_idx1, atom_idx2], "graph_distance": distance,
            "pair_code": int(code), "decoded": finite(ExplainPairScore(code)), "chirality": False}


def ring_systems(smiles: str) -> dict:
    """Group RDKit perceived rings sharing at least two atoms; spiro-only intersections stay separate.

    Return zero-based atom groups of the H-suppressed parsed graph and the explicit
    merge convention. This is neither ring count nor Murcko scaffold extraction.
    """
    mol = molecule(smiles, "remove")
    systems = []
    for ring in mol.GetRingInfo().AtomRings():
        group = set(ring)
        # Repeat until transitive closure; a late merge can join earlier groups.
        changed = True
        while changed:
            changed = False
            remaining = []
            for existing in systems:
                if len(group & existing) >= 2:
                    group |= existing
                    changed = True
                else:
                    remaining.append(existing)
            systems = remaining
        systems.append(group)
    return {"atom_groups": sorted([sorted(s) for s in systems]),
            "convention": "RDKit perceived rings; merge intersections of at least two atoms; no spiro merging"}


def molecular_fragments(smiles: str) -> dict:
    """Return disconnected-component atom-index partitions of the H-suppressed parsed graph."""
    from rdkit import Chem
    mol = molecule(smiles, "remove")
    return {"fragments": [list(x) for x in Chem.GetMolFrags(mol)],
            "atom_count": mol.GetNumAtoms(), "hydrogen_policy": "remove"}


def deprotect(smiles: str) -> dict:
    """Apply RDKit's default protecting-group removal rules and expose the resulting graph."""
    from rdkit.Chem import rdDeprotect
    from .molecular_operations import _report
    return _report(rdDeprotect.Deprotect(molecule(smiles, "remove")), "RDKit default deprotection")


def enumerate_molecule(smiles: str) -> dict:
    """Enumerate supported RDKit molecular variation annotations in a SMILES/CXSMILES graph.

    This is rdMolEnumerator enumeration, not tautomer or stereoisomer enumeration.
    A plain graph may produce no enumerated variants; that is reported explicitly.
    """
    from rdkit import Chem
    from rdkit.Chem import rdMolEnumerator
    bundle = rdMolEnumerator.Enumerate(molecule(smiles, "remove"))
    return {"molecules": [Chem.MolToSmiles(bundle.GetMol(i)) for i in range(bundle.Size())],
            "count": bundle.Size(), "method": "rdMolEnumerator.Enumerate defaults"}


def fraggle_fragments(smiles: str) -> dict:
    """Generate RDKit Fraggle candidate fragmentations; sorted strings preserve attachment atoms."""
    from rdkit.Chem.Fraggle.FraggleSim import generate_fraggle_fragmentation
    result = generate_fraggle_fragmentation(molecule(smiles, "remove"))
    return {"fragments": sorted(".".join(sorted(s.split("."))) for s in result),
            "method": "RDKit Fraggle fragmentation"}


def valid_ring_cut(smiles: str) -> dict:
    """Test one supplied candidate fragment against Fraggle's isValidRingCut predicate.

    Input is the fragment including dummy attachment atoms when applicable, not a
    request to cut arbitrary parent bonds or a general molecular-validity test.
    """
    from rdkit.Chem.Fraggle.FraggleSim import isValidRingCut
    return {"valid_fraggle_ring_cut": bool(isValidRingCut(molecule(smiles, "remove")))}


def fraggle_similarity(smiles1: str, smiles2: str, tverskyThresh: float = 0.8) -> dict:
    """Compare two molecular graphs with RDKit Fraggle similarity and a declared Tversky threshold.

    Distinct from whole-fingerprint Tanimoto/Dice. Return score and best matching
    fragment; zero/no fragment is a valid result rather than a structure error.
    """
    from rdkit.Chem.Fraggle.FraggleSim import GetFraggleSimilarity
    if type(tverskyThresh) not in {int, float} or not 0 <= tverskyThresh <= 1:
        raise ValueError("tverskyThresh must be in [0,1]")
    score, match = GetFraggleSimilarity(molecule(smiles1, "remove"), molecule(smiles2, "remove"), tverskyThresh)
    return {"similarity": finite(score), "matching_fragment": match, "tversky_threshold": float(tverskyThresh)}


def extract_rotatable_dihedrals(sdffile: str) -> dict:
    """Return candidate indexed dihedral quadruplets around non-ring single bonds in SDF record0.

    Endpoints must have nonterminal graph degree. One neighbor per side is chosen
    in parsed order. This loose candidate predicate includes restricted linkages
    and differs from RDKit Strict rotatable-bond counts; no torsional freedom or
    energy-barrier claim is made. Removable explicit H are suppressed.
    """
    mol, _, provenance = coordinate_inventory(sdffile, "sdf", 0, "remove", "all")
    quadruplets = []
    for bond in mol.GetBonds():
        if str(bond.GetBondType()) != "SINGLE" or bond.IsInRing():
            continue
        a, b = bond.GetBeginAtom(), bond.GetEndAtom()
        left = [x.GetIdx() for x in a.GetNeighbors() if x.GetIdx() != b.GetIdx()]
        right = [x.GetIdx() for x in b.GetNeighbors() if x.GetIdx() != a.GetIdx()]
        if left and right:
            quadruplets.append([left[0], a.GetIdx(), b.GetIdx(), right[0]])
    return {"candidate_dihedrals": quadruplets, "predicate": "non-ring single bond with nonterminal endpoints",
            "provenance": provenance}


def sdf_to_csv(sdf_file: str) -> dict:
    """Convert uploaded SDF records/properties to a task-local CSV with explicit source row indices.

    Every invalid SDF record fails; no rows are silently dropped. At most 10000
    records and 25 MiB source. Output contains source_record_index, canonical
    SMILES and a JSON properties column; it never overwrites the uploaded source.
    """
    from rdkit import Chem
    from tools.implementations.general.research_data import _task_artifacts_root
    path, raw, sha = source_bytes(sdf_file, {".sdf"})
    rows = []
    for index, mol in enumerate(Chem.ForwardSDMolSupplier(io.BytesIO(raw), removeHs=False)):
        if index >= 10000:
            raise ValueError("SDF is limited to 10000 records")
        if mol is None:
            raise ValueError(f"Invalid SDF record at zero-based index {index}")
        rows.append({"source_record_index": index, "smiles": Chem.MolToSmiles(mol),
                     "properties": json.dumps(mol.GetPropsAsDict(), ensure_ascii=False)})
    if not rows:
        raise ValueError("SDF has no records")
    output = _task_artifacts_root() / ("sdf_records_" + uuid.uuid4().hex + ".csv")
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"artifact": str(output), "record_count": len(rows), "source": str(path),
            "source_sha256": sha, "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def perceive_bonds(mol_block: str, charge: int, mode: str = "connectivity_and_order") -> dict:
    """Perceive bonds from caller-supplied 3D atom coordinates and an explicit total charge.

    mode=connectivity_and_order uses RDKit DetermineBonds (connect-the-dots,
    useHueckel=false); order_only uses existing edges and DetermineBondOrders.
    No conformer is generated from a known SMILES graph. Atom inventory/coordinates
    are retained; ionic/radical limitations and inconsistent charge can cause errors.
    """
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds
    from .molecular_operations import _report
    import numpy as np
    if not isinstance(mol_block, str) or not mol_block or len(mol_block) > 1024 * 1024:
        raise ValueError("mol_block must be a nonempty inline MOL connection table <=1 MiB")
    if type(charge) is not int or not -20 <= charge <= 20:
        raise ValueError("charge must be an explicit integer in [-20,20]")
    if mode not in {"connectivity_and_order", "order_only"}:
        raise ValueError("mode must be connectivity_and_order or order_only")
    mol = Chem.MolFromMolBlock(mol_block, sanitize=False, removeHs=False, strictParsing=True)
    if mol is None or not 0 < mol.GetNumAtoms() <= 500 or not mol.GetNumConformers() or not mol.GetConformer().Is3D():
        raise ValueError("A valid supplied 3D MOL record with 1-500 atoms is required")
    positions = mol.GetConformer().GetPositions()
    if not np.isfinite(positions).all() or len({tuple(p) for p in positions}) != len(positions):
        raise ValueError("Coordinate positions must be finite and distinct")
    if mode == "connectivity_and_order":
        rdDetermineBonds.DetermineBonds(mol, charge=charge, useHueckel=False)
    else:
        if mol.GetNumBonds() == 0 and mol.GetNumAtoms() > 1:
            raise ValueError("order_only requires the caller's existing connectivity")
        rdDetermineBonds.DetermineBondOrders(mol, charge=charge)
    Chem.SanitizeMol(mol)
    result = _report(mol, "rdDetermineBonds." + mode)
    result["total_charge"] = charge
    result["coordinate_source"] = "supplied MOL block; no embedding or optimization"
    return result
