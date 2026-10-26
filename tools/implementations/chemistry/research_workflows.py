"""Composable, deterministic chemical evidence primitives for workflow tasks.

These functions report representations and computational evidence; they do not
select a task's answer or imply experimental assay performance.
"""

import math


def _molecule(smiles):
    from .core import molecule
    return molecule(smiles, "remove")


def canonical_molecular_identity(
    smiles: str,
    fragment_policy: str = "keep_all",
    tautomer_policy: str = "preserve",
    keep_stereo: bool = True,
) -> dict:
    """Normalize a molecular record under explicit, auditable identity policies.

    Args:
        smiles (str): RDKit-readable SMILES; disconnected components are retained.
        fragment_policy (str): ``keep_all`` preserves every component;
            ``largest_organic`` picks the carbon-containing fragment with most
            heavy atoms (canonical-SMILES lexical tie break), falling back to the largest
            fragment among all components if none contains carbon. This is NOT charge neutralization.
        tautomer_policy (str): ``preserve`` or RDKit ``canonical`` tautomer;
            canonical tautomer does not mean the dominant solution species.
        keep_stereo (bool): Keep assigned stereochemical labels by default.

    Returns:
        dict: Canonical selected SMILES, original component SMILES, selected and
            original formula/charge, chiral center labels, policy and RDKit
            version. Atom indexes refer to the normalized selected molecule.
    """
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize

    if fragment_policy not in {"keep_all", "largest_organic"}:
        raise ValueError("fragment_policy must be keep_all or largest_organic")
    if tautomer_policy not in {"preserve", "canonical"}:
        raise ValueError("tautomer_policy must be preserve or canonical")
    if type(keep_stereo) is not bool:
        raise ValueError("keep_stereo must be a boolean")
    original = _molecule(smiles)
    fragments = list(Chem.GetMolFrags(original, asMols=True, sanitizeFrags=True))
    molecule = Chem.Mol(original)
    discarded = []
    if fragment_policy == "largest_organic":
        organic = [
            m for m in fragments if any(a.GetAtomicNum() == 6 for a in m.GetAtoms())
        ]
        choices = organic or fragments
        molecule = sorted(
            choices, key=lambda m: (-m.GetNumHeavyAtoms(), Chem.MolToSmiles(m))
        )[0]
        chosen = Chem.MolToSmiles(molecule)
        discarded_once = False
        for fragment in fragments:
            text = Chem.MolToSmiles(fragment)
            if text == chosen and not discarded_once:
                discarded_once = True
            else:
                discarded.append(text)
    if tautomer_policy == "canonical":
        molecule = rdMolStandardize.TautomerEnumerator().Canonicalize(molecule)
    if not keep_stereo:
        Chem.RemoveStereochemistry(molecule)
    normalized = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
    molecule = Chem.MolFromSmiles(normalized)
    return {
        "canonical_smiles": normalized,
        "original_formula": rdMolDescriptors.CalcMolFormula(original),
        "original_formal_charge": Chem.GetFormalCharge(original),
        "original_fragments": [
            Chem.MolToSmiles(m, isomericSmiles=True) for m in fragments
        ],
        "discarded_fragments": discarded,
        "formula": rdMolDescriptors.CalcMolFormula(molecule),
        "formal_charge": Chem.GetFormalCharge(molecule),
        "heavy_atom_count": molecule.GetNumHeavyAtoms(),
        "chiral_centers": [
            {"atom_index": int(index), "label": label}
            for index, label in Chem.FindMolChiralCenters(
                molecule, includeUnassigned=True, useLegacyImplementation=False
            )
        ],
        "policy": {
            "fragments": fragment_policy,
            "tautomers": tautomer_policy,
            "keep_stereo": keep_stereo,
        },
        "rdkit_version": rdBase.rdkitVersion,
        "limitations": [
            "No pH-dependent protonation model",
            "No experimental identity or dominant-tautomer claim",
        ],
    }


def substructure_query(
    smiles: str,
    query: str,
    query_format: str = "smarts",
    use_chirality: bool = True,
    max_matches: int = 100,
) -> dict:
    """Return explicit substructure evidence for one molecule and one query.

    Args:
        smiles (str): Target SMILES; original atom ordering is preserved.
        query (str): SMARTS pattern or query SMILES, according to query_format.
        query_format (str): ``smarts`` or ``smiles``; never inferred silently.
        use_chirality (bool): Enforce explicitly specified query stereochemistry.
        max_matches (int): Match reporting cap from 1 through 1000.

    Returns:
        dict: matched boolean, unique atom-index matches, reported match count,
            truncation flag, target canonical SMILES, query settings and version.
            Count is exact only when truncated is false; no physical assay claim.
    """
    from rdkit import Chem, rdBase

    target = _molecule(smiles)
    if not isinstance(query, str) or not query or len(query) > 2000:
        raise ValueError("query must contain 1 to 2000 characters")
    if query_format not in {"smarts", "smiles"}:
        raise ValueError("query_format must be smarts or smiles")
    if type(use_chirality) is not bool:
        raise ValueError("use_chirality must be a boolean")
    if type(max_matches) is not int or not 1 <= max_matches <= 1000:
        raise ValueError("max_matches must be an integer in [1,1000]")
    pattern = (
        Chem.MolFromSmarts(query)
        if query_format == "smarts"
        else Chem.MolFromSmiles(query)
    )
    if pattern is None or pattern.GetNumAtoms() == 0:
        raise ValueError("Query could not be parsed in the declared format")
    matches = target.GetSubstructMatches(
        pattern, uniquify=True, useChirality=use_chirality, maxMatches=max_matches + 1
    )
    return {
        "matched": bool(matches),
        "matches": [list(m) for m in matches[:max_matches]],
        "reported_match_count": min(len(matches), max_matches),
        "truncated": len(matches) > max_matches,
        "target_canonical_smiles": Chem.MolToSmiles(target),
        "query": query,
        "query_format": query_format,
        "use_chirality": use_chirality,
        "rdkit_version": rdBase.rdkitVersion,
    }


def fingerprint_similarity(smiles_a: str, smiles_b: str, fingerprint: str='morgan', radius: int=2, bits: int=2048, chirality: bool=False, metric: str='tanimoto'):
    'FingerprintSimilarity retired: Pair and matrix similarity/distance share one fingerprint comparison kernel. Use CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.'
    raise ValueError('FingerprintSimilarity retired: Pair and matrix similarity/distance share one fingerprint comparison kernel. Use CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.')
