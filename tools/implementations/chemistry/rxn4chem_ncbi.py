from src.utils.paths import local_root, artifacts_root
import logging
import time
import requests
from rdkit import Chem, DataStructs
from tools.implementations.shared.pubchem import (
    properties as pubchem_properties,
    smiles_property,
    PubChemUnavailable,
)
from rdkit.Chem import AllChem, rdMolDescriptors, Descriptors
from langchain import LLMChain, PromptTemplate
from langchain.chat_models import ChatOpenAI
import molbloom

from tools.implementations.shared.http_clients import send_novopro_request

from tools.implementations.chemistry.utils import *


def query_name_to_smiles(molecule_name: str):
    'NameToSMILES retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.'
    raise ValueError('NameToSMILES retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.')


def query_name_to_cas(molecule_name: str):
    'NameToCas retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.'
    raise ValueError('NameToCas retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.')


def check_patent_status(smiles: str):
    'CheckPatent retired: Old CheckPatent used a commercial ZINC Bloom filter and incorrectly labeled it patent status. Use QueryMoleculeCatalog. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CheckPatent retired: Old CheckPatent used a commercial ZINC Bloom filter and incorrectly labeled it patent status. Use QueryMoleculeCatalog. See the catalog migration feedback for explicit arguments.')


def predict_reaction(reactants: str) -> str:
    """
    Predict the outcome of a chemical reaction and return the result in Markdown format.
    Args:
        reactants (str): The SMILES string of the reactants separated by a dot '.'.
    Returns:
        str: A Markdown formatted string containing the reaction prediction.
    """
    if not is_smiles(reactants):
        return "Incorrect input."

    while True:
        time.sleep(2)
        response = rxn4chem.predict_reaction(reactants)
        if "prediction_id" in response.keys():
            break
    while True:
        time.sleep(2)

        results = rxn4chem.get_predict_reaction_results(response["prediction_id"])
        if "payload" in results["response"].keys():
            break

    res_dict = results["response"]["payload"]["attempts"][0]
    product = res_dict["productMolecule"]["smiles"]

    markdown_result = f"""
### Reaction Prediction

#### Reactants

- **Reactants**: `{reactants}`

#### Predicted Product

- **Product**: `{product}`

#### More Information

- [IBM RXN for Chemistry](https://rxn.res.ibm.com)
"""
    return markdown_result


def predict_retrosynthetic_pathway(product: str) -> str:
    """
    Predicts a retrosynthetic pathway for a given product SMILES and returns the first predicted pathway in Markdown format.
    Args:
        product (str): The SMILES string of the product.
    Returns:
        str: A Markdown formatted string containing the first retrosynthetic pathway.
    """

    response = rxn4chem.predict_automatic_retrosynthesis(product)
    results = rxn4chem.get_predict_automatic_retrosynthesis_results(
        response["prediction_id"]
    )
    if results["status"] == "SUCCESS":
        path = results["retrosynthetic_paths"][0]
        markdown_result = f"""
### Retrosynthetic Pathway Prediction

#### Product

- **Product**: `{product}`

#### Path

- **Path ID**: `{path['sequenceId']}`

#### More Information

- [IBM RXN for Chemistry](https://rxn.res.ibm.com)
"""
        return markdown_result
    else:
        return "Prediction failed."


def predict_reaction_properties(reactions: list) -> str:
    """
    Predicts reaction properties such as atom-to-atom mapping and reaction yield based on the provided model.
    Args:
        reactions (list): A list of reaction SMILES strings.
        ai_model (str): Model identifier, e.g., 'atom-mapping-2020' or 'yield-2020-08-10'.
    Returns:
        str: A Markdown formatted string containing predicted properties.
    """
    response = rxn4chem.predict_reaction_properties(
        reactions=reactions, ai_model="atom-mapping-2020"
    )
    properties = []
    for item in response["response"]["payload"]["content"]:
        properties.append(f"- **Property**: `{item['value']}`")

    markdown_result = f"""
### Reaction Properties Prediction

#### Reactions

- **Reactions**: `{', '.join(reactions)}`

#### Predicted Properties

{chr(10).join(properties)}

#### More Information

- [IBM RXN for Chemistry](https://rxn.res.ibm.com)
"""
    return markdown_result


def create_and_start_synthesis(sequence_id: str) -> str:
    """
    Creates a synthesis from a given sequence ID and starts it, returning the status and the synthesis plan.
    Args:
        sequence_id (str): The sequence ID from a retrosynthetic path.
    Returns:
        str: A Markdown formatted string containing the synthesis status and plan.
    """

    response = rxn4chem.create_synthesis_from_sequence(sequence_id)
    synthesis_id = response["synthesis_id"]
    synthesis_tree, ordered_tree_nodes, ordered_list_of_actions = (
        rxn4chem.get_synthesis_plan(synthesis_id)
    )
    actions = [f"- **Action**: `{action}`" for action in ordered_list_of_actions]
    status = rxn4chem.start_synthesis(synthesis_id)

    markdown_result = f"""
### Synthesis Creation and Start

#### Sequence ID

- **Sequence ID**: `{sequence_id}`

#### Synthesis Actions

{chr(10).join(actions)}

#### Synthesis Status

- **Status**: `{status['status']}`

#### More Information

- [IBM RXN for Chemistry](https://rxn.res.ibm.com)
"""
    return markdown_result


def calculate_molecule_similarity(smiles_pair: str):
    'MolSimilarity retired: Pair and matrix similarity/distance share one fingerprint comparison kernel. Use CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.'
    raise ValueError('MolSimilarity retired: Pair and matrix similarity/distance share one fingerprint comparison kernel. Use CompareMolecularFingerprints. See the catalog migration feedback for explicit arguments.')


def calculate_molecular_weight(smiles: str) -> str:
    """
    Calculate the average molar mass using RDKit atomic weights from SMILES.
    Explicit isotope labels are respected. This is not the monoisotopic exact mass.

    Args:
        smiles (str): The SMILES string of the molecule.

    Returns:
        str: A Markdown formatted string containing the molecular weight.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "Invalid SMILES string"

    mol_weight = Descriptors.MolWt(mol)

    markdown_result = f"""
### Molecular Weight Calculation

#### Input Molecule

- **SMILES**: `{smiles}`

#### Molecular Weight

- **Weight**: `{mol_weight:.2f} g/mol`
- **Method**: RDKit average atomic weights; explicit isotope labels respected.

"""
    return markdown_result




from functools import lru_cache

_FUNCTIONAL_GROUP_PATTERNS = {'furan': 'o1cccc1', 'aldehydes': ' [CX3H1](=O)[#6]', 'esters': ' [#6][CX3](=O)[OX2H0][#6]', 'ketones': ' [#6][CX3](=O)[#6]', 'amides': ' C(=O)-N', 'thiol groups': ' [SH]', 'alcohol groups': '[CX4][OX2H]', 'methylamide': '*-[N;D2]-[C;D3](=O)-[C;D1;H3]', 'carboxylic acids': '[CX3](=O)[OX2H1]', 'carbonyl methylester': '*-C(=O)[O;D2]-[C;D1;H3]', 'terminal aldehyde': '[CX3H1](=O)[#6]', 'amide': '*-C(=O)-[N;D1]', 'carbonyl methyl': '*-C(=O)-[C;D1;H3]', 'isocyanate': '*-[N;D2]=[C;D2]=[O;D1]', 'isothiocyanate': '*-[N;D2]=[C;D2]=[S;D1]', 'nitro': '*-[N;D3](=[O;D1])[O;D1]', 'nitroso': '*-[N;R0]=[O;D1]', 'oximes': '*=[N;R0]-[O;D1]', 'Imines': '*-[N;R0]=[C;D1;H2]', 'terminal azo': '*-[N;D2]=[N;D2]-[C;D1;H3]', 'hydrazines': '[NX3][NX3]', 'diazo': '[C]=[N+]=[N-]', 'cyano': '*-[C;D2]#[N;D1]', 'primary sulfonamide': '*-[S;D4](=[O;D1])(=[O;D1])-[N;D1]', 'methyl sulfonamide': '*-[N;D2]-[S;D4](=[O;D1])(=[O;D1])-[C;D1;H3]', 'sulfonic acid': '*-[S;D4](=O)(=O)-[O;D1]', 'methyl ester sulfonyl': '*-[S;D4](=O)(=O)-[O;D2]-[C;D1;H3]', 'methyl sulfonyl': '*-[S;D4](=O)(=O)-[C;D1;H3]', 'sulfonyl chloride': '*-[S;D4](=O)(=O)-[Cl]', 'methyl sulfinyl': '*-[S;D3](=O)-[C;D1]', 'methyl thio': '*-[S;D2]-[C;D1;H3]', 'thiols': '*-[S;D1]', 'thio carbonyls': '*=[S;D1]', 'halogens': '*-[#9,#17,#35,#53]', 't-butyl': '*-[C;D4]([C;D1])([C;D1])-[C;D1]', 'tri fluoromethyl': '*-[C;D4](F)(F)F', 'acetylenes': '*-[C;D2]#[C;D1;H]', 'cyclopropyl': '*-[C;D3]1-[C;D2]-[C;D2]1', 'ethoxy': '*-[O;D2]-[C;D2]-[C;D1;H3]', 'methoxy': '*-[O;D2]-[C;D1;H3]', 'side-chain hydroxyls': '[CX4][OX2H]', 'carbonyl groups': '[CX3]=[OX1]', 'primary amines': '[NX3H2;!$(N-C(=O));!$(N-S(=O)(=O))][#6]', 'nitriles': '*#[N;D1]'}

@lru_cache(maxsize=1)
def _functional_group_queries():
    by_pattern = {}
    for label, smarts in _FUNCTIONAL_GROUP_PATTERNS.items():
        smarts = smarts.strip()
        if smarts not in by_pattern:
            pattern = Chem.MolFromSmarts(smarts)
            if pattern is None:
                raise RuntimeError("Invalid internal functional-group SMARTS: " + label)
            by_pattern[smarts] = [label, [], pattern]
        else:
            by_pattern[smarts][1].append(label)
    return tuple((name, tuple(aliases), smarts, pattern) for smarts, (name, aliases, pattern) in by_pattern.items())

def list_functional_groups(smiles: str) -> dict:
    """Return a nonexhaustive named SMARTS functional-group screen with indexed evidence.

    Parse the molecule once and compile/cache the fixed query library once.
    Exact duplicate SMARTS labels are aliases within one group; different patterns
    remain separate and can overlap. No fragment removal or reaction inference.
    Atom indices use the hydrogen-suppressed graph; matching is chirality-agnostic.
    An empty group list is a successful negative screen, not proof of absence of
    all chemically possible functional groups.
    """
    from .core import molecule
    import hashlib
    import json
    mol = molecule(smiles, "remove")
    groups = []
    for name, aliases, smarts, pattern in _functional_group_queries():
        matches = mol.GetSubstructMatches(pattern, uniquify=True, useChirality=False)
        if matches:
            groups.append({"name": name, "aliases": list(aliases), "smarts": smarts,
                           "matches": [list(m) for m in matches], "match_count": len(matches)})
    return {"groups": groups, "canonical_smiles": Chem.MolToSmiles(mol),
            "library_sha256": hashlib.sha256(json.dumps(_FUNCTIONAL_GROUP_PATTERNS, sort_keys=True).encode()).hexdigest(),
            "operation_counts": {"molecule_parses": 1, "unique_patterns": len(_functional_group_queries())},
            "limitations": ["Fixed nonexhaustive overlapping SMARTS library", "No assay evidence"]}


def safety_summary(cas: str):
    'SafetySummary retired: One genuine PubChem record supplies raw safety sections and targeted GHS evidence. Use PubChemSafety. See the catalog migration feedback for explicit arguments.'
    raise ValueError('SafetySummary retired: One genuine PubChem record supplies raw safety sections and targeted GHS evidence. Use PubChemSafety. See the catalog migration feedback for explicit arguments.')


def check_explosiveness(cas: str):
    'CheckExplosiveness retired: One genuine PubChem record supplies raw safety sections and targeted GHS evidence. Use PubChemSafety. See the catalog migration feedback for explicit arguments.'
    raise ValueError('CheckExplosiveness retired: One genuine PubChem record supplies raw safety sections and targeted GHS evidence. Use PubChemSafety. See the catalog migration feedback for explicit arguments.')


def smiles_to_pdb(smiles):
    """
    Convert the SMILES of the compound into 3D structures and return them in Markdown format.

    Args:
        smiles (str): The SMILES of the compound.

    Returns:
        str: The Markdown content with SMILES to 3D structures.
    """
    data = {"sr": "smiles2pdb", "sq": smiles, "fmt": "pdb"}
    data_str = send_novopro_request(data=data)
    data_list = eval(data_str)

    BASE_URL_NOVOPRO = "https://www.novopro.cn/plus/tmp/"

    generated_markdown = ""
    if data_list is not None:
        pdb_url = BASE_URL_NOVOPRO + data_list[1]
        png_url = BASE_URL_NOVOPRO + data_list[2]

        generated_markdown = f"""
**2D图**

![GIF 图片]({png_url})

[点击下载3D模型文件]({pdb_url})
"""
    return generated_markdown


def predict_retrosynthetic_pathway(product: str) -> str:
    """
    Predicts a retrosynthetic pathway for a product SMILES and returns the first pathway with detailed SMILES for each step
    Args:
        product (str): The SMILES string of the product.
    Returns:
        str: A Markdown formatted string containing the first retrosynthetic pathway and reactions details.
    """
    response = rxn4chem.predict_automatic_retrosynthesis(product)

    # Check whether prediction_id was obtained successfully
    if "prediction_id" not in response:
        return "Failed to initiate retrosynthesis prediction. Response may lack 'prediction_id'."

    prediction_id = response["prediction_id"]
    max_retries = 10  # Set a maximum number of retries to avoid infinite loops
    retries = 0

    while retries < max_retries:
        results = rxn4chem.get_predict_automatic_retrosynthesis_results(prediction_id)
        status = results.get("status", "PENDING")

        if status == "SUCCESS":
            if "retrosynthetic_paths" in results and results["retrosynthetic_paths"]:
                path = results["retrosynthetic_paths"][0]
                reactions = collect_reactions(path)
                reaction_details = "\n".join(
                    [f"- **Reaction**: `{reaction}`" for reaction in reactions]
                )
                markdown_result = f"""
### Retrosynthetic Pathway Prediction

#### Product

- **Product**: `{product}`

#### Path

- **Path ID**: `{path['sequenceId']}`

#### Reactions Details

{reaction_details}

#### More Information

- [IBM RXN for Chemistry](https://rxn.res.ibm.com)
"""
                return markdown_result
            else:
                return "No retrosynthetic paths found in the results."
        elif status in ["NEW", "PENDING", "PROCESSING"]:
            time.sleep(15)  # Wait for 15 seconds before rechecking
            retries += 1
        else:
            error_message = results.get("errorMessage", "Unknown error occurred.")
            return f"Prediction failed with status: {status}. Error message: {error_message}."

    return "Prediction process exceeded maximum retries or timed out."


def collect_reactions(tree):
    reactions = []
    if "children" in tree and tree["children"]:
        reaction_smarts = "{}>>{}".format(
            ".".join([node["smiles"] for node in tree["children"]]), tree["smiles"]
        )
        reactions.append(reaction_smarts)
    for node in tree["children"]:
        reactions.extend(collect_reactions(node))
    return reactions


def predict_reaction_properties(reaction: str) -> str:
    """
    Predicts reaction properties such as atom-to-atom mapping and reaction yield for a single reaction SMILES string.
    Args:
        reaction (str): A reaction SMILES string.
    Returns:
        str: A Markdown formatted string containing predicted properties.
    """
    reactions = [reaction]

    response = rxn4chem.predict_reaction_properties(
        reactions=reactions, ai_model="atom-mapping-2020"
    )

    if (
        response
        and "response" in response
        and "payload" in response["response"]
        and "content" in response["response"]["payload"]
    ):
        properties = []
        for item in response["response"]["payload"]["content"]:
            properties.append(f"- **Property**: `{item['value']}`")

        markdown_result = f"""
### Reaction Properties Prediction

#### Reaction

- **Reaction**: `{reaction}`

#### Predicted Properties

{chr(10).join(properties)}

#### More Information

- [IBM RXN for Chemistry](https://rxn.res.ibm.com)
"""
        return markdown_result
    else:
        return "Failed to fetch reaction properties due to an invalid response."
