# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for pattern learning dispatch handler.

Validates:
    - Factory creates handler that extracts session_id and runs pattern extraction
    - Missing session_id raises ValueError
    - Kafka graceful degradation (no producer => extraction runs, no events)
    - Empty extraction results => no events published
    - Kafka publish failure => handler does not crash
    - Correlation ID threading through published events
    - Max patterns cap (top-K by confidence when exceeding 50)
    - Batch publishing in groups of 25
    - Session enrichment from DB with fallback
    - Insight-to-event transformation field correctness
    - Deterministic signature_hash
    - Confidence clamping [0.5, 1.0]
    - domain_id always 'general'
    - Metadata fields (insight_type, taxonomy_version)

Related:
    - OMN-2210: Wire intelligence nodes into registration + pattern extraction
    - OMN-2222: Wire intelligence pipeline end-to-end
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    EnumInsightType,
    ModelCodebaseInsight,
    ModelPatternExtractionMetadata,
    ModelPatternExtractionOutput,
)
from omniintelligence.runtime.dispatch_handler_pattern_learning import (
    MAX_PATTERNS_PER_SESSION,
    PUBLISH_BATCH_SIZE,
    _fetch_session_snapshot,
    _transform_insights_to_pattern_events,
    create_pattern_learning_dispatch_handler,
)

# =============================================================================
# Constants
# =============================================================================

_TEST_PUBLISH_TOPIC = "test.onex.evt.omniintelligence.pattern-learned.v1"
"""Explicit publish topic for tests (no default in factory)."""

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def correlation_id() -> UUID:
    """Fixed correlation ID for deterministic tests."""
    return UUID("12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def mock_repository() -> MagicMock:
    """Mock ProtocolPatternRepository for dispatch handler tests."""
    repo = MagicMock()
    repo.fetch = AsyncMock(return_value=[])
    repo.fetchrow = AsyncMock(return_value=None)
    repo.execute = AsyncMock(return_value="UPDATE 0")
    return repo


@pytest.fixture
def mock_kafka_producer() -> MagicMock:
    """Mock ProtocolKafkaPublisher for dispatch handler tests."""
    producer = MagicMock()
    producer.publish = AsyncMock(return_value=None)
    return producer


@pytest.fixture
def sample_session_id() -> str:
    """Fixed session ID for tests."""
    return "test-session-pattern-learning-001"


@pytest.fixture
def sample_pattern_learning_payload(
    sample_session_id: str,
    correlation_id: UUID,
) -> dict[str, Any]:
    """Sample PatternLearningRequested command payload."""
    return {
        "session_id": sample_session_id,
        "correlation_id": str(correlation_id),
    }


def _make_insight(
    *,
    insight_type: EnumInsightType = EnumInsightType.FILE_ACCESS_PATTERN,
    description: str = "Frequent access to utils/config.py",
    confidence: float = 0.8,
    evidence_files: tuple[str, ...] = ("src/utils/config.py",),
    evidence_session_ids: tuple[str, ...] = (),
    occurrence_count: int = 3,
    working_directory: str | None = "/workspace",
    insight_id: str | None = None,
) -> ModelCodebaseInsight:
    """Create a ModelCodebaseInsight with sensible defaults."""
    now = datetime.now(UTC)
    return ModelCodebaseInsight(
        insight_id=insight_id or f"insight-{uuid4().hex[:8]}",
        insight_type=insight_type,
        description=description,
        confidence=confidence,
        evidence_files=evidence_files,
        evidence_session_ids=evidence_session_ids,
        occurrence_count=occurrence_count,
        working_directory=working_directory,
        first_observed=now,
        last_observed=now,
        metadata={},
    )


def _make_extraction_output(
    *,
    success: bool = True,
    new_insights: tuple[ModelCodebaseInsight, ...] = (),
    updated_insights: tuple[ModelCodebaseInsight, ...] = (),
    status: str = "completed",
    message: str | None = None,
) -> ModelPatternExtractionOutput:
    """Create a ModelPatternExtractionOutput for testing."""
    return ModelPatternExtractionOutput(
        success=success,
        new_insights=new_insights,
        updated_insights=updated_insights,
        metadata=ModelPatternExtractionMetadata(
            status=status,
            message=message,
        ),
    )


def _make_envelope(
    payload: dict[str, Any],
    correlation_id: UUID,
) -> Any:
    """Create a ModelEventEnvelope wrapping the given payload."""
    from omnibase_core.models.core.model_envelope_metadata import (
        ModelEnvelopeMetadata,
    )
    from omnibase_core.models.events.model_event_envelope import (
        ModelEventEnvelope,
    )

    return ModelEventEnvelope(
        payload=payload,
        correlation_id=correlation_id,
        metadata=ModelEnvelopeMetadata(
            tags={"message_category": "command"},
        ),
    )


def _make_context(correlation_id: UUID) -> Any:
    """Create a ModelEffectContext for handler invocation."""
    from omnibase_core.models.effect.model_effect_context import (
        ModelEffectContext,
    )

    return ModelEffectContext(
        correlation_id=correlation_id,
        envelope_id=uuid4(),
    )


# =============================================================================
# Tests: Handler Happy Path
# =============================================================================


class TestPatternLearningHandlerHappyPath:
    """Validate the happy-path flow: payload -> extraction -> publish -> result."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_happy_path(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """Valid payload with session_id runs extraction and publishes events."""
        insight = _make_insight(confidence=0.85)
        extraction_output = _make_extraction_output(
            new_insights=(insight,),
        )

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            result = await handler(envelope, context)

        assert isinstance(result, str)
        # Kafka should have been called for the single insight
        mock_kafka_producer.publish.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_returns_string(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Handler must return a string (empty string on success)."""
        extraction_output = _make_extraction_output(new_insights=())

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=None,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            result = await handler(envelope, context)

        assert isinstance(result, str)


# =============================================================================
# Tests: Handler Error Cases
# =============================================================================


class TestPatternLearningHandlerErrors:
    """Validate error handling for bad payloads and infrastructure failures."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_missing_session_id(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Payload without session_id must raise ValueError."""
        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        payload_no_session = {"correlation_id": str(correlation_id)}
        envelope = _make_envelope(payload_no_session, correlation_id)
        context = _make_context(correlation_id)

        with pytest.raises(ValueError, match="missing required field 'session_id'"):
            await handler(envelope, context)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_non_dict_payload_raises(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Non-dict payload must raise ValueError."""
        from omnibase_core.models.effect.model_effect_context import (
            ModelEffectContext,
        )
        from omnibase_core.models.events.model_event_envelope import (
            ModelEventEnvelope,
        )

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope: ModelEventEnvelope[object] = ModelEventEnvelope(
            payload="not a dict",
            correlation_id=correlation_id,
        )
        context = ModelEffectContext(
            correlation_id=correlation_id,
            envelope_id=uuid4(),
        )

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, context)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_extraction_failure_returns_empty(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """When extraction returns success=False, handler returns empty string."""
        extraction_output = _make_extraction_output(
            success=False,
            status="compute_error",
            message="Extraction failed",
        )

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            result = await handler(envelope, context)

        assert result == ""
        mock_kafka_producer.publish.assert_not_called()


# =============================================================================
# Tests: Kafka Graceful Degradation
# =============================================================================


class TestPatternLearningKafkaDegradation:
    """Validate that handler works without Kafka producer."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_no_kafka_producer(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """No Kafka producer: extraction runs, no events published, returns success."""
        insight = _make_insight()
        extraction_output = _make_extraction_output(new_insights=(insight,))

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=None,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            result = await handler(envelope, context)

        assert isinstance(result, str)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_empty_extraction(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """No insights found: no events published, returns success."""
        extraction_output = _make_extraction_output(
            new_insights=(),
            updated_insights=(),
        )

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            result = await handler(envelope, context)

        assert isinstance(result, str)
        mock_kafka_producer.publish.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_kafka_publish_failure(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """Kafka publish failure: handler does not crash, returns result."""
        insight = _make_insight()
        extraction_output = _make_extraction_output(new_insights=(insight,))

        # Make publish raise on every call
        mock_kafka_producer.publish = AsyncMock(
            side_effect=RuntimeError("Kafka connection lost"),
        )

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            # Must not raise
            result = await handler(envelope, context)

        assert isinstance(result, str)


# =============================================================================
# Tests: Correlation ID Threading
# =============================================================================


class TestPatternLearningCorrelationId:
    """Validate that correlation_id from payload threads through all events."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_correlation_id_in_events(
        self,
        sample_session_id: str,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """Correlation ID from payload appears in all published events."""
        explicit_correlation = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        payload = {
            "session_id": sample_session_id,
            "correlation_id": str(explicit_correlation),
        }

        insight = _make_insight()
        extraction_output = _make_extraction_output(new_insights=(insight,))

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
        )

        envelope = _make_envelope(payload, explicit_correlation)
        context = _make_context(explicit_correlation)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            await handler(envelope, context)

        assert mock_kafka_producer.publish.call_count == 1
        publish_kwargs = mock_kafka_producer.publish.call_args.kwargs
        published_value = publish_kwargs["value"]
        assert published_value["correlation_id"] == str(explicit_correlation)


# =============================================================================
# Tests: Max Patterns Cap and Batch Publishing
# =============================================================================


class TestPatternLearningCapsAndBatching:
    """Validate max patterns cap and batch publishing behavior."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_max_patterns_cap(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """Extraction returns >50 insights: only top 50 by confidence published."""
        # Create 60 insights with varying confidence
        insights = tuple(
            _make_insight(
                confidence=round(0.5 + (i / 120), 4),
                description=f"Pattern {i} with confidence",
                insight_id=f"insight-{i:03d}",
            )
            for i in range(60)
        )
        extraction_output = _make_extraction_output(new_insights=insights)

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            await handler(envelope, context)

        # Should publish exactly MAX_PATTERNS_PER_SESSION events
        assert mock_kafka_producer.publish.call_count == MAX_PATTERNS_PER_SESSION

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pattern_learning_handler_batch_publishing(
        self,
        sample_pattern_learning_payload: dict[str, Any],
        correlation_id: UUID,
        mock_repository: MagicMock,
        mock_kafka_producer: MagicMock,
    ) -> None:
        """More than 25 patterns are published across multiple batches."""
        # Create exactly 30 insights (should result in 2 batches: 25 + 5)
        insights = tuple(
            _make_insight(
                confidence=0.8,
                description=f"Batch pattern {i}",
                insight_id=f"insight-batch-{i:03d}",
            )
            for i in range(30)
        )
        extraction_output = _make_extraction_output(new_insights=insights)

        handler = create_pattern_learning_dispatch_handler(
            repository=mock_repository,
            kafka_producer=mock_kafka_producer,
            publish_topic=_TEST_PUBLISH_TOPIC,
            correlation_id=correlation_id,
        )

        envelope = _make_envelope(sample_pattern_learning_payload, correlation_id)
        context = _make_context(correlation_id)

        with patch(
            "omniintelligence.runtime.dispatch_handler_pattern_learning"
            ".extract_all_patterns",
            return_value=extraction_output,
        ):
            await handler(envelope, context)

        # All 30 should be published (each via individual publish call)
        assert mock_kafka_producer.publish.call_count == 30

    @pytest.mark.unit
    def test_constants_values(self) -> None:
        """Validate constant values match expected caps."""
        assert MAX_PATTERNS_PER_SESSION == 50
        assert PUBLISH_BATCH_SIZE == 25


# =============================================================================
# Tests: Session Enrichment (_fetch_session_snapshot)
# =============================================================================


class TestFetchSessionSnapshot:
    """Validate session enrichment from PostgreSQL with fallback."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_session_snapshot_db_returns_data(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """DB returns agent_actions rows: snapshot built with files, tools, errors."""
        now = datetime.now(UTC)
        mock_repository.fetch = AsyncMock(
            side_effect=[
                # First call: agent_actions
                [
                    {
                        "action_type": "read",
                        "tool_name": "Read",
                        "file_path": "src/main.py",
                        "status": "success",
                        "error_message": None,
                        "created_at": now,
                    },
                    {
                        "action_type": "edit",
                        "tool_name": "Edit",
                        "file_path": "src/utils.py",
                        "status": "success",
                        "error_message": None,
                        "created_at": now,
                    },
                    {
                        "action_type": "read",
                        "tool_name": "Read",
                        "file_path": "src/broken.py",
                        "status": "error",
                        "error_message": "File not found",
                        "created_at": now,
                    },
                ],
                # Second call: workflow_steps
                [
                    {
                        "step_name": "analysis",
                        "status": "completed",
                        "error_message": None,
                        "started_at": now,
                        "completed_at": now,
                    },
                ],
            ]
        )

        snapshot = await _fetch_session_snapshot(
            repository=mock_repository,
            session_id="session-with-data",
            correlation_id=correlation_id,
        )

        assert snapshot.session_id == str(uuid5(NAMESPACE_URL, "session-with-data"))
        assert "src/main.py" in snapshot.files_accessed
        assert "src/utils.py" in snapshot.files_accessed
        assert "src/utils.py" in snapshot.files_modified
        assert "Read" in snapshot.tools_used
        assert "Edit" in snapshot.tools_used
        assert any("File not found" in e for e in snapshot.errors_encountered)
        assert snapshot.outcome == "success"
        assert snapshot.metadata["source"] == "postgresql"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_session_snapshot_db_returns_empty(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """No rows for session_id: synthetic fallback snapshot returned."""
        mock_repository.fetch = AsyncMock(return_value=[])

        snapshot = await _fetch_session_snapshot(
            repository=mock_repository,
            session_id="empty-session",
            correlation_id=correlation_id,
        )

        assert snapshot.session_id == str(uuid5(NAMESPACE_URL, "empty-session"))
        assert snapshot.metadata["source"] == "synthetic"
        assert snapshot.metadata["reason"] == "db_unavailable"
        assert snapshot.outcome == "unknown"
        assert snapshot.files_accessed == ()
        assert snapshot.files_modified == ()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_session_snapshot_db_error_returns_synthetic(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Repository raises: synthetic fallback returned (no crash)."""
        mock_repository.fetch = AsyncMock(
            side_effect=ConnectionError("DB connection refused"),
        )

        snapshot = await _fetch_session_snapshot(
            repository=mock_repository,
            session_id="error-session",
            correlation_id=correlation_id,
        )

        assert snapshot.session_id == str(uuid5(NAMESPACE_URL, "error-session"))
        assert snapshot.metadata["source"] == "synthetic"
        assert snapshot.metadata["reason"] == "db_unavailable"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_session_snapshot_db_timeout_returns_synthetic(
        self,
        correlation_id: UUID,
        mock_repository: MagicMock,
    ) -> None:
        """Repository raises TimeoutError: synthetic fallback returned."""
        mock_repository.fetch = AsyncMock(
            side_effect=TimeoutError("Query timed out"),
        )

        snapshot = await _fetch_session_snapshot(
            repository=mock_repository,
            session_id="timeout-session",
            correlation_id=correlation_id,
        )

        assert snapshot.session_id == str(uuid5(NAMESPACE_URL, "timeout-session"))
        assert snapshot.metadata["source"] == "synthetic"


# =============================================================================
# Tests: Insight-to-Event Transformer
# =============================================================================


class TestInsightTransformer:
    """Validate _transform_insights_to_pattern_events field mapping."""

    @pytest.mark.unit
    def test_insight_transformer_single_insight_produces_correct_fields(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """All required fields present in transformed event payload."""
        insight = _make_insight(
            insight_type=EnumInsightType.ERROR_PATTERN,
            description="Repeated FileNotFoundError in tests",
            confidence=0.9,
            evidence_files=("tests/test_main.py",),
            evidence_session_ids=("prev-session-1",),
            occurrence_count=5,
            working_directory="/workspace/project",
        )

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        assert len(events) == 1
        event = events[0]

        # Required fields
        assert "pattern_id" in event
        assert "signature" in event
        assert "signature_hash" in event
        assert "domain_id" in event
        assert "confidence" in event
        assert "version" in event
        assert "source_session_ids" in event
        assert "metadata" in event
        assert "correlation_id" in event
        assert "timestamp" in event
        assert "event_type" in event

        # Type checks
        assert isinstance(event["pattern_id"], str)
        assert isinstance(event["signature"], str)
        assert isinstance(event["signature_hash"], str)
        assert isinstance(event["confidence"], float)
        assert isinstance(event["version"], int)
        assert event["version"] == 1
        assert event["event_type"] == "PatternLearned"

    @pytest.mark.unit
    def test_insight_transformer_deterministic_signature_hash(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Same insight produces same signature_hash every time."""
        insight = _make_insight(
            insight_type=EnumInsightType.TOOL_USAGE_PATTERN,
            description="Frequent use of Read tool",
        )

        events_1 = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )
        events_2 = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        assert events_1[0]["signature_hash"] == events_2[0]["signature_hash"]

        # Verify it's the SHA256 of the expected signature
        expected_sig = f"{insight.insight_type.value}::{insight.description}"
        expected_hash = hashlib.sha256(expected_sig.encode("utf-8")).hexdigest()
        assert events_1[0]["signature_hash"] == expected_hash

    @pytest.mark.unit
    def test_insight_transformer_confidence_clamped_below(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Confidence below 0.5 is clamped to 0.5."""
        # ModelCodebaseInsight has ge=0.0 constraint, but the transformer
        # applies its own clamping to [0.5, 1.0]. Use a value just at 0.0.
        insight = _make_insight(confidence=0.0)

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        assert events[0]["confidence"] == 0.5

    @pytest.mark.unit
    def test_insight_transformer_confidence_clamped_above(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Confidence at 1.0 stays at 1.0 (max boundary)."""
        insight = _make_insight(confidence=1.0)

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        assert events[0]["confidence"] == 1.0

    @pytest.mark.unit
    def test_insight_transformer_domain_id_always_general(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """domain_id is always 'general' regardless of insight_type."""
        for insight_type in EnumInsightType:
            insight = _make_insight(
                insight_type=insight_type,
                description=f"Test pattern for {insight_type.value}",
            )

            events = _transform_insights_to_pattern_events(
                insights=[insight],
                session_id=sample_session_id,
                correlation_id=correlation_id,
            )

            assert events[0]["domain_id"] == "general", (
                f"domain_id should be 'general' for {insight_type.value}, "
                f"got {events[0]['domain_id']}"
            )

    @pytest.mark.unit
    def test_insight_transformer_insight_type_in_metadata(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """insight_type is stored in metadata for future taxonomy migration."""
        insight = _make_insight(
            insight_type=EnumInsightType.ARCHITECTURE_PATTERN,
        )

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["insight_type"] == EnumInsightType.ARCHITECTURE_PATTERN.value

    @pytest.mark.unit
    def test_insight_transformer_taxonomy_version_in_metadata(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """taxonomy_version is present and set to '1.0.0' in metadata."""
        insight = _make_insight()

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["taxonomy_version"] == "1.0.0"

    @pytest.mark.unit
    def test_insight_transformer_empty_evidence_session_ids(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Empty evidence_session_ids produces list with just current session_id."""
        insight = _make_insight(evidence_session_ids=())

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        source_ids = events[0]["source_session_ids"]
        assert isinstance(source_ids, list)
        assert len(source_ids) == 1
        assert source_ids[0] == str(uuid5(NAMESPACE_URL, sample_session_id))

    @pytest.mark.unit
    def test_insight_transformer_existing_evidence_session_ids_preserved(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Existing evidence_session_ids are preserved and current session appended."""
        insight = _make_insight(
            evidence_session_ids=("prev-session-a", "prev-session-b"),
        )

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        source_ids = events[0]["source_session_ids"]
        assert str(uuid5(NAMESPACE_URL, "prev-session-a")) in source_ids
        assert str(uuid5(NAMESPACE_URL, "prev-session-b")) in source_ids
        assert str(uuid5(NAMESPACE_URL, sample_session_id)) in source_ids

    @pytest.mark.unit
    def test_insight_transformer_current_session_not_duplicated(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """If current session_id is already in evidence, it is not duplicated."""
        insight = _make_insight(
            evidence_session_ids=(sample_session_id,),
        )

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        source_ids = events[0]["source_session_ids"]
        deterministic_id = str(uuid5(NAMESPACE_URL, sample_session_id))
        assert source_ids.count(deterministic_id) == 1

    @pytest.mark.unit
    def test_insight_transformer_evidence_files_in_metadata(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Evidence files are included in metadata when present."""
        insight = _make_insight(
            evidence_files=("src/main.py", "src/utils.py"),
        )

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["evidence_files"] == ["src/main.py", "src/utils.py"]

    @pytest.mark.unit
    def test_insight_transformer_working_directory_in_metadata(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Working directory is included in metadata when present."""
        insight = _make_insight(working_directory="/workspace/myproject")

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["working_directory"] == "/workspace/myproject"

    @pytest.mark.unit
    def test_insight_transformer_no_evidence_files_omitted(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Empty evidence_files: key not present in metadata."""
        insight = _make_insight(evidence_files=())

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert "evidence_files" not in metadata

    @pytest.mark.unit
    def test_insight_transformer_no_working_directory_omitted(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """None working_directory: key not present in metadata."""
        insight = _make_insight(working_directory=None)

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert "working_directory" not in metadata

    @pytest.mark.unit
    def test_insight_transformer_correlation_id_threaded(
        self,
        sample_session_id: str,
    ) -> None:
        """Correlation ID from input appears in output events."""
        cid = UUID("deadbeef-dead-beef-dead-beefdeadbeef")
        insight = _make_insight()

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=cid,
        )

        assert events[0]["correlation_id"] == str(cid)

    @pytest.mark.unit
    def test_insight_transformer_empty_insights_returns_empty_list(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Empty insights list produces empty events list."""
        events = _transform_insights_to_pattern_events(
            insights=[],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        assert events == []

    @pytest.mark.unit
    def test_insight_transformer_occurrence_count_in_metadata(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """occurrence_count from insight is included in metadata."""
        insight = _make_insight(occurrence_count=7)

        events = _transform_insights_to_pattern_events(
            insights=[insight],
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        metadata = events[0]["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["occurrence_count"] == 7

    @pytest.mark.unit
    def test_insight_transformer_multiple_insights_produce_multiple_events(
        self,
        correlation_id: UUID,
        sample_session_id: str,
    ) -> None:
        """Multiple insights produce one event per insight."""
        insights = [
            _make_insight(
                description=f"Pattern {i}",
                insight_id=f"multi-{i}",
            )
            for i in range(5)
        ]

        events = _transform_insights_to_pattern_events(
            insights=insights,
            session_id=sample_session_id,
            correlation_id=correlation_id,
        )

        assert len(events) == 5
        # Each event should have a unique pattern_id
        pattern_ids = [e["pattern_id"] for e in events]
        assert len(set(pattern_ids)) == 5
