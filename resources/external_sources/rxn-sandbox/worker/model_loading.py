from typing import List, Dict, Optional
import torch
from lightning import seed_everything
from transformers_model.model import LitVanillaTransformer


# Loads a LitVanillaTransformer set for forward (product) prediction
def load_forward_model(
    ckpt_path: str,
    vocab_path: str,
    num_beams: int,
    topn: int,
    device: Optional[str] = None,
) -> LitVanillaTransformer:
    return load_lit_transformer_for_inference(
        ckpt_path=ckpt_path,
        vocab_path=vocab_path,
        task="forward",
        num_beams=num_beams,
        topn=topn,
        gen_max_length=256,
        device=device,
    )


# Loads a LitVanillaTransformer set for retrosynthesis prediction
def load_retro_model(
    ckpt_path: str,
    vocab_path: str,
    num_beams: int,
    topn: int,
    device: Optional[str] = None,
) -> LitVanillaTransformer:
    return load_lit_transformer_for_inference(
        ckpt_path=ckpt_path,
        vocab_path=vocab_path,
        task="forward",
        num_beams=num_beams,
        topn=topn,
        gen_max_length=256,
        device=device,
    )


# Loads the LitVanillaTransformer for prediction
def load_lit_transformer_for_inference(
    ckpt_path: str,
    vocab_path: str,
    task: str = "forward",
    num_beams: int = 3,
    topn: int = 3,
    gen_max_length: int = 256,
    device: Optional[str] = None,
) -> LitVanillaTransformer:
    """
    Load the trained LitVanillaTransformer exactly like LightningCLI would,
    and prepare it for inference/generation.
    """
    torch.set_float32_matmul_precision("high")

    # Device handling when not set
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # Load from checkpoint while ensuring the same hyperparameters used at predict time.
    lit = LitVanillaTransformer.load_from_checkpoint(
        ckpt_path,
        vocab_path=vocab_path,
        task=task,
        num_beams=num_beams,
        topn=topn,
        max_length=gen_max_length,
        device=device,
    )
    lit.eval()

    # Align internal config device with the actual target device to avoid mask/device mismatches
    target_device = torch.device(device)
    lit.to(target_device)
    if hasattr(lit, "model") and hasattr(lit.model, "config"):
        lit.model.config.device = target_device  # your encoder/decoder build masks on config.device

    # Return the LitVanillaTransformer
    return lit


# Uses the transformers model to run predictions with the SMILES inputs
@torch.inference_mode()
def predict_smiles(
    lit: LitVanillaTransformer, # Model used for inference
    inputs: List[str],          # List of SMILES for prediction
    *,
    batch_size: int = 512,
    truncation: bool = True,
    padding: str = "max_length",
    data_max_length: int = 278,
    seed: Optional[int] = 42,
) -> List[Dict]:

    # Sets the seed for reproducibility
    if seed is not None:
        seed_everything(seed, workers=True)

    # Gets the device in use
    device = next(lit.parameters()).device

    # Gets the tokenizer from the LitVanillaTransformer
    tokenizer = lit.tokenizer

    # List to hold prediction results
    all_results: List[Dict] = []

    # Prediction loop for batch prediction
    for start in range(0, len(inputs), batch_size):

        # Prepare the batch inputs according to batch size
        batch_src = inputs[start : start + batch_size]
        print(f"DEBUG - batch_src: {batch_src}")

        # Prepare inputs by tokenizing exactly like in the DataModule
        encoder_input_ids = tokenizer(
            batch_src,
            truncation=truncation,
            padding=padding,
            max_length=data_max_length,
            return_token_type_ids=False,
            return_tensors="pt",
        )["input_ids"]

        # Move inputs to device if one is set
        if device is not None:
            encoder_input_ids = encoder_input_ids.to(device)

        # Generate the model predictions
        outputs = lit.model.generate(
            encoder_input_ids,
            do_sample=False,
            max_length=lit.hparams.max_length,
            num_beams=lit.hparams.num_beams,
            num_return_sequences=lit.hparams.topn,
            return_dict_in_generate=True,
            output_scores=True,
        )

        # Get predicted sequences and scores
        sequences = outputs.sequences       # shape [B*topn, T]
        scores = outputs.sequences_scores   # 1 score per sequence

        # Decode and detokenize the sequences to obtain the predicted SMILES string
        pred_texts = tokenizer.batch_decode(sequences, skip_special_tokens=True)
        pred_texts = tokenizer.batch_detokenize_smiles_string(pred_texts)

        # Also decode and detokenize the encoder inputs to a SMILES string
        src_texts_dec = tokenizer.batch_decode(encoder_input_ids, skip_special_tokens=True)
        src_texts_dec = tokenizer.batch_detokenize_smiles_string(src_texts_dec)
        print(f"DEBUG - src_texts_dec: {src_texts_dec}")

        # Get topn from the hyperparameters to know exactly how many results are grouped for the same source
        topn = lit.hparams.topn

        # List to hold each batch prediction results
        batch_results: List[Dict] = []

        # Loop through the inputs
        for i, src in enumerate(src_texts_dec):

            # Get starting index for each unique input
            start_j = i * topn

            # Loop through all predictions for a given input
            for j in range(start_j, start_j + topn):

                # Build each prediction result object
                item = {
                    "source": src,
                    "predicted_target": pred_texts[j],
                    "confidence": scores[j].item(),  # you keep raw score in your code
                }

                # Add the prediction result to the batch results
                batch_results.append(item)

        # Add this batch results to the total results list
        all_results.extend(batch_results)

    # Return the prediction results
    return all_results


# Uses the transformers model to check the likelihood of a reaction using the input and output SMILES
@torch.inference_mode()
def reaction_likelihood(
    lit: LitVanillaTransformer,
    src_text: str,
    tgt_text: str,
    truncation: bool = True,
    padding: str = "max_length",
    data_max_length: int = 278,
) -> float:
    # Get the model, tokenizer and device from LitVanillaTransformer
    model = lit.model
    tokenizer = lit.tokenizer
    device = next(model.parameters()).device

    # Tokenizes the SMILES sources
    src_ids = tokenizer(
        src_text,
        truncation=truncation,
        padding=padding,
        max_length=data_max_length,
        return_tensors="pt",
    ).input_ids.to(device)

    # Tokenizes the SMILES targets
    tgt_ids = tokenizer(
        tgt_text,
        truncation=truncation,
        padding=padding,
        max_length=data_max_length,
        return_tensors="pt",
    ).input_ids.to(device)

    # Gets the outputs from the model
    outputs = model(
        encoder_input_ids=src_ids,
        decoder_input_ids=tgt_ids,
        labels=tgt_ids,
        return_dict=True,
    )

    # loss = mean NEGATIVE log-prob per token
    loss = outputs.loss

    # Number of actual tokens (excluding padding)
    pad_id = tokenizer.pad_token_id
    num_tokens = (tgt_ids != pad_id).sum()

    # Calculates the log likelihood
    log_likelihood = -loss * num_tokens

    # Returns likelihood probability
    return float(torch.exp(log_likelihood))
