# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Smoke test for intent_classifier_compute dependency importability.

The ``_classify_intent`` function in handler_claude_event.py uses a lazy
import to avoid circular imports:

    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelIntentClassificationInput,
    )

This lazy import creates a runtime landmine: if the node is ever accidentally
removed or renamed, the failure only surfaces at classification time rather
than at boot. This smoke test catches that regression at test time.

Reference:
    - OMN-1492: Add smoke test for intent_classifier_compute dependency
    - OMN-1456: claude_hook_event_effect node (PR #19)
"""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.unit
def test_intent_classifier_compute_import() -> None:
    """Verify intent_classifier_compute node exists and is importable.

    This test catches the case where the node is accidentally removed or
    renamed, which would otherwise only surface as a runtime error during
    intent classification, not at boot.
    """
    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelIntentClassificationInput,
    )

    assert ModelIntentClassificationInput is not None


@pytest.mark.unit
def test_intent_classifier_compute_model_fields() -> None:
    """Verify ModelIntentClassificationInput has expected fields.

    Guards against schema regressions that would break the lazy import
    call site in handler_claude_event._classify_intent().
    """
    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelIntentClassificationInput,
    )

    fields = ModelIntentClassificationInput.model_fields
    assert "content" in fields, (
        "ModelIntentClassificationInput must have 'content' field"
    )
    assert "correlation_id" in fields, (
        "ModelIntentClassificationInput must have 'correlation_id' field"
    )


@pytest.mark.unit
def test_intent_classifier_compute_instantiation() -> None:
    """Verify ModelIntentClassificationInput can be instantiated with required fields.

    Ensures the model's constructor signature matches what handler_claude_event
    expects when building input_data.
    """
    from omniintelligence.nodes.node_intent_classifier_compute.models import (
        ModelIntentClassificationInput,
    )

    correlation_id = uuid.uuid4()
    instance = ModelIntentClassificationInput(
        content="How do I fix this import error?",
        correlation_id=correlation_id,
        context={"session_id": "test-session-id"},
    )

    assert instance.content == "How do I fix this import error?"
    assert instance.correlation_id == correlation_id
