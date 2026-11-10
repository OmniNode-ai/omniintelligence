# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Contract-bound handler class for the pattern learning dispatch factory.

The node contract binds a handler class; the runtime dispatch factory is a
function. This class builds the factory's dispatch handler from the runtime's
keyword dependencies and runs it for one envelope.

Ticket: OMN-23422
"""

from __future__ import annotations

from typing import Any

from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope
from omnibase_core.protocols.handler.protocol_handler_context import (
    ProtocolHandlerContext,
)

from omniintelligence.runtime.dispatch_handler_pattern_learning import (
    create_pattern_learning_dispatch_handler,
)


class HandlerPatternLearningDispatch:
    """Contract-bound handler for ``create_pattern_learning_dispatch_handler``.

    ``dependencies`` are the factory's keyword arguments (repository,
    kafka_producer, publish_topic, correlation_id) supplied by the runtime.
    """

    def __init__(self, **dependencies: Any) -> None:
        self._dependencies = dependencies

    async def handle(
        self, envelope: ModelEventEnvelope[object], context: ProtocolHandlerContext
    ) -> str:
        dispatch = create_pattern_learning_dispatch_handler(**self._dependencies)
        return await dispatch(envelope, context)


__all__ = ["HandlerPatternLearningDispatch"]
