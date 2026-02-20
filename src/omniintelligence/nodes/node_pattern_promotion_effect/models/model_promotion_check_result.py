"""ModelPromotionCheckResult - result of the promotion check operation."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_promotion_effect.models.model_promotion_result import (
    ModelPromotionResult,
)


class ModelPromotionCheckResult(BaseModel):
    """Result of the promotion check operation.

    Aggregates results from checking all provisional patterns for
    promotion eligibility, including counts and individual promotion
    results.
    """

    model_config = ConfigDict(frozen=True)

    dry_run: bool = Field(
        ...,
        description="Whether this was a dry run",
    )
    patterns_checked: int = Field(
        ...,
        ge=0,
        description="Total number of provisional patterns checked",
    )
    patterns_eligible: int = Field(
        ...,
        ge=0,
        description="Number of patterns meeting promotion criteria",
    )
    patterns_promoted: list[ModelPromotionResult] = Field(
        default_factory=list,
        description="List of individual promotion results",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing, if provided in request",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if an error occurred during promotion check",
    )

    @property
    def patterns_failed(self) -> int:
        """Count of promotion attempts that failed (promoted_at is None, not dry_run).

        A failed entry is one where the promotion event could not be emitted
        (e.g. Kafka emit raised, caught by per-pattern exception handler) and
        was caught by the per-pattern error handler in ``check_and_promote_patterns``.
        """
        return sum(
            1 for r in self.patterns_promoted if r.promoted_at is None and not r.dry_run
        )
