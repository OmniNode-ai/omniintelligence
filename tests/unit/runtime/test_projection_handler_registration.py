# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern-projection dispatch handler registration.

Validates:
    - Projection handler registers when pattern_query_store satisfies ProtocolPatternQueryStore
    - Projection handler does NOT register when pattern_query_store is None
    - All 3 projection routes exist (pattern-promoted, pattern-lifecycle-transitioned, pattern-stored)
    - Query-capable store can be invoked through the dispatch handler path

Related:
    - OMN-2424: Pattern projection snapshot publisher
    - OMN-5611: Wire pattern-stored events to projection handler
    - OMN-7140: Pattern intelligence pipeline end-to-end wiring
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.protocols import (
    ProtocolIdempotencyStore,
    ProtocolIntentClassifier,
    ProtocolPatternQueryStore,
    ProtocolPatternRepository,
)
from omniintelligence.runtime.dispatch_handlers import (
    create_intelligence_dispatch_engine,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repository() -> MagicMock:
    """Mock ProtocolPatternRepository."""
    repo = MagicMock()
    repo.fetch = AsyncMock(return_value=[])
    repo.fetchrow = AsyncMock(return_value=None)
    repo.execute = AsyncMock(return_value="UPDATE 0")
    assert isinstance(repo, ProtocolPatternRepository)
    return repo


@pytest.fixture
def mock_idempotency_store() -> MagicMock:
    """Mock ProtocolIdempotencyStore."""
    store = MagicMock()
    store.exists = AsyncMock(return_value=False)
    store.record = AsyncMock(return_value=None)
    store.check_and_record = AsyncMock(return_value=False)
    assert isinstance(store, ProtocolIdempotencyStore)
    return store


@pytest.fixture
def mock_intent_classifier() -> MagicMock:
    """Mock ProtocolIntentClassifier."""
    classifier = MagicMock()
    mock_output = MagicMock()
    mock_output.intent_category = "unknown"
    mock_output.confidence = 0.0
    mock_output.keywords = []
    mock_output.secondary_intents = []
    classifier.compute = AsyncMock(return_value=mock_output)
    assert isinstance(classifier, ProtocolIntentClassifier)
    return classifier


@pytest.fixture
def mock_pattern_query_store() -> MagicMock:
    """Mock ProtocolPatternQueryStore with realistic query response."""
    store = MagicMock(spec=ProtocolPatternQueryStore)
    # Return realistic pattern rows matching what query_patterns_projection returns
    store.query_patterns = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "pattern_signature": "tool_sequence: read -> grep -> edit",
                "domain_id": "general",
                "domain_version": "1.0.0",
                "confidence": 0.85,
                "status": "validated",
                "quality_score": 0.72,
                "signature_hash": "abc123",
                "recurrence_count": 5,
                "first_seen_at": "2026-03-01T00:00:00Z",
                "last_seen_at": "2026-03-30T00:00:00Z",
                "distinct_days_seen": 3,
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "evidence_tier": "measured",
            }
        ]
    )
    store.query_patterns_projection = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "pattern_signature": "tool_sequence: read -> grep -> edit",
                "domain_id": "general",
                "domain_version": "1.0.0",
                "confidence": 0.85,
                "status": "validated",
                "quality_score": 0.72,
                "signature_hash": "abc123",
                "recurrence_count": 5,
                "distinct_days_seen": 3,
                "injection_count_rolling_20": 10,
                "success_count_rolling_20": 8,
                "failure_count_rolling_20": 2,
                "evidence_tier": "measured",
            }
        ]
    )
    # Verify the mock satisfies the protocol
    assert isinstance(store, ProtocolPatternQueryStore)
    return store


# =============================================================================
# Tests: Projection Handler Positive Registration
# =============================================================================


class TestProjectionHandlerRegistration:
    """Validate projection handler registers when pattern_query_store is provided."""

    PROJECTION_HANDLER_ID = "intelligence-pattern-projection-handler"
    PROJECTION_ROUTE_IDS = {
        "intelligence-pattern-promoted-projection-route",
        "intelligence-pattern-lifecycle-transitioned-projection-route",
        "intelligence-pattern-stored-projection-route",
    }

    @pytest.mark.unit
    def test_projection_handler_registered_with_query_store(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
        mock_pattern_query_store: MagicMock,
    ) -> None:
        """Projection handler must register when pattern_query_store satisfies ProtocolPatternQueryStore."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=mock_pattern_query_store,
        )
        # Engine with projection handler has 3 more routes and 1 more handler
        # than engine without. Verify the handler is present by checking
        # handler count increased.
        engine_without = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=None,
        )
        assert engine.handler_count == engine_without.handler_count + 1
        assert engine.route_count == engine_without.route_count + 3

    @pytest.mark.unit
    def test_projection_routes_exist(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
        mock_pattern_query_store: MagicMock,
    ) -> None:
        """All 3 projection routes must exist: promoted, lifecycle-transitioned, stored."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=mock_pattern_query_store,
        )

        # Verify routes by checking that dispatch aliases map to the handler.
        # The engine stores routes internally; we verify by checking the
        # route count delta matches the expected 3 projection routes.
        engine_without = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=None,
        )
        assert engine.route_count - engine_without.route_count == 3, (
            f"Expected 3 projection routes (promoted, lifecycle-transitioned, stored), "
            f"got delta of {engine.route_count - engine_without.route_count}"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_projection_handler_invokes_query_store(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
        mock_pattern_query_store: MagicMock,
    ) -> None:
        """Projection handler must invoke the query store when dispatched."""
        from omnibase_core.models.core.model_envelope_metadata import (
            ModelEnvelopeMetadata,
        )
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        from omniintelligence.runtime.dispatch_handlers import (
            create_pattern_projection_dispatch_handler,
        )

        correlation_id = uuid4()
        handler = create_pattern_projection_dispatch_handler(
            pattern_query_store=mock_pattern_query_store,
            kafka_producer=None,
            publish_topic="onex.evt.omniintelligence.pattern-projection.v1",
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload={
                "event_type": "PatternPromoted",
                "pattern_id": str(uuid4()),
                "correlation_id": str(correlation_id),
            },
            correlation_id=correlation_id,
            metadata=ModelEnvelopeMetadata(
                tags={"message_category": "event"},
            ),
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        result = await handler(envelope, context)
        assert result == "ok"

        # Verify the query store was actually invoked via publish_projection.
        # publish_projection calls query_patterns_projection on the store.
        assert mock_pattern_query_store.query_patterns_projection.await_count >= 1, (
            "Expected query_patterns_projection to be called at least once "
            "during projection handler dispatch"
        )

    @pytest.mark.unit
    def test_upsert_store_fallback_satisfies_protocol(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
        mock_pattern_query_store: MagicMock,
    ) -> None:
        """When pattern_query_store is None but pattern_upsert_store satisfies ProtocolPatternQueryStore, projection registers."""
        # The mock_pattern_query_store also satisfies ProtocolPatternQueryStore,
        # so passing it as pattern_upsert_store should trigger fallback registration.
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=None,
            pattern_upsert_store=mock_pattern_query_store,  # fallback path
        )
        engine_without = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=None,
            pattern_upsert_store=None,
        )
        assert engine.handler_count == engine_without.handler_count + 1, (
            "Expected fallback from pattern_upsert_store to register projection handler"
        )


# =============================================================================
# Tests: Projection Handler Negative Registration
# =============================================================================


class TestProjectionHandlerNotRegistered:
    """Validate projection handler does NOT register when pattern_query_store is None."""

    @pytest.mark.unit
    def test_projection_handler_skipped_when_store_is_none(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
    ) -> None:
        """Projection handler must NOT register when pattern_query_store is None."""
        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            pattern_query_store=None,
        )
        # Without projection handler, handler count should be the baseline (27)
        # and route count should be the baseline (34) — OMN-6979
        assert engine.handler_count == 27
        assert engine.route_count == 34

    @pytest.mark.unit
    def test_projection_handler_skipped_logs_warning(
        self,
        mock_repository: MagicMock,
        mock_idempotency_store: MagicMock,
        mock_intent_classifier: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning must be logged when projection handler is not registered."""
        with caplog.at_level(logging.WARNING):
            create_intelligence_dispatch_engine(
                repository=mock_repository,
                idempotency_store=mock_idempotency_store,
                intent_classifier=mock_intent_classifier,
                pattern_query_store=None,
            )

        assert any(
            "no pattern_query_store available" in record.message
            for record in caplog.records
        ), (
            "Expected warning about missing pattern_query_store, "
            f"got: {[r.message for r in caplog.records]}"
        )
