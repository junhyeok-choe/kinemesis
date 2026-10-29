"""Semantic validation of a ``Project``. Returns every issue found, with JSON Pointer paths."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from .errors import Issue, ValidationError
from .model import (
    ANGLE_CHANNEL_PREFIX,
    BONE_KINDS,
    EASING_KINDS,
    SCALAR_CHANNELS,
    Bone,
    Easing,
    Project,
)

_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_TICK = 2**53


def _finite(x: float) -> bool:
    return isinstance(x, float | int) and not isinstance(x, bool) and math.isfinite(x)


def _unique(ids: Iterable[str], base: str, what: str, issues: list[Issue]) -> None:
    seen: set[str] = set()
    for i, ident in enumerate(ids):
        if not isinstance(ident, str) or not ident:
            issues.append(
                Issue("invalid_id", f"{base}/{i}/id", f"{what} id must be a non-empty string")
            )
        elif ident in seen:
            issues.append(Issue("duplicate_id", f"{base}/{i}/id", f"duplicate {what} id {ident!r}"))
        seen.add(ident)


def _check_easing(e: Easing, path: str, issues: list[Issue]) -> None:
    if e.kind not in EASING_KINDS:
        issues.append(Issue("invalid_easing", f"{path}/kind", f"unknown easing kind {e.kind!r}"))
        return
    if e.kind == "cubic-bezier":
        p = e.points
        if p is None or len(p) != 4 or not all(_finite(v) for v in p):
            issues.append(
                Issue("invalid_easing", f"{path}/points", "cubic-bezier needs 4 finite numbers")
            )
        elif not (0.0 <= p[0] <= 1.0 and 0.0 <= p[2] <= 1.0):
            issues.append(
                Issue("invalid_easing", f"{path}/points", "x1 and x2 must be within [0, 1]")
            )
    elif e.points is not None:
        issues.append(Issue("invalid_easing", f"{path}/points", f"{e.kind} easing takes no points"))


def _check_bone(b: Bone, path: str, issues: list[Issue]) -> None:
    if b.kind not in BONE_KINDS:
        issues.append(Issue("invalid_bone", f"{path}/kind", f"unknown bone kind {b.kind!r}"))
    if not _finite(b.length) or b.length < 0:
        issues.append(Issue("invalid_bone", f"{path}/length", "length must be finite and >= 0"))
    if not _finite(b.rest_angle):
        issues.append(Issue("invalid_bone", f"{path}/rest_angle", "rest_angle must be finite"))
    if not _finite(b.thickness) or b.thickness < 0:
        issues.append(
            Issue("invalid_bone", f"{path}/thickness", "thickness must be finite and >= 0")
        )
    if not isinstance(b.color, str) or not _COLOR.match(b.color):
        issues.append(Issue("invalid_color", f"{path}/color", "color must look like #rrggbb"))
    if b.fill is not None and (not isinstance(b.fill, str) or not _COLOR.match(b.fill)):
        issues.append(Issue("invalid_color", f"{path}/fill", "fill must look like #rrggbb or null"))
    if b.fill is not None and b.kind != "circle":
        issues.append(Issue("invalid_bone", f"{path}/fill", "fill is only valid for circle bones"))
    if isinstance(b.z, bool) or not isinstance(b.z, int):
        issues.append(Issue("invalid_bone", f"{path}/z", "z must be an integer"))


def validate(project: Project) -> list[Issue]:
    """Return all semantic problems in ``project`` (empty if valid)."""
    issues: list[Issue] = []
    if (
        isinstance(project.fps, bool)
        or not isinstance(project.fps, int)
        or not 1 <= project.fps <= 1000
    ):
        issues.append(Issue("invalid_fps", "/fps", "fps must be an integer in [1, 1000]"))
    if (
        isinstance(project.timebase, bool)
        or not isinstance(project.timebase, int)
        or project.timebase < 1
    ):
        issues.append(Issue("invalid_timebase", "/timebase", "timebase must be an integer >= 1"))
    c = project.canvas
    if not (_finite(c.width) and c.width > 0 and _finite(c.height) and c.height > 0):
        issues.append(Issue("invalid_canvas", "/canvas", "width and height must be finite and > 0"))
    if c.background is not None and not (
        isinstance(c.background, str) and _COLOR.match(c.background)
    ):
        issues.append(
            Issue("invalid_color", "/canvas/background", "background must be #rrggbb or null")
        )

    _unique((r.id for r in project.rigs), "/rigs", "rig", issues)
    rigs = {r.id: r for r in project.rigs if isinstance(r.id, str)}
    for ri, rig in enumerate(project.rigs):
        base = f"/rigs/{ri}/bones"
        _unique((b.id for b in rig.bones), base, "bone", issues)
        ids = {b.id for b in rig.bones if isinstance(b.id, str)}
        for bi, bone in enumerate(rig.bones):
            _check_bone(bone, f"{base}/{bi}", issues)
            if bone.parent is not None and bone.parent not in ids:
                issues.append(
                    Issue(
                        "unknown_parent", f"{base}/{bi}/parent", f"no bone {bone.parent!r} in rig"
                    )
                )
        parents = {b.id: b.parent for b in rig.bones}
        for bi, bone in enumerate(rig.bones):
            seen: set[str] = set()
            cur: str | None = bone.id
            while cur is not None and cur in parents:
                if cur in seen:
                    issues.append(Issue("bone_cycle", f"{base}/{bi}/parent", "bones form a cycle"))
                    break
                seen.add(cur)
                cur = parents[cur]

    _unique((f.id for f in project.figures), "/figures", "figure", issues)
    figures = {f.id: f for f in project.figures if isinstance(f.id, str)}
    for fi, fig in enumerate(project.figures):
        base = f"/figures/{fi}"
        if fig.kind != "rig_figure":
            issues.append(
                Issue("invalid_figure", f"{base}/kind", f"unknown figure kind {fig.kind!r}")
            )
        if fig.rig not in rigs:
            issues.append(Issue("unknown_rig", f"{base}/rig", f"no rig {fig.rig!r}"))
        for name in ("x", "y", "scale", "rotation"):
            if not _finite(getattr(fig, name)):
                issues.append(Issue("invalid_figure", f"{base}/{name}", f"{name} must be finite"))

    seen_tracks: set[tuple[str, str]] = set()
    for ti, track in enumerate(project.tracks):
        base = f"/tracks/{ti}"
        owner = figures.get(track.figure)
        if owner is None:
            issues.append(Issue("unknown_figure", f"{base}/figure", f"no figure {track.figure!r}"))
        ch = track.channel
        if ch.startswith(ANGLE_CHANNEL_PREFIX):
            bone_id = ch[len(ANGLE_CHANNEL_PREFIX) :]
            owner_rig = rigs.get(owner.rig) if owner is not None else None
            if owner_rig is not None and bone_id not in {b.id for b in owner_rig.bones}:
                issues.append(Issue("unknown_bone", f"{base}/channel", f"no bone {bone_id!r}"))
        elif ch not in SCALAR_CHANNELS:
            issues.append(Issue("invalid_channel", f"{base}/channel", f"unknown channel {ch!r}"))
        if (track.figure, ch) in seen_tracks:
            issues.append(
                Issue("duplicate_track", base, f"second track for {track.figure!r}/{ch!r}")
            )
        seen_tracks.add((track.figure, ch))
        if not track.keys:
            issues.append(
                Issue("empty_track", f"{base}/keys", "a track needs at least one keyframe")
            )
        previous: int | None = None
        for ki, key in enumerate(track.keys):
            kp = f"{base}/keys/{ki}"
            if (
                isinstance(key.tick, bool)
                or not isinstance(key.tick, int)
                or not 0 <= key.tick <= MAX_TICK
            ):
                issues.append(
                    Issue("invalid_tick", f"{kp}/tick", "tick must be an integer in [0, 2**53]")
                )
            elif previous is not None and key.tick <= previous:
                issues.append(
                    Issue("unordered_keys", f"{kp}/tick", "ticks must be strictly increasing")
                )
            if isinstance(key.tick, int):
                previous = key.tick
            if not _finite(key.value):
                issues.append(Issue("invalid_value", f"{kp}/value", "value must be finite"))
            _check_easing(key.easing, f"{kp}/easing", issues)
    return issues


def ensure_valid(project: Project) -> Project:
    """Raise ``ValidationError`` if the project is invalid; return it unchanged otherwise."""
    issues = validate(project)
    if issues:
        raise ValidationError(issues)
    return project
