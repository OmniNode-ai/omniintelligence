# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node LLM Routing Decision Effect.

Consumer for Bifrost LLM gateway routing decisions emitted by omniclaude.
Persists routing decisions to llm_routing_decisions for model performance analytics.

Reference: OMN-2939, OMN-2740
"""

from omniintelligence.nodes.node_llm_routing_decision_effect.node import (
    NodeLlmRoutingDecisionEffect,
)

__all__ = ["NodeLlmRoutingDecisionEffect"]
