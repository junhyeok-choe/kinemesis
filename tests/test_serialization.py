from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

import kinemesis
from kinemesis import Bone, Easing, Figure, Keyframe, Project, Rig, Track, ValidationError
from kinemesis.serialization import dumps, loads, project_from_dict, project_to_dict

from .conftest import EXAMPLE


def sample() -> Project:
    rig = Rig(
        "r",
        [
            Bone("a", None, 10.0, 0.5, color="#112233"),
            Bone("b", "a", 4.0, kind="circle", fill="#ff0000"),
        ],
    )
    return Project(
        "demo",
        rigs=[rig],
        figures=[Figure("f", "r", x=3.0)],
        tracks=[Track("f", "angle:a", [Keyframe(0, 0.0, Easing.ease_in()), Keyframe(100, 1.0)])],
    )


def codes(exc: pytest.ExceptionInfo[ValidationError]) -> list[tuple[str, str]]:
    return [(i.code, i.path) for i in exc.value.issues]


def test_round_trip_is_canonical_and_stable() -> None:
    text = dumps(sample())
    again = dumps(loads(text))
    assert again == text and again.endswith("\n")
    assert loads(text) == sample()


def test_example_file_is_canonical() -> None:
    raw = EXAMPLE.read_text(encoding="utf-8")
    assert dumps(kinemesis.load(EXAMPLE)) == raw


def test_strict_rejects_unknown_fields_with_paths() -> None:
    doc = project_to_dict(sample())
    doc["surprise"] = 1
    doc["rigs"][0]["bones"][1]["wobble"] = True
    with pytest.raises(ValidationError) as exc:
        project_from_dict(doc)
    assert ("unknown_field", "/surprise") in codes(exc)
    assert ("unknown_field", "/rigs/0/bones/1/wobble") in codes(exc)


def test_lenient_preserves_unknown_fields_everywhere() -> None:
    doc = project_to_dict(sample())
    doc["surprise"] = {"nested": [1, 2]}
    doc["rigs"][0]["bones"][0]["wobble"] = True
    doc["tracks"][0]["keys"][0]["easing"]["note"] = "x"
    doc["canvas"]["dpi"] = 96
    project = project_from_dict(doc, strict=False)
    assert project_to_dict(project) == doc
    assert json.loads(dumps(project)) == doc


def test_invalid_documents_report_every_problem() -> None:
    doc = project_to_dict(sample())
    doc["rigs"][0]["bones"][1]["parent"] = "ghost"
    doc["tracks"][0]["keys"][1]["tick"] = 0
    doc["tracks"][0]["channel"] = "angle:nope"
    with pytest.raises(ValidationError) as exc:
        project_from_dict(doc)
    got = codes(exc)
    assert ("unknown_parent", "/rigs/0/bones/1/parent") in got
    assert ("unordered_keys", "/tracks/0/keys/1/tick") in got
    assert ("unknown_bone", "/tracks/0/channel") in got


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda d: d.update(format="other"), "unsupported_format"),
        (lambda d: d.update(schema_version="9.0"), "unsupported_version"),
        (lambda d: d.update(schema_version="0.2"), "unsupported_version"),
        (lambda d: d.update(fps=0), "invalid_fps"),
        (lambda d: d.update(fps="24"), "invalid_type"),
        (lambda d: d["rigs"][0]["bones"][0].update(length=-1), "invalid_bone"),
        (lambda d: d["rigs"][0]["bones"][0].update(color="red"), "invalid_color"),
        (lambda d: d["rigs"][0]["bones"][0].update(fill="#000000"), "invalid_bone"),
        (
            lambda d: d["rigs"][0]["bones"].append(copy.deepcopy(d["rigs"][0]["bones"][0])),
            "duplicate_id",
        ),
        (lambda d: d["figures"][0].update(rig="zzz"), "unknown_rig"),
        (lambda d: d["tracks"].append(copy.deepcopy(d["tracks"][0])), "duplicate_track"),
        (
            lambda d: d["tracks"][0]["keys"][0]["easing"].update(points=[2, 0, 1, 1]),
            "invalid_easing",
        ),
        (lambda d: d["tracks"][0]["keys"][0]["easing"].update(kind="bouncy"), "invalid_easing"),
        (lambda d: d["tracks"][0].update(channel="wiggle"), "invalid_channel"),
        (lambda d: d["tracks"][0].update(keys=[]), "empty_track"),
        (lambda d: d["rigs"][0]["bones"][0].update(parent="b"), "bone_cycle"),
        (lambda d: d["tracks"][0]["keys"][0].update(value=True), "invalid_type"),
        (lambda d: d["tracks"][0]["keys"][0].pop("tick"), "missing_field"),
    ],
)
def test_validation_codes(mutate: Any, code: str) -> None:
    doc = project_to_dict(sample())
    mutate(doc)
    with pytest.raises(ValidationError) as exc:
        project_from_dict(doc)
    assert code in [i.code for i in exc.value.issues]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("{", "invalid_json"),
        ('{"a": NaN}', "invalid_json"),
        ('{"a": 1, "a": 2}', "invalid_json"),
        ("[" * 100000, "too_deep"),
        ("[]", "invalid_type"),
    ],
)
def test_malformed_text_is_rejected_with_codes(text: str, code: str) -> None:
    with pytest.raises(ValidationError) as exc:
        loads(text)
    assert exc.value.code in {code, "invalid_json"}


def test_non_finite_numbers_cannot_be_written() -> None:
    p = sample()
    p.figures[0].x = float("inf")
    with pytest.raises(ValidationError):
        kinemesis.save(p, Path("/nonexistent/should-not-be-created.json"))


finite_float = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)


@given(
    st.lists(finite_float, min_size=1, max_size=6),
    st.lists(st.integers(min_value=1, max_value=50), min_size=1, max_size=6),
)
def test_round_trip_property(values: list[float], gaps: list[int]) -> None:
    n = min(len(values), len(gaps))
    ticks = [0]
    for g in gaps[: n - 1]:
        ticks.append(ticks[-1] + g)
    keys = [Keyframe(t, v) for t, v in zip(ticks, values[:n], strict=True)]
    p = sample()
    p.tracks = [Track("f", "x", keys)]
    text = dumps(p)
    assert dumps(loads(text)) == text and loads(text) == p
