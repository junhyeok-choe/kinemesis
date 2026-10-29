# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact time handling. Times are rational numbers of seconds."""

from __future__ import annotations

import math
from fractions import Fraction

TimeLike = int | float | str | Fraction


def to_fraction(value: TimeLike) -> Fraction:
    """Convert a time value to an exact Fraction.

    Floats are read by their shortest decimal representation, so ``0.1`` means exactly 1/10.
    Strings may be ``"3/2"`` or ``"0.25"``. Booleans, NaN and infinities are rejected.
    """
    if isinstance(value, bool):
        raise TypeError("time must be a number, not bool")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("time must be finite")
        return Fraction(repr(value))
    if isinstance(value, str):
        return Fraction(value.strip())
    raise TypeError(f"unsupported time type: {type(value).__name__}")
