"""Unit tests for the pattern compliance compute handler.

Tests the handler orchestration function that coordinates prompt building,
LLM inference, and response parsing. Uses a mock LLM client.

Ticket: OMN-2256
"""

from __future__ import annotations

import json
from uuid import UUID

import pytest

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_pattern_compliance_compute.handlers import (
    COMPLIANCE_PROMPT_VERSION,
    ProtocolLlmClient,
    handle_pattern_compliance_compute,
)
from omniintelligence.nodes.node_pattern_compliance_compute.models import (
    ModelApplicablePattern,
    ModelComplianceRequest,
)


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


class TestHandlePatternComplianceCompute:
    """Tests for handle_pattern_compliance_compute."""

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

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        result = await handle_pattern_compliance_compute(
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

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        await handle_pattern_compliance_compute(request, llm_client=client)

        assert client.call_count == 1
        assert len(client.last_messages) == 2
        assert client.last_messages[0]["role"] == "system"
        assert client.last_messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_llm_error_returns_structured_error(self) -> None:
        """LLM errors should be caught and returned as structured error output."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        result = await handle_pattern_compliance_compute(request, llm_client=client)

        assert result.success is False
        assert result.compliant is False
        assert result.metadata is not None
        assert result.metadata.status == "parse_error"

    @pytest.mark.asyncio
    async def test_prompt_version_in_error_output(self) -> None:
        """Even error outputs must include prompt version in metadata."""
        client = MockLlmClientError()
        request = _make_request()

        result = await handle_pattern_compliance_compute(request, llm_client=client)

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

        await handle_pattern_compliance_compute(
            request, llm_client=client, model="custom-model-v2"
        )

        assert client.last_model == "custom-model-v2"
