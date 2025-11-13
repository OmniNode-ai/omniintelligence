#!/usr/bin/env python3
"""
Pattern Assembler Orchestrator Node - ONEX Compliant

Orchestrates pattern extraction pipeline by coordinating all compute nodes.
Part of Pattern Learning Engine Phase 1 Foundation.

Author: Archon Intelligence Team
Date: 2025-10-02
ONEX Compliance: >0.9
"""

import hashlib
import uuid
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from src.archon_services.pattern_learning.phase1_foundation.extraction.node_execution_analyzer_compute import (
    ModelExecutionAnalysisInput,
    ModelExecutionAnalysisOutput,
    NodeExecutionAnalyzerCompute,
)

# Import compute nodes
from src.archon_services.pattern_learning.phase1_foundation.extraction.node_intent_classifier_compute import (
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
    NodeIntentClassifierCompute,
)
from src.archon_services.pattern_learning.phase1_foundation.extraction.node_keyword_extractor_compute import (
    ModelKeywordExtractionInput,
    ModelKeywordExtractionOutput,
    NodeKeywordExtractorCompute,
)
from src.archon_services.pattern_learning.phase1_foundation.extraction.node_success_scorer_compute import (
    ModelSuccessScoringInput,
    ModelSuccessScoringOutput,
    NodeSuccessScorerCompute,
)

# ============================================================================
# Models
# ============================================================================


class ModelPatternExtractionInput(BaseModel):
    """Input state for pattern extraction orchestration."""

    request_text: str = Field(..., description="Original user request text")
    execution_trace: Dict[str, Any] = Field(
        default_factory=dict, description="Execution trace data"
    )
    execution_result: str = Field(..., description="Execution result text")
    expected_outcomes: List[str] = Field(
        default_factory=list, description="Expected outcome indicators"
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


class ModelPatternExtractionOutput(BaseModel):
    """Output state for pattern extraction orchestration."""

    # Intent classification results
    intent: str = Field(..., description="Classified intent")
    intent_confidence: float = Field(
        ..., description="Intent classification confidence"
    )

    # Keyword extraction results
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    phrases: List[str] = Field(default_factory=list, description="Extracted phrases")

    # Execution analysis results
    execution_signature: str = Field(..., description="Execution path signature")
    tool_usage_patterns: Dict[str, int] = Field(
        default_factory=dict, description="Tool usage patterns"
    )
    execution_sequence: List[str] = Field(
        default_factory=list, description="Execution sequence"
    )

    # Success scoring results
    success_score: float = Field(..., description="Overall success score")
    completion_score: float = Field(..., description="Completion score")
    error_score: float = Field(..., description="Error-free score")
    performance_score: float = Field(..., description="Performance score")

    # Assembled pattern
    assembled_pattern: Dict[str, Any] = Field(
        default_factory=dict, description="Complete assembled pattern"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Orchestration metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Orchestrator Node Implementation
# ============================================================================


class NodePatternAssemblerOrchestrator:
    """
    ONEX-Compliant Orchestrator Node for Pattern Assembly.

    Orchestrates the pattern extraction pipeline by coordinating:
    1. Intent Classification (NodeCompute)
    2. Keyword Extraction (NodeCompute)
    3. Execution Analysis (NodeCompute)
    4. Success Scoring (NodeCompute)

    ONEX Patterns:
    - Workflow coordination
    - Correlation ID propagation
    - Parallel execution where possible
    - Error isolation and graceful degradation
    - Performance target: <200ms total pipeline
    """

    def __init__(self) -> None:
        """Initialize orchestrator with compute nodes."""
        # Initialize all compute nodes
        self.intent_classifier = NodeIntentClassifierCompute()
        self.keyword_extractor = NodeKeywordExtractorCompute()
        self.execution_analyzer = NodeExecutionAnalyzerCompute()
        self.success_scorer = NodeSuccessScorerCompute()

    # ========================================================================
    # ONEX Execute Orchestration Method (Primary Interface)
    # ========================================================================

    async def execute_orchestration(
        self, input_state: ModelPatternExtractionInput
    ) -> ModelPatternExtractionOutput:
        """
        Execute pattern extraction orchestration (ONEX NodeOrchestrator interface).

        Coordinates all compute nodes to extract comprehensive patterns
        from execution intelligence data.

        Args:
            input_state: Input state with request, trace, and result data

        Returns:
            ModelPatternExtractionOutput: Assembled pattern with all extracted data
        """
        import asyncio
        import time

        start_time = time.time()

        try:
            # Propagate correlation ID to all operations
            correlation_id = input_state.correlation_id

            # ================================================================
            # Phase 1: Parallel execution of independent nodes
            # ================================================================

            # These operations can run in parallel as they don't depend on each other
            intent_task = asyncio.create_task(
                self._classify_intent(
                    request_text=input_state.request_text,
                    correlation_id=correlation_id,
                )
            )

            keyword_task = asyncio.create_task(
                self._extract_keywords(
                    context_text=input_state.request_text
                    + " "
                    + input_state.execution_result,
                    correlation_id=correlation_id,
                )
            )

            execution_task = asyncio.create_task(
                self._analyze_execution(
                    execution_trace=input_state.execution_trace,
                    correlation_id=correlation_id,
                )
            )

            # Wait for all parallel operations to complete
            intent_result, keyword_result, execution_result = await asyncio.gather(
                intent_task, keyword_task, execution_task
            )

            # ================================================================
            # Phase 2: Success scoring (depends on execution analysis)
            # ================================================================

            success_result = await self._score_success(
                execution_result_text=input_state.execution_result,
                execution_trace=input_state.execution_trace,
                expected_outcomes=input_state.expected_outcomes,
                user_feedback=input_state.user_feedback,
                correlation_id=correlation_id,
            )

            # ================================================================
            # Phase 3: Pattern Assembly
            # ================================================================

            assembled_pattern = self._assemble_pattern(
                intent_result=intent_result,
                keyword_result=keyword_result,
                execution_result=execution_result,
                success_result=success_result,
            )

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            # Build output
            return ModelPatternExtractionOutput(
                # Intent
                intent=intent_result.intent,
                intent_confidence=intent_result.confidence,
                # Keywords
                keywords=keyword_result.keywords,
                phrases=keyword_result.phrases,
                # Execution
                execution_signature=execution_result.execution_signature,
                tool_usage_patterns=execution_result.tool_usage_patterns,
                execution_sequence=execution_result.execution_sequence,
                # Success
                success_score=success_result.success_score,
                completion_score=success_result.completion_score,
                error_score=success_result.error_score,
                performance_score=success_result.performance_score,
                # Assembly
                assembled_pattern=assembled_pattern,
                # Metadata
                metadata={
                    "processing_time_ms": processing_time,
                    "phases_completed": 3,
                    "nodes_executed": 4,
                    "parallel_execution": True,
                    "performance_target_met": processing_time < 200,
                },
                correlation_id=correlation_id,
            )

        except Exception as e:
            # Graceful error handling
            return ModelPatternExtractionOutput(
                intent="unknown",
                intent_confidence=0.0,
                keywords=[],
                phrases=[],
                execution_signature="sha256:error",
                tool_usage_patterns={},
                execution_sequence=[],
                success_score=0.0,
                completion_score=0.0,
                error_score=0.0,
                performance_score=0.0,
                assembled_pattern={},
                metadata={"error": str(e), "orchestration_failed": True},
                correlation_id=input_state.correlation_id,
            )

    # ========================================================================
    # Compute Node Coordination Methods
    # ========================================================================

    async def _classify_intent(
        self, request_text: str, correlation_id: str
    ) -> ModelIntentClassificationOutput:
        """Coordinate with intent classifier node."""
        input_state = ModelIntentClassificationInput(
            request_text=request_text,
            correlation_id=correlation_id,
            confidence_threshold=0.5,
        )
        return await self.intent_classifier.execute_compute(input_state)

    async def _extract_keywords(
        self, context_text: str, correlation_id: str
    ) -> ModelKeywordExtractionOutput:
        """Coordinate with keyword extractor node."""
        input_state = ModelKeywordExtractionInput(
            context_text=context_text,
            correlation_id=correlation_id,
            max_keywords=15,
            include_phrases=True,
        )
        return await self.keyword_extractor.execute_compute(input_state)

    async def _analyze_execution(
        self, execution_trace: Dict[str, Any], correlation_id: str
    ) -> ModelExecutionAnalysisOutput:
        """Coordinate with execution analyzer node."""
        input_state = ModelExecutionAnalysisInput(
            execution_trace=execution_trace,
            correlation_id=correlation_id,
            include_timing=True,
            include_patterns=True,
        )
        return await self.execution_analyzer.execute_compute(input_state)

    async def _score_success(
        self,
        execution_result_text: str,
        execution_trace: Dict[str, Any],
        expected_outcomes: List[str],
        user_feedback: float,
        correlation_id: str,
    ) -> ModelSuccessScoringOutput:
        """Coordinate with success scorer node."""
        input_state = ModelSuccessScoringInput(
            execution_result=execution_result_text,
            execution_trace=execution_trace,
            expected_outcomes=expected_outcomes,
            user_feedback=user_feedback,
            correlation_id=correlation_id,
        )
        return await self.success_scorer.execute_compute(input_state)

    # ========================================================================
    # Pattern Assembly Logic
    # ========================================================================

    def _assemble_pattern(
        self,
        intent_result: ModelIntentClassificationOutput,
        keyword_result: ModelKeywordExtractionOutput,
        execution_result: ModelExecutionAnalysisOutput,
        success_result: ModelSuccessScoringOutput,
    ) -> Dict[str, Any]:
        """
        Assemble comprehensive pattern from all node results.

        Combines results from all compute nodes into a unified pattern
        representation suitable for pattern storage and analysis.

        Args:
            intent_result: Intent classification result
            keyword_result: Keyword extraction result
            execution_result: Execution analysis result
            success_result: Success scoring result

        Returns:
            Dictionary with assembled pattern data
        """
        pattern = {
            # Intent information
            "intent": {
                "primary": intent_result.intent,
                "confidence": intent_result.confidence,
                "keywords": intent_result.keywords,
                "all_scores": intent_result.all_scores,
            },
            # Context information
            "context": {
                "keywords": keyword_result.keywords,
                "keyword_scores": keyword_result.keyword_scores,
                "phrases": keyword_result.phrases,
                "phrase_scores": keyword_result.phrase_scores,
            },
            # Execution information
            "execution": {
                "signature": execution_result.execution_signature,
                "sequence": execution_result.execution_sequence,
                "tool_patterns": execution_result.tool_usage_patterns,
                "timing": execution_result.timing_analysis,
                "success_indicators": execution_result.success_indicators,
            },
            # Success information
            "success": {
                "overall_score": success_result.success_score,
                "completion_score": success_result.completion_score,
                "error_score": success_result.error_score,
                "performance_score": success_result.performance_score,
                "user_feedback_score": success_result.user_feedback_score,
                "success_indicators": success_result.success_indicators,
                "failure_indicators": success_result.failure_indicators,
            },
            # Pattern metadata
            "metadata": {
                "pattern_type": "execution_intelligence",
                "version": "1.0.0",
                "extracted_at": self._get_timestamp(),
                "nodes_used": [
                    "intent_classifier",
                    "keyword_extractor",
                    "execution_analyzer",
                    "success_scorer",
                ],
            },
        }

        return pattern

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def calculate_deterministic_hash(self, data: str) -> str:
        """Calculate deterministic hash for reproducibility."""
        combined = f"{data}|pattern_assembler|v1.0.0"
        hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"sha256:{hash_bytes[:16]}"
