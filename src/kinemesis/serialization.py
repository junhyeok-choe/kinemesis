# SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical JSON (de)serialization with strict or lenient unknown-field handling.

Strict (default): unknown fields are errors (``unknown_field``). Lenient: unknown fields are kept
in each object's ``extras`` and written back unchanged. Nothing is ever dropped silently.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .easing import Bezier
from .errors import Issue, ValidationError
from .model import (
    FORMAT,
    SCHEMA_VERSION,
    Bone,
    Canvas,
    Easing,
    Figure,
    Keyframe,
    Project,
    Rig,
    Track,
)
from .validation import ensure_valid

MAX_BYTES = 64 * 1024 * 1024


class _Ctx:
    def __init__(self, strict: bool) -> None:
        self.strict = strict
        self.issues: list[Issue] = []

    def err(self, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(code, path, message))

    def obj(
        self, value: Any, path: str, known: tuple[str, ...], required: tuple[str, ...] = ()
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        if not isinstance(value, dict):
            self.err("invalid_type", path, "expected an object")
            return None
        for name in required:
            if name not in value:
                self.err("missing_field", f"{path}/{name}", f"missing required field {name!r}")
        extras = {k: v for k, v in value.items() if k not in known}
        if extras and self.strict:
            for k in extras:
                self.err("unknown_field", f"{path}/{k}", f"unknown field {k!r}")
            extras = {}
        return value, extras

    def number(self, value: Any, path: str) -> float | None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            self.err("invalid_type", path, "expected a number")
            return None
        try:
            number = float(value)
        except OverflowError:
            number = math.inf
        if not math.isfinite(number):
            self.err("non_finite_number", path, "number must be finite")
            return None
        return number

    def integer(self, value: Any, path: str) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int):
            self.err("invalid_type", path, "expected an integer")
            return None
        return value

    def string(self, value: Any, path: str) -> str | None:
        if not isinstance(value, str):
            self.err("invalid_type", path, "expected a string")
            return None
        return value

    def optional_string(self, value: Any, path: str) -> str | None:
        return None if value is None else self.string(value, path)


def _list(ctx: _Ctx, value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        ctx.err("invalid_type", path, "expected an array")
        return []
    return value


def _parse_easing(ctx: _Ctx, value: Any, path: str) -> Easing:
    got = ctx.obj(value, path, ("kind", "points"), ("kind",))
    if got is None:
        return Easing()
    data, extras = got
    kind = ctx.string(data.get("kind"), f"{path}/kind") or "linear"
    points: Bezier | None = None
    if data.get("points") is not None:
        raw = _list(ctx, data["points"], f"{path}/points")
        nums = [ctx.number(v, f"{path}/points/{i}") for i, v in enumerate(raw)]
        if len(nums) == 4 and all(n is not None for n in nums):
            points = (
                float(nums[0] or 0),
                float(nums[1] or 0),
                float(nums[2] or 0),
                float(nums[3] or 0),
            )
        elif len(nums) != 4:
            ctx.err("invalid_easing", f"{path}/points", "expected exactly 4 numbers")
    return Easing(kind, points, extras)


def _parse_key(ctx: _Ctx, value: Any, path: str) -> Keyframe:
    got = ctx.obj(value, path, ("tick", "value", "easing"), ("tick", "value"))
    if got is None:
        return Keyframe(0, 0.0)
    data, extras = got
    tick = ctx.integer(data.get("tick"), f"{path}/tick")
    val = ctx.number(data.get("value"), f"{path}/value")
    easing = _parse_easing(ctx, data["easing"], f"{path}/easing") if "easing" in data else Easing()
    return Keyframe(0 if tick is None else tick, 0.0 if val is None else val, easing, extras)


def _parse_track(ctx: _Ctx, value: Any, path: str) -> Track:
    got = ctx.obj(value, path, ("figure", "channel", "keys"), ("figure", "channel", "keys"))
    if got is None:
        return Track("", "", [])
    data, extras = got
    keys = [
        _parse_key(ctx, k, f"{path}/keys/{i}")
        for i, k in enumerate(_list(ctx, data.get("keys"), f"{path}/keys"))
    ]
    return Track(
        ctx.string(data.get("figure"), f"{path}/figure") or "",
        ctx.string(data.get("channel"), f"{path}/channel") or "",
        keys,
        extras,
    )


_BONE_FIELDS = ("id", "parent", "length", "rest_angle", "kind", "thickness", "color", "fill", "z")


def _parse_bone(ctx: _Ctx, value: Any, path: str) -> Bone:
    got = ctx.obj(value, path, _BONE_FIELDS, ("id", "length"))
    if got is None:
        return Bone("", None, 0.0)
    d, extras = got
    bone = Bone(
        ctx.string(d.get("id"), f"{path}/id") or "",
        ctx.optional_string(d.get("parent"), f"{path}/parent"),
        0.0,
    )
    length = ctx.number(d.get("length"), f"{path}/length")
    bone.length = 0.0 if length is None else length
    for name in ("rest_angle", "thickness"):
        if name in d:
            n = ctx.number(d[name], f"{path}/{name}")
            if n is not None:
                setattr(bone, name, n)
    if "kind" in d:
        bone.kind = ctx.string(d["kind"], f"{path}/kind") or "line"
    if "color" in d:
        bone.color = ctx.string(d["color"], f"{path}/color") or ""
    if "fill" in d:
        bone.fill = ctx.optional_string(d["fill"], f"{path}/fill")
    if "z" in d:
        z = ctx.integer(d["z"], f"{path}/z")
        bone.z = 0 if z is None else z
    bone.extras = extras
    return bone


def _parse_rig(ctx: _Ctx, value: Any, path: str) -> Rig:
    got = ctx.obj(value, path, ("id", "bones"), ("id", "bones"))
    if got is None:
        return Rig("", [])
    d, extras = got
    bones = [
        _parse_bone(ctx, b, f"{path}/bones/{i}")
        for i, b in enumerate(_list(ctx, d.get("bones"), f"{path}/bones"))
    ]
    return Rig(ctx.string(d.get("id"), f"{path}/id") or "", bones, extras)


_FIGURE_FIELDS = ("id", "kind", "rig", "x", "y", "scale", "rotation")


def _parse_figure(ctx: _Ctx, value: Any, path: str) -> Figure:
    got = ctx.obj(value, path, _FIGURE_FIELDS, ("id", "rig"))
    if got is None:
        return Figure("", "")
    d, extras = got
    fig = Figure(
        ctx.string(d.get("id"), f"{path}/id") or "", ctx.string(d.get("rig"), f"{path}/rig") or ""
    )
    for name in ("x", "y", "scale", "rotation"):
        if name in d:
            n = ctx.number(d[name], f"{path}/{name}")
            if n is not None:
                setattr(fig, name, n)
    if "kind" in d:
        fig.kind = ctx.string(d["kind"], f"{path}/kind") or ""
    fig.extras = extras
    return fig


def _parse_canvas(ctx: _Ctx, value: Any, path: str) -> Canvas:
    got = ctx.obj(value, path, ("width", "height", "background"))
    if got is None:
        return Canvas()
    d, extras = got
    canvas = Canvas(extras=extras)
    for name in ("width", "height"):
        if name in d:
            n = ctx.number(d[name], f"{path}/{name}")
            if n is not None:
                setattr(canvas, name, n)
    if "background" in d:
        canvas.background = ctx.optional_string(d["background"], f"{path}/background")
    return canvas


_PROJECT_FIELDS = (
    "format",
    "schema_version",
    "name",
    "fps",
    "timebase",
    "canvas",
    "rigs",
    "figures",
    "tracks",
)


def project_from_dict(data: Any, *, strict: bool = True, validate: bool = True) -> Project:
    """Build a ``Project`` from parsed JSON. Raises ``ValidationError`` listing every problem."""
    ctx = _Ctx(strict)
    got = ctx.obj(data, "", _PROJECT_FIELDS, ("format", "schema_version"))
    if got is None:
        raise ValidationError(ctx.issues)
    d, extras = got
    if d.get("format") != FORMAT:
        ctx.err("unsupported_format", "/format", f"expected format {FORMAT!r}")
    version = d.get("schema_version")
    if not isinstance(version, str) or version.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
        ctx.err(
            "unsupported_version",
            "/schema_version",
            f"unsupported schema_version {version!r}; this build reads {SCHEMA_VERSION}.x",
        )
    elif version != SCHEMA_VERSION and strict:
        ctx.err(
            "unsupported_version", "/schema_version", f"strict mode reads exactly {SCHEMA_VERSION}"
        )
    project = Project(extras=extras)
    if "name" in d:
        project.name = ctx.string(d["name"], "/name") or ""
    for name in ("fps", "timebase"):
        if name in d:
            n = ctx.integer(d[name], f"/{name}")
            if n is not None:
                setattr(project, name, n)
    if "canvas" in d:
        project.canvas = _parse_canvas(ctx, d["canvas"], "/canvas")
    project.rigs = [
        _parse_rig(ctx, r, f"/rigs/{i}")
        for i, r in enumerate(_list(ctx, d.get("rigs", []), "/rigs"))
    ]
    project.figures = [
        _parse_figure(ctx, f, f"/figures/{i}")
        for i, f in enumerate(_list(ctx, d.get("figures", []), "/figures"))
    ]
    project.tracks = [
        _parse_track(ctx, t, f"/tracks/{i}")
        for i, t in enumerate(_list(ctx, d.get("tracks", []), "/tracks"))
    ]
    if ctx.issues:
        raise ValidationError(ctx.issues)
    return ensure_valid(project) if validate else project


def _easing_dict(e: Easing) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": e.kind}
    if e.points is not None:
        out["points"] = [float(v) for v in e.points]
    return {**out, **e.extras}


def project_to_dict(p: Project) -> dict[str, Any]:
    """Canonical dictionary form (fixed key order, extras after known keys)."""
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "name": p.name,
        "fps": p.fps,
        "timebase": p.timebase,
        "canvas": {
            "width": float(p.canvas.width),
            "height": float(p.canvas.height),
            "background": p.canvas.background,
            **p.canvas.extras,
        },
        "rigs": [
            {
                "id": r.id,
                "bones": [
                    {
                        "id": b.id,
                        "parent": b.parent,
                        "length": float(b.length),
                        "rest_angle": float(b.rest_angle),
                        "kind": b.kind,
                        "thickness": float(b.thickness),
                        "color": b.color,
                        "fill": b.fill,
                        "z": b.z,
                        **b.extras,
                    }
                    for b in r.bones
                ],
                **r.extras,
            }
            for r in p.rigs
        ],
        "figures": [
            {
                "id": f.id,
                "kind": f.kind,
                "rig": f.rig,
                "x": float(f.x),
                "y": float(f.y),
                "scale": float(f.scale),
                "rotation": float(f.rotation),
                **f.extras,
            }
            for f in p.figures
        ],
        "tracks": [
            {
                "figure": t.figure,
                "channel": t.channel,
                "keys": [
                    {
                        "tick": k.tick,
                        "value": float(k.value),
                        "easing": _easing_dict(k.easing),
                        **k.extras,
                    }
                    for k in t.keys
                ],
                **t.extras,
            }
            for t in p.tracks
        ],
        **p.extras,
    }


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} is not allowed")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def loads(text: str, *, strict: bool = True) -> Project:
    """Parse and validate a project from JSON text."""
    if len(text) > MAX_BYTES:
        raise ValidationError([Issue("too_large", "", f"document exceeds {MAX_BYTES} bytes")])
    try:
        data = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_no_duplicates)
    except RecursionError:
        raise ValidationError([Issue("too_deep", "", "document is nested too deeply")]) from None
    except ValueError as exc:
        raise ValidationError([Issue("invalid_json", "", str(exc))]) from None
    return project_from_dict(data, strict=strict)


def dumps(project: Project) -> str:
    """Canonical JSON text: stable key order, two-space indent, UTF-8 friendly, trailing newline."""
    return (
        json.dumps(project_to_dict(project), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )


def load(path: str | Path, *, strict: bool = True) -> Project:
    p = Path(path)
    if p.stat().st_size > MAX_BYTES:
        raise ValidationError([Issue("too_large", "", f"file exceeds {MAX_BYTES} bytes")])
    return loads(p.read_text(encoding="utf-8"), strict=strict)


def save(project: Project, path: str | Path) -> None:
    ensure_valid(project)
    Path(path).write_text(dumps(project), encoding="utf-8", newline="\n")


__all__: list[str] = ["dumps", "load", "loads", "project_from_dict", "project_to_dict", "save"]
