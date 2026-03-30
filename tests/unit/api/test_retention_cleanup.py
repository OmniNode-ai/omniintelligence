# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Test retention cleanup module for omniintelligence.

OMN-7013: Verifies the retention cleanup SQL targets correct tables
and the module is importable with correct interface.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_retention_cleanup_sql_targets_agent_actions() -> None:
    """Verify the cleanup SQL targets agent_actions with created_at."""
    from omniintelligence.api.retention_cleanup import _CLEANUP_SQL_AGENT_ACTIONS

    assert "agent_actions" in _CLEANUP_SQL_AGENT_ACTIONS
    assert "created_at" in _CLEANUP_SQL_AGENT_ACTIONS
    assert "LIMIT 5000" in _CLEANUP_SQL_AGENT_ACTIONS


@pytest.mark.unit
def test_retention_cleanup_sql_targets_stale_candidates() -> None:
    """Verify the stale candidates cleanup SQL is correct."""
    from omniintelligence.api.retention_cleanup import _CLEANUP_SQL_STALE_CANDIDATES

    assert "learned_patterns" in _CLEANUP_SQL_STALE_CANDIDATES
    assert "lifecycle_status" in _CLEANUP_SQL_STALE_CANDIDATES
    assert "candidate" in _CLEANUP_SQL_STALE_CANDIDATES
    assert "14 days" in _CLEANUP_SQL_STALE_CANDIDATES
    assert "LIMIT 1000" in _CLEANUP_SQL_STALE_CANDIDATES


@pytest.mark.unit
def test_retention_defaults() -> None:
    """Verify default retention configuration."""
    from omniintelligence.api.retention_cleanup import (
        CLEANUP_INTERVAL_SECONDS,
        RETENTION_DAYS,
    )

    assert RETENTION_DAYS == 30
    assert CLEANUP_INTERVAL_SECONDS == 600


@pytest.mark.unit
def test_retention_cleanup_importable() -> None:
    """Module and functions must be importable."""
    from omniintelligence.api.retention_cleanup import (
        run_retention_cleanup,
        start_retention_loop,
    )

    assert callable(run_retention_cleanup)
    assert callable(start_retention_loop)
