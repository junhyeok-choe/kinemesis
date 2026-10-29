"""JSON Schema (draft 2020-12) for the strict project format. Kept in sync by tests."""

from __future__ import annotations

from typing import Any

from .model import EASING_KINDS, FORMAT, SCHEMA_VERSION

_NUM: dict[str, Any] = {"type": "number"}
_COLOR: dict[str, Any] = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}

PROJECT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "kinemesis project",
    "type": "object",
    "additionalProperties": False,
    "required": ["format", "schema_version"],
    "properties": {
        "format": {"const": FORMAT},
        "schema_version": {"const": SCHEMA_VERSION},
        "name": {"type": "string"},
        "fps": {"type": "integer", "minimum": 1, "maximum": 1000},
        "timebase": {"type": "integer", "minimum": 1},
        "canvas": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "width": {"type": "number", "exclusiveMinimum": 0},
                "height": {"type": "number", "exclusiveMinimum": 0},
                "background": {"anyOf": [_COLOR, {"type": "null"}]},
            },
        },
        "rigs": {"type": "array", "items": {"$ref": "#/$defs/rig"}},
        "figures": {"type": "array", "items": {"$ref": "#/$defs/figure"}},
        "tracks": {"type": "array", "items": {"$ref": "#/$defs/track"}},
    },
    "$defs": {
        "rig": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "bones"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "bones": {"type": "array", "items": {"$ref": "#/$defs/bone"}},
            },
        },
        "bone": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "length"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "parent": {"type": ["string", "null"]},
                "length": {"type": "number", "minimum": 0},
                "rest_angle": _NUM,
                "kind": {"enum": ["line", "circle"]},
                "thickness": {"type": "number", "minimum": 0},
                "color": _COLOR,
                "fill": {"anyOf": [_COLOR, {"type": "null"}]},
                "z": {"type": "integer"},
            },
        },
        "figure": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "rig"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "kind": {"const": "rig_figure"},
                "rig": {"type": "string"},
                "x": _NUM,
                "y": _NUM,
                "scale": _NUM,
                "rotation": _NUM,
            },
        },
        "track": {
            "type": "object",
            "additionalProperties": False,
            "required": ["figure", "channel", "keys"],
            "properties": {
                "figure": {"type": "string"},
                "channel": {"type": "string"},
                "keys": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/key"}},
            },
        },
        "key": {
            "type": "object",
            "additionalProperties": False,
            "required": ["tick", "value"],
            "properties": {
                "tick": {"type": "integer", "minimum": 0},
                "value": _NUM,
                "easing": {"$ref": "#/$defs/easing"},
            },
        },
        "easing": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind"],
            "properties": {
                "kind": {"enum": list(EASING_KINDS)},
                "points": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 4,
                    "items": _NUM,
                },
            },
        },
    },
}
