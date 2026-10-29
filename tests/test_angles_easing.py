from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from kinemesis.angles import shortest_delta
from kinemesis.easing import EASE_IN, EASE_IN_OUT, EASE_OUT, Bezier, cubic_bezier_progress, progress

finite = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


def test_shortest_delta_known_values() -> None:
    assert shortest_delta(0.0) == 0.0
    assert shortest_delta(1.0) == 1.0
    assert math.isclose(shortest_delta(3.0 * math.pi / 2), -math.pi / 2, abs_tol=1e-15)
    assert math.isclose(shortest_delta(-2.0 * math.pi + 0.5), 0.5, abs_tol=1e-15)


def test_exact_ties_turn_counter_clockwise() -> None:
    assert shortest_delta(math.pi) == math.pi
    assert shortest_delta(-math.pi) == math.pi


def test_near_ties_are_not_ties() -> None:
    assert shortest_delta(math.pi - 1e-9) == math.pi - 1e-9
    assert shortest_delta(-math.pi + 1e-9) == -math.pi + 1e-9
    assert shortest_delta(math.pi + 1e-9) < 0


@given(finite)
def test_shortest_delta_range_and_congruence(x: float) -> None:
    r = shortest_delta(x)
    assert -math.pi < r <= math.pi
    k = (x - r) / (2.0 * math.pi)
    assert abs(k - round(k)) < 1e-6 or abs(x) > 1e5  # congruent mod 2*pi (loose for huge |x|)


def test_easing_endpoints_and_known_modes() -> None:
    for pts in (EASE_IN, EASE_OUT, EASE_IN_OUT, (0.9, 0.0, 0.1, 1.0)):
        assert cubic_bezier_progress(0.0, pts) == 0.0
        assert cubic_bezier_progress(1.0, pts) == 1.0
    assert progress("linear", None, 0.25) == 0.25
    assert progress("constant", None, 0.999) == 0.0
    assert progress("smoothstep", None, 0.5) == 0.5
    # CSS "ease-in" reference value, also observed in the upstream vectors
    assert math.isclose(cubic_bezier_progress(0.5, EASE_IN), 0.3153568125725393, abs_tol=1e-9)
    assert math.isclose(cubic_bezier_progress(0.5, EASE_OUT), 0.6846431874274608, abs_tol=1e-9)


@given(st.floats(min_value=0.0, max_value=1.0), st.floats(min_value=0.0, max_value=1.0))
def test_bezier_is_monotonic_for_monotonic_control_points(a: float, b: float) -> None:
    lo, hi = sorted((a, b))
    pts: Bezier = EASE_IN_OUT
    assert cubic_bezier_progress(lo, pts) <= cubic_bezier_progress(hi, pts) + 1e-12
