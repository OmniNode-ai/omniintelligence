# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Review-pairing tests start with no overlay root, whatever the host exports (OMN-20936)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_overlay_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONEX_SKILL_OVERLAY_ROOTS", raising=False)
