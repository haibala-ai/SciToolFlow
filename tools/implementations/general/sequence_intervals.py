"""Bounded, literal interval selection from caller-provided sequence text."""

import hashlib
import math


def select_sequence_intervals(sequence: str, intervals: list) -> dict:
    """Select and concatenate explicit 0-based half-open string intervals.

    Args:
        sequence: A nonempty string of at most 2000000 Unicode code points.
            Every supplied character counts, including whitespace. The tool
            does not parse FASTA, normalize case, infer an alphabet or remove
            headers/gaps. Supply a scientifically appropriate clean sequence.
        intervals: Between 1 and 1000 [start, stop] pairs, in ascending source
            order, with 0 <= start < stop <= len(sequence). Pairs must not
            overlap; adjacent pairs are valid. Finite mathematically integral
            JSON numbers are accepted without loss; bool, strings, fractions,
            infinities and null are rejected. Descending source intervals must
            be reordered explicitly by the caller, never silently sorted.

    Returns:
        Object with selected_sequence (exact concatenation in supplied order),
        intervals (normalized integer pairs), source_length, selected_length,
        interval_count, source_sequence_sha256 and selected_sequence_sha256
        (UTF-8 hashes of the exact corresponding strings), coordinate_convention
        and scope. No path or network access occurs. UTF-8-invalid surrogate
        strings fail rather than receiving an ambiguous hash.

    Raises:
        ValueError: Invalid string, types, count, range, order, overlap or empty
            selection. No interval is clipped, reversed, guessed or dropped.
            No biological feature, strand, frame, intron, complement, translation
            or scientific target is inferred; compose those decisions separately.
    """
    maximum_characters = 2_000_000
    if not isinstance(sequence, str) or not 1 <= len(sequence) <= maximum_characters:
        raise ValueError(
            "sequence must be a nonempty string of at most 2000000 characters"
        )
    if not isinstance(intervals, list) or not 1 <= len(intervals) <= 1000:
        raise ValueError(
            "intervals must contain between 1 and 1000 [start, stop] pairs"
        )

    def index(value, label):
        if type(value) is int:
            result = value
        elif type(value) is float and math.isfinite(value) and value.is_integer():
            result = int(value)
        else:
            raise ValueError(
                label + " must be a finite mathematical integer, excluding bool"
            )
        if not 0 <= result <= len(sequence):
            raise ValueError(label + " must lie between 0 and source_length inclusive")
        return result

    normalized = []
    previous_stop = 0
    selected_length = 0
    for position, pair in enumerate(intervals):
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"intervals[{position}] must be exactly [start, stop]")
        start = index(pair[0], f"intervals[{position}].start")
        stop = index(pair[1], f"intervals[{position}].stop")
        if start >= stop:
            raise ValueError(
                f"intervals[{position}] must be nonempty with start < stop"
            )
        if start < previous_stop:
            raise ValueError(
                "intervals must be in ascending source order and not overlap"
            )
        selected_length += stop - start
        if selected_length > maximum_characters:
            raise ValueError("Selected character count exceeds 2000000")
        previous_stop = stop
        normalized.append([start, stop])
    selected = "".join(sequence[start:stop] for start, stop in normalized)
    try:
        source_hash = hashlib.sha256(sequence.encode("utf-8")).hexdigest()
        selected_hash = hashlib.sha256(selected.encode("utf-8")).hexdigest()
    except UnicodeEncodeError as error:
        raise ValueError(
            "sequence must contain valid UTF-8 encodable Unicode characters"
        ) from error
    return {
        "selected_sequence": selected,
        "intervals": normalized,
        "source_length": len(sequence),
        "selected_length": selected_length,
        "interval_count": len(normalized),
        "source_sequence_sha256": source_hash,
        "selected_sequence_sha256": selected_hash,
        "coordinate_convention": "0-based half-open Unicode character intervals, ascending and nonoverlapping",
        "scope": "Literal source-character selection and concatenation only; no alphabet, feature, strand, complement, frame, translation, imputation or scientific interpretation",
    }
