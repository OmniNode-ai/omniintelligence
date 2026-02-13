"""Intelligence Reducer - FSM-driven reducer with handler routing.

This reducer follows the ONEX declarative pattern with FSM type routing:
    - FSM states and transitions defined in contract.yaml
    - FSM type-specific handlers for business logic
    - Thin shell that delegates to handlers and NodeReducer base class
    - Used for ONEX-compliant runtime execution via RuntimeHostProcess

Extends NodeReducer from omnibase_core for FSM-driven state management.
FSM state transitions are validated against contract.yaml. Handler functions
implement business logic and intent emission for each FSM type.

FSM Types Supported:
    - INGESTION: Document ingestion lifecycle (base FSM)
    - PATTERN_LEARNING: 4-phase pattern learning (base FSM)
    - QUALITY_ASSESSMENT: Quality scoring lifecycle (base FSM)
    - PATTERN_LIFECYCLE: Pattern status transitions (custom handler)

Design Decisions:
    - FSM Type Routing: PATTERN_LIFECYCLE routes to custom handler
    - Handler Intent Emission: Handlers build typed ModelIntent payloads
    - Declarative FSM: States/transitions in contract.yaml
    - Pure Function Handlers: (input) -> (result with intent)
    - PostgreSQL Storage: State stored in fsm_state table

Ticket: OMN-1805
"""

from __future__ import annotations

from omnibase_core.models.reducer.model_reducer_input import ModelReducerInput
from omnibase_core.models.reducer.model_reducer_output import ModelReducerOutput
from omnibase_core.nodes.node_reducer import NodeReducer

from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_process import (
    handle_pattern_lifecycle_process,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_intelligence_state import (
    ModelIntelligenceState,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)


class NodeIntelligenceReducer(NodeReducer[dict[str, object], ModelIntelligenceState]):
    """Intelligence reducer - FSM transitions with handler routing.

    This reducer processes intelligence workflows by:
    1. Receiving events with FSM type discriminator
    2. Routing PATTERN_LIFECYCLE events to custom handler
    3. Routing other FSM types to base class FSM execution
    4. Emitting typed intents for effect nodes

    FSM Type Routing:
        - PATTERN_LIFECYCLE -> handle_pattern_lifecycle_process()
        - INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT -> base FSM

    The PATTERN_LIFECYCLE handler validates transitions against the FSM
    defined in contract.yaml and emits ModelPayloadUpdatePatternStatus
    intents for NodePatternLifecycleEffect to process.
    """

    async def process(
        self,
        input_data: ModelReducerInput[dict[str, object]],
    ) -> ModelReducerOutput[ModelIntelligenceState]:
        """Process reducer input with FSM type routing.

        Routes PATTERN_LIFECYCLE events to the handler which validates
        transitions and builds typed intents. Other FSM types fall through
        to the base class FSM execution.

        Args:
            input_data: Reducer input with FSM type discriminator.

        Returns:
            ModelReducerOutput with new state and intents.
        """
        # Route PATTERN_LIFECYCLE to handler
        if isinstance(input_data, ModelReducerInputPatternLifecycle):
            return handle_pattern_lifecycle_process(input_data)

        # All other FSM types use base class FSM execution
        return await super().process(input_data)


__all__ = ["NodeIntelligenceReducer"]
