"""MIT Smiles dataset routines-filtering, dataset building."""

import json
import os
from pathlib import PosixPath
from typing import Dict, List, Union, Optional

import lightning as L
from torch import Tensor
from torch.utils.data import ConcatDataset, DataLoader, Dataset
from transformers import default_data_collator
from transformers.tokenization_utils_base import BatchEncoding

from transformers_model.smiles_tokenizer import SmilesTokenizer
from transformers_model.logging_utils import setup_logger

logger = setup_logger(__name__, logging_level="info")


class SmilesDataset(Dataset):
    """Smiles dataset class."""

    def __init__(
        self,
        filepath: str,
        tokenizer: SmilesTokenizer,
        padding_idx: int = 0,
    ) -> None:
        """Initialize the LM data module.

        Args:
            filepath: path where the dataset is located.
            tokenizer: tokenize function to be used in the module.
        """

        self.filepath = filepath
        if not self.filepath.endswith(".jsonl") and not self.filepath.endswith(".json"):
            raise ValueError(f"{filepath} is not a .jsonl or a json.")
        self.tokenizer = tokenizer
        self.length = SmilesDataset.count_examples(filepath)
        self.padding_idx = padding_idx

        self.examples = self.examples_reader()

    def examples_reader(self) -> List[Dict[str, str]]:
        """Read instances from a filepath.

        Returns:
           list of instances.
        """
        with open(self.filepath) as fp:
            return [json.loads(line.strip()) for line in fp]

    @staticmethod
    def count_examples(filepath: str) -> int:
        """Count instances of a filepath.

        Args:
           filepath: path of the dataset.

        Returns:
           number of examples existed in the given filepath.
        """

        def _make_gen(reader):
            while True:
                b = reader(2**16)
                if not b:
                    break
                yield b

        with open(filepath, "rb") as f:
            count = sum(buf.count(b"\n") for buf in _make_gen(f.raw.read))  # type: ignore
        return count

    def __len__(self) -> int:
        """Number of instances of the dataset.

        Returns:
           number of instances
        """
        return self.length

    def __getitem__(self, index) -> Dict[str, Tensor]:
        """Get an item of the dataset.

        Args:
            index: index of the item.

        Returns:
            tokenized item.
        """

        example = self.examples[index]
        source = example.get("source")
        target = example.get("target")

        if source is None:
            raise ValueError(f"Missing 'source' in example at index {index}")

        item = {}
        source_item = self.tokenizer(source)
        item["encoder_input_ids"] = source_item["input_ids"].squeeze(0)
        item["encoder_padding_mask"] = (1 - source_item["attention_mask"]).squeeze(0).bool()

        if target is not None:
            target_item = self.tokenizer(target)
            item["decoder_input_ids"] = target_item["input_ids"].squeeze(0)
            item["decoder_padding_mask"] = (1 - target_item["attention_mask"]).squeeze(0).bool()

        return item


class LitSmilesDataset(L.LightningDataModule):
    """Pytorch-lightning-style data module for smiles dataset."""

    def __init__(
        self, 
        vocab_path: str, 
        train_path: Optional[str] = None,
        validation_path: Optional[str] = None,
        test_path: Optional[str] = None,
        predict_path: Optional[str] = None,
        truncation: bool = True,
        padding: str = "max_length",
        max_length: int = 278,
        return_token_type_ids: bool = False,
        batch_size: int = 32,
        num_dataloader_workers: int = 8,
    ) -> None:

        super().__init__()
        self.tokenizer = SmilesTokenizer(vocab_path)
        self.train_path = train_path
        self.validation_path = validation_path
        self.test_path = test_path
        self.predict_path = predict_path
        self.truncation = truncation
        self.padding = padding
        self.max_length = max_length
        self.return_token_type_ids = return_token_type_ids
        self.batch_size = batch_size

        cpus_count = os.cpu_count()
        self.num_dataloader_workers = min(num_dataloader_workers, cpus_count or 1)
     
        self.data_collator = default_data_collator

    def setup(self, stage: Optional[str] = None):
        """Setup the data module."""

        if stage == "fit" or stage is None:
            if self.train_path and self.validation_path:
                self.smiles_dataset_train = self.build_dataset(self.train_path)
                self.smiles_dataset_val = self.build_dataset(self.validation_path)
                logger.info(f"Train set size: {len(self.smiles_dataset_train)}")
                logger.info(f"Validation set size: {len(self.smiles_dataset_val)}")
            elif stage == "fit":
                    raise ValueError("Both train_path and validation_path must be provided for training.")

        if stage == "validation" or stage is None:
            if self.validation_path:
                self.smiles_dataset_val = self.build_dataset(self.validation_path)
                logger.info(f"Validation set size: {len(self.smiles_dataset_val)}")
            elif stage == "validation":
                raise ValueError("The validation_path must be provided for validation.")

        if stage == "test" or stage is None:
            if self.test_path:
                self.smiles_dataset_test = self.build_dataset(self.test_path)
                logger.info(f"Test set size: {len(self.smiles_dataset_test)}")
            elif stage == "test":
                raise ValueError("The test_path must be provided for testing.")

        if stage == "predict" or stage is None:
            if self.predict_path:
                self.smiles_dataset_predict = self.build_dataset(self.predict_path)
                logger.info(f"Predict set size: {len(self.smiles_dataset_predict)}")
            elif stage == "predict":
                raise ValueError("The predict_path must be provided for running prediction.")

    def build_dataset(self, path: Union[str, PosixPath]) -> Dataset:
        """Builds the dataset.

        Args:
            path: path of the dataset or the directory that contains it.

        Returns:
            pytorch dataset.
        """
        path = str(path)
        if path.endswith(".jsonl") or path.endswith(".json"):
            return SmilesDataset(
                path, self.tokenize_function, padding_idx=self.tokenizer.pad_token_id  # type: ignore
            )
        elif os.path.isdir(path):
            return ConcatDataset(
                datasets=[
                    SmilesDataset(
                        os.path.join(path, filename),
                        self.tokenize_function,  # type: ignore
                        padding_idx=self.tokenizer.pad_token_id,
                    )
                    for filename in os.listdir(path)
                    if filename.endswith(".jsonl") or filename.endswith(".json")
                ]
            )
        else:
            raise TypeError(f"{path} type is not supported for dataset.")

    def tokenize_function(self, example: str) -> BatchEncoding:
        """Tokenize the given examples.

        Args:
            examples: list of examples.

        Returns:
            tokenized examples.
        """

        return self.tokenizer(  # type: ignore
            example,
            truncation=self.truncation,
            padding=self.padding,
            max_length=self.max_length,
            return_token_type_ids=self.return_token_type_ids,
            return_tensors="pt",
        )

    def train_dataloader(self) -> DataLoader:
        """Creates the dataloader for the training step.

        Returns:
            pytorch dataloader.
        """
        return DataLoader(
            self.smiles_dataset_train,
            batch_size=self.batch_size,
            num_workers=self.num_dataloader_workers,
            collate_fn=self.data_collator,
            pin_memory=True,
            shuffle=True,
            drop_last=True,
        )

    def val_dataloader(self) -> DataLoader:
        """Creates the dataloader for the validation step.

        Returns:
            pytorch dataloader.
        """
        return DataLoader(
            self.smiles_dataset_val,
            batch_size=self.batch_size,
            num_workers=self.num_dataloader_workers,
            collate_fn=self.data_collator,
            pin_memory=True,
            drop_last=True,
        )

    def test_dataloader(self) -> DataLoader:
        """Creates the dataloader for the test step.

        Returns:
            pytorch dataloader.
        """
        return DataLoader(
            self.smiles_dataset_test,
            batch_size=self.batch_size,
            num_workers=self.num_dataloader_workers,
            collate_fn=self.data_collator,
            pin_memory=True,
            drop_last=True,
        )

    def predict_dataloader(self) -> DataLoader:
        """Creates the dataloader for the predict step.

        Returns:
            pytorch dataloader.
        """
        return DataLoader(
            self.smiles_dataset_predict,
            batch_size=self.batch_size,
            num_workers=self.num_dataloader_workers,
            collate_fn=self.data_collator,
            pin_memory=True,
        )
