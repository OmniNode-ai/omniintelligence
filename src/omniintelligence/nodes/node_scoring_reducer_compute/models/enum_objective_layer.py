# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Enum for objective function layers (OMN-2537)."""

from __future__ import annotations

from enum import Enum


class EnumObjectiveLayer(str, Enum):
    """Hierarchical layers at which objectives are evaluated."""

    SYSTEM = "system"
    """System-wide objective across all agents."""

    AGENT = "agent"
    """Per-agent objective for a single agent type."""

    TASK = "task"
    """Task-level objective for a specific task class."""

    RUN = "run"
    """Single execution-run objective."""


__all__ = ["EnumObjectiveLayer"]
