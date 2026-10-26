from rdkit import Chem
from rdkit.Chem import rdmolops
from rdkit.Chem import rdMolDescriptors


# DetermineBondOrders
def determine_bond_orders(smiles):
    'DetermineBondOrders retired: Perception now accepts caller-supplied coordinate evidence instead of embedding an already bonded SMILES graph. Use PerceiveBondsFromCoordinates. See the catalog migration feedback for explicit arguments.'
    raise ValueError('DetermineBondOrders retired: Perception now accepts caller-supplied coordinate evidence instead of embedding an already bonded SMILES graph. Use PerceiveBondsFromCoordinates. See the catalog migration feedback for explicit arguments.')


# DetermineBonds
def determine_bonds(smiles):
    'DetermineBonds retired: Perception now accepts caller-supplied coordinate evidence instead of embedding an already bonded SMILES graph. Use PerceiveBondsFromCoordinates. See the catalog migration feedback for explicit arguments.'
    raise ValueError('DetermineBonds retired: Perception now accepts caller-supplied coordinate evidence instead of embedding an already bonded SMILES graph. Use PerceiveBondsFromCoordinates. See the catalog migration feedback for explicit arguments.')


# GetPatternFingerprint
def get_pattern_fingerprint(smiles):
    'GetPatternFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetPatternFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


# IsSubstructOf
def is_substructof(target_template):
    'IsSubstructof retired: Boolean and enumerated tautomer-aware matching are one explicit query capability. Use SubstructureQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('IsSubstructof retired: Boolean and enumerated tautomer-aware matching are one explicit query capability. Use SubstructureQuery. See the catalog migration feedback for explicit arguments.')


# GetTemplateMolecule
def get_template_molecule(smiles):
    'GetTemplateMolecule retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetTemplateMolecule retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.')


# GetTautomers
def get_tautomers(template_smiles):
    'GetTautomers retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetTautomers retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.')


# GetModifiedAtoms
def get_modified_atoms(template_smiles):
    'GetModifiedAtoms retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetModifiedAtoms retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.')


# GetModifiedBonds
def get_modified_bonds(smiles):
    'GetModifiedBonds retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetModifiedBonds retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.')


# GetSubstructMatches
def get_substruct_matches(smiles_pair):
    'GetSubstructMatches retired: Boolean and enumerated tautomer-aware matching are one explicit query capability. Use SubstructureQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetSubstructMatches retired: Boolean and enumerated tautomer-aware matching are one explicit query capability. Use SubstructureQuery. See the catalog migration feedback for explicit arguments.')


# 可靠性middle
def assignOxidationNumbers(smiles: str) -> dict:
    'Apply RDKit assign_oxidation_numbers to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'assign_oxidation_numbers')


assignOxidationNumbers("O")


def calculate_PBF(smiles: str) -> dict:
    """Compute the plane-of-best-fit molecular shape descriptor. Geometry uses one ETKDGv3 seed42
    conformer without force-field optimization; no ensemble or experimental structure is
    implied. Hydrogen policy: explicit. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcPBF', geometry=True, hydrogen_policy='explicit')


def calculate_PMI1(smiles: str) -> dict:
    """Compute the smallest principal moment of inertia, PMI1. Geometry uses one ETKDGv3 seed42
    conformer without force-field optimization; no ensemble or experimental structure is
    implied. Hydrogen policy: explicit. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcPMI1', geometry=True, hydrogen_policy='explicit')


def calculate_PMI2(smiles: str) -> dict:
    """Compute the intermediate principal moment of inertia, PMI2. Geometry uses one ETKDGv3
    seed42 conformer without force-field optimization; no ensemble or experimental
    structure is implied. Hydrogen policy: explicit. Return the scientific value with
    named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcPMI2', geometry=True, hydrogen_policy='explicit')


def calculate_PMI3(smiles: str) -> dict:
    """Compute the largest principal moment of inertia, PMI3. Geometry uses one ETKDGv3 seed42
    conformer without force-field optimization; no ensemble or experimental structure is
    implied. Hydrogen policy: explicit. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcPMI3', geometry=True, hydrogen_policy='explicit')


def calculate_Phi(smiles: str) -> dict:
    """Compute the graph-based molecular flexibility index Phi. No conformer is generated.
    Hydrogen policy: explicit. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcPhi', geometry=False, hydrogen_policy='explicit')


def calculate_RDF(smiles: str) -> dict:
    """Compute the complete RDKit radial-distribution-function descriptor vector. Geometry uses
    one ETKDGv3 seed42 conformer without force-field optimization; no ensemble or
    experimental structure is implied. Hydrogen policy: explicit. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcRDF', geometry=True, hydrogen_policy='explicit')


def calculate_RadiusOfGyration(smiles: str) -> dict:
    """Compute the molecular radius of gyration. Geometry uses one ETKDGv3 seed42 conformer
    without force-field optimization; no ensemble or experimental structure is implied.
    Hydrogen policy: explicit. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcRadiusOfGyration', geometry=True, hydrogen_policy='explicit')


def calculate_SpherocityIndex(smiles: str) -> dict:
    """Compute the molecular spherocity shape index. Geometry uses one ETKDGv3 seed42 conformer
    without force-field optimization; no ensemble or experimental structure is implied.
    Hydrogen policy: explicit. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcSpherocityIndex', geometry=True, hydrogen_policy='explicit')


def calculate_TPSA(smiles: str) -> dict:
    """Compute topological polar surface area in angstrom^2 from RDKit atomic fragment
    contributions; the default N/O model excludes sulfur/phosphorus contributions. No
    conformer is generated. Hydrogen policy: remove. Return the scientific value with
    named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcTPSA', geometry=False, hydrogen_policy='remove')


def calculate_WHIM(smiles: str) -> dict:
    """Compute the complete weighted holistic invariant molecular (WHIM) descriptor vector.
    Geometry uses one ETKDGv3 seed42 conformer without force-field optimization; no
    ensemble or experimental structure is implied. Hydrogen policy: explicit. Return the
    scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcWHIM', geometry=True, hydrogen_policy='explicit')


def customprop_vsa(smiles: str):
    'CustomPropertyVSA retired: The old function never implemented custom atom-property VSA; it computed explicit-H Labute ASA. Use GetLabuteASA. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CustomPropertyVSA retired: The old function never implemented custom atom-property VSA; it computed explicit-H Labute ASA. Use GetLabuteASA. See the catalog migration feedback for explicit arguments.')


def get_atom_features(smiles: str) -> dict:
    'Return zero-based indexed features values from the RDKit hydrogen-suppressed parsed graph. Raw RDKit feature-vector positions are preserved rather than assigned guessed chemical labels. Full finite values are returned as JSON; invalid structures raise errors.'
    from .molecular_operations import atom_properties
    return atom_properties(smiles, 'features')


def get_AtomPairFingerprint(smiles: str):
    'GetAtomPairFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetAtomPairFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def get_ConnectivityInvariants(smiles: str):
    """
    This tool computes connectivity invariants, similar to ECFP (Extended Connectivity Fingerprints), for a given molecule. These invariants serve as a fingerprint representation of the molecule's structural connectivity, aiding in tasks such as similarity comparison and molecular structure representation.    Args:
        smiles: a SMILES string. Please Input SMILES directly without any other characters。
    Returns:
        str: A markdown string with the connectivity invariants of the molecule(a list of int values), or an error message.
    """
    try:
        smiles = smiles.replace(" ", "").replace("\n", "")
        if "smiles=" in smiles:
            name, smiles = smiles.split("=")

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")
        invariants = rdMolDescriptors.GetConnectivityInvariants(mol)
        markdown = f"""##Get Connectivity Invariants
**Input SMILES:** {smiles}
**Connectivity Invariants:** {invariants}
"""
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


def get_FeatureInvariants(smiles: str):
    """
    This tool computes feature invariants, similar to FCFP (Feature Centroid Fingerprints), for a given molecule. These invariants provide a fingerprint representation of the molecule's features, aiding in tasks such as similarity comparison and molecular structure analysis.
    Args:
        smiles: a SMILES string. Please Input SMILES directly without any other characters。
    Returns:
        str: A markdown string with the feature invariants of the molecule(a list of int), or an error message.
    """
    try:
        smiles = (
            smiles.replace(" ", "")
            .replace("\n", "")
            .replace("'", "")
            .replace('"', "")
            
        )
        if "smiles=" in smiles:
            name, smiles = smiles.split("=")
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")
        invariants = rdMolDescriptors.GetFeatureInvariants(mol)
        markdown = f"""##Get Feature Invariants
**Input SMILES:** {smiles}
**Feature Invariants:** {invariants}
"""
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


def get_AtomPairCode(smiles: str):
    'GetAtomPairCode retired: One atom-code kernel exposes selected/all atoms and explicit chirality. Use AtomPairCodes. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetAtomPairCode retired: One atom-code kernel exposes selected/all atoms and explicit chirality. Use AtomPairCodes. See the catalog migration feedback for explicit arguments.')


def get_Hybridization(smiles: str) -> dict:
    'Return zero-based indexed hybridization values from the RDKit hydrogen-suppressed parsed graph. Raw RDKit feature-vector positions are preserved rather than assigned guessed chemical labels. Full finite values are returned as JSON; invalid structures raise errors.'
    from .molecular_operations import atom_properties
    return atom_properties(smiles, 'hybridization')


def get_ring_systems(smiles: str):
    """
    Compute fused/bridged ring atom groups from RDKit perceived rings.
    Rings join when they share at least two atoms with an accumulated group.
    Rings sharing only one spiro atom remain separate groups. This explicit
    grouping convention is not an assertion that spiro rings are disconnected.
    Args:
        smiles: a SMILES string. Please Input SMILES directly without any other characters。
    Returns:
        str: Markdown containing a Python list of atom-index sets (zero-based
            RDKit indices), or an error message. Set ordering is not chemical
            identity; the result is not a JSON array of ring lists.
    """
    try:
        smiles = (
            smiles.replace(" ", "")
            .replace("\n", "")
            .replace("'", "")
            .replace('"', "")
            
        )
        if "smiles=" in smiles:
            name, smiles = smiles.split("=")
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")
        markdown = f"""##Get Ring Systems
**Input SMILES:** {smiles}
**Ring Systems:**
"""
        ri = mol.GetRingInfo()
        systems = []
        includeSpiro = False
        for ring in ri.AtomRings():
            ringAts = set(ring)
            nSystems = []
            for system in systems:
                nInCommon = len(ringAts.intersection(system))
                if nInCommon and (includeSpiro or nInCommon > 1):
                    ringAts = ringAts.union(system)
                else:
                    nSystems.append(system)
            nSystems.append(ringAts)
            systems = nSystems
        markdown += str(systems)
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


# GetMACCSKeysFingerprint
def get_MACCSKeysFingerprint(smiles: str):
    'GetMACCSKeysFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetMACCSKeysFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def get_MorganFingerprint(smiles: str):
    'GetMorganFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetMorganFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def get_TopologicalTorsionFingerprint(smiles: str):
    'GetTopologicalTorsionFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetTopologicalTorsionFingerprint retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def get_USR(smiles: str) -> dict:
    """Compute the complete ultrafast-shape-recognition (USR) descriptor vector for the declared
    conformer. Geometry uses one ETKDGv3 seed42 conformer without force-field
    optimization; no ensemble or experimental structure is implied. Hydrogen policy:
    explicit. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'GetUSR', geometry=True, hydrogen_policy="explicit")


def get_USRCAT(smiles: str) -> dict:
    """Compute the complete atom-category USR (USRCAT) descriptor vector for the declared
    conformer. Geometry uses one ETKDGv3 seed42 conformer without force-field
    optimization; no ensemble or experimental structure is implied. Hydrogen policy:
    explicit. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'GetUSRCAT', geometry=True, hydrogen_policy="explicit")


def add_hydrogens(smiles: str) -> dict:
    'Apply RDKit add_hydrogens to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'add_hydrogens')


def add_wavabonds_for_stereoany(smiles: str):
    'AddWavyBondsForStereoAny retired: Wavy-bond display/stereo metadata needs an expressive source/output record. Use AddWavyStereoBonds. See the catalog migration feedback for explicit arguments.'
    raise ValueError('AddWavyBondsForStereoAny retired: Wavy-bond display/stereo metadata needs an expressive source/output record. Use AddWavyStereoBonds. See the catalog migration feedback for explicit arguments.')


def assign_AtomChiralTags_FromMolParity(smiles: str):
    'AssignAtomChiralTagsFromStructure retired: A SMILES-only graph did not supply coordinates required by the advertised operation. Use AssignChiralTagsFromCoordinates. See the catalog migration feedback for explicit arguments.'
    raise ValueError('AssignAtomChiralTagsFromStructure retired: A SMILES-only graph did not supply coordinates required by the advertised operation. Use AssignChiralTagsFromCoordinates. See the catalog migration feedback for explicit arguments.')


def assign_radicals(smiles: str) -> dict:
    'Apply RDKit assign_radicals to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'assign_radicals')


def assign_stereochemistry(smiles: str) -> dict:
    'Apply RDKit assign_stereochemistry to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'assign_stereochemistry')


def get_adjacency_matrix(smiles: str) -> dict:
    'Return an atom-indexed molecular graph adjacency matrix; distinct from inter-molecule fingerprint distances. Full finite values are returned as JSON; invalid structures raise errors.'
    from .molecular_operations import graph_matrix
    return graph_matrix(smiles, 'adjacency')


def get_AllowNontetrahedralChirality(smiles: str):
    'GetAllowNontetrahedralChirality retired: Process capabilities/configuration flags are not molecule-specific computations. Use RDKitCapabilities. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetAllowNontetrahedralChirality retired: Process capabilities/configuration flags are not molecule-specific computations. Use RDKitCapabilities. See the catalog migration feedback for explicit arguments.')


def get_DistanceMatrix(smiles: str) -> dict:
    'Return an atom-indexed molecular graph shortest_path matrix; distinct from inter-molecule fingerprint distances. Full finite values are returned as JSON; invalid structures raise errors.'
    from .molecular_operations import graph_matrix
    return graph_matrix(smiles, 'shortest_path')


def get_formal_charge(smiles: str):
    'GetFormalCharge retired: One charge inspection reports total and atom-level formal-charge evidence. Use MolecularFormalCharges. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetFormalCharge retired: One charge inspection reports total and atom-level formal-charge evidence. Use MolecularFormalCharges. See the catalog migration feedback for explicit arguments.')


def get_formal_charge_of_atoms(smiles: str):
    'GetFormalChargeOfAtoms retired: One charge inspection reports total and atom-level formal-charge evidence. Use MolecularFormalCharges. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetFormalChargeOfAtoms retired: One charge inspection reports total and atom-level formal-charge evidence. Use MolecularFormalCharges. See the catalog migration feedback for explicit arguments.')


def get_molfrags(smiles: str):
    """
    This tool identifies disconnected fragments within a molecule and returns them as atom identifiers or molecules. It allows for flexible representation and manipulation of the fragments in further analysis.
    Args:
        smiles: a SMILES string. Please Input SMILES directly without any other characters。
    Returns:
        str: A markdown string with a tuple containing the atom identifiers or molecules for each disconnected fragment within the molecule, or an error message.
    """
    try:
        smiles = (
            smiles.replace(" ", "")
            .replace("\n", "")
            .replace("'", "")
            .replace('"', "")
            
        )
        if "smiles=" in smiles:
            name, smiles = smiles.split("=")
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")
        frags = rdmolops.GetMolFrags(mol)
        markdown = f"""##Get Mol Frags
**Input SMILES:** {smiles}
**Mol Frags:**{frags}
"""
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


def get_UseLegacyStereoPerception(smiles: str):
    'GetUseLegacyStereoPerception retired: Process capabilities/configuration flags are not molecule-specific computations. Use RDKitCapabilities. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetUseLegacyStereoPerception retired: Process capabilities/configuration flags are not molecule-specific computations. Use RDKitCapabilities. See the catalog migration feedback for explicit arguments.')


def hapticbonds_to_dative(smiles: str) -> dict:
    'Apply RDKit haptic_to_dative to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'haptic_to_dative')


def has_query_hs(smiles: str):
    'HasQueryHs retired: Query hydrogen constraints need SMARTS, and MergeQueryHs returns a new query molecule. Use InspectQueryHydrogens, MergeQueryHydrogens. See the catalog migration feedback for explicit arguments.'
    raise ValueError('HasQueryHs retired: Query hydrogen constraints need SMARTS, and MergeQueryHs returns a new query molecule. Use InspectQueryHydrogens, MergeQueryHydrogens. See the catalog migration feedback for explicit arguments.')


def kekulize(smiles: str) -> dict:
    'Apply RDKit kekulize to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'kekulize')


def merge_queryhs(smiles: str):
    'MergeQueryHs retired: Query hydrogen constraints need SMARTS, and MergeQueryHs returns a new query molecule. Use InspectQueryHydrogens, MergeQueryHydrogens. See the catalog migration feedback for explicit arguments.'
    raise ValueError('MergeQueryHs retired: Query hydrogen constraints need SMARTS, and MergeQueryHs returns a new query molecule. Use InspectQueryHydrogens, MergeQueryHydrogens. See the catalog migration feedback for explicit arguments.')


def murcko_decompose(smiles: str) -> dict:
    'Apply RDKit murcko_scaffold to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'murcko_scaffold')


def remove_hydrogens(smiles: str) -> dict:
    'Apply RDKit remove_hydrogens to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'remove_hydrogens')


def remove_stereo_chemistry(smiles: str) -> dict:
    'Apply RDKit remove_stereochemistry to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'remove_stereochemistry')


def set_aromaticity(smiles: str) -> dict:
    'Apply RDKit set_aromaticity to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'set_aromaticity')


def set_bondstereo_from_directions(smiles: str) -> dict:
    'Apply RDKit set_bond_stereo_from_directions to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'set_bond_stereo_from_directions')
