# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Enum for policy types (OMN-2537)."""

from __future__ import annotations

from enum import Enum


class EnumPolicyType(str, Enum):
    """Types of scoring policies."""

    LEXICOGRAPHIC = "lexicographic"
    """Dimensions evaluated in priority order; higher-priority dimension wins."""

    WEIGHTED_SUM = "weighted_sum"
    """Dimensions combined via weighted summation."""

    PARETO = "pareto"
    """Non-dominated solutions preferred (multi-objective Pareto front)."""


__all__ = ["EnumPolicyType"]
