"""Versioned project data. Plain dataclasses with no behavior beyond small lookups.

Conventions (see docs/ARCHITECTURE-SPEC.md section 3.3):
- World space is y-up with the origin at the canvas center; angles are radians, counter-clockwise.
- Bone angles are *local*: relative to the parent bone's world direction (root bones: to the
  figure).
- Keyframe times are integer ticks of ``Project.timebase`` (ticks per second).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from .easing import EASE_IN, EASE_IN_OUT, EASE_OUT, Bezier
from .timeutil import TimeLike, to_fraction

FORMAT = "kinemesis.project"
SCHEMA_VERSION = "0.1"

EASING_KINDS = ("constant", "linear", "smoothstep", "cubic-bezier")
BONE_KINDS = ("line", "circle")
SCALAR_CHANNELS = ("x", "y", "scale", "rotation")
ANGLE_CHANNEL_PREFIX = "angle:"


@dataclass(slots=True)
class Easing:
    """Timing curve owned by a keyframe; it shapes the interval from that key to the next."""

    kind: str = "linear"
    points: Bezier | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def cubic_bezier(cls, x1: float, y1: float, x2: float, y2: float) -> Easing:
        return cls("cubic-bezier", (x1, y1, x2, y2))

    @classmethod
    def ease_in(cls) -> Easing:
        return cls("cubic-bezier", EASE_IN)

    @classmethod
    def ease_out(cls) -> Easing:
        return cls("cubic-bezier", EASE_OUT)

    @classmethod
    def ease_in_out(cls) -> Easing:
        return cls("cubic-bezier", EASE_IN_OUT)


@dataclass(slots=True)
class Keyframe:
    tick: int
    value: float
    easing: Easing = field(default_factory=Easing)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Track:
    """Keyframes for one channel of one figure.

    Channels: ``x``, ``y``, ``scale``, ``rotation`` (scalars, no angle wrapping) and
    ``angle:<bone id>`` (a bone's local angle, interpolated along the shortest arc).
    """

    figure: str
    channel: str
    keys: list[Keyframe]
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Bone:
    id: str
    parent: str | None
    length: float
    rest_angle: float = 0.0
    kind: str = "line"
    thickness: float = 8.0
    color: str = "#000000"
    fill: str | None = None
    z: int = 0
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Rig:
    id: str
    bones: list[Bone]
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Figure:
    """A placed instance of a rig. ``kind`` is the scene-node discriminator."""

    id: str
    rig: str
    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    kind: str = "rig_figure"
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Canvas:
    width: float = 960.0
    height: float = 540.0
    background: str | None = "#ffffff"
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Project:
    name: str = "untitled"
    fps: int = 24
    timebase: int = 14400
    canvas: Canvas = field(default_factory=Canvas)
    rigs: list[Rig] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def ticks(self, seconds: TimeLike) -> int:
        """Convert seconds to integer ticks; raises ValueError if not exactly representable."""
        exact = to_fraction(seconds) * self.timebase
        if exact.denominator != 1:
            raise ValueError(
                f"{seconds!r} s is not a whole number of ticks at timebase {self.timebase}"
            )
        return int(exact)

    def frame_time(self, frame: int) -> Fraction:
        """Timestamp in seconds of a frame: frame ``i`` samples the scene at ``i / fps``."""
        return Fraction(frame, self.fps)

    @property
    def end_tick(self) -> int:
        """Tick of the last keyframe over all tracks (0 if there are none)."""
        return max((k.tick for t in self.tracks for k in t.keys), default=0)

    @property
    def frame_count(self) -> int:
        """Number of frames from 0 through the frame containing the last keyframe."""
        exact = Fraction(self.end_tick * self.fps, self.timebase)
        whole = exact.numerator // exact.denominator
        return whole + (0 if exact.denominator == 1 else 1) + 1

    def rig_by_id(self, rig_id: str) -> Rig:
        for rig in self.rigs:
            if rig.id == rig_id:
                return rig
        raise KeyError(rig_id)
