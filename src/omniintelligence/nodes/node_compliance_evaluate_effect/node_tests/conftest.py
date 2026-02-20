# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Shared fixtures for node_compliance_evaluate_effect tests.

Provides mock implementations of ProtocolLlmClient and ProtocolKafkaPublisher,
plus helpers for building test payloads.

Ticket: OMN-2339
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

import pytest

from omniintelligence.nodes.node_compliance_evaluate_effect.models import (
    ModelApplicablePatternPayload,
    ModelComplianceEvaluateCommand,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ProtocolLlmClient,
)
from omniintelligence.protocols import ProtocolKafkaPublisher

# =============================================================================
# Fixed identifiers for deterministic tests
# =============================================================================

FIXED_CORRELATION_ID: UUID = UUID("12345678-1234-5678-1234-567812345678")
# sha256("class Foo: pass") — recompute if the literal changes.
# Verified by test_fixed_content_sha256_matches_hash() in test_handler_compliance_evaluate.py.
FIXED_CONTENT_SHA256: str = "62317e7166ae196fbee81c56aeedfed1294bae41544e57ee229c939c5c970c6f"  # pragma: allowlist secret

# =============================================================================
# Mock implementations
# =============================================================================


class MockLlmClient:
    """Mock LLM client that returns a configurable response."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count: int = 0
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
    """Mock LLM client that always raises an error."""

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
        raise RuntimeError("LLM inference failed: connection refused")


class MockKafkaProducer:
    """Mock Kafka producer that records publishes."""

    def __init__(self) -> None:
        self.published: list[dict[str, object]] = []
        self.simulate_error: Exception | None = None
        assert isinstance(self, ProtocolKafkaPublisher)

    async def publish(
        self,
        topic: str,
        key: str,
        value: dict[str, object],
    ) -> None:
        if self.simulate_error is not None:
            raise self.simulate_error
        self.published.append({"topic": topic, "key": key, "value": value})


# =============================================================================
# Helpers
# =============================================================================


def sha256_of(content: str) -> str:
    """Return the lowercase SHA-256 hex digest of a UTF-8 encoded string."""
    return hashlib.sha256(content.encode()).hexdigest()


def _compliant_llm_response() -> str:
    """Return a JSON-serialized compliant LLM response."""
    return json.dumps({"compliant": True, "confidence": 0.95, "violations": []})


def _violating_llm_response(
    pattern_id: str = "P001",
    description: str = "Code does not use frozen Pydantic models",
    severity: str = "major",
) -> str:
    """Return a JSON-serialized violating LLM response."""
    return json.dumps(
        {
            "compliant": False,
            "confidence": 0.85,
            "violations": [
                {
                    "pattern_id": pattern_id,
                    "description": description,
                    "severity": severity,
                    "line_reference": "line 5",
                }
            ],
        }
    )


def _make_pattern(
    pattern_id: str = "P001",
    signature: str = "Use frozen Pydantic models",
    domain: str = "onex",
    confidence: float = 0.9,
) -> ModelApplicablePatternPayload:
    return ModelApplicablePatternPayload(
        pattern_id=pattern_id,
        pattern_signature=signature,
        domain_id=domain,
        confidence=confidence,
    )


def _make_command(
    content: str = "class Foo: pass",
    language: str = "python",
    patterns: list[ModelApplicablePatternPayload] | None = None,
    correlation_id: UUID = FIXED_CORRELATION_ID,
    content_sha256: str = FIXED_CONTENT_SHA256,
    source_path: str = "src/foo.py",
    session_id: str | None = None,
) -> ModelComplianceEvaluateCommand:
    if patterns is None:
        patterns = [_make_pattern()]
    return ModelComplianceEvaluateCommand(
        correlation_id=correlation_id,
        source_path=source_path,
        content=content,
        content_sha256=content_sha256,
        language=language,
        applicable_patterns=patterns,
        session_id=session_id,
    )


# =============================================================================
# Pytest fixtures
# =============================================================================


@pytest.fixture
def sample_correlation_id() -> UUID:
    return FIXED_CORRELATION_ID


@pytest.fixture
def sample_command() -> ModelComplianceEvaluateCommand:
    return _make_command()


@pytest.fixture
def compliant_llm_client() -> MockLlmClient:
    return MockLlmClient(_compliant_llm_response())


@pytest.fixture
def violating_llm_client() -> MockLlmClient:
    return MockLlmClient(_violating_llm_response())


@pytest.fixture
def error_llm_client() -> MockLlmClientError:
    return MockLlmClientError()


@pytest.fixture
def mock_kafka_producer() -> MockKafkaProducer:
    return MockKafkaProducer()


@pytest.fixture
def real_sha256_command() -> ModelComplianceEvaluateCommand:
    """Command whose content_sha256 is the actual SHA-256 of its content."""
    content = "class Foo: pass"
    return _make_command(
        content=content,
        content_sha256=sha256_of(content),
    )
