# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""OMN-19998: omnibase_compat is removed; the edited workflows must not name it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = (
    "release.yml",
    "sibling-lock-refresh.yml",
    "workflow-script-refs.yml",
)
_PATTERN = re.compile(r"omnibase.compat", re.IGNORECASE)


@pytest.mark.unit
@pytest.mark.parametrize("name", _WORKFLOWS)
def test_workflow_does_not_mention_omnibase_compat(name: str) -> None:
    text = (_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    assert _PATTERN.search(text) is None
