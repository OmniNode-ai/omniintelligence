#!/usr/bin/env python3
"""
Success Scorer Compute Node - ONEX Compliant

Scores execution success based on multiple weighted factors for pattern extraction.
Part of Pattern Learning Engine Phase 1 Foundation.

Author: Archon Intelligence Team
Date: 2025-10-02
ONEX Compliance: >0.9
"""

import hashlib
import uuid
from typing import Any, Dict, List

from pydantic import BaseModel, Field

# ============================================================================
# Models
# ============================================================================


class ModelSuccessScoringInput(BaseModel):
    """Input state for success scoring."""

    execution_result: str = Field(..., description="Execution result text")
    execution_trace: Dict[str, Any] = Field(
        default_factory=dict, description="Execution trace data"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    user_feedback: float = Field(
        default=0.0,
        description="User feedback score (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    expected_outcomes: List[str] = Field(
        default_factory=list, description="Expected outcome indicators"
    )


class ModelSuccessScoringOutput(BaseModel):
    """Output state for success scoring."""

    success_score: float = Field(..., description="Overall success score (0.0-1.0)")
    completion_score: float = Field(
        ..., description="Completion indicator score (0.0-1.0)"
    )
    error_score: float = Field(..., description="Error-free execution score (0.0-1.0)")
    performance_score: float = Field(
        ..., description="Performance quality score (0.0-1.0)"
    )
    user_feedback_score: float = Field(..., description="User feedback score (0.0-1.0)")
    failure_indicators: List[str] = Field(
        default_factory=list, description="Detected failure indicators"
    )
    success_indicators: List[str] = Field(
        default_factory=list, description="Detected success indicators"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Scoring metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeSuccessScorerCompute:
    """
    ONEX-Compliant Compute Node for Success Scoring.

    Implements weighted multi-factor scoring to assess execution success
    based on completion, error rate, performance, and user feedback.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<20ms target)

    Scoring Weights:
    - Completion: 40%
    - Error Rate: 30%
    - Performance: 20%
    - User Feedback: 10%
    """

    # Scoring weights
    WEIGHT_COMPLETION = 0.40
    WEIGHT_ERROR_RATE = 0.30
    WEIGHT_PERFORMANCE = 0.20
    WEIGHT_USER_FEEDBACK = 0.10

    # Success indicators (keywords in results)
    SUCCESS_KEYWORDS = {
        "success",
        "successful",
        "completed",
        "finished",
        "done",
        "passed",
        "ok",
        "accomplished",
        "achieved",
        "resolved",
    }

    # Failure indicators
    FAILURE_KEYWORDS = {
        "error",
        "failed",
        "failure",
        "exception",
        "crash",
        "abort",
        "timeout",
        "cancelled",
        "rejected",
        "invalid",
        "incorrect",
    }

    # Performance thresholds (ms)
    EXCELLENT_PERFORMANCE_MS = 100
    GOOD_PERFORMANCE_MS = 500
    ACCEPTABLE_PERFORMANCE_MS = 2000

    # Performance constants
    DEFAULT_TIMEOUT_MS = 20

    def __init__(self) -> None:
        """Initialize success scorer."""
        pass

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelSuccessScoringInput
    ) -> ModelSuccessScoringOutput:
        """
        Execute success scoring computation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with execution result and trace

        Returns:
            ModelSuccessScoringOutput: Success scores with breakdown
        """
        import time

        start_time = time.time()

        try:
            # Calculate individual scores
            completion_score = self._calculate_completion_score(
                result_text=input_state.execution_result,
                expected_outcomes=input_state.expected_outcomes,
            )

            error_score = self._calculate_error_score(
                result_text=input_state.execution_result,
                trace=input_state.execution_trace,
            )

            performance_score = self._calculate_performance_score(
                trace=input_state.execution_trace,
            )

            user_feedback_score = input_state.user_feedback

            # Detect indicators
            success_indicators = self._detect_success_indicators(
                input_state.execution_result
            )
            failure_indicators = self._detect_failure_indicators(
                input_state.execution_result
            )

            # Calculate weighted overall score
            overall_score = (
                (completion_score * self.WEIGHT_COMPLETION)
                + (error_score * self.WEIGHT_ERROR_RATE)
                + (performance_score * self.WEIGHT_PERFORMANCE)
                + (user_feedback_score * self.WEIGHT_USER_FEEDBACK)
            )

            # Clamp to 0.0-1.0 range
            overall_score = max(0.0, min(1.0, overall_score))

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            return ModelSuccessScoringOutput(
                success_score=overall_score,
                completion_score=completion_score,
                error_score=error_score,
                performance_score=performance_score,
                user_feedback_score=user_feedback_score,
                failure_indicators=failure_indicators,
                success_indicators=success_indicators,
                metadata={
                    "processing_time_ms": processing_time,
                    "algorithm": "weighted_multi_factor_scoring",
                    "weights": {
                        "completion": self.WEIGHT_COMPLETION,
                        "error_rate": self.WEIGHT_ERROR_RATE,
                        "performance": self.WEIGHT_PERFORMANCE,
                        "user_feedback": self.WEIGHT_USER_FEEDBACK,
                    },
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            return ModelSuccessScoringOutput(
                success_score=0.0,
                completion_score=0.0,
                error_score=0.0,
                performance_score=0.0,
                user_feedback_score=0.0,
                failure_indicators=["scoring_error"],
                success_indicators=[],
                metadata={"error": str(e)},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Pure Functional Scoring Algorithms
    # ========================================================================

    def _calculate_completion_score(
        self, result_text: str, expected_outcomes: List[str]
    ) -> float:
        """
        Calculate completion score based on result text and expected outcomes.

        Algorithm:
        1. Check for success keywords in result
        2. Check for expected outcomes (if provided)
        3. Calculate completion ratio
        4. Return normalized score

        Args:
            result_text: Execution result text
            expected_outcomes: Expected outcome indicators

        Returns:
            Completion score (0.0-1.0)
        """
        result_lower = result_text.lower()

        # Base score from success keywords
        success_keyword_count = sum(
            1 for keyword in self.SUCCESS_KEYWORDS if keyword in result_lower
        )

        # Penalty for failure keywords
        failure_keyword_count = sum(
            1 for keyword in self.FAILURE_KEYWORDS if keyword in result_lower
        )

        # Base completion score
        if success_keyword_count > 0 and failure_keyword_count == 0:
            base_score = 1.0
        elif success_keyword_count > failure_keyword_count:
            base_score = 0.7
        elif failure_keyword_count > 0:
            base_score = 0.2
        else:
            # Neutral (no clear indicators)
            base_score = 0.5

        # Adjust based on expected outcomes
        if expected_outcomes:
            matched_outcomes = sum(
                1 for outcome in expected_outcomes if outcome.lower() in result_lower
            )
            outcome_ratio = matched_outcomes / len(expected_outcomes)

            # Weighted combination: 60% base + 40% outcome matching
            final_score = (base_score * 0.6) + (outcome_ratio * 0.4)
        else:
            final_score = base_score

        return max(0.0, min(1.0, final_score))

    def _calculate_error_score(self, result_text: str, trace: Dict[str, Any]) -> float:
        """
        Calculate error-free execution score.

        Algorithm:
        1. Check for error keywords in result
        2. Check for exceptions in trace
        3. Calculate error rate
        4. Return inverted score (higher = fewer errors)

        Args:
            result_text: Execution result text
            trace: Execution trace data

        Returns:
            Error-free score (0.0-1.0)
        """
        error_count = 0

        # Check result text for error keywords
        result_lower = result_text.lower()
        error_keyword_matches = sum(
            1 for keyword in self.FAILURE_KEYWORDS if keyword in result_lower
        )
        error_count += error_keyword_matches

        # Check trace for error events
        if "events" in trace:
            for event in trace.get("events", []):
                if isinstance(event, dict):
                    if event.get("error") or event.get("exception"):
                        error_count += 1

        # Check for explicit error flags
        if trace.get("has_errors") or trace.get("failed"):
            error_count += 1

        # Calculate error-free score (inverse of error rate)
        if error_count == 0:
            return 1.0
        elif error_count == 1:
            return 0.7
        elif error_count == 2:
            return 0.4
        else:
            # 3+ errors
            return 0.1

    def _calculate_performance_score(self, trace: Dict[str, Any]) -> float:
        """
        Calculate performance quality score based on execution time.

        Algorithm:
        1. Extract total execution duration from trace
        2. Compare against performance thresholds
        3. Return normalized performance score

        Args:
            trace: Execution trace data

        Returns:
            Performance score (0.0-1.0)
        """
        # Try to extract duration
        duration_ms: float = 0.0

        if "duration_ms" in trace:
            try:
                duration_ms = float(trace["duration_ms"])
            except (ValueError, TypeError):
                pass

        elif "timing_summary" in trace:
            timing = trace["timing_summary"]
            if isinstance(timing, dict):
                duration_ms = timing.get("total_duration_ms", 0.0)

        # If no duration found, assume neutral performance
        if duration_ms == 0.0:
            return 0.6  # Neutral score

        # Score based on thresholds
        if duration_ms <= self.EXCELLENT_PERFORMANCE_MS:
            return 1.0  # Excellent
        elif duration_ms <= self.GOOD_PERFORMANCE_MS:
            return 0.8  # Good
        elif duration_ms <= self.ACCEPTABLE_PERFORMANCE_MS:
            return 0.6  # Acceptable
        else:
            # Poor performance (exponential decay)
            # Score decreases as duration increases beyond acceptable
            decay = (duration_ms - self.ACCEPTABLE_PERFORMANCE_MS) / 10000.0
            score = 0.4 * (0.5**decay)  # Exponential decay from 0.4
            return max(0.1, score)  # Minimum score 0.1

    def _detect_success_indicators(self, result_text: str) -> List[str]:
        """
        Detect success indicators in result text.

        Args:
            result_text: Execution result text

        Returns:
            List of detected success indicators
        """
        indicators: List[str] = []
        result_lower = result_text.lower()

        for keyword in self.SUCCESS_KEYWORDS:
            if keyword in result_lower:
                indicators.append(keyword)

        return indicators

    def _detect_failure_indicators(self, result_text: str) -> List[str]:
        """
        Detect failure indicators in result text.

        Args:
            result_text: Execution result text

        Returns:
            List of detected failure indicators
        """
        indicators: List[str] = []
        result_lower = result_text.lower()

        for keyword in self.FAILURE_KEYWORDS:
            if keyword in result_lower:
                indicators.append(keyword)

        return indicators

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def calculate_deterministic_hash(self, data: str) -> str:
        """Calculate deterministic hash for reproducibility."""
        combined = f"{data}|success_scorer|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"
