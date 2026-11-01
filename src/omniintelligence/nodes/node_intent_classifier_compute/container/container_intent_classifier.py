# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for the handler of node_intent_classifier_compute.

The handler is built here, the one binding site, and the node resolves it
through ``resolve_intent_classification_handler`` instead of constructing it
(OMN-21679).
"""

from __future__ import annotations

from omniintelligence.nodes.node_intent_classifier_compute.handlers import (
    HandlerIntentClassification,
)
from omniintelligence.nodes.node_intent_classifier_compute.models import (
    ModelClassificationConfig,
)


def resolve_intent_classification_handler(
    config: ModelClassificationConfig,
) -> HandlerIntentClassification:
    """Resolve the HandlerIntentClassification bound to ``config``."""
    return HandlerIntentClassification(config)


__all__ = ["resolve_intent_classification_handler"]
