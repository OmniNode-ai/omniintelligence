# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Third-party dependency bumps ride the release train, not Dependabot (OMN-21351)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

_DEPENDABOT = Path(__file__).resolve().parents[2] / ".github" / "dependabot.yml"


def test_no_dependabot_version_updates() -> None:
    """No Dependabot version-update schedule is declared; security alerts are repo settings."""
    if not _DEPENDABOT.exists():
        return
    config = yaml.safe_load(_DEPENDABOT.read_text()) or {}
    updates = config.get("updates") or []
    scheduled = [
        entry.get("package-ecosystem")
        for entry in updates
        if isinstance(entry, dict) and entry.get("schedule")
    ]
    assert not scheduled, (
        f".github/dependabot.yml declares version-update schedules for {scheduled}"
    )
