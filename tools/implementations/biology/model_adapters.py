import os
import torch
torch.set_num_threads(int(os.getenv("SCITOOL_MODEL_CPU_THREADS", "4")))
from transformers import T5Tokenizer, T5ForConditionalGeneration, AutoTokenizer
import selfies as sf

from tools.runtime.config import Config
base_dir = Config().QizhiPei_MODEL_PATH


def _load_t5(model_path, tokenizer_class):
    from tools.implementations.biology.model_cache import cached_resource
    def load():
        tokenizer = tokenizer_class.from_pretrained(model_path, model_max_length=512, local_files_only=True)
        model = T5ForConditionalGeneration.from_pretrained(model_path, local_files_only=True)
        return tokenizer, model
    return cached_resource("biot5", model_path, load, (tokenizer_class.__name__, "max_length_512"))


def _check_input_length(input_ids):
    if input_ids.shape[-1] > 512:
        raise ValueError("The complete task prompt exceeds512tokens; no silent sequence truncation is supported")
    return input_ids


def _generate(model, *args, **kwargs):
    from tools.implementations.biology.model_cache import inference_lock
    with inference_lock(model), torch.inference_mode():
        return model.generate(*args, **kwargs)

def generate_molecule_description(selfies):
    """
    Given a molecule SELFIES, generates its English description using a pre-trained T5 model.
    
    Parameters:
    - selfies: A string representing the molecule in SELFIES format.
    
    Returns:
    - A Markdown string containing the molecule SELFIES and its generated English description.
    
    """
    if not isinstance(selfies, str) or not selfies:
        raise ValueError("Invalid SELFIES input. It must be a non-empty string.")
    
    try:
        model_name = "biot5-plus-base-chebi20/"
        model_path = os.path.join(base_dir, model_name)
        
        tokenizer, model = _load_t5(model_path, T5Tokenizer)

        task_definition = 'Definition: You are given a molecule SELFIES. Your job is to generate the molecule description in English that fits the molecule SELFIES.\n\n'
        task_input = f'Now complete the following example -\nInput: <bom>{selfies}<eom>\nOutput: '

        model_input = task_definition + task_input
        input_ids = tokenizer(model_input, return_tensors="pt").input_ids

        max_output_length = 512
        output_beams = 1

        _check_input_length(input_ids)
        outputs = _generate(model, input_ids, max_length=max_output_length, num_beams=output_beams)

        description = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        return f"**SELFIES:** `{selfies}`\n\n**Description:** {description}"
    except Exception as e:
        return f"Error generating description: {str(e)}"
    
def text_to_molecule_SELFIES(description):
    """
    Given a molecule description in English, generates its SELFIES and SMILES representation using a pre-trained T5 model.
    
    Parameters:
    - description: A string containing the molecule description in English.
    
    Returns:
    - A Markdown string containing the molecule description, SELFIES, and SMILES representation.
    
    Raises:
    - ValueError: If the description input is not a valid string.
    """
    if not isinstance(description, str) or not description:
        raise ValueError("Invalid description input. It must be a non-empty string.")
    
    try:
        model_name = "biot5-base-text2mol/"
        model_path = os.path.join(base_dir, model_name)
        
        tokenizer, model = _load_t5(model_path, T5Tokenizer)

        task_definition = 'Definition: You are given a molecule description in English. Your job is to generate the molecule SELFIES that fits the description.\n\n'
        task_input = f'Now complete the following example -\nInput: {description}\nOutput: '

        model_input = task_definition + task_input
        input_ids = tokenizer(model_input, return_tensors="pt").input_ids

        max_output_length = 512
        output_beams = 1

        _check_input_length(input_ids)
        outputs = _generate(model, input_ids, max_length=max_output_length, num_beams=output_beams)
        output_selfies = tokenizer.decode(outputs[0], skip_special_tokens=True).replace(' ', '')
        
        output_smiles = sf.decoder(output_selfies)
        
        return f"**Description:** {description}\n\n**SELFIES:** `{output_selfies}`\n\n**SMILES:** `{output_smiles}`"
    except Exception as e:
        return f"Error generating SMILES: {str(e)}"

def add_prefix_to_amino_acids(protein_sequence):
    """Add a prefix '<p>' to each amino acid in the protein sequence."""
    amino_acids = list(protein_sequence)
    prefixed_amino_acids = ['<p>' + aa for aa in amino_acids]
    return ''.join(prefixed_amino_acids)

def predict_drug_target_interaction(selfies: str, protein_sequence: str):
    """
    Predicts whether a given molecule (SELFIES format) and a protein sequence can interact with each other
    and returns the result in Markdown format with a brief explanation.
    
    Parameters:
    - selfies: Complete molecule SELFIES; dots remain disconnected molecule separators.
    - protein_sequence: Separate canonical protein sequence. The complete prompt must fit512tokens.
    
    Returns:
    - A Markdown formatted string containing the prediction and its explanation.
    """
    try:
        from tools.implementations.biology.sequence_primitives import canonical_sequence
        if not isinstance(selfies, str) or not selfies or len(selfies) > 100000:
            raise ValueError("Require a nonempty molecule SELFIES string")
        sf.decoder(selfies)  # Reject invalid SELFIES; do not split disconnected fragments.
        selfies_input = selfies
        protein_input = canonical_sequence(protein_sequence, maximum=10000)
        model_name = "biot5-base-dti-human/"
        model_path = os.path.join(base_dir, model_name)
        
        tokenizer, model = _load_t5(model_path, T5Tokenizer)

        protein_input_prefixed = add_prefix_to_amino_acids(protein_input)
        task_definition = 'Definition: Drug target interaction prediction task for the human dataset.\n\n'
        task_input = f'Now complete the following example -\nInput: Molecule: <bom>{selfies_input}<eom>\nProtein: <bop>{protein_input_prefixed}<eop>\nOutput: '

        model_input = task_definition + task_input
        input_ids = tokenizer(model_input, return_tensors="pt").input_ids

        max_output_length = 8
        output_beams = 1

        _check_input_length(input_ids)
        outputs = _generate(model, input_ids, max_length=max_output_length, num_beams=output_beams)
        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        return f"### Drug-Target Interaction Prediction\n- **Molecule (SELFIES):** `{selfies_input}`\n- **Protein Sequence:** `{protein_input}`\n- **Prediction:** `{prediction}`"
    except Exception as e:
        return f"Error in prediction: {str(e)}"

def predict_human_protein_interaction(protein_sequence_1: str, protein_sequence_2: str) -> str:
    """
    Predicts whether two given protein sequences can interact with each other
    using a fine-tuned BioT5 model for the protein-protein interaction task with human dataset.
    
    Parameters:
    - protein_sequence_1: The amino acid sequence of the first protein.
    - protein_sequence_2: The amino acid sequence of the second protein.
    
    Returns:
    - A Markdown formatted string containing the two protein sequences and the interaction prediction.
    """
    if not protein_sequence_1 or not protein_sequence_2:
        return "Invalid input: Both protein sequences must be provided."
    
    try:
        from tools.implementations.biology.sequence_primitives import canonical_sequence
        protein_sequence_1 = canonical_sequence(protein_sequence_1, maximum=10000)
        protein_sequence_2 = canonical_sequence(protein_sequence_2, maximum=10000)
        model_name = "biot5-base-peer-human_ppi/"
        model_path = os.path.join(base_dir, model_name)
        
        tokenizer, model = _load_t5(model_path, AutoTokenizer)

        task_definition = 'Definition: Given two human protein sequences, predict whether they can interact with each other.\n\n'
        task_input = f'Now complete the following example -\nInput: Protein 1: {protein_sequence_1} Protein 2: {protein_sequence_2}\nOutput: '

        model_input = task_definition + " " + task_input
        input_ids = tokenizer.encode(model_input, return_tensors="pt")

        # Generate the prediction
        _check_input_length(input_ids)
        outputs = _generate(model, input_ids, max_length=512, num_beams=1)
        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Format and return the result
        result = f"### Protein-Protein Interaction Prediction\n- **Protein 1 Sequence:** `{protein_sequence_1}`\n- **Protein 2 Sequence:** `{protein_sequence_2}`\n- **Prediction:** {prediction}"
        return result
    except Exception as e:
        return f"Error in prediction: {str(e)}"

def predict_yeast_protein_interaction(protein_sequence_1: str, protein_sequence_2: str) -> str:
    """
    Predicts whether two given yeast protein sequences can interact with each other
    using a fine-tuned BioT5 model for the protein-protein interaction task with yeast dataset.
    
    Parameters:
    - protein_sequence_1, protein_sequence_2: Separate canonical yeast protein sequences.
      The complete prompt must fit512tokens; truncation is never implicit.
    
    Returns:
    - A Markdown formatted string containing the two yeast protein sequences and the interaction prediction.
    """
    # Remove possible enclosing quotes and whitespace
    if not protein_sequence_1 or not protein_sequence_2:
        return "Invalid input: Both protein sequences must be provided."
    try:
        from tools.implementations.biology.sequence_primitives import canonical_sequence
        protein_sequence_1 = canonical_sequence(protein_sequence_1, maximum=10000)
        protein_sequence_2 = canonical_sequence(protein_sequence_2, maximum=10000)
        model_name = "biot5-base-peer-yeast_ppi/"
        model_path = os.path.join(base_dir, model_name)
        
        tokenizer, model = _load_t5(model_path, AutoTokenizer)

        task_definition = 'Definition: Given two yeast protein sequences, predict whether they can interact with each other.\n\n'
        task_input = f'Now complete the following example -\nInput: Protein 1: {protein_sequence_1} Protein 2: {protein_sequence_2}\nOutput: '

        model_input = task_definition + " " + task_input
        input_ids = tokenizer.encode(model_input, return_tensors="pt")

        # Generate the prediction
        _check_input_length(input_ids)
        outputs = _generate(model, input_ids, max_length=512, num_beams=1)
        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Format and return the result
        result = f"### Yeast Protein-Protein Interaction Prediction\n- **Protein 1 Sequence:** `{protein_sequence_1}`\n- **Protein 2 Sequence:** `{protein_sequence_2}`\n- **Prediction:** {prediction}"
        return result
    except Exception as e:
        return f"Error in prediction: {str(e)}"

def predict_protein_solubility(protein_sequence: str) -> str:
    """
    Predicts the solubility of a given protein sequence using a fine-tuned BioT5 model
    for the protein solubility prediction task.
    
    Parameters:
    - protein_sequence: The amino acid sequence of the protein.
    
    Returns:
    - A Markdown formatted string containing the protein sequence and its solubility prediction.
    """
    if not protein_sequence:
        return "Invalid input: Protein sequence must be provided."
    
    try:
        from tools.implementations.biology.sequence_primitives import canonical_sequence
        protein_sequence = canonical_sequence(protein_sequence, maximum=10000)
        model_name = "biot5-base-peer-solubility/"
        model_path = os.path.join(base_dir, model_name)
        
        tokenizer, model = _load_t5(model_path, AutoTokenizer)


        # Specific task definition for protein solubility prediction
        task_definition = 'Definition: Predict the solubility of a protein given its amino acid sequence.\n\n'
        task_input = f'Now complete the following example -\nInput: Protein sequence: {protein_sequence}\nOutput: '

        model_input = task_definition + " " + task_input
        input_ids = tokenizer.encode(model_input, return_tensors="pt")

        # Generate the prediction
        _check_input_length(input_ids)
        outputs = _generate(model, input_ids, max_length=512, num_beams=4, early_stopping=True)
        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Format and return the result
        result = f"### Protein Solubility Prediction\n- **Protein Sequence:** `{protein_sequence}`\n- **Prediction:** {prediction}"
        return result
    except Exception as e:
        return f"Error in prediction: {str(e)}"

def predict_protein_binary_localization(protein_sequence: str) -> str:
    """Unsupported until the checkpoint's binary target-label ontology is documented."""
    raise NotImplementedError("Binary-localization label semantics are not established; use a predictor with an explicit target definition")
