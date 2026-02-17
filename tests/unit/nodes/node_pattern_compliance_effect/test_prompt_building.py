"""Unit tests for compliance prompt building.

Tests the pure prompt construction function that builds the LLM prompt
from code content and applicable patterns.

Ticket: OMN-2256
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
    build_compliance_prompt,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models import (
    ModelApplicablePattern,
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


class TestBuildCompliancePrompt:
    """Tests for build_compliance_prompt."""

    def test_includes_code_content(self) -> None:
        """Prompt must contain the source code."""
        patterns = [_make_pattern()]
        prompt = build_compliance_prompt(
            content="class Foo: pass",
            language="python",
            patterns=patterns,
        )
        assert "class Foo: pass" in prompt

    def test_includes_language(self) -> None:
        """Prompt must reference the language."""
        patterns = [_make_pattern()]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "python" in prompt.lower()

    def test_includes_pattern_id(self) -> None:
        """Prompt must include pattern IDs for tracing."""
        patterns = [_make_pattern(pattern_id="PAT-42")]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "PAT-42" in prompt

    def test_includes_pattern_signature(self) -> None:
        """Prompt must include pattern signature text."""
        patterns = [_make_pattern(signature="Always use type hints")]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "Always use type hints" in prompt

    def test_includes_pattern_domain(self) -> None:
        """Prompt must include pattern domain for context."""
        patterns = [_make_pattern(domain="security")]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "security" in prompt

    def test_includes_pattern_confidence(self) -> None:
        """Prompt must include pattern confidence score."""
        patterns = [_make_pattern(confidence=0.85)]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "0.85" in prompt

    def test_multiple_patterns(self) -> None:
        """Prompt must include all provided patterns."""
        patterns = [
            _make_pattern(pattern_id="P1", signature="Use frozen models"),
            _make_pattern(pattern_id="P2", signature="Use TypedDict"),
            _make_pattern(pattern_id="P3", signature="No mutable state"),
        ]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "P1" in prompt
        assert "P2" in prompt
        assert "P3" in prompt
        assert "Use frozen models" in prompt
        assert "Use TypedDict" in prompt
        assert "No mutable state" in prompt

    def test_requests_json_response(self) -> None:
        """Prompt must request JSON response format."""
        patterns = [_make_pattern()]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "JSON" in prompt or "json" in prompt

    def test_requests_violations_in_response(self) -> None:
        """Prompt must ask for violations in the response."""
        patterns = [_make_pattern()]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "violations" in prompt.lower()

    def test_requests_compliant_field(self) -> None:
        """Prompt must ask for compliant field in the response."""
        patterns = [_make_pattern()]
        prompt = build_compliance_prompt(
            content="x = 1",
            language="python",
            patterns=patterns,
        )
        assert "compliant" in prompt.lower()
