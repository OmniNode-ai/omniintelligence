"""Unit tests for the pattern compliance compute handler.

Tests the handler orchestration function that coordinates prompt building,
LLM inference, and response parsing. Uses a mock LLM client.

Includes DLQ routing tests for verifying that failed compliance evaluations
are routed to the Dead Letter Queue when a kafka_producer is available.

Ticket: OMN-2256
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

import pytest

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
    COMPLIANCE_PROMPT_VERSION,
    DLQ_TOPIC,
    ProtocolLlmClient,
    handle_evaluate_compliance,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models import (
    ModelApplicablePattern,
    ModelComplianceRequest,
)
from omniintelligence.protocols import ProtocolKafkaPublisher


def _make_pattern(
    pattern_id: str = "P001",
    signature: str = "Use frozen Pydantic models",
    domain: str = "onex",
    confidence: float = 0.9,
) -> ModelApplicablePattern:
    """Helper to create test patterns."""
    return ModelApplicablePattern(
        pattern_id=pattern_id,
        pattern_signature=signature,
        domain_id=domain,
        confidence=confidence,
    )


_TEST_CORRELATION_ID = UUID("12345678-1234-5678-1234-567812345678")


def _make_request(
    content: str = "class Foo: pass",
    language: str = "python",
    patterns: list[ModelApplicablePattern] | None = None,
    correlation_id: UUID = _TEST_CORRELATION_ID,
) -> ModelComplianceRequest:
    """Helper to create test requests."""
    if patterns is None:
        patterns = [_make_pattern()]
    return ModelComplianceRequest(
        correlation_id=correlation_id,
        source_path="test.py",
        content=content,
        language=language,
        applicable_patterns=patterns,
    )


class MockLlmClient:
    """Mock LLM client for testing."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0
        self.last_messages: list[dict[str, str]] = []
        self.last_model: str = ""
        assert isinstance(self, ProtocolLlmClient)

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        self.call_count += 1
        self.last_messages = messages
        self.last_model = model
        return self._response


class MockLlmClientError:
    """Mock LLM client that raises an error."""

    def __init__(self) -> None:
        assert isinstance(self, ProtocolLlmClient)

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        raise ConnectionError("LLM service unavailable")


class TestHandleEvaluateCompliance:
    """Tests for handle_evaluate_compliance."""

    @pytest.mark.asyncio
    async def test_compliant_code_returns_success(self) -> None:
        """Fully compliant code should return success with no violations."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.95,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.success is True
        assert result.compliant is True
        assert result.violations == []
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_non_compliant_code_returns_violations(self) -> None:
        """Non-compliant code should return violations."""
        llm_response = json.dumps(
            {
                "compliant": False,
                "confidence": 0.85,
                "violations": [
                    {
                        "pattern_id": "P001",
                        "description": "Model is not frozen",
                        "severity": "major",
                        "line_reference": "line 1",
                    }
                ],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request(
            content="class Foo(BaseModel): pass",
            patterns=[_make_pattern(pattern_id="P001", signature="Frozen models")],
        )

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.success is True
        assert result.compliant is False
        assert len(result.violations) == 1
        assert result.violations[0].pattern_id == "P001"
        assert result.violations[0].description == "Model is not frozen"
        assert result.violations[0].severity == "major"
        assert result.violations[0].line_reference == "line 1"
        assert result.violations[0].pattern_signature == "Frozen models"

    @pytest.mark.asyncio
    async def test_metadata_includes_prompt_version(self) -> None:
        """Output metadata must include compliance_prompt_version."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.compliance_prompt_version == COMPLIANCE_PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_metadata_includes_model_used(self) -> None:
        """Output metadata must include the model identifier used."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(
            request, llm_client=client, model="test-model"
        )

        assert result.metadata is not None
        assert result.metadata.model_used == "test-model"

    @pytest.mark.asyncio
    async def test_metadata_includes_processing_time(self) -> None:
        """Output metadata must include processing time."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.processing_time_ms is not None
        assert result.metadata.processing_time_ms >= 0.0

    @pytest.mark.asyncio
    async def test_metadata_includes_patterns_checked(self) -> None:
        """Output metadata must include count of patterns checked."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        patterns = [
            _make_pattern(pattern_id="P1"),
            _make_pattern(pattern_id="P2"),
            _make_pattern(pattern_id="P3"),
        ]
        request = _make_request(patterns=patterns)

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.patterns_checked == 3

    @pytest.mark.asyncio
    async def test_llm_receives_system_and_user_messages(self) -> None:
        """LLM client should receive system and user messages."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        await handle_evaluate_compliance(request, llm_client=client)

        assert client.call_count == 1
        assert len(client.last_messages) == 2
        assert client.last_messages[0]["role"] == "system"
        assert client.last_messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_llm_error_returns_structured_error(self) -> None:
        """LLM errors should be caught and returned as structured error output."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.success is False
        assert result.compliant is False
        assert result.metadata is not None
        assert result.metadata.status == "llm_error"
        assert "LLM inference failed" in (result.metadata.message or "")

    @pytest.mark.asyncio
    async def test_parse_error_returns_structured_error(self) -> None:
        """Unparseable LLM responses should return structured error output."""
        client = MockLlmClient("this is not json")
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.success is False
        assert result.compliant is False
        assert result.metadata is not None
        assert result.metadata.status == "parse_error"

    @pytest.mark.asyncio
    async def test_prompt_version_in_error_output(self) -> None:
        """Even error outputs must include prompt version in metadata."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.compliance_prompt_version == COMPLIANCE_PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_custom_model_passed_to_llm(self) -> None:
        """Custom model should be forwarded to the LLM client."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        await handle_evaluate_compliance(
            request, llm_client=client, model="custom-model-v2"
        )

        assert client.last_model == "custom-model-v2"

    @pytest.mark.asyncio
    async def test_correlation_id_in_metadata(self) -> None:
        """Correlation ID from input must be propagated to output metadata."""
        llm_response = json.dumps(
            {
                "compliant": True,
                "confidence": 0.9,
                "violations": [],
            }
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.correlation_id == _TEST_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_correlation_id_in_error_metadata(self) -> None:
        """Correlation ID must be present in error output metadata."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.correlation_id == _TEST_CORRELATION_ID


class TestCorrelationIdPropagation:
    """Tests that correlation_id is threaded through all code paths."""

    _OVERRIDE_CID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    @pytest.mark.asyncio
    async def test_explicit_correlation_id_overrides_input(self) -> None:
        """Explicit correlation_id kwarg should override input_data.correlation_id."""
        llm_response = json.dumps(
            {"compliant": True, "confidence": 0.9, "violations": []}
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(
            request,
            llm_client=client,
            correlation_id=self._OVERRIDE_CID,
        )

        assert result.metadata is not None
        assert result.metadata.correlation_id == self._OVERRIDE_CID
        assert result.metadata.correlation_id != _TEST_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_none_correlation_id_falls_back_to_input(self) -> None:
        """When correlation_id kwarg is None, input_data.correlation_id is used."""
        llm_response = json.dumps(
            {"compliant": True, "confidence": 0.9, "violations": []}
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        result = await handle_evaluate_compliance(
            request,
            llm_client=client,
            correlation_id=None,
        )

        assert result.metadata is not None
        assert result.metadata.correlation_id == _TEST_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_explicit_cid_in_llm_error_metadata(self) -> None:
        """Explicit correlation_id should appear in LLM error output metadata."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_evaluate_compliance(
            request,
            llm_client=client,
            correlation_id=self._OVERRIDE_CID,
        )

        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.correlation_id == self._OVERRIDE_CID

    @pytest.mark.asyncio
    async def test_explicit_cid_in_parse_error_metadata(self) -> None:
        """Explicit correlation_id should appear in parse error output metadata."""
        client = MockLlmClient("this is not json")
        request = _make_request()

        result = await handle_evaluate_compliance(
            request,
            llm_client=client,
            correlation_id=self._OVERRIDE_CID,
        )

        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "parse_error"
        assert result.metadata.correlation_id == self._OVERRIDE_CID

    @pytest.mark.asyncio
    async def test_correlation_id_in_parse_error_metadata_default(self) -> None:
        """Correlation ID from input should appear in parse error metadata."""
        client = MockLlmClient("this is not json")
        request = _make_request()

        result = await handle_evaluate_compliance(request, llm_client=client)

        assert result.metadata is not None
        assert result.metadata.status == "parse_error"
        assert result.metadata.correlation_id == _TEST_CORRELATION_ID

    @pytest.mark.asyncio
    async def test_logger_includes_correlation_id_on_success(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logger calls should include correlation_id in extra dict on success."""
        llm_response = json.dumps(
            {"compliant": True, "confidence": 0.9, "violations": []}
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        with caplog.at_level(logging.DEBUG):
            await handle_evaluate_compliance(request, llm_client=client)

        cid_str = str(_TEST_CORRELATION_ID)
        debug_messages = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_messages) >= 1, "Expected at least one debug log record"
        for record in debug_messages:
            assert hasattr(record, "correlation_id"), (
                f"Log record missing correlation_id: {record.message}"
            )
            assert record.correlation_id == cid_str

    @pytest.mark.asyncio
    async def test_logger_includes_correlation_id_on_llm_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logger calls should include correlation_id on LLM errors."""
        client = MockLlmClientError()
        request = _make_request()

        with caplog.at_level(logging.DEBUG):
            await handle_evaluate_compliance(request, llm_client=client)

        cid_str = str(_TEST_CORRELATION_ID)
        warning_messages = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_messages) >= 1, "Expected at least one warning log record"
        for record in warning_messages:
            assert hasattr(record, "correlation_id"), (
                f"Log record missing correlation_id: {record.message}"
            )
            assert record.correlation_id == cid_str

    @pytest.mark.asyncio
    async def test_logger_uses_overridden_correlation_id(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Logger should use the explicit correlation_id, not input_data's."""
        llm_response = json.dumps(
            {"compliant": True, "confidence": 0.9, "violations": []}
        )
        client = MockLlmClient(llm_response)
        request = _make_request()

        with caplog.at_level(logging.DEBUG):
            await handle_evaluate_compliance(
                request,
                llm_client=client,
                correlation_id=self._OVERRIDE_CID,
            )

        override_str = str(self._OVERRIDE_CID)
        debug_messages = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_messages) >= 1
        for record in debug_messages:
            assert hasattr(record, "correlation_id")
            assert record.correlation_id == override_str


class TestMockProtocolConformance:
    """Verify that test mocks conform to the ProtocolLlmClient protocol."""

    def test_mock_llm_client_conforms_to_protocol(self) -> None:
        """MockLlmClient must satisfy ProtocolLlmClient at runtime."""
        client = MockLlmClient("test")
        assert isinstance(client, ProtocolLlmClient)

    def test_mock_llm_client_error_conforms_to_protocol(self) -> None:
        """MockLlmClientError must satisfy ProtocolLlmClient at runtime."""
        client = MockLlmClientError()
        assert isinstance(client, ProtocolLlmClient)


# =============================================================================
# Mock Kafka Publisher for DLQ Tests
# =============================================================================


class MockKafkaPublisher:
    """Mock Kafka publisher that records publishes."""

    def __init__(self) -> None:
        self.published: list[dict[str, object]] = []
        assert isinstance(self, ProtocolKafkaPublisher)

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
    ) -> None:
        self.published.append({"topic": topic, "key": key, "value": value})


class MockKafkaPublisherError:
    """Mock Kafka publisher that raises on publish (for testing DLQ failure)."""

    def __init__(self) -> None:
        assert isinstance(self, ProtocolKafkaPublisher)

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
    ) -> None:
        raise ConnectionError("Kafka connection lost")


# =============================================================================
# DLQ Routing Tests
# =============================================================================


class TestDlqRouting:
    """Tests for Dead Letter Queue routing on failed compliance evaluations."""

    @pytest.mark.asyncio
    async def test_no_dlq_when_producer_is_none(self) -> None:
        """Handler works perfectly with kafka_producer=None (no regression)."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_evaluate_compliance(
            request, llm_client=client, kafka_producer=None
        )

        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "llm_error"

    @pytest.mark.asyncio
    async def test_dlq_routing_on_llm_error(self) -> None:
        """DLQ routing is called when LLM fails and producer is available."""
        client = MockLlmClientError()
        producer = MockKafkaPublisher()
        request = _make_request()

        result = await handle_evaluate_compliance(
            request, llm_client=client, kafka_producer=producer
        )

        # Handler still returns structured error
        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "llm_error"

        # DLQ message was published
        assert len(producer.published) == 1
        dlq_msg = producer.published[0]
        assert dlq_msg["topic"] == DLQ_TOPIC
        assert dlq_msg["key"] == str(_TEST_CORRELATION_ID)

        # DLQ payload contains expected fields
        payload = dlq_msg["value"]
        assert isinstance(payload, dict)
        assert payload["correlation_id"] == str(_TEST_CORRELATION_ID)
        assert payload["error_status"] == "llm_error"
        assert payload["source_path"] == "test.py"
        assert payload["language"] == "python"
        assert payload["service"] == "omniintelligence"
        assert payload["node"] == "node_pattern_compliance_effect"
        assert "error_message" in payload
        assert "error_timestamp" in payload

    @pytest.mark.asyncio
    async def test_dlq_routing_on_parse_error(self) -> None:
        """DLQ routing is called when parse fails and producer is available."""
        client = MockLlmClient("this is not json")
        producer = MockKafkaPublisher()
        request = _make_request()

        result = await handle_evaluate_compliance(
            request, llm_client=client, kafka_producer=producer
        )

        # Handler still returns structured error
        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "parse_error"

        # DLQ message was published
        assert len(producer.published) == 1
        dlq_msg = producer.published[0]
        assert dlq_msg["topic"] == DLQ_TOPIC
        assert dlq_msg["key"] == str(_TEST_CORRELATION_ID)

        # DLQ payload contains expected fields
        payload = dlq_msg["value"]
        assert isinstance(payload, dict)
        assert payload["correlation_id"] == str(_TEST_CORRELATION_ID)
        assert payload["error_status"] == "parse_error"

    @pytest.mark.asyncio
    async def test_dlq_publish_failure_does_not_propagate(self) -> None:
        """DLQ publish failure is caught and logged, handler still returns error."""
        client = MockLlmClientError()
        producer = MockKafkaPublisherError()
        request = _make_request()

        # Should NOT raise despite Kafka being broken
        result = await handle_evaluate_compliance(
            request, llm_client=client, kafka_producer=producer
        )

        # Handler still returns structured error normally
        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "llm_error"
        assert "LLM inference failed" in (result.metadata.message or "")

    @pytest.mark.asyncio
    async def test_dlq_publish_failure_on_parse_error_does_not_propagate(
        self,
    ) -> None:
        """DLQ publish failure on parse error is caught, handler returns error."""
        client = MockLlmClient("this is not json")
        producer = MockKafkaPublisherError()
        request = _make_request()

        # Should NOT raise despite Kafka being broken
        result = await handle_evaluate_compliance(
            request, llm_client=client, kafka_producer=producer
        )

        assert result.success is False
        assert result.metadata is not None
        assert result.metadata.status == "parse_error"

    @pytest.mark.asyncio
    async def test_no_dlq_on_success(self) -> None:
        """Successful evaluations should NOT route to DLQ."""
        llm_response = json.dumps(
            {"compliant": True, "confidence": 0.9, "violations": []}
        )
        client = MockLlmClient(llm_response)
        producer = MockKafkaPublisher()
        request = _make_request()

        result = await handle_evaluate_compliance(
            request, llm_client=client, kafka_producer=producer
        )

        assert result.success is True
        assert len(producer.published) == 0

    @pytest.mark.asyncio
    async def test_dlq_correlation_id_matches_override(self) -> None:
        """DLQ payload should use explicit correlation_id when provided."""
        override_cid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        client = MockLlmClientError()
        producer = MockKafkaPublisher()
        request = _make_request()

        await handle_evaluate_compliance(
            request,
            llm_client=client,
            kafka_producer=producer,
            correlation_id=override_cid,
        )

        assert len(producer.published) == 1
        dlq_msg = producer.published[0]
        assert dlq_msg["key"] == str(override_cid)
        payload = dlq_msg["value"]
        assert isinstance(payload, dict)
        assert payload["correlation_id"] == str(override_cid)

    @pytest.mark.asyncio
    async def test_dlq_publish_failure_logged_as_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """DLQ publish failure should be logged at WARNING level."""
        client = MockLlmClientError()
        producer = MockKafkaPublisherError()
        request = _make_request()

        with caplog.at_level(logging.WARNING):
            await handle_evaluate_compliance(
                request, llm_client=client, kafka_producer=producer
            )

        dlq_warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "DLQ publish failed" in r.message
        ]
        assert len(dlq_warnings) >= 1, "Expected DLQ failure warning log"


class TestMockKafkaProtocolConformance:
    """Verify that test Kafka mocks conform to ProtocolKafkaPublisher."""

    def test_mock_kafka_publisher_conforms_to_protocol(self) -> None:
        """MockKafkaPublisher must satisfy ProtocolKafkaPublisher at runtime."""
        publisher = MockKafkaPublisher()
        assert isinstance(publisher, ProtocolKafkaPublisher)

    def test_mock_kafka_publisher_error_conforms_to_protocol(self) -> None:
        """MockKafkaPublisherError must satisfy ProtocolKafkaPublisher at runtime."""
        publisher = MockKafkaPublisherError()
        assert isinstance(publisher, ProtocolKafkaPublisher)
