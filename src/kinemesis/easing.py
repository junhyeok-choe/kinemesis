# SPDX-License-Identifier: GPL-3.0-or-later
"""Easing curves mapping elapsed fraction t in [0, 1] to progress."""

from __future__ import annotations

Bezier = tuple[float, float, float, float]

EASE_IN: Bezier = (0.42, 0.0, 1.0, 1.0)
EASE_OUT: Bezier = (0.0, 0.0, 0.58, 1.0)
EASE_IN_OUT: Bezier = (0.42, 0.0, 0.58, 1.0)

_BISECTION_STEPS = 64


def smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def cubic_bezier_progress(t: float, points: Bezier) -> float:
    """CSS-style cubic-bezier(x1, y1, x2, y2) with P0=(0,0) and P3=(1,1).

    Solves x(u) = t by bisection, then returns y(u). With x1, x2 in [0, 1] the function
    x(u) is monotonic, so the solution is unique.
    """
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    x1, y1, x2, y2 = points

    def coord(u: float, a: float, b: float) -> float:
        v = 1.0 - u
        return 3.0 * v * v * u * a + 3.0 * v * u * u * b + u * u * u

    lo, hi = 0.0, 1.0
    for _ in range(_BISECTION_STEPS):
        mid = (lo + hi) / 2.0
        if coord(mid, x1, x2) < t:
            lo = mid
        else:
            hi = mid
    return coord((lo + hi) / 2.0, y1, y2)


def progress(kind: str, points: Bezier | None, t: float) -> float:
    """Eased progress for an interval whose elapsed fraction is ``t`` (0 <= t < 1)."""
    if kind == "linear":
        return t
    if kind == "constant":
        return 0.0 if t < 1.0 else 1.0
    if kind == "smoothstep":
        return smoothstep(t)
    if kind == "cubic-bezier":
        if points is None:
            raise ValueError("cubic-bezier easing requires four control values")
        return cubic_bezier_progress(t, points)
    raise ValueError(f"unknown easing kind: {kind!r}")
