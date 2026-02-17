# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Node Enforcement Feedback Effect - Declarative effect node for enforcement feedback.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

This node consumes pattern enforcement events from omniclaude's PostToolUse
hook and applies conservative confidence adjustments to violated patterns.

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive ModelEnforcementEvent (input_model in contract)
    2. Route to process_enforcement_feedback handler (handler_routing)
    3. Execute database I/O via handler (PostgreSQL quality_score update)
    4. Return ModelEnforcementFeedbackResult (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - External DI: Handler dependencies resolved by callers/orchestrators

Node Responsibilities:
    - Define I/O model contract (ModelEnforcementEvent -> ModelEnforcementFeedbackResult)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_enforcement_feedback.py: Enforcement feedback handler
    - models/: Input/output model definitions

Related Tickets:
    - OMN-2270: Enforcement feedback loop for pattern confidence adjustment
    - OMN-2263: PostToolUse pattern enforcement hook (producer)
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeEnforcementFeedbackEffect(NodeEffect):
    """Declarative effect node for processing enforcement feedback events.

    This effect node is a lightweight shell that defines the I/O contract
    for enforcement feedback processing. All routing and execution logic is
    driven by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - process_enforcement_feedback: Process enforcement event and apply
          conservative confidence adjustments to violated patterns.

    Dependency Injection:
        The process_enforcement_feedback handler is invoked by callers with
        its dependencies (repository protocol for database operations).
        This node contains NO instance variables for handlers or repositories.

    Example:
        ```python
        from omniintelligence.nodes.node_enforcement_feedback_effect.handlers import (
            process_enforcement_feedback,
        )

        # Handler receives dependencies directly via parameters
        result = await process_enforcement_feedback(
            event=enforcement_event,
            repository=db_connection,
        )

        if result.status == EnumEnforcementFeedbackStatus.SUCCESS:
            print(f"Applied {len(result.adjustments)} adjustments")
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodeEnforcementFeedbackEffect"]
