
# worker/rs2s_tasks/runtime_cli.py
import os
import torch
from lightning.pytorch.cli import LightningCLI
from lightning.pytorch import Trainer
from pathlib import Path
from transformers_model.model import LitVanillaTransformer
from transformers_model.smiles_datamodule import LitSmilesDataset

FORWARD_CKPT_PATH = os.getenv(
    "FORWARD_CKPT_PATH",
    "rs2s_tasks/epoch=59-val_accuracy=0.6476.ckpt"
)

REQUESTED_DEVICE = os.getenv("DEVICE", "").lower()
def _choose_accelerator():
    if REQUESTED_DEVICE == "cuda" and torch.cuda.is_available():
        return "gpu"
    return "cpu"

_CLI = None
_TRAINER = None

def get_cli_runtime():
    """Instantiate LightningCLI once and cache model/datamodule/trainer."""
    global _CLI, _TRAINER
    if _CLI is None:
        # Build CLI programmatically (no argv parsing). We mimic your predict setup.
        _CLI = LightningCLI(
            model_class=LitVanillaTransformer,
            datamodule_class=LitSmilesDataset,
            subclass_mode_model=False,
            subclass_mode_data=False,
            run=False,  # <--- do not launch fit/test/predict automatically
            args=[
                f"--model.vocab_path={str(Path(__file__).with_name('vocab.txt'))}",
                "--model.task=forward",
                "--model.device=cpu",
                f"--data.vocab_path={str(Path(__file__).with_name('vocab.txt'))}",
                "--data.batch_size=512",
                "--seed_everything=42",
            ],
        )

        # Load weights exactly like CLI predict
        _CLI.model = LitVanillaTransformer.load_from_checkpoint(
            checkpoint_path=FORWARD_CKPT_PATH,
            strict=False,
            map_location="cpu",  # safe default
            vocab_path=str(Path(__file__).with_name("vocab.txt")),
            task="forward",
            device="cpu",
        )
        _CLI.model.eval().freeze()

        _CLI.datamodule = LitSmilesDataset(
            batch_size=512,
            vocab_path=str(Path(__file__).with_name("vocab.txt")),
        )

        # Build a lightweight Trainer for predict calls
        _TRAINER = Trainer(
            accelerator="cpu",  #_choose_accelerator(),
            devices=1,
            logger=False,
            enable_checkpointing=False,
            inference_mode=True,
        )

        # Place model on the selected device (after construction)
        #device = torch.device("cuda" if _TRAINER.accelerator.strategy.root_device.type == "cuda" else "cpu")
        device = "cpu"
        _CLI.model.to(device).eval()
        torch.set_grad_enabled(False)

    return _CLI, _TRAINER
