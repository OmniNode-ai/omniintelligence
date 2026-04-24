# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for CI dispatch handlers (OMN-6598).

Validates:
    - CI fingerprint bridge handler computes fingerprint from payload
    - CI failure tracker bridge handler handles missing debug_store gracefully
    - All new dispatch aliases are importable
    - Handler specs in wiring.py are importable
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from omniintelligence.runtime.dispatch_handlers import (
    DISPATCH_ALIAS_CI_FAILURE_TRACKER,
    DISPATCH_ALIAS_CI_FINGERPRINT,
    DISPATCH_ALIAS_CI_RECOVERY,
    create_ci_failure_tracker_dispatch_handler,
    create_ci_fingerprint_dispatch_handler,
)


@pytest.mark.unit
class TestCiFingerprintDispatchHandler:
    """Tests for the CI fingerprint bridge handler (OMN-6598)."""

    @pytest.mark.asyncio
    async def test_handler_rejects_non_dict_payload(self) -> None:
        """Handler raises ValueError for non-dict payload."""
        handler = create_ci_fingerprint_dispatch_handler()

        envelope = MagicMock()
        envelope.payload = "not-a-dict"
        context = MagicMock()

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_computes_fingerprint(self) -> None:
        """Handler extracts failure_output and computes a fingerprint."""
        handler = create_ci_fingerprint_dispatch_handler()

        envelope = MagicMock()
        envelope.payload = {
            "failure_output": 'File "test.py", line 10, in test_foo\nAssertionError',
            "failing_tests": ["test_foo"],
        }
        context = MagicMock()
        context.correlation_id = uuid4()

        result = await handler(envelope, context)
        parsed = json.loads(result)
        assert "fingerprint" in parsed
        assert len(parsed["fingerprint"]) == 64  # SHA-256 hex digest

    def test_dispatch_alias_is_canonical(self) -> None:
        """CI fingerprint dispatch alias uses canonical cmd topic form."""
        assert DISPATCH_ALIAS_CI_FINGERPRINT.startswith("onex.commands.")
        assert "ci-failure-detected" in DISPATCH_ALIAS_CI_FINGERPRINT


@pytest.mark.unit
class TestCiFailureTrackerDispatchHandler:
    """Tests for the CI failure tracker bridge handler (OMN-6598)."""

    @pytest.mark.asyncio
    async def test_handler_rejects_non_dict_payload(self) -> None:
        """Handler raises ValueError for non-dict payload."""
        handler = create_ci_failure_tracker_dispatch_handler()

        envelope = MagicMock()
        envelope.payload = "not-a-dict"
        context = MagicMock()

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_skips_without_debug_store(self) -> None:
        """Handler returns skip result when no debug_store is provided."""
        handler = create_ci_failure_tracker_dispatch_handler(debug_store=None)

        envelope = MagicMock()
        envelope.payload = {
            "repo": "OmniNode-ai/test",
            "branch": "main",
            "sha": "abc123",
        }
        context = MagicMock()
        context.correlation_id = uuid4()

        result = await handler(envelope, context)
        parsed = json.loads(result)
        assert parsed["skipped"] is True
        assert parsed["reason"] == "no_debug_store"

    def test_dispatch_aliases_are_canonical(self) -> None:
        """CI tracker dispatch aliases use canonical cmd topic form."""
        assert DISPATCH_ALIAS_CI_FAILURE_TRACKER.startswith("onex.commands.")
        assert DISPATCH_ALIAS_CI_RECOVERY.startswith("onex.commands.")
        assert "ci-recovery-detected" in DISPATCH_ALIAS_CI_RECOVERY


@pytest.mark.unit
class TestWiringSpecs:
    """Tests that handler specs in wiring.py are importable (OMN-6598)."""

    def test_ci_fingerprint_handler_importable(self) -> None:
        """compute_error_fingerprint is importable."""
        from omniintelligence.nodes.node_ci_fingerprint_compute.handlers.handler_fingerprint import (
            compute_error_fingerprint,
        )

        assert callable(compute_error_fingerprint)

    def test_ci_streak_handler_importable(self) -> None:
        """increment_streak is importable."""
        from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_streak import (
            increment_streak,
        )

        assert callable(increment_streak)

    def test_ci_trigger_record_handler_importable(self) -> None:
        """handle_trigger_record is importable."""
        from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_trigger_record import (
            handle_trigger_record,
        )

        assert callable(handle_trigger_record)
