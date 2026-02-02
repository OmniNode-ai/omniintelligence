"""Intelligence Reducer - FSM-driven declarative reducer.

This reducer follows the ONEX declarative pattern:
    - DECLARATIVE reducer driven by contract.yaml
    - Zero custom routing logic - all behavior from FSM state_machine
    - Lightweight shell that delegates to NodeReducer base class
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess
    - Pattern: "Contract-driven, FSM state transitions"

Extends NodeReducer from omnibase_core for FSM-driven state management.
All state transition logic is 100% driven by contract.yaml, not Python code.

FSM Types Supported:
    - INGESTION: Document ingestion lifecycle
    - PATTERN_LEARNING: 4-phase pattern learning (Foundation -> Matching -> Validation -> Traceability)
    - QUALITY_ASSESSMENT: Quality scoring lifecycle (Raw -> Assessing -> Scored -> Stored)

Design Decisions:
    - 100% Contract-Driven: All FSM logic in YAML, not Python
    - Zero Custom Methods: Base class handles everything
    - Declarative Execution: State transitions defined in state_machine
    - Pure Function Pattern: (state, event) -> (new_state, intents)
    - PostgreSQL Storage: All state stored in fsm_state table
"""
from __future__ import annotations

from typing import Any

from omnibase_core.nodes.node_reducer import NodeReducer


class NodeIntelligenceReducer(NodeReducer[dict[str, Any], dict[str, Any]]):
    """Intelligence reducer - FSM state transitions driven by contract.yaml.

    This reducer processes intelligence workflows by:
    1. Receiving events (document received, pattern learning started, etc.)
    2. Executing FSM transitions defined in contract.yaml
    3. Emitting workflow intents to the orchestrator
    4. Storing state in PostgreSQL fsm_state table

    All state transition logic, intent emission, and validation are driven
    entirely by the contract.yaml FSM configuration.
    """

    # No custom __init__ needed - uses NodeReducer's default initialization


__all__ = ["NodeIntelligenceReducer"]
