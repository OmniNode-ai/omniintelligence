# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Routing feedback processing status enum.

Reference: OMN-2366
"""

from enum import Enum


class EnumRoutingFeedbackStatus(str, Enum):
    """Status of the routing feedback processing."""

    SUCCESS = "success"
    """Event was processed and upserted to routing_feedback_scores."""

    ERROR = "error"
    """Unhandled exception prevented processing."""


__all__ = ["EnumRoutingFeedbackStatus"]
