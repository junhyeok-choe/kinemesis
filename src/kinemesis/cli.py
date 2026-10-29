# SPDX-License-Identifier: GPL-3.0-or-later
"""Command-line interface: a thin wrapper over ``kinemesis.api``."""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path

from . import __version__, api
from .errors import KinemesisError, ValidationError
from .model import Project
from .scene import scene_to_dict
from .schema import PROJECT_SCHEMA

EXIT_OK, EXIT_INVALID, EXIT_IO = 0, 1, 3


def _time_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--time", metavar="SECONDS", help='seconds, e.g. 1.5 or "3/2"')
    group.add_argument("--frame", type=int, metavar="N", help="frame index (time = N / fps)")


def _resolve_time(project: Project, args: argparse.Namespace) -> Fraction:
    if args.frame is not None:
        return project.frame_time(args.frame)
    return Fraction(args.time)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kinemesis", description="Deterministic 2D rig animation engine."
    )
    parser.add_argument("--version", action="version", version=f"kinemesis {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check a project file")
    p.add_argument("file", type=Path)
    p.add_argument("--lenient", action="store_true", help="keep unknown fields instead of failing")

    p = sub.add_parser("evaluate", help="print the evaluated scene as JSON")
    p.add_argument("file", type=Path)
    _time_args(p)

    p = sub.add_parser("render", help="render SVG for one instant, or all frames into a directory")
    p.add_argument("file", type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--time", metavar="SECONDS")
    group.add_argument("--frame", type=int, metavar="N")
    group.add_argument("--all", action="store_true", help="render every frame (needs -o DIR)")
    p.add_argument(
        "-o", "--output", type=Path, help="output file (or directory with --all); default stdout"
    )

    sub.add_parser("schema", help="print the JSON Schema of the project format")
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command == "schema":
        print(json.dumps(PROJECT_SCHEMA, indent=2))
        return EXIT_OK
    project = api.load(args.file, strict=not getattr(args, "lenient", False))
    if args.command == "validate":
        print(f"{args.file}: valid ({len(project.figures)} figures, {len(project.tracks)} tracks)")
        return EXIT_OK
    if args.command == "evaluate":
        scene = api.evaluate(project, _resolve_time(project, args))
        print(json.dumps(scene_to_dict(scene), indent=2))
        return EXIT_OK
    if args.command == "render":
        if args.all:
            if args.output is None:
                print("error: --all needs -o DIR", file=sys.stderr)
                return EXIT_INVALID
            paths = api.render_frames(project, args.output)
            print(f"wrote {len(paths)} frames to {args.output}")
            return EXIT_OK
        svg = api.render_svg(project, _resolve_time(project, args))
        if args.output is None or str(args.output) == "-":
            sys.stdout.write(svg)
        else:
            args.output.write_text(svg, encoding="utf-8", newline="\n")
        return EXIT_OK
    raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except ValidationError as exc:
        for issue in exc.issues:
            print(f"error: {issue}", file=sys.stderr)
        return EXIT_INVALID
    except KinemesisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_IO
    except (ValueError, ZeroDivisionError) as exc:
        print(f"error: invalid time or value: {exc}", file=sys.stderr)
        return EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
