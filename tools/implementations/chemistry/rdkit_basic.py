from rdkit import Chem
from rdkit.Chem import rdMolEnumerator, rdDeprotect, rdSLNParse, rdMHFPFingerprint


# PatternFingerprintTemplate
def get_pattern_fingerprint(smiles):
    'GetPatternFingerprintTemplate retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetPatternFingerprintTemplate retired: One TautomerQuery construction supplies distinct inspection fields without repeated object setup. Use InspectTautomerQuery. See the catalog migration feedback for explicit arguments.')


# TautomerQueryCanSerialize
def can_serialize(smiles):
    'CanSerialize retired: Process capabilities/configuration flags are not molecule-specific computations. Use RDKitCapabilities. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CanSerialize retired: Process capabilities/configuration flags are not molecule-specific computations. Use RDKitCapabilities. See the catalog migration feedback for explicit arguments.')


# AssignCIPLabels
def assign_CIPlabels(smiles: str) -> dict:
    'Apply RDKit assign_cip_labels to the explicitly parsed SMILES graph; return a typed molecule report with atom/bond properties, canonical and Kekule SMILES, and a MOL connection table. No unknown stereochemistry, missing coordinates or experimental identity is inferred. Oxidation/CIP/radical assignments are exposed explicitly when present. Invalid input or backend failures raise errors.'
    from .molecular_operations import graph_operation
    return graph_operation(smiles, 'assign_cip_labels')


# Enumerate
def Enumerate(smiles):
    """
    The rdkit.Chem.rdMolEnumerator.Enumerate function is used to perform enumeration on a given molecule and returns a MolBundle object containing multiple molecules generated during the enumeration process.
    Args:
        smiles: a SMILES string. Input SMILES directly without any other characters.
    Returns:
        str: A markdown string wtih the enumeration results, or an error message.smiles = smiles.replace(" ", "").replace("\n", "").replace("\'", "").replace("\"", "").replace('.), '
    """
    try:
        mol = Chem.MolFromSmiles(smiles)

        mol_bundle = rdMolEnumerator.Enumerate(mol)
        num_mols = mol_bundle.Size()

        markdown = f"""
## Enumerate Molecule
**Input SMILES:** {smiles}

**Result**
**Number of molecules:** {num_mols}
**Molecular List:**
"""
        for i in range(num_mols):
            mol = mol_bundle.GetMol(i)
            markdown += Chem.MolToSmiles(mol)
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


def deprotect(smiles: str):
    """
     The rdkit.Chem.rdDeprotect.Deprotect function removes protecting groups from a molecule, returning the deprotected version.
    Args:
        smiles: a SMILES string. Input SMILES directly without any other characters.
    Returns:
        str: A markdown string wtih the deprotected SMILES, or an error message.
    """
    try:
        smiles = (
            smiles.replace(" ", "").replace("\n", "").replace("'", "").replace('"', "")
        )
        mol = Chem.MolFromSmiles(smiles)
        deprotected_mol = rdDeprotect.Deprotect(mol)

        markdown = f"""
## Deprotect Molecule
**Input SMILES:** {smiles}

**Result**
**Deprotected SMILES:** {Chem.MolToSmiles(deprotected_mol)}
"""
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


# CondenseAbbreviationSubstanceGroups
def condense_abbreviation_substance_groups(smiles):
    'CondenseAbbreviationSubstanceGroups retired: Abbreviation SGroups require an expressive source connection table. Use CondenseAbbreviations. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CondenseAbbreviationSubstanceGroups retired: Abbreviation SGroups require an expressive source connection table. Use CondenseAbbreviations. See the catalog migration feedback for explicit arguments.')


def sln_to_smiles(sln: str):
    """
    This tool is used to convert a SLN string to a SMILES string. Input SMILES directly without any other characters.
    Args:
        sln: a SLN string. Input SLN directly without any other characters.
    Returns:
        str: A markdown string wtih the SMILES, or an error message.
    """
    try:

        sln = sln.replace(" ", "").replace("\n", "").replace("'", "").replace('"', "")
        mol = rdSLNParse.MolFromSLN(sln)
        if mol is None:
            raise ValueError("Invalid SLN string.")
        smiles = Chem.MolToSmiles(mol)
        markdown = f"""
## SLN to SMILES
**Input SLN:** {sln}
**Output SMILES:** {smiles}
"""
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


def create_shingling(smiles: str):
    """
    This tool is used to create a shingling for a molecule.
    Args:
        smiles: a SMILES string. Input SMILES directly without any other characters.
    Returns:
        str: A markdown string wtih the shingling, or an error message.
    """
    try:
        smiles = (
            smiles.replace(" ", "").replace("\n", "").replace("'", "").replace('"', "")
        )

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            raise ValueError("Invalid SMILES string.")
        encoder = rdMHFPFingerprint.MHFPEncoder()
        shingling = encoder.CreateShinglingFromMol(mol)

        markdown = f"""
## Create Shingling
**Input SMILES:** {smiles}

**Result**
**Shingling Size:**{len(shingling)}
**Shingling:**
"""
        for element in shingling:
            markdown += element + ", "
        return markdown
    except Exception as e:
        markdown = f"An error occurred: {e}"
        return markdown


def encode_mol(smiles: str):
    'EncodeMolecule retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('EncodeMolecule retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


def encode_SECFP(smiles: str):
    'EncodeSECFP retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.'
    raise ValueError('EncodeSECFP retired: One declared fingerprint kernel replaces duplicate wrappers and implicit algorithm presets. Use MolecularFingerprint. See the catalog migration feedback for explicit arguments.')


# rdMolDescriptors.BCUT2D
def get_BCUT(smiles: str) -> dict:
    """Compute the ordered BCUT2D eigenvalue descriptor vector using RDKit mass, Gasteiger-charge
    and Crippen atom-property weightings. No conformer is generated. Hydrogen policy:
    remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'BCUT2D', geometry=False, hydrogen_policy='remove')


# CalcAUTOCORR2D
def calculate_Autocorrelation2D(smiles: str) -> dict:
    """Compute the complete 2D molecular autocorrelation descriptor vector using graph distances.
    No conformer is generated. Hydrogen policy: remove. Return the scientific value with
    named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcAUTOCORR2D', geometry=False, hydrogen_policy='remove')


# CalcAUTOCORR3D
def calculate_Autocorrelation3D(smiles: str) -> dict:
    """Compute the complete 3D molecular autocorrelation descriptor vector using the declared
    conformer. Geometry uses one ETKDGv3 seed42 conformer without force-field
    optimization; no ensemble or experimental structure is implied. Hydrogen policy:
    remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcAUTOCORR3D', geometry=True, hydrogen_policy='remove')


def calculate_asphericity(smiles: str) -> dict:
    """Compute the molecular asphericity shape descriptor. Geometry uses one ETKDGv3 seed42
    conformer without force-field optimization; no ensemble or experimental structure is
    implied. Hydrogen policy: remove. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcAsphericity', geometry=True, hydrogen_policy='remove')


def calculate_chi0n(smiles: str) -> dict:
    """Compute the RDKit Chi0n molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi0n', geometry=False, hydrogen_policy='remove')


def calculate_chi0v(smiles: str) -> dict:
    """Compute the RDKit Chi0v molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi0v', geometry=False, hydrogen_policy='remove')


def calculate_chi1n(smiles: str) -> dict:
    """Compute the RDKit Chi1n molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi1n', geometry=False, hydrogen_policy='remove')


def calculate_chi1v(smiles: str) -> dict:
    """Compute the RDKit Chi1v molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi1v', geometry=False, hydrogen_policy='remove')


def calculate_chi2n(smiles: str) -> dict:
    """Compute the RDKit Chi2n molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi2n', geometry=False, hydrogen_policy='remove')


def calculate_chi2v(smiles: str) -> dict:
    """Compute the RDKit Chi2v molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi2v', geometry=False, hydrogen_policy='remove')


def calculate_chi3n(smiles: str) -> dict:
    """Compute the RDKit Chi3n molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi3n', geometry=False, hydrogen_policy='remove')


def calculate_chi3v(smiles: str) -> dict:
    """Compute the RDKit Chi3v molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi3v', geometry=False, hydrogen_policy='remove')


def calculate_chi4n(smiles: str) -> dict:
    """Compute the RDKit Chi4n molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi4n', geometry=False, hydrogen_policy='remove')


def calculate_chi4v(smiles: str) -> dict:
    """Compute the RDKit Chi4v molecular connectivity index, preserving the named order and n/v
    definition. No conformer is generated. Hydrogen policy: remove. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcChi4v', geometry=False, hydrogen_policy='remove')


def calculate_coulombmatrix(smiles: str) -> dict:
    """Return the complete RDKit Coulomb descriptor sequence without assuming an independently
    verified matrix-axis convention or physical energy interpretation. Geometry uses one
    ETKDGv3 seed42 conformer without force-field optimization; no ensemble or experimental
    structure is implied. Hydrogen policy: explicit. Return the scientific value with
    named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcCoulombMat', geometry=True, hydrogen_policy='explicit')


def calculate_crippen_descriptors(smiles: str) -> dict:
    """Retired pair wrapper; select MolLogP/MolMR on MolecularElectronicDescriptors."""
    raise NotImplementedError("GetCrippenDescriptors retired; use MolecularElectronicDescriptors(smiles=smiles, descriptors=['MolLogP','MolMR']). Values are named descriptor fields rather than a positional value pair; no automatic signature/output alias is supplied")


def calculate_EEMcharges(smiles: str) -> dict:
    """Compute atom-indexed electronegativity-equalization-model partial charges. Geometry uses
    one ETKDGv3 seed42 conformer without force-field optimization; no ensemble or
    experimental structure is implied. Hydrogen policy: explicit. Return the scientific
    value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcEEMcharges', geometry=True, hydrogen_policy='explicit')


def calculate_Eccentricity(smiles: str) -> dict:
    """Compute the molecular eccentricity shape descriptor. Geometry uses one ETKDGv3 seed42
    conformer without force-field optimization; no ensemble or experimental structure is
    implied. Hydrogen policy: explicit. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcEccentricity', geometry=True, hydrogen_policy='explicit')


def calculate_exact_molweight(smiles: str) -> dict:
    """Compute exact molecular mass in Da, retaining explicitly encoded isotope labels; this
    differs from isotope-averaged mass and does not infer adduct m/z. No conformer is
    generated. Hydrogen policy: remove. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcExactMolWt', geometry=False, hydrogen_policy='remove')


def calculate_FractionCSP3(smiles: str) -> dict:
    """Compute the fraction of carbon atoms that are sp3 hybridized; this is a graph-composition
    fraction, not a measured 3D shape. No conformer is generated. Hydrogen policy: remove.
    Return the scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcFractionCSP3', geometry=False, hydrogen_policy='remove')


def calculate_GETAWAY(smiles: str) -> dict:
    """Compute the complete GETAWAY molecular descriptor vector; undefined components remain null
    with explicit indices and partially_undefined status rather than zero imputation.
    Geometry uses one ETKDGv3 seed42 conformer without force-field optimization; no
    ensemble or experimental structure is implied. Hydrogen policy: explicit. Return the
    scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcGETAWAY', geometry=True, hydrogen_policy='explicit')


def calculate_HallKierAlpha(smiles: str) -> dict:
    """Compute the Hall-Kier alpha graph correction using the installed RDKit atomic conventions.
    No conformer is generated. Hydrogen policy: remove. Return the scientific value with
    named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcHallKierAlpha', geometry=False, hydrogen_policy='remove')


def calculate_InertialShapeFactor(smiles: str) -> dict:
    """Compute the molecular inertial shape factor. Geometry uses one ETKDGv3 seed42 conformer
    without force-field optimization; no ensemble or experimental structure is implied.
    Hydrogen policy: explicit. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcInertialShapeFactor', geometry=True, hydrogen_policy='explicit')


def calculate_Kappa1(smiles: str) -> dict:
    """Compute the graph-based Kier Kappa1 molecular shape index. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcKappa1', geometry=False, hydrogen_policy='remove')


def calculate_Kappa2(smiles: str) -> dict:
    """Compute the graph-based Kier Kappa2 molecular shape index. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcKappa2', geometry=False, hydrogen_policy='remove')


def calculate_Kappa3(smiles: str) -> dict:
    """Compute the graph-based Kier Kappa3 molecular shape index. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcKappa3', geometry=False, hydrogen_policy='remove')


def calculate_LabuteASA(smiles: str, hydrogen_policy: str = "remove") -> dict:
    """Compute the RDKit Labute approximate surface-area descriptor in angstrom^2 under an
    explicit hydrogen policy; this is not custom-property VSA or a solvent-accessible
    surface calculation. No conformer is generated. Hydrogen policy: caller-selected.
    Return the scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, "CalcLabuteASA", hydrogen_policy=hydrogen_policy)


def calculate_MORSE(smiles: str) -> dict:
    """Compute the complete 3D-MoRSE molecular descriptor vector from the declared conformer.
    Geometry uses one ETKDGv3 seed42 conformer without force-field optimization; no
    ensemble or experimental structure is implied. Hydrogen policy: explicit. Return the
    scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcMORSE', geometry=True, hydrogen_policy='explicit')


def calculate_MolFormula(smiles: str) -> dict:
    """Compute the molecular formula from the supplied molecular graph, retaining RDKit
    isotope/charge notation; do not infer a different fragment, tautomer or protonation
    state. No conformer is generated. Hydrogen policy: remove. Return the scientific value
    with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcMolFormula', geometry=False, hydrogen_policy='remove')


def calculate_NPR1(smiles: str):
    'GetNPR1 retired: One NPR1/NPR2 core exposes geometry and optimization policy explicitly. Use NormalizedPrincipalMoments. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetNPR1 retired: One NPR1/NPR2 core exposes geometry and optimization policy explicitly. Use NormalizedPrincipalMoments. See the catalog migration feedback for explicit arguments.')


def calculate_NPR2(smiles: str):
    'GetNPR2 retired: One NPR1/NPR2 core exposes geometry and optimization policy explicitly. Use NormalizedPrincipalMoments. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetNPR2 retired: One NPR1/NPR2 core exposes geometry and optimization policy explicitly. Use NormalizedPrincipalMoments. See the catalog migration feedback for explicit arguments.')


def calculate_NumAliphaticCarbocycles(smiles: str) -> dict:
    """Count RDKit nonaromatic rings containing only carbon atoms. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAliphaticCarbocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumAliphaticHeterocycles(smiles: str) -> dict:
    """Count RDKit nonaromatic rings containing at least one noncarbon ring atom. No conformer is
    generated. Hydrogen policy: remove. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAliphaticHeterocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumAliphaticRings(smiles: str) -> dict:
    """Count RDKit nonaromatic rings, including carbon-only and heteroatom-containing rings. No
    conformer is generated. Hydrogen policy: remove. Return the scientific value with
    named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAliphaticRings', geometry=False, hydrogen_policy='remove')


def calculate_NumAmideBonds(smiles: str) -> dict:
    """Count amide bonds using RDKit molecular substructure rules. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAmideBonds', geometry=False, hydrogen_policy='remove')


def calculate_NumAromaticCarbocycles(smiles: str) -> dict:
    """Count RDKit aromatic rings whose ring atoms are all carbon. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAromaticCarbocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumAromaticHeterocycles(smiles: str) -> dict:
    """Count RDKit aromatic rings containing a noncarbon ring atom. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAromaticHeterocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumAromaticRings(smiles: str) -> dict:
    """Count aromatic rings under RDKit ring perception. No conformer is generated. Hydrogen
    policy: remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAromaticRings', geometry=False, hydrogen_policy='remove')


def calculate_NumAtomStereoCenters(smiles: str) -> dict:
    """Count RDKit atom stereocenters, including unspecified centers; this is not a count of
    experimentally determined configurations. No conformer is generated. Hydrogen policy:
    remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumAtomStereoCenters', geometry=False, hydrogen_policy='remove')


def calculate_NumAtoms(smiles: str):
    'GetAtomsNum retired: One inventory-count API makes the atom subset and hydrogen/parser policy explicit. Use CountMolecularAtoms. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetAtomsNum retired: One inventory-count API makes the atom subset and hydrogen/parser policy explicit. Use CountMolecularAtoms. See the catalog migration feedback for explicit arguments.')


def calculate_NumBridgeheadAtoms(smiles: str) -> dict:
    """Count bridgehead atoms under RDKit ring perception. No conformer is generated. Hydrogen
    policy: remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumBridgeheadAtoms', geometry=False, hydrogen_policy='remove')


def calculate_NumHBA(smiles: str) -> dict:
    """Count hydrogen-bond acceptor sites using RDKit functional-group SMARTS rules; do not
    substitute its simpler N/O Lipinski heuristic. No conformer is generated. Hydrogen
    policy: remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumHBA', geometry=False, hydrogen_policy='remove')


def calculate_NumHBD(smiles: str) -> dict:
    """Count hydrogen-bond donor sites using RDKit functional-group SMARTS rules; this counts
    donor sites rather than the simpler number of N/O-attached hydrogens. No conformer is
    generated. Hydrogen policy: remove. Return the scientific value with named backend,
    version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumHBD', geometry=False, hydrogen_policy='remove')


def calculate_NumHeavyAtoms(smiles: str):
    'GetHeavyAtomsNum retired: One inventory-count API makes the atom subset and hydrogen/parser policy explicit. Use CountMolecularAtoms. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetHeavyAtomsNum retired: One inventory-count API makes the atom subset and hydrogen/parser policy explicit. Use CountMolecularAtoms. See the catalog migration feedback for explicit arguments.')


def calculate_NumHeteroatoms(smiles: str):
    'GetHeteroatomsNum retired: One inventory-count API makes the atom subset and hydrogen/parser policy explicit. Use CountMolecularAtoms. See the catalog migration feedback for explicit arguments.'
    raise ValueError('GetHeteroatomsNum retired: One inventory-count API makes the atom subset and hydrogen/parser policy explicit. Use CountMolecularAtoms. See the catalog migration feedback for explicit arguments.')


def calculate_NumHeterocycles(smiles: str) -> dict:
    """Count RDKit rings containing at least one heteroatom. No conformer is generated. Hydrogen
    policy: remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumHeterocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumLipinskiHBA(smiles: str) -> dict:
    """Count nitrogen and oxygen atoms using RDKit CalcNumLipinskiHBA; this simple heuristic
    differs from functional-group hydrogen-bond acceptor detection and does not itself
    establish oral bioavailability. No conformer is generated. Hydrogen policy: remove.
    Return the scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumLipinskiHBA', geometry=False, hydrogen_policy='remove')


def calculate_NumLipinskiHBD(smiles: str) -> dict:
    """Count hydrogens attached to nitrogen or oxygen using RDKit CalcNumLipinskiHBD; this
    heuristic differs from functional-group donor-site counts and does not itself
    establish oral bioavailability. No conformer is generated. Hydrogen policy: remove.
    Return the scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumLipinskiHBD', geometry=False, hydrogen_policy='remove')


def calculate_NumRings(smiles: str) -> dict:
    """Count rings in the RDKit SSSR-based ring-perception result; this is not a count of every
    possible graph cycle. No conformer is generated. Hydrogen policy: remove. Return the
    scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumRings', geometry=False, hydrogen_policy='remove')


def calculate_NumRotatableBonds(smiles: str) -> dict:
    """Count rotatable bonds using the installed RDKit default rotor definition; backend version
    and hydrogen policy are reported. No conformer is generated. Hydrogen policy: remove.
    Return the scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumRotatableBonds', geometry=False, hydrogen_policy='remove')


def calculate_NumSaturatedCarbocycles(smiles: str) -> dict:
    """Count RDKit saturated rings containing only carbon atoms. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumSaturatedCarbocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumSaturatedHeterocycles(smiles: str) -> dict:
    """Count RDKit saturated rings containing a noncarbon ring atom. No conformer is generated.
    Hydrogen policy: remove. Return the scientific value with named backend, version and
    molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumSaturatedHeterocycles', geometry=False, hydrogen_policy='remove')


def calculate_NumSaturatedRings(smiles: str) -> dict:
    """Count saturated rings under RDKit ring perception. No conformer is generated. Hydrogen
    policy: remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumSaturatedRings', geometry=False, hydrogen_policy='remove')


def calculate_NumSpiroAtoms(smiles: str) -> dict:
    """Count spiro atoms under RDKit ring perception. No conformer is generated. Hydrogen policy:
    remove. Return the scientific value with named backend, version and molecular
    provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumSpiroAtoms', geometry=False, hydrogen_policy='remove')


def calculate_NumUnspecifiedAtomStereoCenters(smiles: str) -> dict:
    """Count RDKit atom stereocenters whose configuration is unspecified; do not assign a missing
    configuration. No conformer is generated. Hydrogen policy: remove. Return the
    scientific value with named backend, version and molecular provenance."""
    from .molecular_analysis import descriptor_value
    return descriptor_value(smiles, 'CalcNumUnspecifiedAtomStereoCenters', geometry=False, hydrogen_policy='remove')
