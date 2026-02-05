# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Pattern Storage Effect - Declarative effect node for pattern persistence.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive pattern event (input_model in contract)
    2. Route to appropriate handler based on operation (handler_routing)
    3. Execute infrastructure I/O via handler (PostgreSQL storage)
    4. Return structured response (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - Container DI: Handler dependencies resolved via container

Node Responsibilities:
    - Define I/O model contract (ModelPatternStorageInput -> ModelPatternStoredEvent)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

The actual handler execution and routing is performed by:
    - Direct handler invocation by callers
    - Or RuntimeHostProcess for workflow coordination

Handlers receive their dependencies directly via constructor injection:
    - handle_store_pattern(input_data, pattern_store, conn)
    - handle_promote_pattern(pattern_id, to_state, reason, state_manager, conn)

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_store_pattern.py: Store pattern handler
    - handlers/handler_promote_pattern.py: Promote pattern handler
    - handlers/handler_pattern_storage.py: Operation router

Related Tickets:
    - OMN-1668: Pattern storage effect node implementation
    - OMN-1757: Refactor to declarative pattern
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodePatternStorageEffect(NodeEffect):
    """Declarative effect node for pattern storage with governance enforcement.

    This effect node is a lightweight shell that defines the I/O contract
    for pattern storage operations. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - store_pattern: Persist learned patterns with governance enforcement
        - promote_pattern: Promote pattern state (CANDIDATE -> PROVISIONAL -> VALIDATED)

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (pattern_store, state_manager, conn). This node contains NO
        instance variables for handlers or registries.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_pattern_storage_effect import (
            NodePatternStorageEffect,
            handle_store_pattern,
            handle_promote_pattern,
        )

        # Create effect node via container (pure declarative shell)
        container = ModelONEXContainer()
        effect = NodePatternStorageEffect(container)

        # Handlers are invoked directly with their dependencies
        result = await handle_store_pattern(
            input_data,
            pattern_store=pattern_store_impl,
            conn=db_conn,
        )

        # Or use RuntimeHostProcess for event-driven execution
        # which reads handler_routing from contract.yaml
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodePatternStorageEffect"]
