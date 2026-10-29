# SPDX-License-Identifier: GPL-3.0-or-later
"""Angle helpers. Angles are radians; positive is counter-clockwise (y-up)."""

from __future__ import annotations

import math

TAU = 2.0 * math.pi


def shortest_delta(delta: float) -> float:
    """Wrap an angular difference into (-pi, pi].

    Exact ties (a difference of +pi or -pi, or any odd multiple) are resolved to +pi so the
    interpolation direction is deterministic: ties turn counter-clockwise.
    """
    r = math.fmod(delta + math.pi, TAU)
    if r <= 0.0:
        r += TAU
    return r - math.pi
