"""
Decides if a rewrite is correct: it must return the same rows as the input
query (same count, duplicates included), and in the same order if the input
has a top-level ORDER BY. Values are normalized first (rounding to 4 decimals,
3 = 3.0, trailing spaces) so small representation differences don't count.
"""

import math
from decimal import Decimal


def _norm_value(v, decimals):
    """Return a comparable version of one value.

    - Decimal / float -> rounded to `decimals` digits. Two equivalent
      queries can compute sums or averages in a different order and differ
      at the 10th digit; that is not a wrong result.
    - int   -> float, so that 3 (from one query) equals 3.0 (from another).
    - str   -> trailing spaces removed (PostgreSQL pads char(n) columns).
    - None  -> kept as None (SQL NULL).
    - other (dates, intervals...) -> text.

    Examples (decimals=4):
        Decimal("2.500001") -> 2.5
        7                   -> 7.0
        "AIR      "         -> "AIR"
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, Decimal):
        return round(float(v), decimals)
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return round(v, decimals)
    if isinstance(v, int):
        return float(v)
    if isinstance(v, str):
        return v.rstrip()
    return str(v)


def normalize_rows(rows, decimals):
    """Apply _norm_value to every value of every row."""
    return [tuple(_norm_value(v, decimals) for v in r) for r in rows]


def _sort_key(row):
    """Sort key that works even when a column mixes NULL and values.

    Python cannot compare None with a number, so each value is wrapped in
    (is_null, type_name, value). Only used to put both results in the same
    order before an order-insensitive comparison.
    """
    return tuple((v is None, str(type(v)), v if v is not None else 0) for v in row)


def compare_results(ref_rows, cand_rows, ordered, decimals):
    """Compare the input query's result with the rewrite's result.

    ref_rows  : rows returned by the input query (the reference)
    cand_rows : rows returned by the LLM rewrite (the candidate)
    ordered   : True if the input query has a top-level ORDER BY
    decimals  : rounding used by _norm_value (default 4, --decimals)

    Returns (True, "") if equal, else (False, reason). The reason is stored
    in measurements.csv to understand failures afterwards.

    Checks, in order:
      1. same number of rows
      2. same number of columns
      3. same rows: in the same order if `ordered`, otherwise as multisets
         (both sorted, then compared; duplicates count)
    """
    a = normalize_rows(ref_rows, decimals)
    b = normalize_rows(cand_rows, decimals)
    if len(a) != len(b):
        return False, f"row count {len(b)} != {len(a)}"
    if a and b and len(a[0]) != len(b[0]):
        return False, f"column count {len(b[0])} != {len(a[0])}"
    if ordered:
        if a == b:
            return True, ""
        same_set = sorted(a, key=_sort_key) == sorted(b, key=_sort_key)
        return False, "same rows, different order" if same_set else "different rows"
    if sorted(a, key=_sort_key) == sorted(b, key=_sort_key):
        return True, ""
    return False, "different rows"