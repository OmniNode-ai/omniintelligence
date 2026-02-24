# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Outcome enum for routing feedback operations."""

from __future__ import annotations

import enum


class EnumRoutingFeedbackOutcome(str, enum.Enum):
    """Outcome values for routing feedback operations.

    Used on all external contract surfaces (models that cross boundaries):
    ``ModelRoutingFeedbackEvent``, ``ModelRoutingFeedbackResult``, and
    ``ModelRoutingFeedbackProcessedEvent``.

    Wire-compatible: the enum value is the plain string, so JSON serialization
    and asyncpg parameter binding both receive the expected string literal.
    """

    SUCCESS = "success"
    FAILED = "failed"


__all__ = ["EnumRoutingFeedbackOutcome"]
