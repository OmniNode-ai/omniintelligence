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
    IntentClassificationComputeError,
    IntentClassificationValidationError,
    classify_intent,
)
from omniintelligence.nodes.intent_classifier_compute.models import (
    IntentMetadataDict,
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
    SecondaryIntentDict,
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

    Note:
        This node follows the declarative node pattern - no custom __init__ is needed.
        The base NodeCompute class handles initialization.
    """

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

            # Extract context parameters with defaults
            context = input_data.context or {}
            confidence_threshold = context.get("confidence_threshold", 0.5)
            max_intents = context.get("max_intents", 5)

            # Call pure handler function for TF-IDF classification
            result = classify_intent(
                content=input_data.content,
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

            # Build metadata with classification details
            metadata: IntentMetadataDict = {
                "status": "completed",
                "classifier_version": "1.0.0",
                "classification_time_ms": processing_time,
                "threshold_used": confidence_threshold,
                "raw_scores": result.get("all_scores", {}),
            }

            return ModelIntentClassificationOutput(
                success=True,
                intent_category=result["intent_category"],
                confidence=result["confidence"],
                secondary_intents=secondary_intents,
                metadata=metadata,
            )

        except IntentClassificationValidationError as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            return ModelIntentClassificationOutput(
                success=False,
                intent_category="unknown",
                confidence=0.0,
                secondary_intents=[],
                metadata=IntentMetadataDict(
                    status="validation_error",
                    message=str(e),
                    classification_time_ms=processing_time,
                ),
            )

        except IntentClassificationComputeError as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            return ModelIntentClassificationOutput(
                success=False,
                intent_category="unknown",
                confidence=0.0,
                secondary_intents=[],
                metadata=IntentMetadataDict(
                    status="compute_error",
                    message=str(e),
                    classification_time_ms=processing_time,
                ),
            )

        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "Unexpected error in intent classification: %s: %s",
                type(e).__name__,
                e,
            )
            return ModelIntentClassificationOutput(
                success=False,
                intent_category="unknown",
                confidence=0.0,
                secondary_intents=[],
                metadata=IntentMetadataDict(
                    status="unexpected_error",
                    message=f"Unexpected error: {type(e).__name__}: {e}",
                    classification_time_ms=processing_time,
                ),
            )


__all__ = ["NodeIntentClassifierCompute"]
