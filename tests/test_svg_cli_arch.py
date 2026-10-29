# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import kinemesis
from kinemesis import cli
from kinemesis.render.svg import _n
from kinemesis.schema import PROJECT_SCHEMA
from kinemesis.serialization import project_to_dict

from .conftest import EXAMPLE, ROOT

GOLDEN = ROOT / "tests" / "golden"
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def assert_svg_close(actual: str, expected: str, tol: float = 1e-6) -> None:
    """Structure must match exactly; numbers must agree within ``tol`` (formatting is 1e-6)."""
    assert NUMBER.sub("#", actual) == NUMBER.sub("#", expected)
    a, e = NUMBER.findall(actual), NUMBER.findall(expected)
    assert len(a) == len(e)
    assert all(abs(float(x) - float(y)) <= tol for x, y in zip(a, e, strict=True))


@pytest.mark.parametrize("frame", [0, 12, 30, 48])
def test_svg_matches_golden(frame: int) -> None:
    project = kinemesis.load(EXAMPLE)
    svg = kinemesis.render_svg(project, project.frame_time(frame))
    golden = GOLDEN / f"stick_figure_f{frame:02d}.svg"
    if not golden.exists():  # first run creates the golden; it must be reviewed before committing
        golden.write_text(svg, encoding="utf-8", newline="\n")
        pytest.fail(f"created {golden.name}; review it and re-run")
    assert_svg_close(svg, golden.read_text(encoding="utf-8"))


def test_svg_is_deterministic_and_well_formed() -> None:
    import xml.etree.ElementTree as ET

    project = kinemesis.load(EXAMPLE)
    a = kinemesis.render_svg(project, "1/3")
    assert a == kinemesis.render_svg(project, "1/3")
    root = ET.fromstring(a)
    assert root.tag.endswith("svg")


def test_number_formatting_never_emits_negative_zero() -> None:
    assert _n(-0.0) == "0" and _n(-1e-9) == "0" and _n(1.5) == "1.5" and _n(2.0) == "2"


def test_svg_escapes_attribute_values() -> None:
    import xml.etree.ElementTree as ET

    rig = kinemesis.Rig("r", [kinemesis.Bone('a"<&', None, 1.0)])
    p = kinemesis.Project(rigs=[rig], figures=[kinemesis.Figure('f"x', "r")])
    ET.fromstring(kinemesis.render_svg(p, 0))  # parses: attributes are escaped


# --- CLI -------------------------------------------------------------------------------------


def test_cli_validate_evaluate_render(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert cli.main(["validate", str(EXAMPLE)]) == 0
    assert "valid" in capsys.readouterr().out
    assert cli.main(["evaluate", str(EXAMPLE), "--time", "1/2"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["time"] == "1/2" and data["figures"][0]["id"] == "walker"
    assert cli.main(["render", str(EXAMPLE), "--frame", "12", "-o", str(tmp_path / "f.svg")]) == 0
    assert (tmp_path / "f.svg").read_text().startswith("<svg")
    assert cli.main(["render", str(EXAMPLE), "--all", "-o", str(tmp_path / "frames")]) == 0
    assert len(list((tmp_path / "frames").glob("*.svg"))) == 49


def test_cli_reports_errors_with_exit_codes(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    bad = tmp_path / "bad.json"
    doc = project_to_dict(kinemesis.load(EXAMPLE))
    doc["rigs"][0]["bones"][0]["parent"] = "ghost"
    bad.write_text(json.dumps(doc))
    assert cli.main(["validate", str(bad)]) == 1
    assert "/rigs/0/bones/0/parent" in capsys.readouterr().err
    assert cli.main(["validate", str(tmp_path / "missing.json")]) == 3
    assert cli.main(["evaluate", str(EXAMPLE), "--time", "abc"]) == 1
    assert cli.main(["render", str(EXAMPLE), "--all"]) == 1
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0


def test_cli_schema_prints_valid_json_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["schema"]) == 0
    Draft202012Validator.check_schema(json.loads(capsys.readouterr().out))


def test_python_dash_m_entrypoint_runs() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "kinemesis", "--version"], capture_output=True, text=True, check=True
    )
    assert out.stdout.startswith("kinemesis ")


# --- schema ----------------------------------------------------------------------------------


def test_json_schema_agrees_with_strict_loader() -> None:
    validator = Draft202012Validator(PROJECT_SCHEMA)
    valid = project_to_dict(kinemesis.load(EXAMPLE))
    assert list(validator.iter_errors(valid)) == []
    invalid = json.loads(json.dumps(valid))
    invalid["surprise"] = 1
    assert list(validator.iter_errors(invalid))
    invalid = json.loads(json.dumps(valid))
    invalid["tracks"][0]["keys"][0]["easing"]["kind"] = "bouncy"
    assert list(validator.iter_errors(invalid))


# --- architecture ----------------------------------------------------------------------------

ALLOWED: dict[str, set[str]] = {
    "errors": set(),
    "angles": set(),
    "easing": set(),
    "timeutil": set(),
    "kinematics": set(),
    "scene": set(),
    "compat.pivot32": set(),
    "model": {"easing", "timeutil"},
    "validation": {"errors", "model"},
    "evaluation": {"easing", "angles", "kinematics", "model", "scene", "timeutil", "validation"},
    "serialization": {"easing", "errors", "model", "validation"},
    "schema": {"model"},
    "render.svg": {"scene"},
    "api": {
        "evaluation",
        "model",
        "render.svg",
        "scene",
        "serialization",
        "timeutil",
        "validation",
    },
    "cli": {"api", "errors", "model", "scene", "schema"},
}


def internal_imports(path: Path, package: str) -> set[str]:
    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    base = package.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            parent = base[: len(base) - (node.level - 1)] if node.level > 1 else base
            module = ".".join(parent + ([node.module] if node.module else []))
            if node.module:
                found.add(module)
            else:
                found.update(".".join([*parent, a.name]) for a in node.names)
    return found


def test_module_layering_has_no_upward_imports() -> None:
    src = ROOT / "src" / "kinemesis"
    for dotted, allowed in ALLOWED.items():
        path = src.joinpath(*dotted.split(".")).with_suffix(".py")
        package = "kinemesis" if "." not in dotted else "kinemesis." + dotted.rsplit(".", 1)[0]
        imports = {i.removeprefix("kinemesis.") for i in internal_imports(path, package)}
        imports.discard("kinemesis")
        imports = {i for i in imports if i}
        unexpected = {i for i in imports if i not in allowed and i != "__init__"}
        # `from . import __version__` in cli is the only package-level import allowed
        assert not unexpected - {"__version__"}, f"{dotted} imports {unexpected}"
    listed = {
        p.relative_to(src).with_suffix("").as_posix().replace("/", ".") for p in src.rglob("*.py")
    }
    listed -= {"__init__", "__main__", "compat.__init__", "render.__init__"}
    assert listed == set(ALLOWED), f"unlisted modules: {listed ^ set(ALLOWED)}"


IGNORED_RUNTIME_MODULES = ("kinemesis", "__main__", "_virtualenv", "sitecustomize", "usercustomize")


def test_core_imports_only_the_standard_library() -> None:
    code = (
        "import sys\n"
        "import kinemesis, kinemesis.cli, kinemesis.compat.pivot32\n"
        "names = {m.split('.')[0] for m in sys.modules}\n"
        f"ignored = {IGNORED_RUNTIME_MODULES!r}\n"
        "stdlib = sys.stdlib_module_names\n"
        "extra = sorted(n for n in names if n not in stdlib and n not in ignored)\n"
        "print(extra)\n"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]", out.stdout
