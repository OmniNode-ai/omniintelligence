"""Intelligence Reducer - FSM-driven reducer with handler routing.

This reducer follows the ONEX declarative pattern with FSM type routing:
    - FSM states and transitions defined in contract.yaml
    - FSM type-specific handlers for business logic
    - Lightweight shell that delegates to handlers and NodeReducer base class
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

import logging
import time
from typing import Any
from uuid import uuid4

from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.model_reducer_input import ModelReducerInput
from omnibase_core.models.reducer.model_reducer_output import ModelReducerOutput
from omnibase_core.models.reducer.payloads.model_extension_payloads import (
    ModelPayloadExtension,
)
from omnibase_core.nodes.node_reducer import NodeReducer

from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_pattern_lifecycle import (
    handle_pattern_lifecycle_transition,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)

logger = logging.getLogger(__name__)


class NodeIntelligenceReducer(NodeReducer[dict[str, Any], dict[str, Any]]):
    """Intelligence reducer - FSM transitions with handler routing.

    This reducer processes intelligence workflows by:
    1. Receiving events with FSM type discriminator
    2. Routing PATTERN_LIFECYCLE events to custom handler
    3. Routing other FSM types to base class FSM execution
    4. Emitting typed intents for effect nodes

    FSM Type Routing:
        - PATTERN_LIFECYCLE → handle_pattern_lifecycle_transition()
        - INGESTION, PATTERN_LEARNING, QUALITY_ASSESSMENT → base FSM

    The PATTERN_LIFECYCLE handler validates transitions against the FSM
    defined in contract.yaml and emits ModelPayloadUpdatePatternStatus
    intents for NodePatternLifecycleEffect to process.
    """

    async def process(
        self,
        input_data: ModelReducerInput[dict[str, Any]],
    ) -> ModelReducerOutput[dict[str, Any]]:
        """Process reducer input with FSM type routing.

        Routes PATTERN_LIFECYCLE events to the custom handler which
        validates transitions and builds typed intents. Other FSM types
        fall through to the base class FSM execution.

        Args:
            input_data: Reducer input with FSM type discriminator.

        Returns:
            ModelReducerOutput with new state and intents.
        """
        # Route PATTERN_LIFECYCLE to custom handler
        if isinstance(input_data, ModelReducerInputPatternLifecycle):
            return self._handle_pattern_lifecycle(input_data)

        # All other FSM types use base class FSM execution
        return await super().process(input_data)

    def _handle_pattern_lifecycle(
        self,
        input_data: ModelReducerInputPatternLifecycle,
    ) -> ModelReducerOutput[dict[str, Any]]:
        """Handle PATTERN_LIFECYCLE FSM transitions.

        Delegates to the handler which validates the transition against
        the FSM rules and builds the intent payload.

        Args:
            input_data: Pattern lifecycle transition request.

        Returns:
            ModelReducerOutput with state and intents.
        """
        start_time = time.perf_counter()
        result = handle_pattern_lifecycle_transition(input_data)
        processing_time_ms = (time.perf_counter() - start_time) * 1000

        if not result.success:
            # Return error output with no intents
            logger.warning(
                "Pattern lifecycle transition rejected",
                extra={
                    "pattern_id": input_data.payload.pattern_id,
                    "from_status": result.from_status,
                    "to_status": result.to_status,
                    "trigger": result.trigger,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                    "correlation_id": str(input_data.correlation_id),
                },
            )
            return ModelReducerOutput(
                result={
                    "fsm_type": "PATTERN_LIFECYCLE",
                    "success": False,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                    "pattern_id": input_data.payload.pattern_id,
                    "from_status": result.from_status,
                    "to_status": result.to_status,
                    "trigger": result.trigger,
                },
                operation_id=uuid4(),
                reduction_type="transform",
                processing_time_ms=processing_time_ms,
                items_processed=1,
                intents=(),
            )

        # Build intent from handler result using ModelPayloadExtension
        # which implements ProtocolIntentPayload
        # Note: extension_type must be in format "namespace.name" per omnibase_core
        # Note: data must be JSON-serializable, so use mode="json" for UUIDs/datetimes
        intent_payload = ModelPayloadExtension(
            extension_type="omniintelligence.pattern_lifecycle_update",
            plugin_name="omniintelligence",
            data=result.intent.model_dump(mode="json") if result.intent else {},
        )
        intent = ModelIntent(
            intent_type="extension",
            target=f"postgres://patterns/{input_data.payload.pattern_id}",
            payload=intent_payload,
        )

        logger.info(
            "Pattern lifecycle transition accepted",
            extra={
                "pattern_id": input_data.payload.pattern_id,
                "from_status": result.from_status,
                "to_status": result.to_status,
                "trigger": result.trigger,
                "correlation_id": str(input_data.correlation_id),
            },
        )

        return ModelReducerOutput(
            result={
                "fsm_type": "PATTERN_LIFECYCLE",
                "success": True,
                "pattern_id": input_data.payload.pattern_id,
                "from_status": result.from_status,
                "to_status": result.to_status,
                "trigger": result.trigger,
            },
            operation_id=uuid4(),
            reduction_type="transform",
            processing_time_ms=processing_time_ms,
            items_processed=1,
            intents=(intent,),
        )


__all__ = ["NodeIntelligenceReducer"]
