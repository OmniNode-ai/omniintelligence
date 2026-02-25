# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node Pattern Lifecycle Effect - Declarative effect node for pattern transitions.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

This node applies pattern status transition projections to the database. It is
the ONLY code path that may update learned_patterns.status.

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive transition intent (input_model in contract)
    2. Route to apply_transition handler (handler_routing)
    3. Execute infrastructure I/O via handler (PostgreSQL update + audit)
    4. Return structured response (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - Container DI: Handler dependencies resolved via container

Node Responsibilities:
    - Define I/O model contract (ModelPayloadUpdatePatternStatus -> ModelTransitionResult)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

The actual handler execution and routing is performed by:
    - Direct handler invocation by callers
    - Or RuntimeHostProcess for workflow coordination

Handlers receive their dependencies directly via constructor injection:
    - apply_transition(repository, idempotency_store, producer, ...)

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_transition.py: Apply transition handler

Related Tickets:
    - OMN-1805: Pattern lifecycle effect node implementation
    - OMN-1757: Refactor to declarative pattern
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodePatternLifecycleEffect(NodeEffect):
    """Declarative effect node for pattern lifecycle status transitions.

    This effect node is a lightweight shell that defines the I/O contract
    for pattern lifecycle transitions. All routing and execution logic is
    driven by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - apply_transition: Apply pattern status transition with idempotency,
          status guard, and atomic audit trail

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (repository, idempotency_store, producer). This node contains NO
        instance variables for handlers or registries.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_pattern_lifecycle_effect import (
            NodePatternLifecycleEffect,
            apply_transition,
            ModelTransitionResult,
        )

        # Create effect node via container (pure declarative shell)
        container = ModelONEXContainer()
        effect = NodePatternLifecycleEffect(container)

        # Handlers are invoked directly with their dependencies
        result = await apply_transition(
            repository=db_conn,
            idempotency_store=idempotency_impl,
            producer=kafka_producer,  # Optional, can be None
            request_id=request_id,
            correlation_id=correlation_id,
            pattern_id=pattern_id,
            from_status="provisional",
            to_status="validated",
            trigger="promote",
            transition_at=datetime.now(UTC),
        )

        # Or use RuntimeHostProcess for event-driven execution
        # which reads handler_routing from contract.yaml
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodePatternLifecycleEffect"]
