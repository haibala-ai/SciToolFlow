"""Pytorch Lightning implementation for VanillaTransformer."""

import math
import json
import Levenshtein
import lightning as L
import torch
import torch.nn.functional as F
import torch.optim as optim
from typing import Dict
from torch import Tensor
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem.rdFingerprintGenerator import GetMorganGenerator
from functools import lru_cache
from transformers import get_cosine_schedule_with_warmup
from types import MethodType
from transformers_model.smiles_tokenizer import SmilesTokenizer
from transformers_model.configuration import VanillaTransformerConfig
from transformers_model.transformer import VanillaTransformer
from transformers_model.logging_utils import setup_logger

logger = setup_logger(__name__, logging_level="info")
RDLogger.DisableLog('rdApp.*')


class LitVanillaTransformer(L.LightningModule):
    """Pytorch lightning model for VanillaTransformer."""

    def __init__(
        self,
        vocab_path: str,
        task: str,
        learning_rate: float = 0.0001,
        adam_beta1: float = 0.9,
        adam_beta2: float = 0.98,
        adam_epsilon: float = 1e-9,
        adam_weight_decay: float = 0.01,
        embedding_dim: int = 256,
        ffnn_hidden_dim: int = 2048,
        dropout: float = 0.1,
        activation: str = "relu",
        num_attention_heads: int = 8,
        num_encoder_layers: int = 4,
        num_decoder_layers: int = 4,
        attention_mask: float = float("-inf"),
        init_std: float = 0.02,
        max_position_embeddings: int = 5000,
        num_beams: int = 1,
        topn: int = 1,
        max_length: int = 256,
        warmup_ratio: float = 0.06,
        predictions_path: str = "data/predictions.jsonl",
        ignore_nan: bool = False,
        device: str = "cuda"

    ) -> None:
        """Construct an LM lightning module.
        """
        super().__init__()

        self.save_hyperparameters()

        self.model: VanillaTransformer
        self.tokenizer = SmilesTokenizer(vocab_path)
        self.task = task
        self.learning_rate = learning_rate
        self.adam_beta1 = adam_beta1
        self.adam_beta2 = adam_beta2
        self.adam_epsilon = adam_epsilon
        self.adam_weight_decay = adam_weight_decay
        self.embedding_dim = embedding_dim
        self.ffnn_hidden_dim = ffnn_hidden_dim
        self.dropout = dropout
        self.activation = activation
        self.num_attention_heads = num_attention_heads
        self.num_encoder_layers = num_encoder_layers
        self.num_decoder_layers = num_decoder_layers
        self.attention_mask = attention_mask
        self.init_std = init_std
        self.max_position_embeddings = max_position_embeddings
        self.num_beams = num_beams
        self.topn = max(self.num_beams, topn)
        self.max_length = max_length
        self.warmup_ratio = warmup_ratio
        self.predictions_path = predictions_path
        self.ignore_nan = ignore_nan
        self.device_pref = device
        self.invalid_pred = 0

        self.init_model()

    def init_model(self) -> None:
        """Initialize a VanillaTransformer."""

        config_args = {
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.sep_token_id,
            "bos_token_id": self.tokenizer.cls_token_id,
            "decoder_start_token_id": self.tokenizer.cls_token_id,
            "vocabulary_size": self.tokenizer.vocab_size,
            "vocab_size": self.tokenizer.vocab_size,
            "embedding_dim": self.embedding_dim,
            "ffnn_hidden_dim": self.ffnn_hidden_dim,
            "dropout": self.dropout,
            "activation": self.activation,
            "num_attention_heads": self.num_attention_heads,
            "num_encoder_layers": self.num_encoder_layers,
            "num_decoder_layers": self.num_decoder_layers,
            "attention_mask": self.attention_mask,
            "init_std": self.init_std,
            "max_position_embeddings": self.max_position_embeddings,
            "num_beams": self.num_beams,
            "device": self.device_pref,
        }
        config = VanillaTransformerConfig(**config_args)
        self.model = VanillaTransformer(config)

    def forward(self, x: Tensor) -> Tensor:  # type: ignore
        """Forwards through the model.
        """
        return self.model(**kwargs)

    @lru_cache()
    def total_steps(self):
        return len(self.trainer.datamodule.train_dataloader()) // self.trainer.accumulate_grad_batches * self.trainer.max_epochs

    def configure_optimizers(
        self,
    ) -> Dict[str, object]:
        """Create and return the optimizer.

        Returns:
            output (dict of str: Any):
                - optimizer: the optimizer used to update the parameter.
        """

        # definition of the optimizer
        optimizer = optim.AdamW(
            params=self.parameters(),
            lr=self.learning_rate,
            betas=(self.adam_beta1, self.adam_beta2),
            eps=self.adam_epsilon,
            weight_decay=self.adam_weight_decay,
        )

        total_steps = self.total_steps()
        print("Total steps: ", total_steps)
        warmup_steps = int(self.total_steps() * self.warmup_ratio)
        print("Warmup steps: ", warmup_steps)

        scheduler = get_cosine_schedule_with_warmup(
            optimizer,
            num_warmup_steps=warmup_steps,
            num_training_steps=total_steps,
        )

        output = {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "interval": "step",
                "frequency": 1
            }
        }

        return output  # type: ignore

    def training_step(self, batch: Dict[str, Tensor], batch_idx: int) -> Tensor:  # type: ignore
        """
        Training step which encompasses the forward pass and the computation of the loss value.

        Args:
            batch: dictionary containing the input_ids and the attention_type.
            batch_idx: index of the current batch, unused.

        Returns:
            loss computed on the batch.
        """
        loss = self.model(**batch).loss  # type:ignore
        self.log("train_loss", loss, on_step=False, on_epoch=True, logger=True)

        
        current_lr = self.trainer.optimizers[0].param_groups[0]['lr']
        self.log("current_lr", current_lr, on_step=False, on_epoch=True, logger=True)
        
        # stop training if loss is NaN
        if not self.ignore_nan:
            if torch.isnan(loss):
                raise ValueError("Train loss is NaN")

        return loss

    def on_validation_epoch_start(self):
        if self.task == "forward":
            self.invalid_pred = 0

    def validation_step(self, batch: Dict[str, Tensor], batch_idx: int) -> Tensor:  # type: ignore
        """
        Validation step which encompasses the forward pass and the computation of the loss value.

        Args:
            batch: dictionary containing the input_ids and the attention_type.
            batch_idx: index of the current batch, unused.

        Returns:
            loss computed on the batch.
        """

        # compute loss
        outputs = self.model(**batch)
        loss = outputs.loss
        self.log("val_loss", loss, on_step=False, on_epoch=True, logger=True)
        
        # stop training if loss is NaN
        if not self.ignore_nan:
            if torch.isnan(loss):
                raise ValueError("Validation loss is NaN")


        sources = batch["encoder_input_ids"]
        targets = batch["decoder_input_ids"]

        # generating predictions
        predictions = self.model.generate(
            sources,
            do_sample=False,
            max_length=self.max_length,
            num_beams=self.num_beams,
        )

        # decode predictions and labels into untokenized strings
        predicted_texts = self.tokenizer.batch_decode(predictions, skip_special_tokens=True)
        predicted_texts = self.tokenizer.batch_detokenize_smiles_string(predicted_texts)
        target_texts = self.tokenizer.batch_decode(targets, skip_special_tokens=True)
        target_texts = self.tokenizer.batch_detokenize_smiles_string(target_texts)
        
        # calculate accuracy
        correct = sum(pred == tgt for pred, tgt in zip(predicted_texts, target_texts))
        accuracy = correct / len(target_texts)
        self.log("val_accuracy", accuracy, prog_bar=True, on_step=False, on_epoch=True, logger=True)

        # compute Levenshtein distance
        levenshtein_distances = [
            Levenshtein.distance(pred, tgt)
            for pred, tgt in zip(predicted_texts, target_texts)
        ]
        avg_levenshtein_distance = sum(levenshtein_distances) / len(levenshtein_distances)
        self.log("val_levenshtein_distance_avg", avg_levenshtein_distance, on_step=False, on_epoch=True, logger=True)

        # compute Levenshtein ratio
        levenshtein_ratios = [
            Levenshtein.ratio(pred, tgt)
            for pred, tgt in zip(predicted_texts, target_texts)
        ]
        avg_levenshtein_ratio = sum(levenshtein_ratios) / len(levenshtein_ratios)
        self.log("val_levenshtein_ratio_avg", avg_levenshtein_ratio, on_step=False, on_epoch=True, logger=True)

        if self.task == "forward":
            similarities = []
            generator = GetMorganGenerator(radius=2, fpSize=2048)
            for pred, tgt in zip(predicted_texts, target_texts):
                mol1 = Chem.MolFromSmiles(pred)
                mol2 = Chem.MolFromSmiles(tgt)
                
                if mol1 is None or mol2 is None:
                    if mol1 is None:
                        self.invalid_pred += 1
                    continue

                fp1 = generator.GetFingerprint(mol1)
                fp2 = generator.GetFingerprint(mol2)
                sim = DataStructs.TanimotoSimilarity(fp1, fp2)
                similarities.append(sim)

            avg_valid_tanimoto = sum(similarities) / len(similarities) if len(similarities) > 0 else 0
            avg_total_tanimoto = sum(similarities) / len(predicted_texts)
            self.log("val_tanimoto_valid_avg", avg_valid_tanimoto, on_step=False, on_epoch=True, logger=True)
            self.log("val_tanimoto_total_avg", avg_total_tanimoto, on_step=False, on_epoch=True, logger=True)
            return {"val_loss": loss, "val_accuracy": accuracy, "val_levenshtein_distance_avg": avg_levenshtein_distance, "val_levenshtein_ratio_avg": avg_levenshtein_ratio, "val_tanimoto_valid_avg": avg_valid_tanimoto, "val_tanimoto_total_avg": avg_total_tanimoto}
        else:
            return {"val_loss": loss, "val_accuracy": accuracy, "val_levenshtein_distance_avg": avg_levenshtein_distance, "val_levenshtein_ratio_avg": avg_levenshtein_ratio}

    def on_validation_epoch_end(self):
        if self.task == "forward":
            self.log("val_tanimoto_invalid_pred", self.invalid_pred)
            self.invalid_pred = 0

    def test_step(self, batch: Dict[str, Tensor], batch_idx: int) -> float:  # type: ignore
        """
        Test step which encompasses the forward pass and the computation of the accuracy and the loss value.

        Args:
            batch: dictionary containing the input_ids and the attention_type.
            batch_idx: index of the current batch, unused.

        Returns:
            accuracy computed on the batch.
        """

        sources = batch["encoder_input_ids"]
        targets = batch["decoder_input_ids"]

        # generating predictions
        predictions = self.model.generate(
            sources,
            do_sample=False,
            max_length=self.max_length,
            num_beams=self.num_beams,
        )

        # decode predictions and labels into untokenized strings
        predicted_texts = self.tokenizer.batch_decode(predictions, skip_special_tokens=True)
        predicted_texts = self.tokenizer.batch_detokenize_smiles_string(predicted_texts)
        target_texts = self.tokenizer.batch_decode(targets, skip_special_tokens=True)
        target_texts = self.tokenizer.batch_detokenize_smiles_string(target_texts)
        
        # calculate accuracy
        correct = sum(pred == tgt for pred, tgt in zip(predicted_texts, target_texts))
        accuracy = correct / len(target_texts)
        self.log("accuracy", accuracy, prog_bar=True, on_step=False, on_epoch=True, logger=True)

        # compute Levenshtein distance
        levenshtein_distances = [
            Levenshtein.distance(pred, tgt)
            for pred, tgt in zip(predicted_texts, target_texts)
        ]
        avg_levenshtein_distance = sum(levenshtein_distances) / len(levenshtein_distances)
        self.log("levenshtein_distance_avg", avg_levenshtein_distance, on_step=False, on_epoch=True, logger=True)

        # compute Levenshtein ratio
        levenshtein_ratios = [
            Levenshtein.ratio(pred, tgt)
            for pred, tgt in zip(predicted_texts, target_texts)
        ]
        avg_levenshtein_ratio = sum(levenshtein_ratios) / len(levenshtein_ratios)
        self.log("levenshtein_ratio_avg", avg_levenshtein_ratio, on_step=False, on_epoch=True, logger=True)

        if self.task == "forward":
            similarities = []
            generator = GetMorganGenerator(radius=2, fpSize=2048)
            for pred, tgt in zip(predicted_texts, target_texts):
                mol1 = Chem.MolFromSmiles(pred)
                mol2 = Chem.MolFromSmiles(tgt)
                
                if mol1 is None or mol2 is None:
                    if mol1 is None:
                        self.invalid_pred += 1
                    continue

                fp1 = generator.GetFingerprint(mol1)
                fp2 = generator.GetFingerprint(mol2)
                sim = DataStructs.TanimotoSimilarity(fp1, fp2)
                similarities.append(sim)

            avg_valid_tanimoto = sum(similarities) / len(similarities) if len(similarities) > 0 else 0
            avg_total_tanimoto = sum(similarities) / len(predicted_texts)
            self.log("tanimoto_valid_avg", avg_valid_tanimoto, on_step=False, on_epoch=True, logger=True)
            self.log("tanimoto_total_avg", avg_total_tanimoto, on_step=False, on_epoch=True, logger=True)
            return {"accuracy": accuracy, "levenshtein_distance_avg": avg_levenshtein_distance, "levenshtein_ratio_avg": avg_levenshtein_ratio, "tanimoto_valid_avg": avg_valid_tanimoto, "tanimoto_total_avg": avg_total_tanimoto}
        else:
            return {"accuracy": accuracy, "levenshtein_distance_avg": avg_levenshtein_distance, "levenshtein_ratio_avg": avg_levenshtein_ratio}

    def on_predict_start(self):
        # Clear the predictions file at the start of prediction
        with open("predictions.jsonl", "w") as f:
            f.truncate(0)  # or just pass if you want to create/overwrite

    def predict_step(self, batch: Dict[str, Tensor], batch_idx: int) -> Dict:  # type: ignore
        """
        Predict step.

        Args:
            batch: dictionary containing the input_ids and the attention_type.
            batch_idx: index of the current batch, unused.

        Returns:
            Predictions
        """

        sources = batch["encoder_input_ids"]

        # generating the predicted sequence
        outputs = self.model.generate(
            sources,
            do_sample=False,
            max_length=self.max_length,
            num_beams=self.num_beams,
            num_return_sequences=self.topn,
            return_dict_in_generate=True,
            output_scores=True,
        )

        predictions = outputs.sequences                                # shape: (B * top_n, T)
        scores = outputs.sequences_scores

        cross_mats_all = self._collect_cross_attentions(sources, predictions)

        # decode predictions and labels into untokenized strings
        predicted_texts = self.tokenizer.batch_decode(predictions, skip_special_tokens=True)
        predicted_texts = self.tokenizer.batch_detokenize_smiles_string(predicted_texts)
        target_texts = self.tokenizer.batch_decode(sources, skip_special_tokens=True)
        target_texts = self.tokenizer.batch_detokenize_smiles_string(target_texts)

        results = []

        # write predictions to file
        with open(self.predictions_path, "a") as f:
            for i, target_text in enumerate(target_texts):
                start = i * self.topn
                end = start + self.topn
                for j in range(start, end):
                    result = {
                        "source": target_text,
                        "predicted_target": predicted_texts[j],
                        "confidence": scores[j].item()  #math.exp(float(scores[j].item())) if isinstance(scores, torch.Tensor) else math.exp(float(scores[j])),
                    }

                    if cross_mats_all and j < len(cross_mats_all):
                        # If JSON size becomes large, you may choose only the last layer: cross_mats_all[j][-1]
                        result["cross_attentions"] = cross_mats_all[j]

                    # f.write(json.dumps(result) + "\n")
                    results.append(result)
        
        # return predictions
        return results

    def _collect_cross_attentions(self, sources: torch.Tensor, predictions: torch.Tensor):
        """
        Collect decoder→encoder cross-attention for each returned hypothesis.
        Returns: List[List[torch.Tensor]]
            out_all[b][l] is a tensor of shape [tgt_len, src_len] for hypothesis b and decoder layer l.
        """
        model = self.model  # VanillaTransformer
        device = sources.device

        # 1) Encode sources (batch = original B)
        enc_out = model.encode(input_ids=sources)
        memory = enc_out.last_hidden_state  # [B, src_len, dim]

        # 2) Match memory batch to predictions batch (B_eff = B * topn)
        B_eff = predictions.size(0)
        B_mem = memory.size(0)
        if B_mem != B_eff:
            memory = memory.expand(B_eff, -1, -1)  # cheap view; use .repeat if necessary

        # 3) Temporarily override cross-attn forward to request weights
        layers = list(model.decoder.decoder.layers)
        orig_forwards = []
        for layer in layers:
            mha = layer.multihead_attn
            orig_forward = mha.forward

            def forward_with_weights(self_mha, query, key, value, **kwargs):
                kwargs['need_weights'] = True
                kwargs.setdefault('average_attn_weights', True)  # -> [B, tgt_len, src_len]
                out = orig_forward(query, key, value, **kwargs)
                layer._last_cross_attn = out[1]
                return out

            mha.forward = MethodType(forward_with_weights, mha)
            orig_forwards.append(orig_forward)

        try:
            # 4) Teacher forcing pass on generated sequences
            _ = model.decoder(
                input_ids=predictions,  # [B_eff, tgt_len]
                encoder_output=memory,  # [B_eff, src_len, dim]
                padding_mask=None,
            )
        finally:
            # 5) Restore original forward functions
            for layer, orig in zip(layers, orig_forwards):
                layer.multihead_attn.forward = orig

        # 6) Build per-hypothesis per-layer tensors

        out_all = []
        num_layers = len(layers)

        for b in range(B_eff):
            last_mat = None
            # search from last layer backwards for robustness
            for li in range(num_layers - 1, -1, -1):
                attn = getattr(layers[li], "_last_cross_attn", None)
                if attn is not None and attn.numel() > 0:
                    # average_attn_weights=True -> [B_eff, tgt_len, src_len]
                    last_mat = attn[b].detach().cpu()  # [tgt_len, src_len]
                    break

            if last_mat is None:
                # fall back to an empty tensor (or you can raise a warning)
                last_mat = torch.empty(0, 0)

            out_all.append(last_mat)

        return out_all  # List[Tensor], each [tgt_len, src_len]
