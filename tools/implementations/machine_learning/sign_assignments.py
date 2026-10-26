"""Bounded deterministic enumeration of labelled binary sign assignments."""

import math


def enumerate_sign_assignments(
    dimension: int, start_index: int = 0, max_rows: int = 256
) -> dict:
    """Enumerate a contiguous chunk of all2**dimension sign vectors.

    dimension is an integer-valued number1..16; start_index is an integer in
    [0,2**dimension], and max_rows is an integer1..10000. Boolean,fractional,
    nonfinite and string values fail. Return at most max_rows and10000sign cells.
    Coordinate0is the least significant index bit:bit0maps to-1,bit1maps to+1.
    Assignment IDs are the dimension-bit zero-padded binary index strings.
    No random sampling,probability weights,scientific exchangeability,matching,
    test statistic or tail event is inferred. Caller must establish its design
    and cover all chunks when a complete enumeration is scientifically needed.
    """

    def integer(v, name, lo, hi):
        if (
            type(v) not in (int, float)
            or not lo <= v <= hi
            or not math.isfinite(v)
            or not float(v).is_integer()
        ):
            raise ValueError(
                name
                + " must be an integer-valued number in["
                + str(lo)
                + ","
                + str(hi)
                + "],excluding boolean and fractions"
            )
        return int(v)

    dimension = integer(dimension, "dimension", 1, 16)
    total = 1 << dimension
    start_index = integer(start_index, "start_index", 0, total)
    max_rows = integer(max_rows, "max_rows", 1, 10000)
    count = min(max_rows, 10000 // dimension, total - start_index)
    stop = start_index + count
    return dict(
        dimension=dimension,
        total_assignments=total,
        start_index=start_index,
        stop_index_exclusive=stop,
        returned_assignments=count,
        assignment_indices=list(range(start_index, stop)),
        assignment_ids=[
            format(i, "0" + str(dimension) + "b") for i in range(start_index, stop)
        ],
        signs=[
            [1 if (i >> j) & 1 else -1 for j in range(dimension)]
            for i in range(start_index, stop)
        ],
        next_start_index=stop if stop < total else None,
        complete_from_zero=start_index == 0 and stop == total,
        bit_convention="Coordinate0is the least significant assignment-index bit;0gives-1and1gives+1. IDs display most significant bit first as a conventional binary string.",
        scope="Deterministic combinatorial enumeration only. All states are listed once when contiguous chunks cover[0,total_assignments). No probability,randomization validity,independence,scientific null model,observed orientation or test conclusion is inferred.",
    )
