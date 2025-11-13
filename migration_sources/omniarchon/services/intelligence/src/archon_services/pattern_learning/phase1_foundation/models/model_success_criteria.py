"""
Pattern Learning Engine - Success Criteria Model

Tracks what makes a pattern execution successful with weighted scoring.
"""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class ModelSuccessCriteria(BaseModel):
    """
    Defines what makes an execution successful for pattern learning.

    Uses weighted boolean criteria to determine overall success and
    calculate a confidence score for pattern matching.
    """

    # Core success indicators
    execution_completed: bool = Field(
        default=True, description="Trace reached completion without interruption"
    )

    no_errors: bool = Field(
        default=True, description="No error status or error messages in execution"
    )

    hooks_succeeded: bool = Field(
        default=True, description="All mandatory hooks executed successfully"
    )

    quality_gates_passed: bool = Field(
        default=True, description="All quality gates validated successfully"
    )

    # Performance indicators
    within_performance_thresholds: bool = Field(
        default=True, description="Execution met performance targets and thresholds"
    )

    no_timeouts: bool = Field(
        default=True, description="No timeout errors occurred during execution"
    )

    # Intelligence indicators
    intelligence_gathered: bool = Field(
        default=True, description="RAG queries and intelligence gathering succeeded"
    )

    patterns_identified: bool = Field(
        default=True, description="Known patterns were successfully matched"
    )

    # User feedback indicator
    user_confirmed_success: bool = Field(
        default=True,
        description="User confirmed success (assume true unless reported otherwise)",
    )

    def is_successful(self) -> bool:
        """
        Determine if execution meets minimum success criteria.

        Returns:
            True if core criteria are met (execution completed, no errors,
            hooks succeeded, quality gates passed, no timeouts)
        """
        return (
            self.execution_completed
            and self.no_errors
            and self.hooks_succeeded
            and self.quality_gates_passed
            and self.no_timeouts
        )

    def success_score(self) -> float:
        """
        Calculate weighted success score from 0.0 to 1.0.

        Weights:
            - execution_completed: 0.25 (critical)
            - no_errors: 0.25 (critical)
            - hooks_succeeded: 0.15 (important)
            - quality_gates_passed: 0.15 (important)
            - within_performance_thresholds: 0.10 (nice-to-have)
            - intelligence_gathered: 0.05 (bonus)
            - user_confirmed_success: 0.05 (bonus)

        Returns:
            Weighted success score between 0.0 and 1.0
        """
        weights = {
            "execution_completed": 0.25,
            "no_errors": 0.25,
            "hooks_succeeded": 0.15,
            "quality_gates_passed": 0.15,
            "within_performance_thresholds": 0.10,
            "intelligence_gathered": 0.05,
            "user_confirmed_success": 0.05,
        }

        score = sum(
            weights[field]
            for field, value in self.model_dump().items()
            if value and field in weights
        )

        return min(score, 1.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "execution_completed": True,
                "no_errors": True,
                "hooks_succeeded": True,
                "quality_gates_passed": True,
                "within_performance_thresholds": True,
                "no_timeouts": True,
                "intelligence_gathered": True,
                "patterns_identified": True,
                "user_confirmed_success": True,
            }
        }
    )
