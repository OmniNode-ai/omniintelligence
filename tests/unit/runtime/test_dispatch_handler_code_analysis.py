# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for code analysis dispatch handler (OMN-6969).

Verifies that:
- Handler parses ModelCodeAnalysisRequestPayload correctly
- Quality scoring produces reasonable results
- Completed events are published on success
- Failed events are published on parse errors
- Handler registered in dispatch engine
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from omnibase_core.models.core.model_envelope_metadata import ModelEnvelopeMetadata
from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)
from omniintelligence.runtime.dispatch_handler_code_analysis import (
    DISPATCH_ALIAS_CODE_ANALYSIS,
    TOPIC_PATTERN_DISCOVERED,
    _build_pattern_discovered_events,
    _extract_findings,
    _heuristic_quality_score,
    create_code_analysis_dispatch_handler,
)


def _make_envelope(payload: dict[str, object]) -> ModelEventEnvelope[object]:
    """Create a test envelope wrapping the given payload."""
    return ModelEventEnvelope(
        event_type="code-analysis-requested",
        metadata=ModelEnvelopeMetadata(
            source="test",
            version="1",
        ),
        payload=payload,
    )


def _make_context() -> MagicMock:
    """Create a mock handler context."""
    ctx = MagicMock()
    ctx.correlation_id = uuid4()
    return ctx


class TestHeuristicQualityScore:
    """Tests for the heuristic quality scoring function."""

    @pytest.mark.unit
    def test_empty_content_has_issues(self) -> None:
        """Empty file content should produce an issue."""
        result = _heuristic_quality_score(
            "", "python", EnumAnalysisOperationType.QUALITY_ASSESSMENT
        )
        assert result.issues_count >= 1
        assert result.quality_score >= 0.0
        assert result.quality_score <= 1.0

    @pytest.mark.unit
    def test_clean_code_scores_high(self) -> None:
        """Clean Python code should score well."""
        code = """def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
"""
        result = _heuristic_quality_score(
            code, "python", EnumAnalysisOperationType.QUALITY_ASSESSMENT
        )
        assert result.quality_score > 0.5
        assert result.issues_count == 0
        assert result.processing_time_ms >= 0

    @pytest.mark.unit
    def test_code_with_issues_scores_lower(self) -> None:
        """Code with anti-patterns should have issues flagged."""
        code = """import *
# TODO fix this later
try:
    x = 1
except:
    pass
print("debug output")
"""
        result = _heuristic_quality_score(
            code, "python", EnumAnalysisOperationType.QUALITY_ASSESSMENT
        )
        assert result.issues_count > 0
        assert result.operation_type == EnumAnalysisOperationType.QUALITY_ASSESSMENT

    @pytest.mark.unit
    def test_complexity_score_calculated(self) -> None:
        """Deeply nested code should have lower complexity score."""
        deep_code = "\n".join(
            [f"{'    ' * i}if True:" for i in range(8)] + ["        pass"]
        )
        result = _heuristic_quality_score(
            deep_code, "python", EnumAnalysisOperationType.QUALITY_ASSESSMENT
        )
        assert result.complexity_score is not None
        assert result.complexity_score < 1.0

    @pytest.mark.unit
    def test_maintainability_score_is_average(self) -> None:
        """Maintainability should be average of quality and complexity."""
        result = _heuristic_quality_score(
            "x = 1\n", "python", EnumAnalysisOperationType.QUALITY_ASSESSMENT
        )
        assert result.maintainability_score is not None
        expected = round((result.quality_score + (result.complexity_score or 0)) / 2, 3)
        assert abs(result.maintainability_score - expected) < 0.01


class TestCodeAnalysisDispatchHandler:
    """Tests for the dispatch handler factory and handler execution."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_successful_analysis(self) -> None:
        """Handler should produce completed event for valid request."""
        mock_producer = AsyncMock()
        mock_producer.publish = AsyncMock()

        handler = create_code_analysis_dispatch_handler(
            kafka_producer=mock_producer,
        )

        correlation_id = uuid4()
        envelope = _make_envelope(
            {
                "correlation_id": str(correlation_id),
                "source_path": "src/module/foo.py",
                "content": "def foo():\n    return 42\n",
                "operation_type": "quality_assessment",
                "language": "python",
            }
        )

        result = await handler(envelope, _make_context())
        assert result == "ok"

        # Should have published a completed event
        mock_producer.publish.assert_called_once()
        call_kwargs = mock_producer.publish.call_args
        assert "code-analysis-completed" in call_kwargs.kwargs.get(
            "topic", call_kwargs[1].get("topic", "")
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_payload_publishes_failure(self) -> None:
        """Handler should produce failed event for invalid payload."""
        mock_producer = AsyncMock()
        mock_producer.publish = AsyncMock()

        handler = create_code_analysis_dispatch_handler(
            kafka_producer=mock_producer,
        )

        # Missing required 'operation_type' field
        envelope = _make_envelope({"content": "x = 1"})

        result = await handler(envelope, _make_context())
        assert result == "error:invalid_request"

        # Should have published a failed event
        mock_producer.publish.assert_called_once()
        call_kwargs = mock_producer.publish.call_args
        assert "code-analysis-failed" in call_kwargs.kwargs.get(
            "topic", call_kwargs[1].get("topic", "")
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_producer_graceful_degradation(self) -> None:
        """Handler should work without a Kafka producer."""
        handler = create_code_analysis_dispatch_handler(
            kafka_producer=None,
        )

        envelope = _make_envelope(
            {
                "source_path": "test.py",
                "content": "pass\n",
                "operation_type": "quality_assessment",
                "language": "python",
            }
        )

        result = await handler(envelope, _make_context())
        assert result == "ok"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_dict_payload_raises(self) -> None:
        """Non-dict payload should raise ValueError."""
        handler = create_code_analysis_dispatch_handler()

        envelope = ModelEventEnvelope(
            event_type="code-analysis-requested",
            metadata=ModelEnvelopeMetadata(source="test", version="1"),
            payload="not a dict",  # type: ignore[arg-type]
        )

        with pytest.raises(ValueError, match="Unexpected payload type"):
            await handler(envelope, _make_context())

    @pytest.mark.unit
    def test_dispatch_alias_format(self) -> None:
        """Dispatch alias should use .commands. format for the engine."""
        assert ".commands." in DISPATCH_ALIAS_CODE_ANALYSIS
        assert "code-analysis" in DISPATCH_ALIAS_CODE_ANALYSIS


class _FakeEnrichmentResult:
    """Minimal stand-in for ContractEnrichmentResult."""

    def __init__(self, summary_markdown: str) -> None:
        self.summary_markdown = summary_markdown
        self.model_used = "qwen2.5-coder-14b"
        self.latency_ms = 12.5


class _FakeLLMAdapter:
    """Fake adapter returning a scripted markdown summary."""

    def __init__(self, summary: str | None = None, raise_on_call: bool = False) -> None:
        self._summary = summary or (
            "## Affected Functions / Methods\n"
            "- foo: returns a literal\n\n"
            "## Potential Issues\n"
            "- Missing type hints on foo\n"
            "- Bare return without docstring\n\n"
            "## Recommendations\n"
            "- Add a type hint for the return value\n\n"
            "## Summary\n"
            "Trivial change, low risk.\n"
        )
        self._raise = raise_on_call
        self.calls: list[tuple[str, str]] = []

    async def enrich(self, prompt: str, context: str) -> _FakeEnrichmentResult:
        self.calls.append((prompt, context))
        if self._raise:
            raise RuntimeError("boom")
        return _FakeEnrichmentResult(self._summary)


class TestFindingsExtraction:
    """Tests for _extract_findings markdown parser."""

    @pytest.mark.unit
    def test_issues_and_recommendations_split(self) -> None:
        markdown = (
            "## Potential Issues\n- one\n- two\n\n## Recommendations\n- use logging\n"
        )
        issues, recs = _extract_findings(markdown)
        assert issues == ["one", "two"]
        assert recs == ["use logging"]

    @pytest.mark.unit
    def test_no_sections_treats_bullets_as_issues(self) -> None:
        issues, recs = _extract_findings("- lone bullet\n- second\n")
        assert issues == ["lone bullet", "second"]
        assert recs == []


class TestLLMDispatchHandler:
    """Tests for the LLM-backed code analysis path (OMN-6967)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_llm_success_publishes_completed_and_patterns(self) -> None:
        mock_producer = AsyncMock()
        mock_producer.publish = AsyncMock()
        adapter = _FakeLLMAdapter()

        handler = create_code_analysis_dispatch_handler(
            kafka_producer=mock_producer,
            llm_adapter=adapter,
        )

        envelope = _make_envelope(
            {
                "correlation_id": str(uuid4()),
                "source_path": "src/foo.py",
                "content": "def foo():\n    return 1\n",
                "operation_type": "quality_assessment",
                "language": "python",
            }
        )

        result = await handler(envelope, _make_context())
        assert result == "ok"
        assert len(adapter.calls) == 1

        topics = [
            call.kwargs.get("topic") for call in mock_producer.publish.call_args_list
        ]
        # First publish is the completed event
        assert any("code-analysis-completed" in t for t in topics if t)
        # Remaining publishes are pattern.discovered events
        pattern_calls = [t for t in topics if t == TOPIC_PATTERN_DISCOVERED]
        assert len(pattern_calls) >= 1

        # Assert pattern_type metadata is stamped
        pattern_values = [
            call.kwargs["value"]
            for call in mock_producer.publish.call_args_list
            if call.kwargs.get("topic") == TOPIC_PATTERN_DISCOVERED
        ]
        for value in pattern_values:
            assert value["metadata"]["pattern_type"] == "code_analysis_pattern"
            assert value["domain"] == "code_analysis"
            assert value["confidence"] >= 0.5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_heuristic(self) -> None:
        mock_producer = AsyncMock()
        mock_producer.publish = AsyncMock()
        adapter = _FakeLLMAdapter(raise_on_call=True)

        handler = create_code_analysis_dispatch_handler(
            kafka_producer=mock_producer,
            llm_adapter=adapter,
        )

        envelope = _make_envelope(
            {
                "source_path": "src/foo.py",
                "content": "def foo():\n    return 1\n",
                "operation_type": "quality_assessment",
                "language": "python",
            }
        )

        result = await handler(envelope, _make_context())
        assert result == "ok"
        # Adapter was called and raised
        assert len(adapter.calls) == 1
        # Completed event still published
        topics = [
            call.kwargs.get("topic") for call in mock_producer.publish.call_args_list
        ]
        assert any("code-analysis-completed" in t for t in topics if t)
        # No pattern.discovered events on the heuristic fallback path
        pattern_calls = [t for t in topics if t == TOPIC_PATTERN_DISCOVERED]
        assert pattern_calls == []

    @pytest.mark.unit
    def test_build_pattern_events_shape(self) -> None:
        from uuid import uuid4

        events = _build_pattern_discovered_events(
            issues=["missing type hint"],
            recommendations=["use logging"],
            source_path="src/foo.py",
            language="python",
            correlation_id=uuid4(),
            session_id=uuid4(),
        )
        assert len(events) == 2
        for evt in events:
            assert evt["event_type"] == "PatternDiscovered"
            assert evt["source_system"] == "omniintelligence.code_analysis"
            assert evt["metadata"]["pattern_type"] == "code_analysis_pattern"
            assert len(evt["signature_hash"]) == 64  # SHA-256 hex
