# STUB: This node is a stub implementation. Full functionality is not yet available.
# Tracking: https://github.com/OmniNode-ai/omniintelligence/issues/6
# Status: Interface defined, implementation pending
"""Intent Classifier Compute - STUB compute node for intent classification."""
from __future__ import annotations

import warnings
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute

from omniintelligence.nodes.intent_classifier_compute.models import (
    ModelIntentClassificationInput,
    ModelIntentClassificationOutput,
)

# Issue tracking URL for this stub implementation
_STUB_TRACKING_URL = "https://github.com/OmniNode-ai/omniintelligence/issues/6"


class NodeIntentClassifierCompute(NodeCompute):
    """STUB: Pure compute node for classifying user intents.

    Attributes:
        is_stub: Class attribute indicating this is a stub implementation.

    WARNING: This is a stub implementation that does not provide full functionality.
    The node is included for forward compatibility and interface definition.

    Expected functionality when implemented:
        - Classify user intents from natural language
        - Support multi-label classification
        - Confidence scoring for classifications
    """

    is_stub: ClassVar[bool] = True

    async def compute(
        self, _input_data: ModelIntentClassificationInput
    ) -> ModelIntentClassificationOutput:
        """Compute intent classification (STUB - returns empty result).

        Args:
            _input_data: Typed input model for intent classification (unused in stub).

        Returns:
            Typed ModelIntentClassificationOutput with success=True but default values.
        """
        warnings.warn(
            f"NodeIntentClassifierCompute.compute() is a stub that returns empty "
            f"results. No actual intent classification is performed. "
            f"See {_STUB_TRACKING_URL} for progress.",
            category=RuntimeWarning,
            stacklevel=2,
        )
        # Note: metadata is None because stub status info doesn't match IntentMetadataDict
        # schema. Stub status is communicated via the warning above.
        return ModelIntentClassificationOutput(
            success=True,
            intent_category="unknown",
            confidence=0.0,
            secondary_intents=[],
            metadata=None,
        )


__all__ = ["NodeIntentClassifierCompute"]
