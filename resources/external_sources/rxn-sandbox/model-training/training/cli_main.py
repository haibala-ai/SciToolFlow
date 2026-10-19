import torch

from lightning.pytorch.cli import LightningCLI
from transformers_model.model import LitVanillaTransformer
from transformers_model.smiles_datamodule import LitSmilesDataset


def main():
    
    # Enable Tensor Core optimization
    torch.set_float32_matmul_precision('high')

    LightningCLI(
        model_class=LitVanillaTransformer,
        datamodule_class=LitSmilesDataset,
    )


if __name__ == "__main__":
    main()
