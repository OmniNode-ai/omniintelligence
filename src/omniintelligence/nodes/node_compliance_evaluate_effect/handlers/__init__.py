"""Handlers for node_compliance_evaluate_effect.

Provides the main handler function that bridges Kafka command payloads
to the existing handle_evaluate_compliance() leaf node handler.

Ticket: OMN-2339
"""

from omniintelligence.nodes.node_compliance_evaluate_effect.handlers.handler_compliance_evaluate import (
    handle_compliance_evaluate_command,
)

__all__ = ["handle_compliance_evaluate_command"]
