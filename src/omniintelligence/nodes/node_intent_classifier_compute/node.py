"""Intent Classifier Compute - Pure compute node for TF-IDF intent classification.

This node performs deterministic intent classification on text content using
a TF-IDF based algorithm. It matches input against predefined intent patterns
across 14 categories (9 original + 5 domain-specific).

Key characteristics:
    - Pure computation: no HTTP calls, no LLM, no side effects
    - Deterministic: same input always produces same output
    - Multi-label support: returns secondary intents above threshold
    - Thin shell pattern: delegates ALL logic to handler

ONEX Compliance:
    - Declarative node pattern: no try/except, no logging in node
    - Handler owns timing, error handling, and logging
    - Node is pure delegation shell (~30 lines)
"""

from __future__ import annotations

from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    DEFAULT_CLASSIFICATION_CONFIG,
    handle_intent_classification,
)
from omniintelligence.nodes.node_intent_classifier_compute.models import (
    ModelClassificationConfig,
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
)


class NodeIntentClassifierCompute(
    NodeCompute[ModelIntentClassificationInput, ModelIntentClassificationOutput]
):
    """Pure compute node for classifying user intents using TF-IDF.

    This node follows the ONEX thin shell pattern - it contains no logic,
    no error handling, no logging. All computation is delegated to the handler.
    """

    is_stub: ClassVar[bool] = True

    _classification_config: ModelClassificationConfig = DEFAULT_CLASSIFICATION_CONFIG

    async def compute(
        self, input_data: ModelIntentClassificationInput
    ) -> ModelIntentClassificationOutput:
        """Classify intent from text content using TF-IDF algorithm.

        Thin shell delegation - handler owns timing, error handling, logging.
        """
        return handle_intent_classification(
            input_data=input_data,
            config=self._classification_config,
        )


__all__ = ["NodeIntentClassifierCompute"]
