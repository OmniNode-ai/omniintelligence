# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Guard the workflow and validator spec paths against the retired package."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PATHS = (
    ".github/workflows/release.yml",
    ".github/workflows/sibling-lock-refresh.yml",
    ".github/workflows/workflow-script-refs.yml",
    "architecture-handshakes/validator-requirements.yaml",
)
_PATTERN = re.compile(r"omnibase.compat", re.IGNORECASE)


@pytest.mark.unit
@pytest.mark.parametrize("path", _PATHS)
def test_retired_package_is_absent(path: str) -> None:
    text = (_ROOT / path).read_text(encoding="utf-8")
    assert _PATTERN.search(text) is None
