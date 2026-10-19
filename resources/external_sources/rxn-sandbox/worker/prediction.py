import logging
from collections import Counter
from typing import Dict, List
import numpy as np
from rdkit import Chem
from utils import standardize_molecules
from model_loading import predict_smiles

logger = logging.getLogger()

RXN_SMILES_SEPARATOR = ">>"


def matching_atomic_numbers(
    product_atomic_numbers: List[int],
    reactant_atomic_numbers: List[int],
    ignore_stoichiometry: bool = True,
) -> bool:
    """
    Check for matching atomic numbers in products and reactants.

    Args:
        product_atomic_numbers (List[int]): list of atomic numbers for the atoms in the product(s).
        reactant_atomic_numbers (List[int]): list of atomic numbers for the atoms in the reactant(s).
        ignore_stoichiometry (bool): whether stoichiometry is ignored. Default to True.

    Returns:
        bool: whether the atomic numbers are matching.
    """
    container_type = set if ignore_stoichiometry else list
    atomic_numbers_difference = Counter(
        container_type(product_atomic_numbers)
    ) - Counter(container_type(reactant_atomic_numbers))
    return sum(atomic_numbers_difference.values()) == 0


def forward_reaction(
    smiles_list: List[str],
    lit,
) -> List[Dict]:
    """
    Get structured results and pictures from a batch reaction prediction.

    Args:
        smiles_list (List[str]): List of reactants SMILES.
        lit (Translator): predictive model.

    Returns:
        Dict[str, List[Dict[str, Any]]]: Dict of predictions lists from the model.
    """

    # Make product predictions
    results_list = predict_smiles(lit, smiles_list, batch_size=512)

    # Get the products, reactants and confidences
    reactants_list = [result["source"] for result in results_list]
    predicted_list = [result["predicted_target"] for result in results_list]
    confidence_list = [result["confidence"] for result in results_list]

    # Start list to save the results
    final_results_list = []

    # Loop the prediction results data
    for (
        predicted_smiles,
        confidence,
        reactants,
    ) in zip(
        predicted_list,
        confidence_list,
        reactants_list,
    ):
        try:
            # process predicted SMILES and get molecules
            predicted_mol = Chem.MolFromSmiles(predicted_smiles)
            predicted_can_smiles = standardize_molecules(
                predicted_smiles,
                canonicalize=True,
                sanitize=True,
                fragment_bond="~",
                ordered_precursors=False,
            )
            reactants_mol = Chem.MolFromSmiles(reactants)
            # sanity check on atomic numbers
            products_atoms = [atom.GetAtomicNum() for atom in predicted_mol.GetAtoms()]
            reactants_atoms = [atom.GetAtomicNum() for atom in reactants_mol.GetAtoms()]
            atoms_ok = matching_atomic_numbers(products_atoms, reactants_atoms)
            if not atoms_ok:
                predicted_can_smiles = ""
                logger.info("Atoms not ok!")
            # represent reaction SMARTS
            reaction_smiles = reactants + RXN_SMILES_SEPARATOR + predicted_can_smiles

        except Exception as errrr:
            logger.error(errrr)
            reaction_smiles = (
                reactants + RXN_SMILES_SEPARATOR + predicted_smiles
            ).replace(" ", "")
            message = "Invalid SMILES predicted"
            logger.info("Predicted invalid reaction")

        # Create the product prediction object and append it to results list
        final_results_list.append(
            {
                "reactants": reactants,
                "product": predicted_smiles,
                "confidence": float(np.exp(confidence)),  # Convert confidence to probability
                "smiles": reaction_smiles,
            }
        )

    # Return product prediction results
    return final_results_list


def retro_reaction(
    smiles: str,
    lit,
) -> List[Dict]:
    """
    Get structured results and pictures from a batch reaction prediction.

    Args:
        smiles (str): Reactants SMILES string.
        lit (Translator): predictive model.

    Returns:
        Dict[str, List[Dict[str, Any]]]: Dict of predictions lists from the model.
    """

    # Make retro predictions
    results_list = predict_smiles(lit, [smiles], batch_size=512)

    # Get the products, reactants and confidences
    product_list = [result["source"] for result in results_list]
    predicted_list = [result["predicted_target"] for result in results_list]
    confidence_list = [result["confidence"] for result in results_list]

    # Start list to save the results
    final_results_list = []

    # Loop the prediction results data
    for (
        predicted_smiles,
        confidence,
        product,
    ) in zip(
        predicted_list,
        confidence_list,
        product_list,
    ):
        # Create the full reaction SMILES
        reaction_smiles = predicted_smiles + RXN_SMILES_SEPARATOR + product

        # Create the retro prediction object and append it to results list
        final_results_list.append(
            {
                "reactants": predicted_smiles,
                "product": product,
                "confidence": float(np.exp(confidence)),  # Convert confidence to probability
                "smiles": reaction_smiles,
            }
        )

    # Return retro prediction results
    return final_results_list
