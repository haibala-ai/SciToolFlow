"""Typed structure operations; graph, query, and coordinate inputs stay explicit."""

from .core import molecule, finite


def _molblock(text):
    from rdkit import Chem
    if not isinstance(text, str) or not text or len(text) > 1024 * 1024:
        raise ValueError("mol_block must be a nonempty inline MOL connection table of at most 1 MiB")
    mol = Chem.MolFromMolBlock(text, removeHs=False, strictParsing=True)
    if mol is None or not 0 < mol.GetNumAtoms() <= 1000:
        raise ValueError("Invalid, empty or oversized MOL connection table")
    return mol


def _report(mol, operation):
    from rdkit import Chem, rdBase
    atoms = []
    for atom in mol.GetAtoms():
        atoms.append({"atom_index": atom.GetIdx(), "element": atom.GetSymbol(),
                      "formal_charge": atom.GetFormalCharge(), "radical_electrons": atom.GetNumRadicalElectrons(),
                      "chiral_tag": str(atom.GetChiralTag()),
                      "cip_label": atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else None,
                      "oxidation_number": atom.GetIntProp("OxidationNumber") if atom.HasProp("OxidationNumber") else None})
    return {"operation": operation, "canonical_smiles": Chem.MolToSmiles(mol),
            "kekule_smiles": Chem.MolToSmiles(mol, kekuleSmiles=True),
            "mol_block": Chem.MolToMolBlock(mol), "atom_count": mol.GetNumAtoms(),
            "atoms": atoms, "bonds": [{"bond_index": b.GetIdx(), "atom_indices": [b.GetBeginAtomIdx(), b.GetEndAtomIdx()],
                                          "bond_type": str(b.GetBondType()), "aromatic": b.GetIsAromatic(),
                                          "direction": str(b.GetBondDir()), "stereo": str(b.GetStereo())}
                                         for b in mol.GetBonds()], "rdkit_version": rdBase.rdkitVersion}


def graph_operation(smiles, operation):
    """Internal adapter for separately named scientific operations."""
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    mol = molecule(smiles)
    operations = {
        "add_hydrogens": lambda m: Chem.AddHs(m),
        "remove_hydrogens": lambda m: Chem.RemoveHs(m),
        "haptic_to_dative": lambda m: Chem.HapticBondsToDative(m),
        # The standard wrapper refreshes property/ring caches after removing
        # substituents. The raw primitive can retain stale hydrogen valences
        # with our atom-preserving parser and fail during Kekule serialization.
        "murcko_scaffold": MurckoScaffold.GetScaffoldForMol,
    }
    if operation in operations:
        mol = operations[operation](mol)
    elif operation == "assign_oxidation_numbers":
        rdMolDescriptors.CalcOxidationNumbers(mol)
    elif operation == "assign_radicals":
        Chem.AssignRadicals(mol)
    elif operation == "assign_stereochemistry":
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    elif operation == "assign_cip_labels":
        from rdkit.Chem import rdCIPLabeler
        rdCIPLabeler.AssignCIPLabels(mol)
    elif operation == "kekulize":
        Chem.Kekulize(mol, clearAromaticFlags=True)
    elif operation == "set_aromaticity":
        Chem.SetAromaticity(mol)
    elif operation == "set_bond_stereo_from_directions":
        Chem.SetBondStereoFromDirections(mol)
    elif operation == "remove_stereochemistry":
        Chem.RemoveStereochemistry(mol)
    else:
        raise ValueError("Unknown internal graph operation")
    if mol is None:
        raise ValueError("RDKit operation did not return a molecule")
    return _report(mol, operation)


def assign_chiral_tags_from_coordinates(mol_block: str) -> dict:
    """Assign atom chiral tags from supplied 3D MOL coordinates, without generating geometry.

    Explicit hydrogen/atom inventory is preserved. The MOL record must contain a
    conformer marked 3D; a SMILES-only graph cannot provide this evidence. Existing
    tags are replaced from coordinates, then dedicated CIP labeling is applied.
    Returns atom/bond labels and the resulting connection table.
    """
    from rdkit import Chem
    from rdkit.Chem import rdCIPLabeler
    mol = _molblock(mol_block)
    if not mol.GetNumConformers() or not mol.GetConformer().Is3D():
        raise ValueError("A supplied MOL conformer marked 3D is required")
    Chem.AssignAtomChiralTagsFromStructure(mol, replaceExistingTags=True)
    rdCIPLabeler.AssignCIPLabels(mol)
    return _report(mol, "assign_chiral_tags_from_supplied_coordinates")


def add_wavy_stereo_bonds(mol_block: str) -> dict:
    """Mark unspecified double-bond stereo from a supplied MOL record with wavy bonds.

    STEREOANY must be representable in the caller's record. Return explicit bond
    direction/stereo properties and a MOL block; SMILES text alone can omit wavy
    display information. No unspecified stereoisomer is inferred.
    """
    from rdkit import Chem
    mol = _molblock(mol_block)
    Chem.AddWavyBondsForStereoAny(mol)
    return _report(mol, "add_wavy_bonds_for_stereoany")


def condense_abbreviations(mol_block: str) -> dict:
    """Condense abbreviation substance groups in a supplied MOL record.

    Uses RDKit CondenseAbbreviationSubstanceGroups and returns the resulting
    connection table; plain SMILES cannot reliably carry these source SGroups.
    No protecting-group removal or general chemical standardization is implied.
    """
    from rdkit.Chem import rdAbbreviations
    mol = _molblock(mol_block)
    result = rdAbbreviations.CondenseAbbreviationSubstanceGroups(mol)
    return _report(result, "condense_abbreviation_substance_groups")


def inspect_query_hydrogens(smarts: str) -> dict:
    """Detect RDKit query hydrogens in an explicitly declared SMARTS query graph."""
    from rdkit import Chem
    if not isinstance(smarts, str) or not smarts or len(smarts) > 10000:
        raise ValueError("smarts must contain 1-10000 characters")
    mol = Chem.MolFromSmarts(smarts)
    if mol is None:
        raise ValueError("Invalid SMARTS query")
    has_hs, unmergeable = Chem.HasQueryHs(mol)
    return {"query_smarts": Chem.MolToSmarts(mol), "has_query_hydrogens": bool(has_hs),
            "has_unmergeable_query_hydrogens": bool(unmergeable)}


def merge_query_hydrogens(smarts: str) -> dict:
    """Merge query hydrogen nodes into constraints of an explicit SMARTS query.

    Capture RDKit's returned query molecule; return SMARTS and query-H diagnostics,
    not a SMILES serialization that discards query constraints.
    """
    from rdkit import Chem
    inspect_query_hydrogens(smarts)
    mol = Chem.MergeQueryHs(Chem.MolFromSmarts(smarts))
    result = inspect_query_hydrogens(Chem.MolToSmarts(mol))
    result["query_atom_count"] = mol.GetNumAtoms()
    return result


def atom_properties(smiles, feature):
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    mol = molecule(smiles, "remove")
    if feature == "features":
        rows = [{"atom_index": a.GetIdx(), "rdkit_atom_features": finite(rdMolDescriptors.GetAtomFeatures(mol, a.GetIdx()))}
                for a in mol.GetAtoms()]
    elif feature == "hybridization":
        rows = [{"atom_index": a.GetIdx(), "element": a.GetSymbol(), "hybridization": str(a.GetHybridization())}
                for a in mol.GetAtoms()]
    elif feature == "patty":
        from rdkit.Chem.AtomPairs.Sheridan import AssignPattyTypes
        rows = [{"atom_index": i, "patty_type": str(value)} for i, value in enumerate(AssignPattyTypes(mol))]
    else:
        raise ValueError("Unknown atom-property view")
    return {"atoms": rows, "canonical_smiles": Chem.MolToSmiles(mol), "hydrogen_policy": "remove"}


def graph_matrix(smiles, kind):
    from rdkit import Chem
    mol = molecule(smiles, "remove")
    if kind == "adjacency":
        matrix = Chem.GetAdjacencyMatrix(mol)
    elif kind == "shortest_path":
        matrix = Chem.GetDistanceMatrix(mol)
    else:
        raise ValueError("Unknown graph matrix kind")
    return {"matrix": finite(matrix), "matrix_kind": kind,
            "axes": "zero-based parsed atom indices", "atom_count": mol.GetNumAtoms(),
            "hydrogen_policy": "remove", "unit": "bond count" if kind == "shortest_path" else "binary bond adjacency"}
