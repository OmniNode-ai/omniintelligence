# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Process handler for Intelligence Reducer node.

This module provides the handler function that builds ModelReducerOutput from
pattern lifecycle transition results. It encapsulates all the output building
logic that was previously in the node class, following the ONEX declarative
pattern where nodes are thin shells delegating to handlers.

Design Principles:
    - Handler owns all business logic, logging, and timing
    - Node only delegates to this handler
    - Pure function pattern with structured error handling
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from omnibase_core.enums import EnumReductionType
from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.model_reducer_output import ModelReducerOutput
from omnibase_core.models.reducer.payloads.model_extension_payloads import (
    ModelPayloadExtension,
)

from omniintelligence.nodes.node_intelligence_reducer.handlers.handler_pattern_lifecycle import (
    handle_pattern_lifecycle_transition,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_intelligence_state import (
    ModelIntelligenceState,
)
from omniintelligence.nodes.node_intelligence_reducer.models.model_reducer_input import (
    ModelReducerInputPatternLifecycle,
)

logger = logging.getLogger(__name__)


def handle_pattern_lifecycle_process(
    input_data: ModelReducerInputPatternLifecycle,
) -> ModelReducerOutput[ModelIntelligenceState]:
    """Handle PATTERN_LIFECYCLE FSM transitions and build reducer output.

    This handler:
    1. Delegates to handle_pattern_lifecycle_transition for FSM validation
    2. Builds ModelReducerOutput with ModelIntelligenceState result and intents
    3. Logs transition acceptance or rejection with correlation context

    Args:
        input_data: Pattern lifecycle transition request.

    Returns:
        ModelReducerOutput with typed state and intents.
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
            result=ModelIntelligenceState(
                fsm_type="PATTERN_LIFECYCLE",
                entity_id=input_data.payload.pattern_id,
                success=False,
                from_status=result.from_status,
                to_status=result.to_status,
                trigger=result.trigger,
                correlation_id=input_data.correlation_id,
                error_code=result.error_code,
                error_message=result.error_message,
            ),
            operation_id=uuid4(),
            reduction_type=EnumReductionType.TRANSFORM,
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
        result=ModelIntelligenceState(
            fsm_type="PATTERN_LIFECYCLE",
            entity_id=input_data.payload.pattern_id,
            success=True,
            from_status=result.from_status,
            to_status=result.to_status,
            trigger=result.trigger,
            correlation_id=input_data.correlation_id,
        ),
        operation_id=uuid4(),
        reduction_type=EnumReductionType.TRANSFORM,
        processing_time_ms=processing_time_ms,
        items_processed=1,
        intents=(intent,),
    )


__all__ = ["handle_pattern_lifecycle_process"]
