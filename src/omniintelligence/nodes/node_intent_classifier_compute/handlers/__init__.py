# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pure computation handlers for intent classification and semantic analysis.

Each handler accepts a typed request through ``handle``. Configuration for the
orchestrating HandlerIntentClassification is injected through its constructor.

Usage:
    from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
        HandlerIntentClassifier,
        HandlerSemanticAnalysis,
        HandlerSemanticIntentBoost,
        ModelSemanticIntentBoostRequest,
    )
    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelAnalyzeSemanticsRequest,
        ModelClassifyIntentRequest,
    )

    result = HandlerIntentClassifier().handle(
        ModelClassifyIntentRequest(content="Create a REST API endpoint")
    )
    semantic_result = HandlerSemanticAnalysis().handle(
        ModelAnalyzeSemanticsRequest(content="Create a REST API endpoint")
    )
    boosts = HandlerSemanticIntentBoost().handle(
        ModelSemanticIntentBoostRequest(semantic_result=semantic_result)
    )
"""

from typing import TYPE_CHECKING

from omniintelligence.nodes.node_intent_classifier_compute.handlers.exceptions import (
    IntentClassificationComputeError,
    IntentClassificationError,
    IntentClassificationValidationError,
    SemanticAnalysisError,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification import (
    DEFAULT_CLASSIFICATION_CONFIG,
    INTENT_PATTERNS,
    EnumIntentCategory,
    HandlerIntentClassification,
    HandlerIntentClassifier,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_langextract import (
    DEFAULT_SEMANTIC_CONFIG,
    EnumSemanticDomain,
    HandlerSemanticAnalysis,
    HandlerSemanticIntentBoost,
    ModelSemanticIntentBoostRequest,
    SemanticResult,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_typed_classification import (
    DEFAULT_TYPED_CONFIDENCE_THRESHOLD,
    HandlerTypedClassification,
)

# ---------------------------------------------------------------------------
# Lazy re-export of the adaptive intent backend (OMN-14176)
# ---------------------------------------------------------------------------
# `handler_adaptive_classification` imports `adaptive_classifier`, which pulls
# torch + transformers. Those live in the opt-in, non-default `rl` dependency
# group, so importing THIS package must stay torch-free. The adaptive backend is
# NOT on the node's runtime path (TF-IDF via `HandlerIntentClassification` is) —
# only its unit tests exercise it. These symbols resolve lazily on first access
# via module __getattr__ (PEP 562); torch is imported only if something actually
# requests an adaptive symbol.
if TYPE_CHECKING:
    from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_adaptive_classification import (
        UNKNOWN_CONFIDENCE_THRESHOLD,
        AdaptiveClassificationResult,
        classify_intent_adaptive,
        get_classifier_version,
        reset_classifier,
    )

_LAZY_ADAPTIVE_EXPORTS = frozenset(
    {
        "UNKNOWN_CONFIDENCE_THRESHOLD",
        "AdaptiveClassificationResult",
        "classify_intent_adaptive",
        "get_classifier_version",
        "reset_classifier",
    }
)


def __getattr__(name: str) -> object:
    """Lazily resolve adaptive-backend symbols (PEP 562).

    Keeps ``import ...handlers`` torch-free: importing the adaptive handler (and
    thus ``adaptive_classifier``/torch) happens only when one of the adaptive
    symbols is actually accessed.
    """
    if name in _LAZY_ADAPTIVE_EXPORTS:
        from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
            handler_adaptive_classification,
        )

        return getattr(handler_adaptive_classification, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AdaptiveClassificationResult",
    "DEFAULT_CLASSIFICATION_CONFIG",
    "DEFAULT_SEMANTIC_CONFIG",
    "DEFAULT_TYPED_CONFIDENCE_THRESHOLD",
    "EnumIntentCategory",
    "EnumSemanticDomain",
    "HandlerIntentClassification",
    "HandlerIntentClassifier",
    "HandlerSemanticAnalysis",
    "HandlerSemanticIntentBoost",
    "HandlerTypedClassification",
    "INTENT_PATTERNS",
    "IntentClassificationComputeError",
    "IntentClassificationError",
    "IntentClassificationValidationError",
    "ModelSemanticIntentBoostRequest",
    "SemanticAnalysisError",
    "SemanticResult",
    "UNKNOWN_CONFIDENCE_THRESHOLD",
    "classify_intent_adaptive",
    "get_classifier_version",
    "reset_classifier",
]
