"""Evaluated, immutable scene: backend-neutral geometry for one instant. Never persisted."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Segment:
    """One bone's evaluated geometry."""

    bone: str
    start: Point
    end: Point
    world_angle: float


@dataclass(frozen=True, slots=True)
class EvaluatedFigure:
    id: str
    origin: Point
    segments: tuple[Segment, ...]

    @property
    def joints(self) -> dict[str, Point]:
        """Bone id -> end position, in rig order."""
        return {s.bone: s.end for s in self.segments}


@dataclass(frozen=True, slots=True)
class Line:
    figure: str
    bone: str
    start: Point
    end: Point
    width: float
    color: str


@dataclass(frozen=True, slots=True)
class Circle:
    figure: str
    bone: str
    center: Point
    radius: float
    stroke_width: float
    stroke: str
    fill: str | None


Drawable = Line | Circle


@dataclass(frozen=True, slots=True)
class EvaluatedScene:
    time: Fraction
    width: float
    height: float
    background: str | None
    figures: tuple[EvaluatedFigure, ...]
    drawables: tuple[Drawable, ...]


def scene_to_dict(scene: EvaluatedScene) -> dict[str, Any]:
    """JSON-ready summary of the evaluated scene (positions are float64)."""
    return {
        "time": str(scene.time),
        "canvas": {"width": scene.width, "height": scene.height, "background": scene.background},
        "figures": [
            {
                "id": f.id,
                "origin": list(f.origin),
                "bones": [
                    {
                        "id": s.bone,
                        "start": list(s.start),
                        "end": list(s.end),
                        "world_angle": s.world_angle,
                    }
                    for s in f.segments
                ],
            }
            for f in scene.figures
        ],
    }
