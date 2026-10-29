# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kinemesis.kinematics import bone_order, forward_kinematics

angle = st.floats(min_value=-10, max_value=10, allow_nan=False)
length = st.floats(min_value=0, max_value=500, allow_nan=False)


def test_single_bone_points_along_its_angle() -> None:
    starts, ends, world = forward_kinematics([None], [10.0], [math.pi / 2], root=(1.0, 2.0))
    assert starts == [(1.0, 2.0)]
    assert math.isclose(ends[0][0], 1.0, abs_tol=1e-12) and math.isclose(ends[0][1], 12.0)
    assert world == [math.pi / 2]


def test_child_angle_is_local_to_parent() -> None:
    _, ends, world = forward_kinematics([None, 0], [10.0, 5.0], [0.0, math.pi / 2])
    assert math.isclose(world[1], math.pi / 2)
    assert math.isclose(ends[1][0], 10.0) and math.isclose(ends[1][1], 5.0)


def test_negative_scale_is_a_point_reflection_about_the_root() -> None:
    _, plain, _ = forward_kinematics([None, 0], [10.0, 5.0], [0.3, 0.4], root=(0.0, 0.0))
    _, flipped, _ = forward_kinematics(
        [None, 0], [10.0, 5.0], [0.3, 0.4], root=(0.0, 0.0), scale=-1.0
    )
    for a, b in zip(plain, flipped, strict=True):
        assert math.isclose(a[0], -b[0], abs_tol=1e-12) and math.isclose(a[1], -b[1], abs_tol=1e-12)


def test_order_is_independent_of_listing_order() -> None:
    # child listed before its parent
    order = bone_order([1, None, 1])
    assert order.index(1) < order.index(0) and order.index(1) < order.index(2)
    starts, ends, _ = forward_kinematics([1, None, 1], [3.0, 4.0, 5.0], [0.0, 0.0, math.pi / 2])
    assert ends[1] == (4.0, 0.0) and starts[0] == ends[1] and starts[2] == ends[1]


def test_cycles_and_bad_parents_are_rejected() -> None:
    with pytest.raises(ValueError):
        bone_order([1, 0])
    with pytest.raises(ValueError):
        bone_order([5])


@given(
    st.lists(st.tuples(length, angle), min_size=1, max_size=12),
    st.floats(min_value=-5, max_value=5, allow_nan=False),
    st.floats(min_value=-3, max_value=3, allow_nan=False),
)
def test_bone_lengths_and_rotation_covariance(
    chain: list[tuple[float, float]], scale: float, theta: float
) -> None:
    parents: list[int | None] = [None, *list(range(len(chain) - 1))]
    lengths = [c[0] for c in chain]
    angles = [c[1] for c in chain]
    starts, ends, _ = forward_kinematics(parents, lengths, angles, scale=scale)
    for s, e, ln in zip(starts, ends, lengths, strict=True):
        assert math.isclose(math.dist(s, e), abs(ln * scale), rel_tol=1e-9, abs_tol=1e-9)
    # rotating the figure by theta rotates every joint about the root by theta
    _, rotated, _ = forward_kinematics(parents, lengths, angles, scale=scale, rotation=theta)
    c, s_ = math.cos(theta), math.sin(theta)
    for (x, y), (rx, ry) in zip(ends, rotated, strict=True):
        assert math.isclose(rx, c * x - s_ * y, abs_tol=1e-7 * (1 + abs(x) + abs(y)))
        assert math.isclose(ry, s_ * x + c * y, abs_tol=1e-7 * (1 + abs(x) + abs(y)))
