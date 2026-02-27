# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node Routing Feedback Effect - Declarative effect node for routing feedback processing.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

This node consumes routing-outcome-raw events from omniclaude's session-end hook
and persists idempotent upsert records to routing_feedback_scores table.

OMN-2935: Updated to subscribe to onex.evt.omniclaude.routing-outcome-raw.v1
(was: onex.evt.omniclaude.routing-feedback.v1 — deprecated).

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive ModelSessionRawOutcomePayload (input_model in contract)
    2. Route to process_routing_feedback handler (handler_routing)
    3. Execute database I/O via handler (PostgreSQL upsert to routing_feedback_scores)
    4. Publish onex.evt.omniintelligence.routing-feedback-processed.v1
    5. Return ModelRoutingFeedbackResult (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - External DI: Handler dependencies resolved by callers/orchestrators

Node Responsibilities:
    - Define I/O model contract (ModelSessionRawOutcomePayload -> ModelRoutingFeedbackResult)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_routing_feedback.py: Routing feedback processing handler
    - models/: Input/output model definitions

Related Tickets:
    - OMN-2366: Add routing.feedback consumer in omniintelligence (orphan topic)
    - OMN-2356: Session-end hook routing feedback producer (omniclaude)
    - OMN-2935: Fix routing feedback loop — subscribe to routing-outcome-raw.v1
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeRoutingFeedbackEffect(NodeEffect):
    """Declarative effect node for processing routing feedback events.

    This effect node is a lightweight shell that defines the I/O contract
    for routing feedback processing. All routing and execution logic is
    driven by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - process_routing_feedback: Consume routing-outcome-raw event, upsert
          record to routing_feedback_scores with idempotency on session_id,
          publish processed event.

    Dependency Injection:
        The process_routing_feedback handler is invoked by callers with
        its dependencies (repository protocol for database operations,
        optional kafka publisher). This node contains NO instance variables
        for handlers or repositories.

    Example:
        ```python
        from omniintelligence.nodes.node_routing_feedback_effect.handlers import (
            process_routing_feedback,
        )

        # Handler receives dependencies directly via parameters
        result = await process_routing_feedback(
            event=routing_feedback_event,
            repository=db_connection,
        )

        if result.status == EnumRoutingFeedbackStatus.SUCCESS:
            print(f"Processed routing feedback for session {result.session_id}")
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeRoutingFeedbackEffect"]
