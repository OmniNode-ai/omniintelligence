# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""`sibling-lock-refresh.yml` runs only by dispatch (OMN-18594).

RULING 2026-11-09T21:54:25Z lane=orchestrator-31d9: a downstream repository
moves its pin on a sibling only when it needs something new from it. The
workflow used to open a lock-refresh PR every day at 06:17 UTC; it now carries
no automatic trigger and keeps ``workflow_dispatch`` so a needed refresh stays
one command.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "sibling-lock-refresh.yml"
)


def _triggers() -> dict[str, object]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 reads the bare key ``on`` as the boolean True.
    return loaded.get("on", loaded.get(True))


@pytest.mark.unit
def test_manual_dispatch_is_kept() -> None:
    assert "workflow_dispatch" in _triggers()


@pytest.mark.unit
def test_no_automatic_trigger_remains() -> None:
    assert set(_triggers()) == {"workflow_dispatch"}, (
        "sibling-lock-refresh.yml gained an automatic trigger; pins move only "
        "when the repository needs something new (RULING 2026-11-09T21:54:25Z)"
    )
