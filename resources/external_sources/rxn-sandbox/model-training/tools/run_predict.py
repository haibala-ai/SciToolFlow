"""
Run predictions with the model directly via Lightning, bypassing LightningCLI.

Useful for quick experiments where you want to set options in code rather
than via a YAML config. For production inference use cli_main.py with
training/predict.yaml.

Usage (run from model-training/):
    python debug/run_predict.py
"""

import os
import sys

# Allow running from any directory inside model-training/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import lightning as L

from transformers_model.smiles_datamodule import LitSmilesDataset
from transformers_model.model import LitVanillaTransformer


if __name__ == "__main__":
    L.seed_everything(42)

    smiles_dataset = LitSmilesDataset(
        vocab_path="vocab/vocab.txt",
        predict_path="data/input.jsonl",
        num_dataloader_workers=16,
        batch_size=256,
        max_length=256,
    )

    # Replace with the actual checkpoint path
    model = LitVanillaTransformer.load_from_checkpoint(
        checkpoint_path="lightning_logs/forward/checkpoints/epoch=59-val_accuracy=0.6476.ckpt",
        vocab_path="vocab/vocab.txt",
    )

    trainer = L.Trainer(
        accelerator="gpu",
        devices=1,
        precision=32,
    )

    trainer.predict(model, datamodule=smiles_dataset)
    print("Prediction complete.")
