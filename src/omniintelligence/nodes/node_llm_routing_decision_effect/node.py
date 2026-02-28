# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node LLM Routing Decision Effect - Declarative effect node for Bifrost feedback loop.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

This node consumes LLM routing decision events from omniclaude's Bifrost LLM
gateway and persists routing decisions for model performance analytics.

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive ModelLlmRoutingDecisionEvent (input_model in contract)
    2. Route to process_llm_routing_decision handler (handler_routing)
    3. Execute database I/O via handler (PostgreSQL upsert to llm_routing_decisions)
    4. Publish onex.evt.omniintelligence.llm-routing-decision-processed.v1
    5. Return ModelLlmRoutingDecisionResult (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - External DI: Handler dependencies resolved by callers/orchestrators

Node Responsibilities:
    - Define I/O model contract (ModelLlmRoutingDecisionEvent -> ModelLlmRoutingDecisionResult)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_llm_routing_decision.py: LLM routing decision processing handler
    - models/: Input/output model definitions

Related Tickets:
    - OMN-2939: Bifrost feedback loop — add LLM routing decision consumer in omniintelligence
    - OMN-2740: Bifrost LLM Gateway (producer in omniclaude)
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeLlmRoutingDecisionEffect(NodeEffect):
    """Declarative effect node for processing LLM routing decision events.

    This effect node is a lightweight shell that defines the I/O contract
    for LLM routing decision processing. All routing and execution logic is
    driven by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - process_llm_routing_decision: Consume llm.routing.decision event,
          upsert record to llm_routing_decisions with idempotency on
          (session_id, correlation_id), publish processed event.

    Dependency Injection:
        The process_llm_routing_decision handler is invoked by callers with
        its dependencies (repository protocol for database operations,
        optional kafka publisher). This node contains NO instance variables
        for handlers or repositories.

    Example:
        ```python
        from omniintelligence.nodes.node_llm_routing_decision_effect.handlers import (
            process_llm_routing_decision,
        )

        # Handler receives dependencies directly via parameters
        result = await process_llm_routing_decision(
            event=llm_routing_decision_event,
            repository=db_connection,
        )

        if result.status == EnumLlmRoutingDecisionStatus.SUCCESS:
            print(f"Processed routing decision for session {result.session_id}")
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeLlmRoutingDecisionEffect"]
