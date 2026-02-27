# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Policy type enum (OMN-2557)."""

from __future__ import annotations

from enum import Enum


class EnumPolicyType(str, Enum):
    """The four policy types managed by PolicyStateReducer."""

    TOOL_RELIABILITY = "tool_reliability"
    """Tool reliability: tracks tool_id, reliability score, run/failure counts."""

    PATTERN_EFFECTIVENESS = "pattern_effectiveness"
    """Pattern effectiveness: tracks pattern_id, effectiveness score, tier."""

    MODEL_ROUTING_CONFIDENCE = "model_routing_confidence"
    """Model routing confidence: tracks model_id, task_class, confidence, cost."""

    RETRY_THRESHOLD = "retry_threshold"
    """Retry threshold: tracks context_class, max_retries, escalation_after."""


__all__ = ["EnumPolicyType"]
