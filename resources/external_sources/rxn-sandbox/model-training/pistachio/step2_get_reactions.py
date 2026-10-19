"""
Extract reaction SMILES from a Pistachio archive.

This script is self-contained: all logic that was previously provided by the
rxn_pistachio package has been inlined here. No external dependencies beyond
the Python standard library are required.

Usage:
    python step2_get_reactions.py                          # defaults below
    python step2_get_reactions.py --input my.tar.gz --output reactions.txt
"""

import argparse
import json
import logging
import tarfile
from pathlib import Path
from typing import Any, Dict, Iterator, Union

# ---------------------------------------------------------------------------
# Pistachio archive navigation (inlined from rxn_pistachio)
# ---------------------------------------------------------------------------

def _is_json(path: Union[str, Path]) -> bool:
    path_str = str(path)
    return path_str.endswith(".json") or path_str.endswith(".JSON")


def _iter_reaction_dicts(archive_path: Path) -> Iterator[Dict[str, Any]]:
    """
    Iterate over every reaction JSON object inside a Pistachio .tar.gz file
    or a directory tree of JSON files.
    """
    if archive_path.is_dir():
        for json_file in (p for p in archive_path.rglob("*") if _is_json(p)):
            print(f'Reading file "{json_file}"')
            with open(json_file, "rt") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
    else:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if not _is_json(member.name):
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                for raw_line in extracted:
                    line = raw_line.strip()
                    if line:
                        yield json.loads(line)


def _reaction_smiles(record: Dict[str, Any]) -> str:
    """
    Return the reaction SMILES string from a Pistachio record dictionary.
    Mirrors Record.reaction_smiles from rxn_pistachio.
    """
    data = record.get("data", {})
    if "reactionSmiles" in data:
        return data["reactionSmiles"]
    return data.get("smiles", "")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract_reactions(input_path: str, output_path: str) -> None:
    archive = Path(input_path)
    if not archive.exists():
        raise FileNotFoundError(f"Input not found: {archive}")

    written = 0
    skipped = 0

    with open(output_path, "w") as out:
        for record in _iter_reaction_dicts(archive):
            smiles = _reaction_smiles(record)
            if smiles:
                out.write(smiles + "\n")
                written += 1
            else:
                skipped += 1

    print(f"Done. Written: {written}, skipped (no SMILES): {skipped}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract reaction SMILES from a Pistachio archive."
    )
    parser.add_argument(
        "--input",
        default="pistachio.tar.gz",
        help="Path to pistachio.tar.gz or extracted directory (default: pistachio.tar.gz)",
    )
    parser.add_argument(
        "--output",
        default="reactions.txt",
        help="Output file path (default: reactions.txt)",
    )
    args = parser.parse_args()
    extract_reactions(args.input, args.output)
