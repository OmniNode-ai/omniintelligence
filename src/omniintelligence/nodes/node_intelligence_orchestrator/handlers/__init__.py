# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handlers for Intelligence Orchestrator Node.

This package provides handler classes for the intelligence orchestrator,
following the ONEX declarative pattern where nodes are thin shells
delegating all logic to handlers.

Ticket: OMN-2034
"""

from omniintelligence.nodes.node_intelligence_orchestrator.handlers.handler_receive_intent import (
    HandlerReceiveIntent,
    HandlerReceiveIntents,
)

__all__ = ["HandlerReceiveIntent", "HandlerReceiveIntents"]
