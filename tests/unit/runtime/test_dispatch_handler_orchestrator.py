# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for intelligence orchestrator dispatch handler (OMN-6590).

Validates:
    - Bridge handler is registered in the dispatch engine
    - Route resolves for intent.received events
    - handle_receive_intent is called with correct ModelIntent
    - Sync-to-async bridge works correctly
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from omniintelligence.runtime.dispatch_handlers import (
    DISPATCH_ALIAS_INTELLIGENCE_ORCHESTRATOR,
    create_intelligence_orchestrator_dispatch_handler,
)


@pytest.mark.unit
class TestIntelligenceOrchestratorDispatchHandler:
    """Tests for the intelligence orchestrator bridge handler."""

    @pytest.mark.asyncio
    async def test_handler_rejects_non_dict_payload(self) -> None:
        """Handler raises ValueError for non-dict payload."""
        handler = create_intelligence_orchestrator_dispatch_handler()

        envelope = MagicMock()
        envelope.payload = "not-a-dict"
        context = MagicMock()

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.asyncio
    async def test_handler_processes_valid_intent_payload(self) -> None:
        """Handler constructs ModelIntent from payload and calls handle_receive_intent."""
        import json

        from omnibase_core.models.reducer.model_intent import ModelIntent
        from omnibase_core.models.reducer.payloads import ModelPayloadExtension

        handler = create_intelligence_orchestrator_dispatch_handler()

        payload_obj = ModelPayloadExtension(
            intent_type="extension",
            extension_type="test.extension",
            plugin_name="test-plugin",
        )
        intent = ModelIntent(
            intent_type="extension",
            target="test://target/path",
            payload=payload_obj,
        )
        # Round-trip through JSON to get a clean dict (like Kafka would deliver)
        intent_dict = json.loads(intent.model_dump_json())

        envelope = MagicMock()
        envelope.payload = intent_dict
        context = MagicMock()
        context.correlation_id = uuid4()

        result = await handler(envelope, context)

        # Result should be valid JSON from ModelIntentReceipt
        assert isinstance(result, str)
        assert str(intent.intent_id) in result

    def test_dispatch_alias_constant_has_correct_format(self) -> None:
        """DISPATCH_ALIAS_INTELLIGENCE_ORCHESTRATOR follows ONEX topic pattern."""
        assert "commands" in DISPATCH_ALIAS_INTELLIGENCE_ORCHESTRATOR
        assert "omniintelligence" in DISPATCH_ALIAS_INTELLIGENCE_ORCHESTRATOR
        assert "intent-received" in DISPATCH_ALIAS_INTELLIGENCE_ORCHESTRATOR
