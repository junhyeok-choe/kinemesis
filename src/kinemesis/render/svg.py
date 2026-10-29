"""Standalone SVG backend (standard library only). Deterministic text output."""

from __future__ import annotations

from html import escape

from ..scene import Circle, EvaluatedScene, Line


def _n(x: float) -> str:
    """Format a number with at most six decimals; never emits '-0'."""
    text = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _attr(value: str) -> str:
    return escape(value, quote=True)


def render_svg(scene: EvaluatedScene) -> str:
    """Render a scene to an SVG document.

    The viewBox is centered on the origin and the drawing group flips y, so world coordinates
    (y-up, origin at the canvas center) are used unchanged.
    """
    w, h = scene.width, scene.height
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{_n(w)}" height="{_n(h)}" viewBox="{_n(-w / 2)} {_n(-h / 2)} {_n(w)} {_n(h)}">'
    ]
    if scene.background is not None:
        out.append(
            f'<rect x="{_n(-w / 2)}" y="{_n(-h / 2)}" width="{_n(w)}" height="{_n(h)}"'
            f' fill="{_attr(scene.background)}"/>'
        )
    out.append(
        '<g transform="scale(1 -1)" fill="none" stroke-linecap="round" stroke-linejoin="round">'
    )
    for d in scene.drawables:
        ident = f'data-figure="{_attr(d.figure)}" data-bone="{_attr(d.bone)}"'
        if isinstance(d, Line):
            out.append(
                f'<line {ident} x1="{_n(d.start[0])}" y1="{_n(d.start[1])}"'
                f' x2="{_n(d.end[0])}" y2="{_n(d.end[1])}"'
                f' stroke="{_attr(d.color)}" stroke-width="{_n(d.width)}"/>'
            )
        elif isinstance(d, Circle):
            fill = _attr(d.fill) if d.fill is not None else "none"
            stroke = (
                f' stroke="{_attr(d.stroke)}" stroke-width="{_n(d.stroke_width)}"'
                if d.stroke_width > 0
                else ""
            )
            out.append(
                f'<circle {ident} cx="{_n(d.center[0])}" cy="{_n(d.center[1])}"'
                f' r="{_n(d.radius)}" fill="{fill}"{stroke}/>'
            )
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"
