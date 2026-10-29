# SPDX-License-Identifier: GPL-3.0-or-later
"""Forward kinematics for bone trees. Pure functions over plain numbers; no model imports."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

Point = tuple[float, float]


def bone_order(parents: Sequence[int | None]) -> list[int]:
    """Indices ordered so every bone follows its parent; ties broken by index (deterministic).

    Raises ValueError on a cycle or an out-of-range parent.
    """
    n = len(parents)
    for p in parents:
        if p is not None and not 0 <= p < n:
            raise ValueError("bone parent index out of range")
    depth = [-1] * n
    for start in range(n):
        chain: list[int] = []
        cur: int | None = start
        while cur is not None and depth[cur] < 0:
            if cur in chain:
                raise ValueError("bone parents form a cycle")
            chain.append(cur)
            cur = parents[cur]
        base = -1 if cur is None else depth[cur]
        for offset, idx in enumerate(reversed(chain)):
            depth[idx] = base + 1 + offset
    return sorted(range(n), key=lambda i: (depth[i], i))


def forward_kinematics(
    parents: Sequence[int | None],
    lengths: Sequence[float],
    local_angles: Sequence[float],
    *,
    root: Point = (0.0, 0.0),
    scale: float = 1.0,
    rotation: float = 0.0,
    round_end: Callable[[float], float] | None = None,
    order: Sequence[int] | None = None,
) -> tuple[list[Point], list[Point], list[float]]:
    """Compute (starts, ends, world_angles) for each bone.

    A bone's world angle is its parent's world angle plus its local angle (root bones: the
    figure ``rotation`` plus the local angle). Its end is ``start + length * scale * (cos, sin)``.
    ``round_end`` optionally post-processes each computed end coordinate (compat profiles only).
    """
    n = len(parents)
    if not (len(lengths) == len(local_angles) == n):
        raise ValueError("parents, lengths and local_angles must have equal length")
    starts: list[Point] = [(0.0, 0.0)] * n
    ends: list[Point] = [(0.0, 0.0)] * n
    world: list[float] = [0.0] * n
    for i in order if order is not None else bone_order(parents):
        p = parents[i]
        if p is None:
            start = root
            angle = rotation + local_angles[i]
        else:
            start = ends[p]
            angle = world[p] + local_angles[i]
        length = lengths[i] * scale
        x = start[0] + length * math.cos(angle)
        y = start[1] + length * math.sin(angle)
        if round_end is not None:
            x, y = round_end(x), round_end(y)
        starts[i] = start
        ends[i] = (x, y)
        world[i] = angle
    return starts, ends, world
