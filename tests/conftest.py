from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
ORACLE_DIR = ROOT / "fixtures" / "upstream-oracle" / "out"
EXAMPLE = ROOT / "examples" / "stick_figure.json"


@pytest.fixture(scope="session")
def oracle() -> dict[str, Any]:
    data = (ORACLE_DIR / "vectors.json").read_bytes()
    expected = {
        line.split()[1]: line.split()[0]
        for line in (ORACLE_DIR / "SHA256SUMS").read_text().splitlines()
        if line.strip()
    }
    assert hashlib.sha256(data).hexdigest() == expected["out/vectors.json"], (
        "oracle fixture changed"
    )
    loaded: dict[str, Any] = json.loads(data)
    assert loaded["meta"]["commit"] == "def97214c2b491fbce82647f625a73f78416c6d8"
    return loaded
