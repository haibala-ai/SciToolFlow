import json
import os
import re
from collections import Counter

# Reserved tokens
reserved_tokens = [
    "[PAD]", "[unused1]", "[unused2]", "[unused3]", "[unused4]", "[unused5]",
    "[unused6]", "[unused7]", "[unused8]", "[unused9]", "[unused10]", "[UNK]",
    "[CLS]", "[SEP]", "[MASK]"
]

def count_characters(file_path):
    char_counter = Counter()
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            source = data.get('source', '')
            target = data.get('target', '')
            combined = source + target

            # Extract and count bracketed tokens
            bracket_tokens = re.findall(r'\[.*?\]', combined)
            char_counter.update(bracket_tokens)

            # Remove bracketed tokens
            combined = re.sub(r'\[.*?\]', '', combined)

            # Extract and count composite % tokens (e.g., %10, %11)
            percent_tokens = re.findall(r'%\d{2}', combined)
            char_counter.update(percent_tokens)

            # Remove composite % tokens
            combined = re.sub(r'%\d{2}', '', combined)

            # Tokenize remaining string
            tokens = []
            i = 0
            while i < len(combined):
                if combined[i:i+2] in ('Cl', 'Br'):
                    tokens.append(combined[i:i+2])
                    i += 2
                else:
                    tokens.append(combined[i])
                    i += 1

            char_counter.update(tokens)

    return char_counter

def generate_vocab(train_file, val_file, output_file):
    train_counter = count_characters(train_file)
    val_counter = count_characters(val_file)
    total_counter = train_counter + val_counter
    sorted_tokens = [token for token, _ in total_counter.most_common()]
    vocab = reserved_tokens + sorted_tokens
    with open(output_file, 'w') as file:
        for token in vocab:
            file.write(token + '\n')


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a vocabulary file from forward or retro JSONL splits."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing train.jsonl and validation.jsonl (e.g. data/pistachio/data.forward.256)",
    )
    parser.add_argument(
        "--output",
        default="vocab.txt",
        help="Output vocabulary file path (default: vocab.txt)",
    )
    args = parser.parse_args()

    train_file = os.path.join(args.data_dir, "train.jsonl")
    val_file = os.path.join(args.data_dir, "validation.jsonl")
    generate_vocab(train_file, val_file, args.output)
    print(f"Vocabulary written to '{args.output}'")
