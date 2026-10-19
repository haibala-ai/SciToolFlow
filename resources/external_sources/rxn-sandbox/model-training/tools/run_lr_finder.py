"""
Runs the Lightning learning rate finder and saves a plot and CSV of the results.

Output files are written to the same directory as this script:
  - lr_finder_plot.png
  - lr_finder_results.csv

Usage (run from model-training/):
    python debug/run_lr_finder.py
    python debug/run_lr_finder.py --data-dir data/pistachio/data.forward --vocab vocab/vocab.txt
"""

import argparse
import csv
import os
import sys
import torch

# Allow running from any directory inside model-training/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import lightning as L
import matplotlib.pyplot as plt
from lightning.pytorch.tuner import Tuner

from transformers_model.smiles_datamodule import LitSmilesDataset
from transformers_model.model import LitVanillaTransformer

HERE = os.path.dirname(os.path.abspath(__file__))


def run(data_dir: str, vocab_path: str) -> None:
    L.seed_everything(42)
    torch.set_float32_matmul_precision("high")

    smiles_dataset = LitSmilesDataset(
        vocab_path=vocab_path,
        train_path=os.path.join(data_dir, "train.jsonl"),
        validation_path=os.path.join(data_dir, "validation.jsonl"),
        num_dataloader_workers=16,
        batch_size=1024,
        max_length=256,
    )

    model = LitVanillaTransformer(
        vocab_path=vocab_path,
        task="forward",
        max_length=256,
        ignore_nan=True,
    )

    trainer = L.Trainer(
        max_epochs=60,
        accelerator="gpu",
        devices=1,
        precision="16-mixed",
        deterministic=True,
        gradient_clip_val=1.0,
        gradient_clip_algorithm="norm",
    )

    tuner = Tuner(trainer)
    lr_finder = tuner.lr_find(model, datamodule=smiles_dataset)

    # Plot
    fig = lr_finder.plot(suggest=True)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plot_path = os.path.join(HERE, "lr_finder_plot.png")
    fig.savefig(plot_path)
    print(f"Plot saved to {plot_path}")
    plt.show()

    # Save results as CSV
    csv_path = os.path.join(HERE, "lr_finder_results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["learning_rate", "loss"])
        writer.writerows(zip(lr_finder.results["lr"], lr_finder.results["loss"]))
    print(f"Results saved to {csv_path}")

    print(f"Suggested learning rate: {lr_finder.suggestion()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Lightning LR finder.")
    parser.add_argument(
        "--data-dir",
        default="data/pistachio/data.forward",
        help="Directory containing train.jsonl and validation.jsonl "
             "(default: data/pistachio/data.forward)",
    )
    parser.add_argument(
        "--vocab",
        default="vocab/vocab.txt",
        help="Path to vocab.txt (default: vocab/vocab.txt)",
    )
    args = parser.parse_args()
    run(args.data_dir, args.vocab)
