"""
Train the model directly with Lightning, bypassing LightningCLI.

Useful for quick experiments where you want to set options in code rather
than via a YAML config. For production training use cli_main.py with the
YAML configs in training/.

Usage (run from model-training/):
    python debug/run_fit.py
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
        train_path="data/pistachio/data.forward/train.jsonl",
        validation_path="data/pistachio/data.forward/validation.jsonl",
        num_dataloader_workers=16,
        batch_size=256,
        max_length=256,
    )

    model = LitVanillaTransformer(
        vocab_path="vocab/vocab.txt",
        task="forward",
        max_length=256,
    )

    trainer = L.Trainer(
        max_epochs=10,
        accelerator="gpu",
        devices=1,
        precision=32,
    )

    trainer.fit(model, datamodule=smiles_dataset)
    print("Training complete.")
