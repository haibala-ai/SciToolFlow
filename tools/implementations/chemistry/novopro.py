import logging
import re
from rdkit import Chem
import html2text
import selfies as sf
import random

from .utils import is_smiles
from tools.implementations.shared.http_clients import send_chemspider_request


# IsValidInChIKey
def is_valid_inchikey(inchikey: str) -> str:
    """Validate the standard InChIKey string format locally; does not assert database membership."""
    return (
        "true"
        if re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", inchikey.strip())
        else "false"
    )


def smiles_to_inchi(smiles: str) -> str:
    """
    Convert a SMILES string to an InChI string.
    Args:
        smiles: SMILES string.
    Return:
        str: The Markdown content with InChI.
    """
    try:
        cleaned_smiles = smiles.replace("\n", "").replace(" ", "")
        mol = Chem.MolFromSmiles(cleaned_smiles)
        inchi = Chem.MolToInchi(mol)
        if is_smiles(cleaned_smiles):
            #     data ={
            #         "smiles": cleaned_smiles,
            #     }
            #     response = send_chemspider_request("http://legacy.chemspider.com/InChI.asmx/SMILESToInChI", data)
            #     h = html2text.HTML2Text()
            #     result = h.handle(response)
            markdown = f"""
**SMILES to InChI**
SMILES={cleaned_smiles}
**Result:**
{inchi}
"""
            return markdown
        else:
            return "Invalid SMILES input."
    except Exception as e:
        logging.error(f"Error SMILES to InChI: {e}")


# InChIKeyToSMILES
def inchikey_to_smiles(inchikey: str):
    'InChIKeyToSMILES retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.'
    raise ValueError('InChIKeyToSMILES retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.')


# InChIKeyToInChI
def inchikey_to_inchi(inchikey: str):
    'InChIKeyToInChI retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.'
    raise ValueError('InChIKeyToInChI retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.')


# InChIKeyToMOL
def inchikey_to_mol(inchikey: str):
    'InChIKeyToMOL retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.'
    raise ValueError('InChIKeyToMOL retired: One PubChem structure resolver exposes namespace, output representation and ambiguous-record policy. Use ResolveChemicalIdentifier. See the catalog migration feedback for explicit arguments.')


# InChIToSMILES
def inchi_to_smiles(inchi: str) -> str:
    """
    Convert an InChI string to a SMILES string.

    The retired ChemSpider legacy ASMX route is no longer used; the conversion is
    performed locally with RDKit and an invalid InChI is reported as an error
    instead of a success message.

    Args:
        inchi: InChI string.
    Return:
        str: The Markdown content with SMILES.
    """
    text = (inchi or "").strip()
    if not text:
        raise ValueError("Require a non-empty InChI string")
    processed_inchi = text if text.startswith("InChI=") else "InChI=" + text
    molecule = Chem.MolFromInchi(processed_inchi)
    if molecule is None:
        raise ValueError("Invalid InChI string")
    smiles = Chem.MolToSmiles(molecule)
    return f"""
**InChI to SMILES**
{processed_inchi}
**SMILES:**
{smiles}
"""


def inchi_to_inchikey(inchi: str) -> str:
    """Compute an InChIKey locally with the installed RDKit InChI implementation."""
    molecule = Chem.MolFromInchi(inchi.strip())
    if molecule is None:
        raise ValueError("Invalid InChI")
    return Chem.MolToInchiKey(molecule)


# InChIToCSID
def inchi_to_csid(inchi: str) -> str:
    """
    Convert InChI to ChemSpider ID.
    Args:
        inchi: InChI string.
    Return:
        str: The Markdown content with CSID.
    """
    try:
        cleaned_inchi = inchi.replace("\n", "").replace(" ", "")
        data = {
            "inchi": cleaned_inchi,
        }
        response = send_chemspider_request(
            "http://legacy.chemspider.com/InChI.asmx/InChIToCSID", data
        )
        h = html2text.HTML2Text()
        result = h.handle(response)
        markdown = f"""
**InChI to CSID**
Input: {cleaned_inchi}
**Reuslt**
{result}
"""
        return markdown
    except Exception as e:
        logging.error(f"Error InChI to CSID: {e}")


# SMILEStoSELFIES
def smiles_to_selfies(smiles: str) -> str:
    """
    Translates a SMILES string into its corresponding SELFIES string.
    Args:
        smiles: SMILES string.
    Return:
        str: The Markdown content with SELFIES.
    """
    try:
        cleaned_smiles = smiles.replace("\n", "").replace(" ", "")
        if is_smiles(cleaned_smiles):
            selfies = sf.encoder(cleaned_smiles)
            markdown = f"""
**SMILES to SELFIES**
Input: {cleaned_smiles}

**Reuslt**
{selfies}
"""
            return markdown
        else:
            return "Invalid SMILES input."
    except Exception as e:
        logging.error(f"Error SMILES to SELFIES: {e}")


# SELFIEStoSMILES
def selfies_to_smiles(selfies: str) -> str:
    """
    Translates a SELFIES string into its corresponding SMILES string.
    Args:
        selfies: SELFIES string.
    Return:
        str: The Markdown content with SMILES.
    """
    try:
        smiles = sf.decoder(selfies)
        markdown = f"""
**SELFIES to SMILES**
Input: {selfies}

**Reuslt**
{smiles}
"""
        return markdown
    except Exception as e:
        logging.error(f"Error SELFIES to SMILES: {e}")


# RandomMoelcule
def generate_random_molecule(length: str):
    'RandomMoelcule retired: Random SELFIES sampling now declares token length, seed and replacement policy. Use GenerateRandomSELFIES. See the catalog migration feedback for explicit arguments.'
    raise ValueError('RandomMoelcule retired: Random SELFIES sampling now declares token length, seed and replacement policy. Use GenerateRandomSELFIES. See the catalog migration feedback for explicit arguments.')


# Length_SELFIES
def length_selfies(selfies: str):
    'Length_SELFIES retired: One token inspection returns both tokens and the installed semantic-symbol count. Use InspectSELFIES. See the catalog migration feedback for explicit arguments.'
    raise ValueError('Length_SELFIES retired: One token inspection returns both tokens and the installed semantic-symbol count. Use InspectSELFIES. See the catalog migration feedback for explicit arguments.')


# Split_SELFIES
def split_selfies(selfies: str):
    'Split_SELFIES retired: One token inspection returns both tokens and the installed semantic-symbol count. Use InspectSELFIES. See the catalog migration feedback for explicit arguments.'
    raise ValueError('Split_SELFIES retired: One token inspection returns both tokens and the installed semantic-symbol count. Use InspectSELFIES. See the catalog migration feedback for explicit arguments.')
