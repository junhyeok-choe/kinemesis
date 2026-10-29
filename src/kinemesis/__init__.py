"""kinemesis: deterministic 2D rig animation engine (pre-alpha)."""

__version__ = "0.0.1.dev0"

from .api import dumps, evaluate, load, loads, render_frames, render_svg, save
from .errors import Issue, KinemesisError, ValidationError
from .model import Bone, Canvas, Easing, Figure, Keyframe, Project, Rig, Track
from .scene import EvaluatedScene

__all__ = [
    "Bone",
    "Canvas",
    "Easing",
    "EvaluatedScene",
    "Figure",
    "Issue",
    "Keyframe",
    "KinemesisError",
    "Project",
    "Rig",
    "Track",
    "ValidationError",
    "__version__",
    "dumps",
    "evaluate",
    "load",
    "loads",
    "render_frames",
    "render_svg",
    "save",
]
