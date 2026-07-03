# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Node Cursor Hook Event Effect - Declarative effect node for Cursor IDE hooks.

This node is the Cursor peer of NodeClaudeHookEventEffect. It defines the I/O
contract for Cursor hook event processing. All routing/execution is driven by
contract.yaml; the heavy processing is reused from the shared intelligence
pipeline via event-type translation (see handler_cursor_event).

Design Decisions:
    - 100% Contract-Driven: routing in YAML, not Python
    - Direct Dependency Injection: handler dependencies passed at call site
    - NO custom logic: pure declarative shell
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeCursorHookEventEffect(NodeEffect):
    """Declarative effect node for Cursor IDE hook event handling.

    A lightweight shell that defines the I/O contract for Cursor hook event
    processing. Routing and execution remain contract-defined in contract.yaml.

    Supported Operations (defined in contract.yaml handler_routing):
        - beforeSubmitPrompt: Classify intent, emit to Kafka
        - stop: Trigger pattern learning
        - afterFileEdit, beforeShellExecution: tool-use handling / no-op
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeCursorHookEventEffect"]
