# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Feedback Effect - Records session outcomes and updates rolling metrics.

This node follows the ONEX declarative pattern:
    - Thin shell effect node that delegates to handler
    - Dependencies retrieved from registry (no setters)
    - No error handling in node (propagates to caller)
    - Pattern: "Contract-driven, registry-wired dependencies"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    record_session_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    ModelSessionOutcomeRequest,
    ModelSessionOutcomeResult,
)
from omniintelligence.nodes.node_pattern_feedback_effect.registry import (
    RegistryPatternFeedbackEffect,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodePatternFeedbackEffect(NodeEffect):
    """Effect node for recording session outcomes and updating pattern metrics.

    Thin shell that delegates to record_session_outcome handler.
    Repository dependency is retrieved from RegistryPatternFeedbackEffect.
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)

    async def execute(
        self, request: ModelSessionOutcomeRequest
    ) -> ModelSessionOutcomeResult:
        """Execute the effect node to record session outcome.

        Delegates to record_session_outcome handler with registry-wired repository.
        """
        repository = RegistryPatternFeedbackEffect.get_repository()
        return await record_session_outcome(
            session_id=request.session_id,
            success=request.success,
            failure_reason=request.failure_reason,
            repository=repository,
            correlation_id=request.correlation_id,
        )


__all__ = ["NodePatternFeedbackEffect"]
