# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Enum for reward target types (OMN-2537)."""

from __future__ import annotations

from enum import Enum


class EnumRewardTargetType(str, Enum):
    """What the shaped reward is optimizing for."""

    CORRECTNESS = "correctness"
    """Task correctness / accuracy."""

    SAFETY = "safety"
    """Safety constraints and guardrails."""

    COST = "cost"
    """Compute / token cost efficiency."""

    LATENCY = "latency"
    """End-to-end execution latency."""

    MAINTAINABILITY = "maintainability"
    """Code quality and long-term maintainability."""

    HUMAN_TIME = "human_time"
    """Human operator time saved."""


__all__ = ["EnumRewardTargetType"]
