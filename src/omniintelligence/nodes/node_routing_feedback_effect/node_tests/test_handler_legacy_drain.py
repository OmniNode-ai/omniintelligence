# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for the legacy routing.feedback drain handler (OMN-8157).

Verifies that ``handle_legacy_routing_feedback_drain`` logs a warning,
does not raise, and returns None for arbitrary payloads.
"""

from __future__ import annotations

import logging

import pytest

from omniintelligence.constants import (
    TOPIC_LEGACY_ROUTING_FEEDBACK_BARE,
    TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1,
)
from omniintelligence.nodes.node_routing_feedback_effect.handlers.handler_routing_feedback import (
    handle_legacy_routing_feedback_drain,
)


class TestLegacyRoutingFeedbackDrain:
    """Tests for the legacy routing.feedback drain handler."""

    @pytest.mark.unit
    async def test_drain_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        payload: dict[str, object] = {"session_id": "legacy-abc-123"}
        with caplog.at_level(logging.WARNING):
            await handle_legacy_routing_feedback_drain(payload)

        assert any(
            TOPIC_LEGACY_ROUTING_FEEDBACK_BARE in record.message
            for record in caplog.records
        ), f"Expected warning log mentioning {TOPIC_LEGACY_ROUTING_FEEDBACK_BARE}"

    @pytest.mark.unit
    async def test_drain_mentions_replacement_topic(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        payload: dict[str, object] = {"session_id": "legacy-abc-123"}
        with caplog.at_level(logging.WARNING):
            await handle_legacy_routing_feedback_drain(payload)

        assert any(
            TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1 in record.message
            for record in caplog.records
        ), f"Expected warning log mentioning {TOPIC_OMNICLAUDE_ROUTING_FEEDBACK_V1}"

    @pytest.mark.unit
    async def test_drain_does_not_raise(self) -> None:
        result = await handle_legacy_routing_feedback_drain(
            {"session_id": "legacy-abc-123", "junk": True},
        )
        assert result is None

    @pytest.mark.unit
    async def test_drain_empty_payload(self) -> None:
        result = await handle_legacy_routing_feedback_drain({})
        assert result is None

    @pytest.mark.unit
    async def test_drain_non_dict_payload(self) -> None:
        result = await handle_legacy_routing_feedback_drain({"raw": "bytes"})
        assert result is None
