# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Handlers for node_compliance_evaluate_effect.

Provides the handler class that bridges Kafka command payloads
to the existing handle_evaluate_compliance() leaf node handler.

Ticket: OMN-2339
"""

from omniintelligence.nodes.node_compliance_evaluate_effect.handlers.handler_compliance_evaluate import (
    HandlerComplianceEvaluate,
)

__all__ = ["HandlerComplianceEvaluate"]
