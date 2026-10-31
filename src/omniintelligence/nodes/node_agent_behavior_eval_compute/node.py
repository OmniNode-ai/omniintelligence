# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeAgentBehaviorEvalCompute — thin shell delegating to handler.

This node evaluates AGENT_EXECUTION failure modes via LLM judge.
All logic is delegated to HandlerAgentBehaviorEvaluation in the handlers package.
"""

from __future__ import annotations

from omniintelligence.nodes.node_agent_behavior_eval_compute.handlers import (
    HandlerAgentBehaviorEvaluation,
)

__all__ = ["HandlerAgentBehaviorEvaluation"]
