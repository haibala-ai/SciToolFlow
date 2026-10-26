#!/usr/bin/env python
# coding: utf-8

#import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))
import pandas as pd
from tqdm.notebook import tqdm
# import torch
# import random
import numpy as np
# from transformers import get_linear_schedule_with_warmup
import time
import datetime
# from transformers import Trainer, TrainingArguments,DataCollatorForLanguageModeling

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer#, BitsAndBytesConfig
# import transformers

def ForceGPTmodel(model_name, device):
    from tools.implementations.biology.model_cache import cached_resource
    def load():
        model = AutoModelForCausalLM.from_pretrained(
            model_name, trust_remote_code=False, local_files_only=True)
        model.config.use_cache = False
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=False, local_files_only=True)
        tokenizer.pad_token = tokenizer.eos_token
        return model.to(device), tokenizer
    return cached_resource("forcegpt", model_name, load, (str(device), "use_cache_false"))


def predict_normalized_protein_mechanics(sequence: str, target: str = "joint") -> dict:
    """ProteinForceGPT forward prediction in its dimensionless training scale.

    target is force (maximum unfolding force), energy (area under the unfolding
    force-extension curve), or joint. The author's paper states these targets
    were normalized. No SI/unit conversion or experimental equivalence is
    supplied here; normalization constants are not exposed by the model card.
    Canonical protein only; context overflow, malformed/nonfinite/negative
    model values fail. Preserves the existing CPU sampling settings, including
    temperature0.01, top_k500, top_p0.9 and no explicit RNG reseeding.
    """
    import math
    import os
    import re
    from tools.runtime.config import Config
    from tools.implementations.biology.sequence_primitives import canonical_sequence
    from tools.implementations.biology.support.utils import generate_output_from_prompt
    tasks = {"force": "CalculateForce", "energy": "CalculateEnergy", "joint": "CalculateForceEnergy"}
    if target not in tasks:
        raise ValueError("target must be force, energy or joint")
    sequence = canonical_sequence(sequence, maximum=1000)
    torch.set_num_threads(int(os.getenv("SCITOOL_MODEL_CPU_THREADS", "4")))
    model, tokenizer = ForceGPTmodel(Config().FORCEGPT_MODEL_PATH, torch.device("cpu"))
    prompt = f"{tasks[target]}<{sequence}> "
    tokens = tokenizer.encode(prompt, add_special_tokens=False)
    context = getattr(model.config, "max_position_embeddings", None)
    if context is not None and len(tokens) + 378 > context:
        raise ValueError("Complete prompt plus generation budget exceeds model context; no truncation")
    outputs = generate_output_from_prompt(model, torch.device("cpu"), tokenizer, prompt=prompt,
                                          num_return_sequences=1, num_beams=1, temperature=0.01)
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    tail = decoded.split(">", 1)[-1].strip()
    match = re.fullmatch(r"\[\s*([^\[\]]+)\s*\]", tail)
    if match is None:
        raise RuntimeError("ProteinForceGPT did not return a complete numeric bracket result")
    try:
        values = [float(part.strip()) for part in match.group(1).split(",")]
    except ValueError as error:
        raise RuntimeError("ProteinForceGPT returned nonnumeric target text") from error
    if len(values) != (2 if target == "joint" else 1) or any(not math.isfinite(v) or v < 0 for v in values):
        raise RuntimeError("ProteinForceGPT returned invalid normalized target values")
    names = ["normalized_maximum_force", "normalized_unfolding_energy"] if target == "joint" else [
        "normalized_maximum_force" if target == "force" else "normalized_unfolding_energy"]
    return {"method": "ProteinForceGPT configured local checkpoint", "target": target,
            "predictions": dict(zip(names, values)), "units": "dimensionless normalized training scale",
            "normalization_constants": "not supplied; no SI conversion is performed",
            "experimental_accuracy_verified": False,
            "source": "https://huggingface.co/lamm-mit/ProteinForceGPT",
            "target_scale_reference": "https://openreview.net/pdf/cc865849b1f57912706687c3e0b10edd74f21f91.pdf"}
