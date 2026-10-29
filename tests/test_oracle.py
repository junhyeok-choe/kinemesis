# SPDX-License-Identifier: GPL-3.0-or-later
"""Equivalence with the upstream reference vectors (fixtures/upstream-oracle).

These tests are the only evidence of upstream equivalence (compatibility level C2) and cover
exactly the subset listed in docs/ARCHITECTURE-SPEC.md section 10 under decision D3: native FK and
tween sampling. Upstream is y-down with absolute angles; the engine is y-up with local angles, so
every vector is converted: (x, y, angle) -> (x, -y, -angle), absolute -> local along the chain.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from kinemesis import Bone, Easing, Figure, Keyframe, Project, Rig, Track, evaluate
from kinemesis.angles import shortest_delta
from kinemesis.compat.pivot32 import fround, shortest_atan2
from kinemesis.easing import cubic_bezier_progress, progress


def ulp32(x: float) -> float:
    x = abs(x)
    return 2.0 ** (math.frexp(x)[1] - 24) if x else 2.0**-149


# --- easing ------------------------------------------------------------------------------------


def bezier_tolerance(points: list[float], t: float) -> float:
    """Upstream stops bisecting when |x - t| < 1e-10, so its y error is <= 1e-10 * |dy/dx|."""
    x1, y1, x2, y2 = points
    u = 0.5
    lo, hi = 0.0, 1.0
    for _ in range(64):
        u = (lo + hi) / 2
        x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u * u * x2 + u**3
        lo, hi = (u, hi) if x < t else (lo, u)
    v = 1 - u
    dx = 3 * v * v * x1 + 6 * v * u * (x2 - x1) + 3 * u * u * (1 - x2)
    dy = 3 * v * v * y1 + 6 * v * u * (y2 - y1) + 3 * u * u * (1 - y2)
    slope = abs(dy / dx) if dx > 1e-300 else math.inf
    return 1.5e-10 * max(1.0, slope) + 1e-14


def test_bezier_curves_match_upstream_within_solver_tolerance(oracle: dict[str, Any]) -> None:
    for curve in oracle["bezier"]:
        for t, expected in curve["samples"]:
            got = cubic_bezier_progress(t, tuple(curve["points"]))
            assert abs(got - expected) <= bezier_tolerance(curve["points"], t), (curve["name"], t)


@pytest.mark.parametrize(
    ("upstream", "ours", "points"),
    [
        ("auto", "smoothstep", None),  # upstream's isolated "auto" is smoothstep
        ("linear", "linear", None),
        ("constant", "constant", None),
        ("ease-in", "cubic-bezier", (0.42, 0.0, 1.0, 1.0)),
        ("ease-out", "cubic-bezier", (0.0, 0.0, 0.58, 1.0)),
        ("bezier", "cubic-bezier", (0.42, 0.0, 0.58, 1.0)),
    ],
)
def test_easing_modes_match_upstream(
    oracle: dict[str, Any],
    upstream: str,
    ours: str,
    points: tuple[float, float, float, float] | None,
) -> None:
    entry = next(m for m in oracle["modes"] if m["mode"] == upstream)
    for t, expected in entry["samples"]:
        tol = bezier_tolerance(list(points), t) if points else 1e-15
        assert abs(progress(ours, points, t) - expected) <= tol, (upstream, t)


def test_upstream_isolated_auto_is_smoothstep_exactly(oracle: dict[str, Any]) -> None:
    case = oracle["autoValue"][0]  # a=0, b=10, no neighbours
    assert case["prev"] is None and case["next"] is None
    for t, value in case["samples"]:
        assert (
            value == 10.0 * progress("smoothstep", None, t)
            or abs(value - 10.0 * t * t * (3 - 2 * t)) < 1e-12
        )


def test_angle_wrap_matches_upstream_except_at_exact_ties(oracle: dict[str, Any]) -> None:
    for a, expected in oracle["shortest"]:
        assert shortest_atan2(a) == pytest.approx(expected, abs=1e-15)  # the compat helper
        k = round(abs(a) / math.pi)
        if k % 2 == 1 and abs(abs(a) - k * math.pi) < 1e-14:
            # an odd multiple of pi: upstream depends on the sign of sin(a) rounding; the engine
            # specifies +pi
            assert shortest_delta(a) == pytest.approx(math.pi, abs=1e-14)
        else:
            assert shortest_delta(a) == pytest.approx(expected, abs=1e-9)


# --- forward kinematics ------------------------------------------------------------------------


def rig_from_case(case: dict[str, Any]) -> tuple[Rig, list[float]]:
    """Convert upstream segments + absolute y-down angles into a rig with local y-up angles."""
    parent_of = {s["id"]: s["parent"] for s in case["segments"]}
    absolute = {s["id"]: -a for s, a in zip(case["segments"], case["angles"], strict=True)}
    bones = []
    for s in case["segments"]:
        parent = parent_of[s["id"]]
        local = absolute[s["id"]] - (absolute[parent] if parent else 0.0)
        bones.append(Bone(str(s["id"]), str(parent) if parent else None, s["length"], local))
    return Rig("r", bones), [absolute[s["id"]] for s in case["segments"]]


def depth(case: dict[str, Any], segment_id: int) -> int:
    parents = {s["id"]: s["parent"] for s in case["segments"]}
    n = 0
    while segment_id:
        segment_id = parents[segment_id]
        n += 1
    return n


def fk_cases(oracle: dict[str, Any]) -> list[dict[str, Any]]:
    # Curved (bend) segments are M2 scope; the vector is kept and skipped explicitly.
    return [c for c in oracle["fk"] if not any(s["bend"] for s in c["segments"])]


def run_fk(case: dict[str, Any], *, pivot32: bool) -> dict[str, tuple[float, float]]:
    rig, _ = rig_from_case(case)
    x, y = case["root"]
    fig = Figure("f", "r", x=x, y=-y, scale=case["scale"])
    project = Project(rigs=[rig], figures=[fig])
    scene = evaluate(project, 0, round_end=fround if pivot32 else None)
    return scene.figures[0].joints


@pytest.mark.parametrize("pivot32", [True, False], ids=["pivot32", "float64"])
def test_fk_matches_upstream_within_derived_bound(oracle: dict[str, Any], pivot32: bool) -> None:
    cases = fk_cases(oracle)
    assert len(cases) == 10
    for case in cases:
        joints = run_fk(case, pivot32=pivot32)
        for key, (ux, uy) in case["joints"].items():
            if key == "0":
                continue
            ex, ey = joints[key]
            bound = (depth(case, int(key)) + 1) * max(ulp32(ux), ulp32(uy))
            assert abs(ex - ux) <= bound and abs(ey - (-uy)) <= bound, (case["name"], key)


def test_fk_pivot32_profile_is_nearly_bit_exact(oracle: dict[str, Any]) -> None:
    """Informational strength check: in float32 emulation almost every joint is bit-identical."""
    exact = total = 0
    for case in fk_cases(oracle):
        joints = run_fk(case, pivot32=True)
        for key, (ux, uy) in case["joints"].items():
            if key == "0":
                continue
            total += 1
            exact += joints[key] == (ux, -uy)
    assert exact / total >= 0.9, f"only {exact}/{total} joints bit-identical"


def test_fk_with_bends_is_not_yet_supported_and_is_skipped_explicitly(
    oracle: dict[str, Any],
) -> None:
    skipped = [c["name"] for c in oracle["fk"] if any(s["bend"] for s in c["segments"])]
    assert skipped == ["bend"]


# --- native tween sampling ---------------------------------------------------------------------

TIE_SENSITIVE = {"wrap-exact-pi", "wrap-minus-pi", "wrap-3pi"}  # an exact +-pi step in some bone
UNSUPPORTED = {
    "mode-auto": "upstream Auto uses neighbour-aware tangents (deferred by decision D3)",
    "duration-zero-mid": "zero-duration keyframes are not representable (ticks must increase)",
}


def easing_from(spec: dict[str, Any]) -> Easing:
    mode = spec["interpolation"]
    return {
        "linear": Easing("linear"),
        "constant": Easing("constant"),
        "ease-in": Easing.ease_in(),
        "ease-out": Easing.ease_out(),
        "bezier": Easing.cubic_bezier(*spec.get("bezier", (0.42, 0.0, 0.58, 1.0))),
    }[mode]


def tween_project(case: dict[str, Any]) -> Project:
    lengths = (60.0, 40.0, 30.0)
    bones = [
        Bone("b1", None, lengths[0]),
        Bone("b2", "b1", lengths[1]),
        Bone("b3", "b2", lengths[2]),
    ]
    starts: list[int] = []
    acc = 0
    for d in case["durations"]:
        starts.append(acc)
        acc += d
    tracks: dict[str, list[Keyframe]] = {
        name: [] for name in ("angle:b1", "angle:b2", "angle:b3", "x")
    }
    for k, tick in enumerate(starts):
        a1, a2, a3 = (-v for v in case["keyframe_angles"][k])
        easing = easing_from(case["easings"][k])
        for name, value in (
            ("angle:b1", a1),
            ("angle:b2", a2 - a1),
            ("angle:b3", a3 - a2),
            ("x", case["keyframe_root_x"][k]),
        ):
            tracks[name].append(Keyframe(tick, value, easing))
    return Project(
        timebase=1,
        rigs=[Rig("r", bones)],
        figures=[Figure("f", "r", y=-100.0)],
        tracks=[Track("f", ch, ks) for ch, ks in tracks.items()],
    )


def test_native_tween_sampling_matches_upstream(oracle: dict[str, Any]) -> None:
    checked = 0
    for case in oracle["tween"]:
        name = case["name"]
        if name in UNSUPPORTED or name in TIE_SENSITIVE:
            continue
        project = tween_project(case)
        spans = [
            abs(case["keyframe_root_x"][i + 1] - case["keyframe_root_x"][i])
            for i in range(len(case["durations"]) - 1)
        ]
        x_tol = 1e-9 * max([1.0, *spans])
        for s in case["samples"]:
            scene = evaluate(project, s["tick"])
            fig = scene.figures[0]
            for seg, upstream_angle in zip(fig.segments, s["angles"], strict=True):
                assert seg.world_angle == pytest.approx(-upstream_angle, abs=1e-9), (
                    name,
                    s["tick"],
                )
            assert fig.origin[0] == pytest.approx(s["root"][0], abs=x_tol), (name, s["tick"])
            checked += 1
    assert checked == 98  # 5 modes x 17 + wrap-170 (11) + duration-1 (2)


def test_tie_sensitive_wraps_are_deterministic_and_documented(oracle: dict[str, Any]) -> None:
    """At an exact 180-degree difference the engine always turns counter-clockwise (y-up)."""
    for name in TIE_SENSITIVE:
        case = next(c for c in oracle["tween"] if c["name"] == name)
        project = tween_project(case)
        first = [
            evaluate(project, s["tick"]).figures[0].segments[0].world_angle for s in case["samples"]
        ]
        second = [
            evaluate(project, s["tick"]).figures[0].segments[0].world_angle for s in case["samples"]
        ]
        assert first == second
    case = next(c for c in oracle["tween"] if c["name"] == "wrap-exact-pi")
    mid = evaluate(tween_project(case), 5).figures[0].segments[0].world_angle
    assert mid == pytest.approx(
        math.pi / 2, abs=1e-12
    )  # key angle goes 0 -> -pi in y-up: tie -> ccw
    # Upstream (y-down 0 -> pi, positive in its frame) turns the other way in y-up terms:
    upstream_mid = case["samples"][5]["angles"][0]
    assert upstream_mid == pytest.approx(math.pi / 2, abs=1e-9)


def test_last_keyframe_holds_unwrapped_value(oracle: dict[str, Any]) -> None:
    case = next(c for c in oracle["tween"] if c["name"] == "wrap-3pi")
    project = tween_project(case)
    last = case["samples"][-1]
    assert evaluate(project, last["tick"]).figures[0].segments[0].world_angle == pytest.approx(
        -last["angles"][0], abs=1e-12
    )
    assert abs(last["angles"][0] - 3 * math.pi) < 1e-12  # upstream also holds 3*pi unwrapped


def test_unsupported_vectors_are_listed_not_forgotten(oracle: dict[str, Any]) -> None:
    names = {c["name"] for c in oracle["tween"]}
    assert set(UNSUPPORTED) <= names
