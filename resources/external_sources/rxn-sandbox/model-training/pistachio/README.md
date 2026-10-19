# Pistachio Data Pipeline

This directory contains a sequence of scripts that download and process [Pistachio](https://www.nextmovesoftware.com/pistachio.html) reaction data into the JSONL format expected by the forward and retrosynthesis model training pipelines.

## Prerequisites

- **Pistachio license** — Access to the Pistachio release archives requires a license from [NextMove Software](https://www.nextmovesoftware.com/). Obtain your credentials before running step 1.
- **`rxn-reaction-preprocessing`** — Provides the `rxn-data-pipeline` CLI used in steps 4 and 6. Install it from [rxn4chemistry/rxn-reaction-preprocessing](https://github.com/rxn4chemistry/rxn-reaction-preprocessing/).
- **Python dependencies** — `pandas` is required for steps 7 and 8.

> **Working directory**: unless noted otherwise, all scripts assume they are run from the root of the repository, and data is written under `data/pistachio/`.

---

## Step 1 — Download the Pistachio archive

Edit `step1_download.sh` to set the desired release version and replace `<USER>` and `<PASSWORD>` with your NextMove Software credentials, then run:

```bash
bash model-training/pistachio/step1_download.sh
```

This downloads `pistachio.tar.gz` for the configured release into the current directory. The `-C -` flag enables resuming an interrupted download.

---

## Step 2 — Extract reaction SMILES

```bash
python model-training/pistachio/step2_get_reactions.py
```

Iterates over every record in `pistachio.tar.gz` and writes one reaction SMILES per line to `reactions.txt`.

The input and output paths can be overridden if needed:

```bash
python model-training/pistachio/step2_get_reactions.py \
  --input path/to/pistachio.tar.gz \
  --output path/to/reactions.txt
```

Both a `.tar.gz` archive and an already-extracted directory of JSON files are accepted as input.

---

## Step 3 — Remove extended SMILES annotations

```bash
python model-training/pistachio/step3_clean_reactions.py
```

Some reaction SMILES contain extended SMILES notation blocks such as `|&1:4,24,f:2.4|` or `|f:1.2|` that are not handled correctly by downstream tools. This script strips everything after the first `|` character on each line and writes the result to `reactions_cleaned.txt`.

---

## Step 4 — Standardize reactions (IMPORT + STANDARDIZE)

```bash
rxn-data-pipeline \
  --config-dir model-training/pistachio \
  --config-name step4_standardize_reactions_config.yaml
```

Runs the **IMPORT** and **STANDARDIZE** stages of the `rxn-data-pipeline` on `reactions_cleaned.txt`. After completion, the pipeline directory (`data/pistachio/pipeline/`) will contain:

| File | Description |
|------|-------------|
| `data.imported.csv` | Raw reactions imported into the pipeline CSV format |
| `data.standardized.csv` | Reactions after SMILES standardization |

> The full pipeline will fail at this point because a subset of standardized reactions contain coordinate-bond arrow annotations such as `->[Cu+2]<-`. Step 5 removes these before the pipeline is resumed.

---

## Step 5 — Remove arrow annotations

```bash
bash model-training/pistachio/step5_remove_arrow_annotations.sh
```

Filters `data.standardized.csv` to remove any rows whose reaction SMILES contain arrow-bond annotations (`->` or `<-`). The removed rows are saved to `arrow.forward.csv` and `arrow.backward.csv` for inspection. The cleaned output is written to `arrow.removed.csv`, which is the input for the next step.

---

## Step 6 — Preprocess and split reactions (PREPROCESS + SPLIT)

```bash
rxn-data-pipeline \
  --config-dir model-training/pistachio \
  --config-name step6_preprocess_reactions_config.yaml
```

Resumes the pipeline from `arrow.removed.csv`, running the **PREPROCESS** and **SPLIT** stages. After completion, the pipeline directory will contain:

| File | Description |
|------|-------------|
| `data.processed.train.csv` | Training split |
| `data.processed.test.csv` | Test split |
| `data.processed.validation.csv` | Validation split |

The split ratio is set to 5 % for test and validation (see `step6_preprocess_reactions_config.yaml`).

---

## Step 7 — Convert splits to JSONL

```bash
python model-training/pistachio/step7_convert_to_jsonl.py
```

Reads the three CSV splits and writes them as JSONL files in the format expected by the model trainer (`{"source": "...", "target": "..."}`). Two sets of output files are produced — one for each task direction:

| Directory | Task | source | target |
|-----------|------|--------|--------|
| `data/pistachio/data.forward/` | Forward prediction | reactants | products |
| `data/pistachio/data.retro/` | Retrosynthesis | products | reactants |

Each directory contains `train.jsonl`, `test.jsonl`, and `validation.jsonl`.

---

## Step 8 — Generate model vocabulary

The vocabulary can be built with either the forward or retro data, from its training and validation splits, since the data is the same with only the source and target being switched.

```bash
python model-training/pistachio/step8_generate_vocab.py \
  --data-dir data/pistachio/data.forward \
  --output data/pistachio/vocab.txt
```

The script tokenizes all SMILES strings in `train.jsonl` and `validation.jsonl`, counts every token (bracketed atoms, two-character elements such as `Cl`/`Br`, `%nn` ring-closure labels, and individual characters), and writes a `vocab.txt` file with reserved BERT tokens prepended and all remaining tokens ordered by frequency.
