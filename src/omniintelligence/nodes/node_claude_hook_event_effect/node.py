# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Claude Hook Event Effect - Thin shell node following ONEX declarative pattern.

This node is a thin shell that delegates all processing to HandlerClaudeHookEvent.
Dependencies are injected via the handler (constructor injection pattern).

Reference:
    - OMN-1456: Unified Claude Code hook endpoint
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.node_claude_hook_event_effect.handlers import (
    HandlerClaudeHookEvent,
)
from omniintelligence.nodes.node_claude_hook_event_effect.models import (
    ModelClaudeCodeHookEvent,
    ModelClaudeHookResult,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


class NodeClaudeHookEventEffect(NodeEffect):
    """Thin shell effect node for Claude Code hook event handling.

    Delegates all processing to HandlerClaudeHookEvent.
    Dependencies are injected via the handler constructor.

    Example:
        >>> handler = HandlerClaudeHookEvent(
        ...     kafka_publisher=kafka_producer,
        ...     intent_classifier=classifier,
        ... )
        >>> node = NodeClaudeHookEventEffect(container, handler)
        >>> result = await node.execute(event)
    """

    def __init__(
        self,
        container: ModelONEXContainer,
        handler: HandlerClaudeHookEvent,
    ) -> None:
        """Initialize the effect node with handler.

        Args:
            container: ONEX dependency injection container.
            handler: Handler with injected dependencies.
        """
        super().__init__(container)
        self._handler = handler

    async def execute(self, event: ModelClaudeCodeHookEvent) -> ModelClaudeHookResult:
        """Execute by delegating to handler.

        Args:
            event: The Claude Code hook event to process.

        Returns:
            ModelClaudeHookResult with processing outcome.
        """
        return await self._handler.handle(event)


__all__ = ["NodeClaudeHookEventEffect"]
