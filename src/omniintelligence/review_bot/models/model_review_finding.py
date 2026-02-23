"""ReviewFinding Pydantic model for Code Intelligence Review Bot.

A ReviewFinding represents a single detected code issue. Findings are
immutable after creation (frozen=True) and serve as the central data
contract flowing between review bot components.

OMN-2495: Implement ReviewFinding and ReviewScore Pydantic models.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity


class ModelReviewFinding(BaseModel):
    """A single detected code issue from the Code Intelligence Review Bot.

    ReviewFindings are immutable after creation. They are produced by the
    review runner and consumed by:
    - PR comment poster (OMN-2497)
    - Auto-remediation pipeline (OMN-2498)
    - ReviewScore computation
    - OmniMemory learning loop (OMN-2499)

    Attributes:
        finding_id: Unique identifier for this finding (UUID4).
        rule_id: The rule that triggered this finding (e.g., "no-bare-except").
        severity: How severe this finding is (BLOCKER/WARNING/INFO).
        confidence: Confidence score in range [0.0, 1.0].
        rationale: Human-readable explanation of why this is a finding.
        suggested_fix: Human-readable description of how to fix it.
        patch: Optional git diff patch for auto-remediation.
        file_path: Path to the file where the finding was detected.
        line_number: Optional line number within the file.

    Example::

        finding = ModelReviewFinding(
            rule_id="no-bare-except",
            severity=ReviewSeverity.BLOCKER,
            confidence=0.95,
            rationale="Bare except catches all exceptions including KeyboardInterrupt",
            suggested_fix="Replace with `except Exception:` or a specific exception type",
            file_path="src/myapp/handler.py",
            line_number=42,
        )
    """

    finding_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this finding",
    )
    rule_id: str = Field(
        ...,
        description="The rule ID that triggered this finding",
        min_length=1,
    )
    severity: ReviewSeverity = Field(
        ...,
        description="Severity level of this finding",
    )
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        ...,
        description="Confidence score in range [0.0, 1.0]",
    )
    rationale: str = Field(
        ...,
        description="Human-readable explanation of why this is a finding",
        min_length=1,
    )
    suggested_fix: str = Field(
        ...,
        description="Human-readable description of how to fix the finding",
        min_length=1,
    )
    patch: str | None = Field(
        default=None,
        description="Optional git diff patch for auto-remediation",
    )
    file_path: str = Field(
        ...,
        description="Path to the file where the finding was detected",
        min_length=1,
    )
    line_number: int | None = Field(
        default=None,
        description="Optional line number within the file",
        ge=1,
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Validate confidence is in [0.0, 1.0]."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be in range [0.0, 1.0], got: {v}")
        return v

    model_config = {"frozen": True, "extra": "ignore", "from_attributes": True}


__all__ = ["ModelReviewFinding"]
