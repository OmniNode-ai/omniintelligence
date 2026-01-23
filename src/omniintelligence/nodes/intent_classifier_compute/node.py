"""Intent Classifier Compute - Pure compute node for TF-IDF intent classification.

This node performs deterministic intent classification on text content using
a TF-IDF based algorithm. It matches input against predefined intent patterns
across 9 categories (6 original + 3 intelligence-focused).

Key characteristics:
    - Pure computation: no HTTP calls, no LLM, no side effects
    - Deterministic: same input always produces same output
    - Multi-label support: returns secondary intents above threshold
    - Configurable: confidence threshold and max intents via context
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.intent_classifier_compute.handlers import (
    DEFAULT_CLASSIFICATION_CONFIG,
    IntentClassificationComputeError,
    IntentClassificationValidationError,
    classify_intent,
)
from omniintelligence.nodes.intent_classifier_compute.models import (
    IntentMetadataDict,
    ModelClassificationConfig,
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
    SecondaryIntentDict,
)


def _build_error_response(
    start_time: float,
    status: str,
    message: str,
    *,
    error_code: str | None = None,
    error_type: str | None = None,
) -> ModelIntentClassificationOutput:
    """Build standardized error response with timing and exception details.

    Args:
        start_time: The perf_counter timestamp when processing started.
        status: Error status type (e.g., "validation_error", "compute_error").
        message: Human-readable error message.
        error_code: Contract-defined error code (e.g., "INTENT_001") for traceability.
        error_type: Exception class name for debugging context.

    Returns:
        ModelIntentClassificationOutput configured for error state.
    """
    processing_time = (time.perf_counter() - start_time) * 1000
    return ModelIntentClassificationOutput(
        success=False,
        intent_category="unknown",
        confidence=0.0,
        secondary_intents=[],
        keywords=[],  # Contract alignment: operations.classify_intent.output_fields.keywords
        processing_time_ms=processing_time,  # Contract alignment: operations.classify_intent.output_fields.processing_time_ms
        metadata=IntentMetadataDict(
            status=status,
            message=message,
            classification_time_ms=processing_time,
            error_code=error_code,
            error_type=error_type,
        ),
    )


class NodeIntentClassifierCompute(
    NodeCompute[ModelIntentClassificationInput, ModelIntentClassificationOutput]
):
    """Pure compute node for classifying user intents using TF-IDF.

    This node analyzes text content to determine user intent across 9 categories:
        - code_generation: Generate, create, implement, write code
        - debugging: Fix, troubleshoot, diagnose errors
        - refactoring: Improve, optimize, restructure code
        - testing: Test, validate, verify functionality
        - documentation: Document, explain, annotate code
        - analysis: Analyze, review, inspect code
        - pattern_learning: Learn, train, extract patterns
        - quality_assessment: Assess, score, validate quality
        - semantic_analysis: Analyze semantics, extract concepts

    The node follows the ONEX pure shell pattern, delegating computation
    to side-effect-free handler functions.

    Attributes:
        _classification_config: Configuration for TF-IDF classification.
            Uses default config; can be overridden in subclasses or via contract.

    Note:
        This node follows the declarative node pattern - no custom __init__ is needed.
        The base NodeCompute class handles initialization.
    """

    # Use default config - can be overridden in subclasses or via contract loading
    _classification_config: ModelClassificationConfig = DEFAULT_CLASSIFICATION_CONFIG

    async def compute(
        self, input_data: ModelIntentClassificationInput
    ) -> ModelIntentClassificationOutput:
        """Classify intent from text content using TF-IDF algorithm.

        Follows ONEX pure shell pattern - delegates to handler for computation.

        Args:
            input_data: Typed input model containing content and classification context.

        Returns:
            ModelIntentClassificationOutput with primary intent, confidence,
            secondary intents (if multi-label), and classification metadata.
        """
        start_time = time.perf_counter()

        try:
            # Validate input content
            if not input_data.content or not input_data.content.strip():
                raise IntentClassificationValidationError("Content cannot be empty")

            # Extract context parameters - use None to fall through to config defaults
            context = input_data.context or {}
            confidence_threshold = context.get("confidence_threshold")
            max_intents = context.get("max_intents")

            # Call pure handler function for TF-IDF classification
            # Handler applies config defaults when parameters are None
            result = classify_intent(
                content=input_data.content,
                config=self._classification_config,  # Pass explicit config
                confidence_threshold=confidence_threshold,
                multi_label=True,  # Always compute secondary intents
                max_intents=max_intents,
            )

            processing_time = (time.perf_counter() - start_time) * 1000

            # Map secondary intents from handler to typed output
            secondary_intents: list[SecondaryIntentDict] = []
            for intent in result.get("secondary_intents", []):
                # Extract values with type-safe defaults
                intent_category_raw = intent.get("intent_category", "")
                confidence_raw = intent.get("confidence", 0.0)
                keywords_raw = intent.get("keywords", [])

                secondary_intents.append(
                    SecondaryIntentDict(
                        intent_category=str(intent_category_raw),
                        confidence=float(confidence_raw)
                        if isinstance(confidence_raw, (int, float))
                        else 0.0,
                        keywords=list(keywords_raw)
                        if isinstance(keywords_raw, list)
                        else [],
                    )
                )

            # Determine actual threshold used (config default if None was passed)
            actual_threshold = (
                confidence_threshold
                if confidence_threshold is not None
                else self._classification_config.default_confidence_threshold
            )

            # Build metadata with classification details
            metadata: IntentMetadataDict = {
                "status": "completed",
                "classifier_version": self._classification_config.classifier_version,
                "classification_time_ms": processing_time,
                "threshold_used": actual_threshold,
                "raw_scores": result.get("all_scores", {}),
            }

            # Extract primary intent keywords from handler result
            primary_keywords: list[str] = result.get("keywords", [])

            return ModelIntentClassificationOutput(
                success=True,
                intent_category=result["intent_category"],
                confidence=result["confidence"],
                secondary_intents=secondary_intents,
                keywords=primary_keywords,  # Contract alignment: operations.classify_intent.output_fields.keywords
                processing_time_ms=processing_time,  # Contract alignment: operations.classify_intent.output_fields.processing_time_ms
                metadata=metadata,
            )

        except IntentClassificationValidationError as e:
            return _build_error_response(
                start_time,
                "validation_error",
                str(e),
                error_code=e.code,
                error_type=type(e).__name__,
            )

        except IntentClassificationComputeError as e:
            return _build_error_response(
                start_time,
                "compute_error",
                str(e),
                error_code=e.code,
                error_type=type(e).__name__,
            )

        except Exception as e:
            logger.exception(
                "Unexpected error in intent classification: %s: %s",
                type(e).__name__,
                e,
            )
            return _build_error_response(
                start_time,
                "unexpected_error",
                f"Unexpected error: {type(e).__name__}: {e}",
                error_code=None,
                error_type=type(e).__name__,
            )


__all__ = ["NodeIntentClassifierCompute"]
