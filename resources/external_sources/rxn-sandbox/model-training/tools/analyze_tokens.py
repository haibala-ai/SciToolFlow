"""
Analyse token lengths across the train/test/validation JSONL splits.

Reports the maximum token count for source and target sequences and how
many samples exceed the configured max_length threshold.

Usage:
    python analyze_tokens.py --data-dir data/pistachio/data.forward --vocab vocab/vocab.txt
    python analyze_tokens.py --data-dir data/pistachio/data.forward --vocab vocab/vocab.txt --max-length 512
"""

import argparse
import json
import os
import sys

# Allow running from any directory inside model-training/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from transformers_model.smiles_tokenizer import SmilesTokenizer

SPLITS = ["train", "test", "validation"]
BATCH_SIZE = 1000


def analyse(data_dir: str, vocab_path: str, max_length: int) -> None:
    tokenizer = SmilesTokenizer(vocab_path)

    source_max_tokens = 0
    target_max_tokens = 0
    source_over_limit = 0
    target_over_limit = 0
    total_samples = 0

    for split in SPLITS:
        file_path = os.path.join(data_dir, f"{split}.jsonl")
        if not os.path.exists(file_path):
            print(f"  [skip] {file_path} not found")
            continue

        print(f"  Processing {file_path} ...")
        with open(file_path, "r", encoding="utf-8") as f:
            batch_sources = []
            batch_targets = []

            def process_batch(sources, targets):
                nonlocal source_max_tokens, target_max_tokens
                nonlocal source_over_limit, target_over_limit

                source_encodings = tokenizer(sources, add_special_tokens=True, truncation=False)
                target_encodings = tokenizer(targets, add_special_tokens=True, truncation=False)

                for s_ids, t_ids in zip(source_encodings["input_ids"], target_encodings["input_ids"]):
                    s_len = len(s_ids)
                    t_len = len(t_ids)
                    source_max_tokens = max(source_max_tokens, s_len)
                    target_max_tokens = max(target_max_tokens, t_len)
                    if s_len > max_length:
                        source_over_limit += 1
                    if t_len > max_length:
                        target_over_limit += 1

            for line in f:
                data = json.loads(line)
                batch_sources.append(data["source"])
                batch_targets.append(data["target"])
                total_samples += 1

                if len(batch_sources) == BATCH_SIZE:
                    process_batch(batch_sources, batch_targets)
                    batch_sources = []
                    batch_targets = []

            if batch_sources:
                process_batch(batch_sources, batch_targets)

    print()
    print(f"Max length threshold : {max_length}")
    print(f"Max tokens in source : {source_max_tokens}")
    print(f"Max tokens in target : {target_max_tokens}")
    print(f"Source over limit    : {source_over_limit} / {total_samples} ({(source_over_limit / total_samples) * 100:.2f}%)" if total_samples else "No samples processed.")
    print(f"Target over limit    : {target_over_limit} / {total_samples} ({(target_over_limit / total_samples) * 100:.2f}%)" if total_samples else "")
    print(f"Total samples        : {total_samples}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse token lengths in JSONL splits.")
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing train.jsonl, test.jsonl, validation.jsonl "
             "(e.g. data/pistachio/data.forward)",
    )
    parser.add_argument(
        "--vocab",
        required=True,
        help="Path to vocab.txt (e.g. data/pistachio/vocab.txt)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=256,
        help="Token length threshold to count over-limit samples (default: 256)",
    )
    args = parser.parse_args()
    analyse(args.data_dir, args.vocab, args.max_length)
