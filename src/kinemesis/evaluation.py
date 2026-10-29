# SPDX-License-Identifier: GPL-3.0-or-later
"""Time -> scene evaluation. ``evaluate`` is a pure function of (project, time)."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Callable
from fractions import Fraction

from . import easing as _easing
from .angles import shortest_delta
from .kinematics import Point, bone_order, forward_kinematics
from .model import ANGLE_CHANNEL_PREFIX, Figure, Keyframe, Project, Rig, Track
from .scene import Circle, Drawable, EvaluatedFigure, EvaluatedScene, Line, Segment
from .timeutil import TimeLike, to_fraction
from .validation import ensure_valid


def sample_keys(keys: list[Keyframe], tick: Fraction, *, angular: bool) -> float | None:
    """Value of a keyframe sequence at ``tick`` (exact rational ticks).

    Before the first key there is no value (None: the caller uses its default). At and after the
    last key the last value holds. Between keys, the earlier key's easing shapes the interval;
    ``angular`` interpolates along the shortest arc (ties turn counter-clockwise).
    """
    if not keys or tick < keys[0].tick:
        return None
    last = keys[-1]
    if tick >= last.tick:
        return last.value
    ticks = [k.tick for k in keys]
    i = bisect_right(ticks, tick) - 1
    a, b = keys[i], keys[i + 1]
    t = float((tick - a.tick) / (b.tick - a.tick))
    p = _easing.progress(a.easing.kind, a.easing.points, t)
    delta = b.value - a.value
    if angular:
        delta = shortest_delta(delta)
    return a.value + delta * p


def _tracks_for(project: Project) -> dict[tuple[str, str], Track]:
    return {(t.figure, t.channel): t for t in project.tracks}


def _evaluate_figure(
    fig: Figure,
    rig: Rig,
    tracks: dict[tuple[str, str], Track],
    tick: Fraction,
    round_end: Callable[[float], float] | None,
) -> tuple[EvaluatedFigure, list[tuple[int, int, int, Drawable]]]:
    def scalar(channel: str, default: float) -> float:
        track = tracks.get((fig.id, channel))
        value = sample_keys(track.keys, tick, angular=False) if track else None
        return default if value is None else value

    x, y = scalar("x", fig.x), scalar("y", fig.y)
    scale, rotation = scalar("scale", fig.scale), scalar("rotation", fig.rotation)

    index = {b.id: i for i, b in enumerate(rig.bones)}
    parents = [None if b.parent is None else index[b.parent] for b in rig.bones]
    angles: list[float] = []
    for bone in rig.bones:
        track = tracks.get((fig.id, ANGLE_CHANNEL_PREFIX + bone.id))
        value = sample_keys(track.keys, tick, angular=True) if track else None
        angles.append(bone.rest_angle if value is None else value)

    root: Point = (x, y)
    starts, ends, world = forward_kinematics(
        parents,
        [b.length for b in rig.bones],
        angles,
        root=root,
        scale=scale,
        rotation=rotation,
        round_end=round_end,
        order=bone_order(parents),
    )
    segments = tuple(Segment(b.id, starts[i], ends[i], world[i]) for i, b in enumerate(rig.bones))
    drawables: list[tuple[int, int, int, Drawable]] = []
    for i, b in enumerate(rig.bones):
        width = b.thickness * abs(scale)
        item: Drawable
        if b.kind == "circle":
            cx = (starts[i][0] + ends[i][0]) / 2.0
            cy = (starts[i][1] + ends[i][1]) / 2.0
            radius = abs(b.length * scale) / 2.0
            item = Circle(fig.id, b.id, (cx, cy), radius, 0.0 if b.fill else width, b.color, b.fill)
        else:
            item = Line(fig.id, b.id, starts[i], ends[i], width, b.color)
        drawables.append((0, b.z, i, item))
    return EvaluatedFigure(fig.id, root, segments), drawables


def evaluate(
    project: Project,
    time: TimeLike,
    *,
    check: bool = True,
    round_end: Callable[[float], float] | None = None,
) -> EvaluatedScene:
    """Evaluate ``project`` at ``time`` seconds.

    ``check`` validates the project first (skip it when evaluating many frames of a project you
    already validated). ``round_end`` is a compatibility hook, see ``kinemesis.compat.pivot32``.
    """
    if check:
        ensure_valid(project)
    seconds = to_fraction(time)
    tick = seconds * project.timebase
    rigs = {r.id: r for r in project.rigs}
    tracks = _tracks_for(project)
    figures: list[EvaluatedFigure] = []
    ordered: list[tuple[int, int, int, int, Drawable]] = []
    for fi, fig in enumerate(project.figures):
        evaluated, drawables = _evaluate_figure(fig, rigs[fig.rig], tracks, tick, round_end)
        figures.append(evaluated)
        ordered.extend((fi, z, bi, 0, d) for (_, z, bi, d) in drawables)
    ordered.sort(key=lambda row: row[:4])
    return EvaluatedScene(
        seconds,
        project.canvas.width,
        project.canvas.height,
        project.canvas.background,
        tuple(figures),
        tuple(row[4] for row in ordered),
    )
