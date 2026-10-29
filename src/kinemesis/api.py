"""Stable Python facade. The CLI and any future front-end call only this module."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .evaluation import evaluate
from .model import Project
from .render.svg import render_svg as _render_svg
from .scene import EvaluatedScene
from .serialization import dumps, load, loads, save
from .timeutil import TimeLike
from .validation import ensure_valid

__all__ = [
    "dumps",
    "ensure_valid",
    "evaluate",
    "load",
    "loads",
    "render_frames",
    "render_svg",
    "save",
]


def render_svg(project: Project, time: TimeLike) -> str:
    """Evaluate ``project`` at ``time`` seconds and render the scene to SVG text."""
    return _render_svg(evaluate(project, time))


def iter_scenes(
    project: Project, *, start: int = 0, stop: int | None = None
) -> Iterator[EvaluatedScene]:
    """Evaluate frames ``start`` .. ``stop`` (exclusive; default: through the last keyframe)."""
    ensure_valid(project)
    end = project.frame_count if stop is None else stop
    for frame in range(start, end):
        yield evaluate(project, project.frame_time(frame), check=False)


def render_frames(
    project: Project, directory: str | Path, *, start: int = 0, stop: int | None = None
) -> list[Path]:
    """Write ``frame_000000.svg``-style files and return their paths in order."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for offset, scene in enumerate(iter_scenes(project, start=start, stop=stop)):
        path = out / f"frame_{start + offset:06d}.svg"
        path.write_text(_render_svg(scene), encoding="utf-8", newline="\n")
        paths.append(path)
    return paths
