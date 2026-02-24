# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node Pattern Feedback Effect - Declarative effect node for session outcome recording.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - Zero custom routing logic - all behavior from handler_routing
    - Lightweight shell that delegates to handlers via container resolution
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, handlers wired externally"

Extends NodeEffect from omnibase_core for infrastructure I/O operations.
All handler routing is 100% driven by contract.yaml, not Python code.

Handler Routing Pattern:
    1. Receive ClaudeSessionOutcome event (input_model in contract)
    2. Route to record_session_outcome handler (handler_routing)
    3. Execute database I/O via handler (PostgreSQL rolling metrics)
    4. Return ModelSessionOutcomeResult (output_model in contract)

Design Decisions:
    - 100% Contract-Driven: All routing logic in YAML, not Python
    - Zero Custom Routing: Base class handles handler dispatch via contract
    - Declarative Handlers: handler_routing section defines dispatch rules
    - External DI: Handler dependencies resolved by callers/orchestrators

Node Responsibilities:
    - Define I/O model contract (ClaudeSessionOutcome -> ModelSessionOutcomeResult)
    - Delegate all execution to handlers via base class
    - NO custom logic - pure declarative shell

Related Modules:
    - contract.yaml: Handler routing and I/O model definitions
    - handlers/handler_session_outcome.py: Session outcome recording handler
    - models/: Input/output model definitions

Related Tickets:
    - OMN-1678: Rolling window metric updates for session outcomes
    - OMN-1757: Refactor to declarative pattern
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodePatternFeedbackEffect(NodeEffect):
    """Declarative effect node for recording session outcomes and pattern metrics.

    This effect node is a lightweight shell that defines the I/O contract
    for pattern feedback operations. All routing and execution logic is driven
    by contract.yaml - this class contains NO custom routing code.

    Supported Operations (defined in contract.yaml handler_routing):
        - record_session_outcome: Record session outcome and update rolling metrics

    Dependency Injection:
        The record_session_outcome handler is invoked by callers with its
        dependencies (repository protocol for database operations).
        This node contains NO instance variables for handlers or repositories.

    Example:
        ```python
        from omniintelligence.nodes.node_pattern_feedback_effect.handlers import (
            record_session_outcome,
        )

        # Handler receives dependencies directly via parameters
        result = await record_session_outcome(
            session_id=session_uuid,
            success=True,
            repository=db_connection,
        )

        if result.status == EnumOutcomeRecordingStatus.SUCCESS:
            print(f"Recorded outcome for {result.patterns_updated} patterns")
        ```
    """

    # Pure declarative shell - all behavior defined in contract.yaml


__all__ = ["NodePatternFeedbackEffect"]
