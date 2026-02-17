"""Protocols for pattern compliance handler dependencies.

Defines the LLM client protocol used by the compliance handler.
The protocol allows injection of any OpenAI-compatible LLM backend
(Coder-14B via vLLM, OpenAI API, mock for testing).

Ticket: OMN-2256
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict, runtime_checkable

#: Valid severity levels for compliance violations.
SeverityLiteral = Literal["critical", "major", "minor", "info"]


class ComplianceViolationDict(TypedDict):
    """Parsed violation from LLM response.

    Attributes:
        pattern_id: ID of the violated pattern.
        pattern_signature: Pattern signature text.
        description: Description of the violation.
        severity: Severity level.
        line_reference: Optional line reference.
    """

    pattern_id: str
    pattern_signature: str
    description: str
    severity: SeverityLiteral
    line_reference: str | None


class ComplianceLlmResponseDict(TypedDict):
    """Parsed LLM response for compliance evaluation.

    Attributes:
        compliant: Whether the code is fully compliant.
        violations: List of violations found.
        confidence: Confidence in the evaluation (0.0-1.0).
        raw_response: Raw text from the LLM for debugging.
    """

    compliant: bool
    violations: list[ComplianceViolationDict]
    confidence: float
    raw_response: str


@runtime_checkable
class ProtocolLlmClient(Protocol):
    """Protocol for OpenAI-compatible LLM inference.

    Abstracts the LLM call so the compliance handler can work with
    any backend: Coder-14B via vLLM, OpenAI, or a mock for testing.

    The method signature mirrors a simplified chat completion call.
    """

    async def chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Execute a chat completion and return the generated text.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model identifier (e.g., 'Qwen/Qwen2.5-Coder-14B-Instruct').
            temperature: Sampling temperature (0.0 for deterministic).
            max_tokens: Maximum tokens to generate.

        Returns:
            The generated text content from the LLM response.
        """
        ...


__all__ = [
    "ComplianceLlmResponseDict",
    "ComplianceViolationDict",
    "ProtocolLlmClient",
]
