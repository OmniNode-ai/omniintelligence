# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Typed action spaces for RL training.

Actions are discrete choices represented as enums with ``to_index()`` /
``from_index()`` methods for policy-network integration.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Self


class RoutingAction(IntEnum):
    """Discrete routing action -- selects one of four LLM endpoints.

    Enum values are zero-indexed to serve directly as policy-network
    output indices.
    """

    QWEN3_30B = 0  # Qwen3-Coder-30B-A3B (64K ctx, RTX 5090)
    QWEN3_14B = 1  # Qwen3-14B-AWQ (40K ctx, RTX 4090)
    DEEPSEEK_R1 = 2  # DeepSeek-R1-Distill-Qwen-32B (M2 Ultra)
    EMBEDDING = 3  # Qwen3-Embedding-8B (M2 Ultra)

    def to_index(self) -> int:
        """Return the integer index for this action."""
        return int(self.value)

    @classmethod
    def from_index(cls, index: int) -> Self:
        """Construct a ``RoutingAction`` from an integer index."""
        return cls(index)


#: Total number of discrete routing actions.
NUM_ROUTING_ACTIONS: int = len(RoutingAction)
