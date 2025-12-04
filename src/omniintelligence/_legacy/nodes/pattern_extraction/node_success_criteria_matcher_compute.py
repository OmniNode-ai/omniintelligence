#!/usr/bin/env python3
"""
Success Criteria Matcher Compute Node - ONEX Compliant

Matches execution results against success criteria using fuzzy and semantic matching.
Part of Track 2 Intelligence Hook System (Track 3-1.4).

Generated with DeepSeek-Lite via vLLM
Author: Archon Intelligence Team
Date: 2025-10-02
"""

import hashlib
import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# Models
# ============================================================================


class ModelSuccessMatchingInput(BaseModel):
    """Input state for success criteria matching."""

    execution_result: str = Field(..., description="Execution result to evaluate")
    success_criteria: list[str] = Field(
        ..., description="List of success criteria to match against"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    fuzzy_threshold: float = Field(
        default=0.7,
        description="Fuzzy matching threshold (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    require_all_criteria: bool = Field(
        default=False, description="Require all criteria to match (AND) vs any (OR)"
    )


@dataclass
class CriteriaMatch:
    """Individual criteria match result."""

    criterion: str
    matched: bool
    confidence: float
    match_type: str  # exact, fuzzy, semantic, pattern
    matched_text: str | None


class ModelSuccessMatchingOutput(BaseModel):
    """Output state for success criteria matching."""

    overall_success: bool = Field(..., description="Overall success determination")
    overall_confidence: float = Field(..., description="Overall match confidence")
    criteria_matches: list[dict[str, Any]] = Field(
        default_factory=list, description="Individual criteria match results"
    )
    matched_criteria: list[str] = Field(
        default_factory=list, description="Criteria that matched"
    )
    unmatched_criteria: list[str] = Field(
        default_factory=list, description="Criteria that didn't match"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Matching metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeSuccessCriteriaMatcherCompute:
    """
    ONEX-Compliant Compute Node for Success Criteria Matching.

    Implements fuzzy and semantic matching to evaluate execution results
    against defined success criteria.

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<50ms target)

    Matching Strategies:
    1. Exact matching: Direct string match
    2. Fuzzy matching: SequenceMatcher similarity
    3. Pattern matching: Regex patterns
    4. Semantic matching: Keyword-based similarity
    """

    # Success indicators (positive keywords)
    SUCCESS_INDICATORS = {
        "success",
        "passed",
        "completed",
        "done",
        "finished",
        "ok",
        "valid",
        "correct",
        "true",
    }

    # Failure indicators (negative keywords)
    FAILURE_INDICATORS = {
        "fail",
        "failed",
        "error",
        "exception",
        "invalid",
        "incorrect",
        "false",
        "timeout",
        "crashed",
    }

    # Performance constants
    MAX_RESULT_LENGTH = 100000
    DEFAULT_TIMEOUT_MS = 50

    def __init__(self) -> None:
        """Initialize success criteria matcher."""

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelSuccessMatchingInput
    ) -> ModelSuccessMatchingOutput:
        """
        Execute success criteria matching computation (ONEX NodeCompute interface).

        Pure functional method with no side effects, deterministic results.

        Args:
            input_state: Input state with execution result and criteria

        Returns:
            ModelSuccessMatchingOutput: Matching results with confidence scores
        """
        import time

        start_time = time.time()

        try:
            # Validate input
            if not input_state.execution_result.strip():
                return ModelSuccessMatchingOutput(
                    overall_success=False,
                    overall_confidence=0.0,
                    criteria_matches=[],
                    matched_criteria=[],
                    unmatched_criteria=input_state.success_criteria,
                    metadata={"error": "Empty execution result"},
                    correlation_id=input_state.correlation_id,
                )

            if not input_state.success_criteria:
                return ModelSuccessMatchingOutput(
                    overall_success=True,  # No criteria to fail
                    overall_confidence=1.0,
                    criteria_matches=[],
                    matched_criteria=[],
                    unmatched_criteria=[],
                    metadata={"warning": "No success criteria provided"},
                    correlation_id=input_state.correlation_id,
                )

            # Match each criterion
            criteria_matches: list[CriteriaMatch] = []
            for criterion in input_state.success_criteria:
                match_result = self._match_criterion(
                    execution_result=input_state.execution_result,
                    criterion=criterion,
                    fuzzy_threshold=input_state.fuzzy_threshold,
                )
                criteria_matches.append(match_result)

            # Determine overall success
            matched_count = sum(1 for m in criteria_matches if m.matched)
            total_count = len(criteria_matches)

            if input_state.require_all_criteria:
                # AND logic: all must match
                overall_success = matched_count == total_count
            else:
                # OR logic: at least one must match
                overall_success = matched_count > 0

            # Calculate overall confidence
            if criteria_matches:
                confidences = [m.confidence for m in criteria_matches]
                overall_confidence = sum(confidences) / len(confidences)
            else:
                overall_confidence = 0.0

            # Build output lists
            matched_criteria = [m.criterion for m in criteria_matches if m.matched]
            unmatched_criteria = [
                m.criterion for m in criteria_matches if not m.matched
            ]

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            return ModelSuccessMatchingOutput(
                overall_success=overall_success,
                overall_confidence=overall_confidence,
                criteria_matches=[self._match_to_dict(m) for m in criteria_matches],
                matched_criteria=matched_criteria,
                unmatched_criteria=unmatched_criteria,
                metadata={
                    "processing_time_ms": processing_time,
                    "total_criteria": total_count,
                    "matched_count": matched_count,
                    "match_rate": (
                        matched_count / total_count if total_count > 0 else 0.0
                    ),
                    "matching_mode": (
                        "all" if input_state.require_all_criteria else "any"
                    ),
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            return ModelSuccessMatchingOutput(
                overall_success=False,
                overall_confidence=0.0,
                criteria_matches=[],
                matched_criteria=[],
                unmatched_criteria=input_state.success_criteria,
                metadata={"error": str(e)},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Pure Functional Matching Algorithms
    # ========================================================================

    def _match_criterion(
        self, execution_result: str, criterion: str, fuzzy_threshold: float = 0.7
    ) -> CriteriaMatch:
        """
        Match a single criterion against execution result.

        Tries multiple matching strategies in order:
        1. Exact match
        2. Fuzzy string match
        3. Pattern match (if criterion looks like regex)
        4. Semantic match (keyword-based)

        Args:
            execution_result: Execution result text
            criterion: Success criterion to match
            fuzzy_threshold: Threshold for fuzzy matching

        Returns:
            CriteriaMatch with match result and confidence
        """
        result_lower = execution_result.lower()
        criterion_lower = criterion.lower()

        # Strategy 1: Exact match
        if criterion_lower in result_lower:
            return CriteriaMatch(
                criterion=criterion,
                matched=True,
                confidence=1.0,
                match_type="exact",
                matched_text=criterion,
            )

        # Strategy 2: Fuzzy string match
        fuzzy_score = SequenceMatcher(None, result_lower, criterion_lower).ratio()
        if fuzzy_score >= fuzzy_threshold:
            return CriteriaMatch(
                criterion=criterion,
                matched=True,
                confidence=fuzzy_score,
                match_type="fuzzy",
                matched_text=None,
            )

        # Strategy 3: Pattern match (if criterion looks like regex)
        if self._is_regex_pattern(criterion):
            pattern_match = self._match_pattern(execution_result, criterion)
            if pattern_match:
                return CriteriaMatch(
                    criterion=criterion,
                    matched=True,
                    confidence=0.9,  # High confidence for regex match
                    match_type="pattern",
                    matched_text=pattern_match,
                )

        # Strategy 4: Semantic keyword match
        semantic_score = self._calculate_semantic_similarity(
            execution_result, criterion
        )
        if semantic_score >= fuzzy_threshold:
            return CriteriaMatch(
                criterion=criterion,
                matched=True,
                confidence=semantic_score,
                match_type="semantic",
                matched_text=None,
            )

        # No match found
        return CriteriaMatch(
            criterion=criterion,
            matched=False,
            confidence=max(fuzzy_score, semantic_score),  # Best attempt
            match_type="none",
            matched_text=None,
        )

    def _is_regex_pattern(self, text: str) -> bool:
        """
        Check if text looks like a regex pattern.

        Args:
            text: Text to check

        Returns:
            True if text contains regex metacharacters
        """
        regex_chars = {
            "^",
            "$",
            "*",
            "+",
            "?",
            ".",
            "[",
            "]",
            "{",
            "}",
            "(",
            ")",
            "|",
            "\\",
        }
        return any(char in text for char in regex_chars)

    def _match_pattern(self, execution_result: str, pattern: str) -> str | None:
        """
        Match regex pattern against execution result.

        Args:
            execution_result: Result text
            pattern: Regex pattern

        Returns:
            Matched text if found, None otherwise
        """
        try:
            match = re.search(pattern, execution_result, re.IGNORECASE)
            if match:
                return match.group(0)
        except re.error:
            # Invalid regex pattern
            pass

        return None

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity using keyword overlap.

        Simple keyword-based similarity without external dependencies.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)
        """
        # Extract keywords (words longer than 3 chars)
        words1 = {w.lower() for w in re.findall(r"\w+", text1) if len(w) > 3}
        words2 = {w.lower() for w in re.findall(r"\w+", text2) if len(w) > 3}

        if not words1 or not words2:
            return 0.0

        # Calculate Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)

        if union == 0:
            return 0.0

        return intersection / union

    def _match_to_dict(self, match: CriteriaMatch) -> dict[str, Any]:
        """Convert CriteriaMatch to dictionary."""
        return {
            "criterion": match.criterion,
            "matched": match.matched,
            "confidence": match.confidence,
            "match_type": match.match_type,
            "matched_text": match.matched_text,
        }

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def calculate_deterministic_hash(self, data: str) -> str:
        """Calculate deterministic hash for reproducibility."""
        combined = f"{data}|success_matcher|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"


# ============================================================================
# Unit Test Helpers
# ============================================================================


async def test_success_matcher() -> None:
    """Test success criteria matcher with various scenarios."""
    matcher = NodeSuccessCriteriaMatcherCompute()

    # Test 1: All criteria match (exact)
    test_input = ModelSuccessMatchingInput(
        execution_result="Test passed successfully with all checks validated",
        success_criteria=["passed", "successfully", "validated"],
        require_all_criteria=True,
    )
    result = await matcher.execute_compute(test_input)

    print("Test 1 - All criteria (exact):")
    print(f"  Success: {result.overall_success}")
    print(f"  Confidence: {result.overall_confidence}")
    print(f"  Matched: {result.matched_criteria}")
    print(f"  Processing time: {result.metadata.get('processing_time_ms')}ms")

    assert result.overall_success is True
    assert len(result.matched_criteria) == 3

    # Test 2: Fuzzy matching
    test_input = ModelSuccessMatchingInput(
        execution_result="Function completed with minor warnings",
        success_criteria=["complete", "warning"],
        fuzzy_threshold=0.7,
    )
    result = await matcher.execute_compute(test_input)

    print("\nTest 2 - Fuzzy matching:")
    print(f"  Success: {result.overall_success}")
    print(f"  Matches: {result.criteria_matches}")

    # Test 3: Pattern matching
    test_input = ModelSuccessMatchingInput(
        execution_result="Processing finished in 125ms with status: OK",
        success_criteria=[
            r"\d+ms",  # Regex for timing
            "status: OK",  # Exact match
        ],
    )
    result = await matcher.execute_compute(test_input)

    print("\nTest 3 - Pattern matching:")
    print(f"  Success: {result.overall_success}")
    print(f"  Matched: {result.matched_criteria}")
    print(f"  Match types: {[m['match_type'] for m in result.criteria_matches]}")

    # Test 4: No criteria match
    test_input = ModelSuccessMatchingInput(
        execution_result="Operation failed with error",
        success_criteria=["success", "completed", "validated"],
        require_all_criteria=False,
    )
    result = await matcher.execute_compute(test_input)

    print("\nTest 4 - No match:")
    print(f"  Success: {result.overall_success}")
    print(f"  Unmatched: {result.unmatched_criteria}")

    assert result.overall_success is False

    # Test 5: OR mode (at least one matches)
    test_input = ModelSuccessMatchingInput(
        execution_result="Test passed but with some warnings",
        success_criteria=["passed", "failed", "error"],
        require_all_criteria=False,  # OR mode
    )
    result = await matcher.execute_compute(test_input)

    print("\nTest 5 - OR mode:")
    print(f"  Success: {result.overall_success}")
    print(f"  Matched: {result.matched_criteria}")
    print(f"  Match rate: {result.metadata.get('match_rate')}")

    assert result.overall_success is True  # "passed" matches

    print("\nAll tests passed!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_success_matcher())
