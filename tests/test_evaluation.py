from __future__ import annotations

import math
from fractions import Fraction

import pytest

from kinemesis import Bone, Easing, Figure, Keyframe, Project, Rig, Track, evaluate
from kinemesis.evaluation import sample_keys


def keys(*pairs: tuple[int, float], easing: Easing | None = None) -> list[Keyframe]:
    return [Keyframe(t, v, easing or Easing()) for t, v in pairs]


def test_before_first_key_has_no_value_and_after_last_holds() -> None:
    ks = keys((10, 1.0), (20, 3.0))
    assert sample_keys(ks, Fraction(9), angular=False) is None
    assert sample_keys(ks, Fraction(10), angular=False) == 1.0
    assert sample_keys(ks, Fraction(15), angular=False) == 2.0
    assert sample_keys(ks, Fraction(20), angular=False) == 3.0
    assert sample_keys(ks, Fraction(10_000), angular=False) == 3.0


def test_easing_belongs_to_outgoing_key() -> None:
    ks = [Keyframe(0, 0.0, Easing("constant")), Keyframe(10, 10.0, Easing()), Keyframe(20, 20.0)]
    assert sample_keys(ks, Fraction(5), angular=False) == 0.0  # held by key 0's constant easing
    assert sample_keys(ks, Fraction(15), angular=False) == 15.0  # key 10 is linear
    assert sample_keys(ks, Fraction(10), angular=False) == 10.0  # reaches the next key exactly


def test_angular_uses_shortest_arc_and_scalar_keeps_full_turns() -> None:
    a, b = math.radians(170), math.radians(-170)
    ks = keys((0, a), (10, b))
    mid = sample_keys(ks, Fraction(5), angular=True)
    assert mid is not None and math.isclose(mid, math.pi, abs_tol=1e-12)
    turns = keys((0, 0.0), (10, 4.0 * math.pi))
    full = sample_keys(turns, Fraction(5), angular=False)
    assert full is not None and math.isclose(full, 2.0 * math.pi, abs_tol=1e-12)


def make_project(fps: int = 24) -> Project:
    rig = Rig("r", [Bone("a", None, 10.0, 0.0), Bone("b", "a", 5.0, 0.0)])
    fig = Figure("f", "r", x=1.0, y=2.0)
    tracks = [
        Track("f", "x", keys((0, 0.0), (100, 10.0))),
        Track("f", "angle:a", keys((0, 0.0), (100, math.pi / 2))),
    ]
    return Project("t", fps=fps, timebase=100, rigs=[rig], figures=[fig], tracks=tracks)


def test_unset_channels_use_figure_and_rest_values_before_tracks_start() -> None:
    p = make_project()
    p.tracks[0].keys[0].tick = 50
    scene = evaluate(p, Fraction(1, 4))  # tick 25: x track not started yet
    assert scene.figures[0].origin == (1.0, 2.0)


def test_evaluation_is_exact_in_time_and_independent_of_fps() -> None:
    times = [Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1)]
    baseline = [evaluate(make_project(24), t) for t in times]
    for fps in (25, 30, 60, 144):
        project = make_project(fps)
        assert [evaluate(project, t) for t in times] == baseline
    # frame i at fps A and frame j at fps B address the same instant when i/A == j/B
    p24, p60 = make_project(24), make_project(60)
    assert p24.frame_time(12) == p60.frame_time(30)
    assert evaluate(p24, p24.frame_time(12)) == evaluate(p60, p60.frame_time(30))


@pytest.mark.parametrize("value", ["1/2", 0.5, Fraction(1, 2)])
def test_time_inputs_are_interpreted_exactly(value: object) -> None:
    p = make_project()
    assert evaluate(p, value) == evaluate(p, Fraction(1, 2))  # type: ignore[arg-type]


def test_float_time_means_its_decimal_representation() -> None:
    p = make_project()
    assert evaluate(p, 0.1).time == Fraction(1, 10)


def test_evaluation_is_pure_and_does_not_mutate_project() -> None:
    p = make_project()
    before = repr(p)
    first = evaluate(p, "1/3")
    second = evaluate(p, "1/3")
    assert first == second and repr(p) == before


def test_draw_order_follows_figure_then_z_then_rig_order() -> None:
    rig = Rig("r", [Bone("lo", None, 1.0, 0.0, z=5), Bone("hi", None, 1.0, 0.0, z=1)])
    p = Project(rigs=[rig], figures=[Figure("f", "r")])
    order = [d.bone for d in evaluate(p, 0).drawables]
    assert order == ["hi", "lo"]


def test_frame_count_includes_the_frame_holding_the_last_key() -> None:
    p = make_project(24)  # last key at tick 100, timebase 100 -> 1 s -> frame 24 -> 25 frames
    assert p.frame_count == 25
    p.fps = 30
    assert p.frame_count == 31
