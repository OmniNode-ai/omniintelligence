# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Feedback Effect - Records session outcomes and updates rolling metrics.

This node follows the ONEX declarative pattern:
    - EFFECT node for database writes (pattern_injections, learned_patterns)
    - Implements decay approximation for rolling-20 window metrics
    - Lightweight shell that delegates to handlers via dependency injection
    - Pattern: "Contract-driven, handlers wired externally"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
    ProtocolPatternRepository,
    record_session_outcome,
)
from omniintelligence.nodes.node_pattern_feedback_effect.models import (
    EnumOutcomeRecordingStatus,
    ModelSessionOutcomeRequest,
    ModelSessionOutcomeResult,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodePatternFeedbackEffect(NodeEffect):
    """Effect node for recording session outcomes and updating pattern metrics."""

    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        self._repository: ProtocolPatternRepository | None = None

    def set_repository(self, repository: ProtocolPatternRepository) -> None:
        """Inject the pattern repository (database adapter)."""
        self._repository = repository

    @property
    def has_repository(self) -> bool:
        """Check if repository is configured."""
        return self._repository is not None

    async def execute(
        self, request: ModelSessionOutcomeRequest
    ) -> ModelSessionOutcomeResult:
        """Execute the effect node to record session outcome."""
        if self._repository is None:
            return ModelSessionOutcomeResult(
                status=EnumOutcomeRecordingStatus.ERROR,
                session_id=request.session_id,
                error_message="Repository not configured",
            )

        try:
            return await record_session_outcome(
                session_id=request.session_id,
                success=request.success,
                failure_reason=request.failure_reason,
                repository=self._repository,
                correlation_id=request.correlation_id,
            )
        except Exception as e:
            return ModelSessionOutcomeResult(
                status=EnumOutcomeRecordingStatus.ERROR,
                session_id=request.session_id,
                error_message=str(e),
            )


__all__ = ["NodePatternFeedbackEffect"]
