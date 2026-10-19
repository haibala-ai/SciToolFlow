# Model Training

This directory contains everything needed to retrain the forward prediction and retrosynthesis models.

- **`pistachio/`** — Scripts to download and preprocess Pistachio reaction data into the JSONL format required for training. See [`pistachio/README.md`](pistachio/README.md) for the full data pipeline.
- **`training/`** — The LightningCLI entry point (`cli_main.py`) and YAML configuration files for training, testing, and running predictions.
- **`tools/`** — Standalone utility scripts for data analysis, model diagnostics, and running training/testing/prediction directly without LightningCLI.

The model source code lives in [`worker/transformers_model/`](../worker/transformers_model/). The key files are:
- [`model.py`](../worker/transformers_model/model.py) — `LitVanillaTransformer`, the Lightning module that wraps the model.
- [`smiles_datamodule.py`](../worker/transformers_model/smiles_datamodule.py) — `LitSmilesDataset`, the Lightning data module.
- [`configuration.py`](../worker/transformers_model/configuration.py) — `VanillaTransformerConfig`, the model's default hyperparameter configuration.

---

## Setup

### Copy the model package

`cli_main.py` imports `transformers_model` as a local package. Python has no way to resolve this import across the repository boundary to `worker/transformers_model/` without installing it, so the folder must be copied into `model-training/` before running any command:

```bash
cp -r ../worker/transformers_model model-training/transformers_model
```

This only needs to be done once, or again whenever the model source in `worker/` changes.

### Install dependencies

#### With uv (recommended)

```bash
# Install uv if not already available
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate a virtual environment
uv venv --python 3.11
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

#### Without uv

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> On Windows replace `source .venv/bin/activate` with `.venv\Scripts\activate`.

---

## Running LightningCLI commands

All commands are run from the `model-training/` directory using `cli_main.py` together with one of the provided YAML configuration files.

### Training

```bash
# Forward model — with uv
uv run python training/cli_main.py fit --config=training/train.yaml

# Forward model — without uv (venv already activated)
python training/cli_main.py fit --config=training/train.yaml

# Retrosynthesis model
python training/cli_main.py fit --config=training/train_retro.yaml
```

### Testing

```bash
# Forward model
python training/cli_main.py test --config=training/test.yaml

# Retrosynthesis model
python training/cli_main.py test --config=training/test_retro.yaml
```

### Prediction

```bash
python training/cli_main.py predict --config=training/predict.yaml
```

---

## Configuration

Default values are defined in [`VanillaTransformerConfig`](../worker/transformers_model/configuration.py). Additional defaults are set directly in [`LitVanillaTransformer`](../worker/transformers_model/model.py) and [`LitSmilesDataset`](../worker/transformers_model/smiles_datamodule.py). Note that some defaults from `VanillaTransformerConfig` are overridden inside `LitVanillaTransformer`, so always verify which value is actually used at runtime.

Lightning saves the configuration used for each run to `hparams.yaml` inside the corresponding `lightning_logs/<version>/` folder.

### Passing options inline

Any option from a YAML file can also be passed directly on the command line:

**Model flags** — forwarded to `LitVanillaTransformer.__init__`:
```
--model.vocab_path=vocab/vocab.txt
--model.learning_rate=0.0002
--model.task=forward
```

**Data flags** — forwarded to `LitSmilesDataset.__init__`:
```
--data.vocab_path=vocab/vocab.txt
--data.train_path=data/pistachio/data.forward/train.jsonl
--data.validation_path=data/pistachio/data.forward/validation.jsonl
--data.num_dataloader_workers=16
--data.batch_size=256
```

**Trainer flags** — forwarded to the Lightning `Trainer`:
```
--trainer.max_epochs=10
--trainer.accelerator=gpu
--trainer.devices=1
--trainer.precision=32
--trainer.enable_progress_bar=false
```

**Global flags**:
```
--seed_everything=42
--config=training/train.yaml
```

### Example YAML with callbacks

More complex options, such as callbacks, are easier to specify via a YAML file:

```yaml
model:
  vocab_path: vocab/vocab.txt
  learning_rate: 0.0002
data:
  vocab_path: vocab/vocab.txt
  train_path: data/pistachio/data.forward/train.jsonl
  validation_path: data/pistachio/data.forward/validation.jsonl
  num_dataloader_workers: 16
  batch_size: 256
trainer:
  max_epochs: 10
  accelerator: gpu
  enable_progress_bar: false
  devices: 1
  precision: 32
  callbacks:
    - class_path: lightning.pytorch.callbacks.ModelCheckpoint
      init_args:
        monitor: val_accuracy
        mode: max
        save_top_k: 3
        filename: "{epoch:02d}-{val_accuracy:.4f}"
```

---

## Requirements

`requirements.txt` covers all dependencies for both model training and the Pistachio data pipeline:

| Package | Used by |
|---------|---------|
| `lightning` | LightningCLI, model and data modules |
| `pandas` | Pistachio data pipeline (steps 7 and 8) |
| `python-Levenshtein` | Edit-distance metrics during validation and testing |
| `rdkit` | SMILES validation and Tanimoto similarity during training |
| `rxn-chem-utils` | SMILES tokenization regex pattern |
| `torch` | Model training |
| `transformers` | Tokenizer, scheduler, model base classes |


---

## Improving training throughput

- **`num_dataloader_workers`** — Number of CPU workers for data loading. 16 has shown the best results in practice.
- **`batch_size`** — Samples per training step. Increasing from the default 32 to 256 (or higher) significantly reduces wall time per epoch.
- **`accumulate_grad_batches`** — Simulates a larger effective batch size without increasing GPU memory usage.
- **`precision`** — `32` is the stable default. `16-mixed` can speed up training but has shown instability (NaN loss values) in practice.
- **`profiler`** — Set `trainer.profiler: simple` to identify time bottlenecks across training steps.
