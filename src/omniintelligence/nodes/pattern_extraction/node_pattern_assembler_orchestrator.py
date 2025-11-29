#!/usr/bin/env python3
"""
Pattern Assembler Orchestrator Node - ONEX Compliant

Orchestrates pattern extraction pipeline by coordinating all compute nodes.
Part of Track 2 Intelligence Hook System (Track 3-1.4).

Generated with DeepSeek-Lite via vLLM
Author: Archon Intelligence Team
Date: 2025-10-02
"""

import hashlib
import uuid
from typing import Any, Dict, List

from pydantic import BaseModel, Field

# Import compute nodes from omniintelligence package
from omniintelligence.nodes.pattern_extraction.node_context_keyword_extractor_compute import (
    ModelKeywordExtractionInput,
    ModelKeywordExtractionOutput,
    NodeContextKeywordExtractorCompute,
)
from omniintelligence.nodes.pattern_extraction.node_execution_trace_parser_compute import (
    ModelTraceParsingInput,
    ModelTraceParsingOutput,
    NodeExecutionTraceParserCompute,
)
from omniintelligence.nodes.pattern_extraction.node_intent_classifier_compute import (
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
    NodeIntentClassifierCompute,
)
from omniintelligence.nodes.pattern_extraction.node_success_criteria_matcher_compute import (
    ModelSuccessMatchingInput,
    ModelSuccessMatchingOutput,
    NodeSuccessCriteriaMatcherCompute,
)


# ============================================================================
# Models
# ============================================================================


class ModelPatternExtractionInput(BaseModel):
    """Input state for pattern extraction orchestration."""

    request_text: str = Field(..., description="Original user request text")
    execution_trace: str = Field(..., description="Execution trace data")
    execution_result: str = Field(..., description="Execution result text")
    success_criteria: List[str] = Field(
        default_factory=list, description="Success criteria for validation"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing",
    )
    trace_format: str = Field(
        default="json", description="Trace format: json, log, structured"
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

    # Trace parsing results
    trace_events: List[Dict[str, Any]] = Field(
        default_factory=list, description="Parsed trace events"
    )
    execution_flow: List[str] = Field(
        default_factory=list, description="Execution flow sequence"
    )
    timing_summary: Dict[str, float] = Field(
        default_factory=dict, description="Timing statistics"
    )

    # Success matching results
    success_status: bool = Field(..., description="Overall success determination")
    success_confidence: float = Field(..., description="Success match confidence")
    matched_criteria: List[str] = Field(
        default_factory=list, description="Matched success criteria"
    )

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
    3. Trace Parsing (NodeCompute)
    4. Success Matching (NodeCompute)

    ONEX Patterns:
    - Workflow coordination
    - Correlation ID propagation
    - Parallel execution where possible
    - Error isolation and graceful degradation
    """

    def __init__(self) -> None:
        """Initialize orchestrator with compute nodes."""
        # Initialize all compute nodes
        self.intent_classifier = NodeIntentClassifierCompute()
        self.keyword_extractor = NodeContextKeywordExtractorCompute()
        self.trace_parser = NodeExecutionTraceParserCompute()
        self.success_matcher = NodeSuccessCriteriaMatcherCompute()

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
        import time

        start_time = time.time()

        try:
            # Propagate correlation ID to all operations
            correlation_id = input_state.correlation_id

            # ================================================================
            # Phase 1: Parallel execution of independent nodes
            # ================================================================

            # These operations can run in parallel as they don't depend on each other
            import asyncio

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

            trace_task = asyncio.create_task(
                self._parse_trace(
                    trace_data=input_state.execution_trace,
                    trace_format=input_state.trace_format,
                    correlation_id=correlation_id,
                )
            )

            # Wait for all parallel operations to complete
            intent_result, keyword_result, trace_result = await asyncio.gather(
                intent_task, keyword_task, trace_task
            )

            # ================================================================
            # Phase 2: Sequential execution (depends on Phase 1)
            # ================================================================

            # Success matching depends on having success criteria
            success_result = await self._match_success_criteria(
                execution_result=input_state.execution_result,
                success_criteria=input_state.success_criteria,
                correlation_id=correlation_id,
            )

            # ================================================================
            # Phase 3: Pattern Assembly
            # ================================================================

            assembled_pattern = self._assemble_pattern(
                intent_result=intent_result,
                keyword_result=keyword_result,
                trace_result=trace_result,
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
                # Trace
                trace_events=trace_result.events,
                execution_flow=trace_result.execution_flow,
                timing_summary=trace_result.timing_summary,
                # Success
                success_status=success_result.overall_success,
                success_confidence=success_result.overall_confidence,
                matched_criteria=success_result.matched_criteria,
                # Assembly
                assembled_pattern=assembled_pattern,
                # Metadata
                metadata={
                    "processing_time_ms": processing_time,
                    "phases_completed": 3,
                    "nodes_executed": 4,
                    "parallel_execution": True,
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
                trace_events=[],
                execution_flow=[],
                timing_summary={},
                success_status=False,
                success_confidence=0.0,
                matched_criteria=[],
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
            max_keywords=10,
            include_phrases=True,
        )
        return await self.keyword_extractor.execute_compute(input_state)

    async def _parse_trace(
        self, trace_data: str, trace_format: str, correlation_id: str
    ) -> ModelTraceParsingOutput:
        """Coordinate with trace parser node."""
        input_state = ModelTraceParsingInput(
            trace_data=trace_data,
            correlation_id=correlation_id,
            trace_format=trace_format,
            extract_errors=True,
            extract_timing=True,
        )
        return await self.trace_parser.execute_compute(input_state)

    async def _match_success_criteria(
        self, execution_result: str, success_criteria: List[str], correlation_id: str
    ) -> ModelSuccessMatchingOutput:
        """Coordinate with success criteria matcher node."""
        input_state = ModelSuccessMatchingInput(
            execution_result=execution_result,
            success_criteria=success_criteria,
            correlation_id=correlation_id,
            fuzzy_threshold=0.7,
            require_all_criteria=False,  # OR mode
        )
        return await self.success_matcher.execute_compute(input_state)

    # ========================================================================
    # Pattern Assembly Logic
    # ========================================================================

    def _assemble_pattern(
        self,
        intent_result: ModelIntentClassificationOutput,
        keyword_result: ModelKeywordExtractionOutput,
        trace_result: ModelTraceParsingOutput,
        success_result: ModelSuccessMatchingOutput,
    ) -> Dict[str, Any]:
        """
        Assemble comprehensive pattern from all node results.

        Combines results from all compute nodes into a unified pattern
        representation suitable for pattern storage and analysis.

        Args:
            intent_result: Intent classification result
            keyword_result: Keyword extraction result
            trace_result: Trace parsing result
            success_result: Success matching result

        Returns:
            Dictionary with assembled pattern data
        """
        pattern = {
            # Intent information
            "intent": {
                "primary": intent_result.intent,
                "confidence": intent_result.confidence,
                "all_scores": intent_result.all_scores,
            },
            # Context information
            "context": {
                "keywords": keyword_result.keywords,
                "phrases": keyword_result.phrases,
                "keyword_scores": keyword_result.keyword_scores,
            },
            # Execution information
            "execution": {
                "flow": trace_result.execution_flow,
                "events": trace_result.events[:5],  # Top 5 events for brevity
                "timing": trace_result.timing_summary,
                "errors": trace_result.error_events,
            },
            # Success information
            "success": {
                "status": success_result.overall_success,
                "confidence": success_result.overall_confidence,
                "matched_criteria": success_result.matched_criteria,
                "unmatched_criteria": success_result.unmatched_criteria,
            },
            # Pattern metadata
            "metadata": {
                "pattern_type": "execution_intelligence",
                "version": "1.0.0",
                "extracted_at": self._get_timestamp(),
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


# ============================================================================
# Unit Test Helpers
# ============================================================================


async def test_pattern_assembler() -> None:
    """Test pattern assembler orchestrator with complete pipeline."""
    orchestrator = NodePatternAssemblerOrchestrator()

    # Test 1: Complete pattern extraction
    import json

    test_input = ModelPatternExtractionInput(
        request_text="Generate async function for database connection with error handling",
        execution_trace=json.dumps(
            {
                "events": [
                    {
                        "type": "function_call",
                        "function": "generate_function",
                        "duration_ms": 45.2,
                    },
                    {
                        "type": "function_call",
                        "function": "add_error_handling",
                        "duration_ms": 12.5,
                    },
                    {"type": "status", "status": "completed", "duration_ms": 5.1},
                ]
            }
        ),
        execution_result="Function generated successfully with async/await pattern and try/except error handling",
        success_criteria=["generated", "async", "error handling"],
        trace_format="json",
    )

    result = await orchestrator.execute_orchestration(test_input)

    print("Test 1 - Complete Pattern Extraction:")
    print(f"  Intent: {result.intent} (confidence: {result.intent_confidence})")
    print(f"  Keywords: {result.keywords}")
    print(f"  Phrases: {result.phrases}")
    print(f"  Execution flow: {result.execution_flow}")
    print(f"  Success: {result.success_status}")
    print(f"  Matched criteria: {result.matched_criteria}")
    print(f"  Processing time: {result.metadata.get('processing_time_ms')}ms")
    print("\n  Assembled Pattern:")
    print(f"    - Intent: {result.assembled_pattern.get('intent')}")
    print(
        f"    - Context: {len(result.assembled_pattern.get('context', {}).get('keywords', []))} keywords"
    )
    print(
        f"    - Execution: {len(result.assembled_pattern.get('execution', {}).get('events', []))} events"
    )
    print(f"    - Success: {result.assembled_pattern.get('success', {}).get('status')}")

    assert result.intent == "code_generation"
    assert result.success_status is True
    assert len(result.keywords) > 0

    # Test 2: Error scenario
    test_input = ModelPatternExtractionInput(
        request_text="Debug authentication failure",
        execution_trace="",  # Empty trace
        execution_result="Error: Authentication token expired",
        success_criteria=["success", "authenticated"],
    )

    result = await orchestrator.execute_orchestration(test_input)

    print("\nTest 2 - Error Scenario:")
    print(f"  Intent: {result.intent}")
    print(f"  Success: {result.success_status}")
    print(f"  Processing time: {result.metadata.get('processing_time_ms')}ms")

    assert result.intent == "debugging"
    assert result.success_status is False

    print("\nAll tests passed!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_pattern_assembler())
