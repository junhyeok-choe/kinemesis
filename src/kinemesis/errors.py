# SPDX-License-Identifier: GPL-3.0-or-later
"""Error types. Validation errors carry a machine-readable code and a JSON Pointer path."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Issue:
    """One problem found in a project document."""

    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path or '/'}: [{self.code}] {self.message}"


class KinemesisError(Exception):
    """Base class for all errors raised by kinemesis."""


class ValidationError(KinemesisError):
    """A project document is structurally or semantically invalid."""

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues: tuple[Issue, ...] = tuple(issues)
        super().__init__("; ".join(str(i) for i in self.issues) or "invalid project")

    @property
    def code(self) -> str:
        return self.issues[0].code if self.issues else "invalid"

    @property
    def path(self) -> str:
        return self.issues[0].path if self.issues else ""
