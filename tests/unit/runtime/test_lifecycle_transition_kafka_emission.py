# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit test for lifecycle transition Kafka emission wiring.

Verifies that the lifecycle dispatch handler passes kafka_producer and
publish_topic through to apply_transition(), ensuring that lifecycle
transition events reach Kafka.

Reference: OMN-6808 Task 5
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from omniintelligence.runtime.dispatch_handlers import (
    create_pattern_lifecycle_dispatch_handler,
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestLifecycleTransitionKafkaEmission:
    """Verify lifecycle handler passes producer to apply_transition."""

    async def test_producer_passed_to_apply_transition(self) -> None:
        """Handler passes kafka_producer and publish_topic to apply_transition."""
        mock_producer = AsyncMock()
        mock_repository = AsyncMock()
        mock_idempotency = AsyncMock()
        publish_topic = "onex.evt.omniintelligence.pattern-lifecycle-transitioned.v1"

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency,
            kafka_producer=mock_producer,
            publish_topic=publish_topic,
        )

        pattern_id = uuid4()
        request_id = uuid4()

        envelope = MagicMock()
        envelope.payload = {
            "pattern_id": str(pattern_id),
            "request_id": str(request_id),
            "from_status": "CANDIDATE",
            "to_status": "PROVISIONAL",
            "trigger": "promotion",
        }
        envelope.correlation_id = uuid4()

        context = MagicMock()
        context.correlation_id = uuid4()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.duplicate = False

        with patch(
            "omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.apply_transition",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_apply:
            await handler(envelope, context)

            mock_apply.assert_called_once()
            call_kwargs = mock_apply.call_args.kwargs

            assert call_kwargs["producer"] is mock_producer
            assert call_kwargs["publish_topic"] == publish_topic
            assert call_kwargs["pattern_id"] == pattern_id
            assert call_kwargs["request_id"] == request_id

    async def test_producer_none_still_calls_apply_transition(self) -> None:
        """When producer is None, handler still calls apply_transition (graceful)."""
        mock_repository = AsyncMock()
        mock_idempotency = AsyncMock()

        handler = create_pattern_lifecycle_dispatch_handler(
            repository=mock_repository,
            idempotency_store=mock_idempotency,
            kafka_producer=None,
            publish_topic=None,
        )

        envelope = MagicMock()
        envelope.payload = {
            "pattern_id": str(uuid4()),
            "request_id": str(uuid4()),
            "from_status": "CANDIDATE",
            "to_status": "PROVISIONAL",
            "trigger": "test",
        }
        envelope.correlation_id = uuid4()
        context = MagicMock()
        context.correlation_id = uuid4()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.duplicate = False

        with patch(
            "omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.apply_transition",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_apply:
            await handler(envelope, context)

            mock_apply.assert_called_once()
            call_kwargs = mock_apply.call_args.kwargs
            assert call_kwargs["producer"] is None
            assert call_kwargs["publish_topic"] is None
