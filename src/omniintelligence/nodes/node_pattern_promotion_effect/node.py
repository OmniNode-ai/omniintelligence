# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Pattern Promotion Effect - Declarative effect node for pattern promotion.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive promotion check request (input_model in contract)
    2. Route to appropriate handler based on operation (handler_routing)
    3. Execute infrastructure I/O via handler (PostgreSQL queries, Kafka events)
    4. Return structured response (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - Container DI: Handler dependencies resolved via container

Node Responsibilities:
    - Define I/O model contract (ModelPromotionCheckRequest -> ModelPromotionCheckResult)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

The actual handler execution and routing is performed by:
    - Direct handler invocation by callers
    - Or RuntimeHostProcess for workflow coordination

Handlers receive their dependencies directly via parameters:
    - check_and_promote_patterns(repository, producer, ...)
    - promote_pattern(repository, producer, pattern_id, pattern_data, ...)
    - meets_promotion_criteria(pattern) - pure function

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_promotion.py: Main promotion handlers

Related Tickets:
    - OMN-1680: Auto-promote logic for provisional patterns
    - OMN-1757: Refactor to declarative pattern
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodePatternPromotionEffect(NodeEffect):
    """Declarative effect node for promoting provisional patterns to validated status.

    This effect node is a lightweight shell that defines the I/O contract
    for pattern promotion operations. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - check_and_promote: Check all provisional patterns and promote eligible ones
        - promote_pattern: Promote a single pattern with gate snapshot

    Dependency Injection:
        Handlers are invoked by callers with their dependencies
        (repository, producer, correlation_id). This node contains NO
        instance variables for handlers or registries.

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.node_pattern_promotion_effect import (
            NodePatternPromotionEffect,
            check_and_promote_patterns,
            promote_pattern,
            meets_promotion_criteria,
        )

        # Create effect node via container (pure declarative shell)
        container = ModelONEXContainer()
        effect = NodePatternPromotionEffect(container)

        # Handlers are invoked directly with their dependencies
        result = await check_and_promote_patterns(
            repository=db_conn,
            producer=kafka_producer,
            dry_run=False,
            correlation_id=correlation_id,
            topic_env_prefix="dev",
        )

        # Or use RuntimeHostProcess for event-driven execution
        # which reads handler_routing from contract.yaml
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodePatternPromotionEffect"]
