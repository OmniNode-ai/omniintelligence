# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Enum for storage routing operation status.

Reference:
    - OMN-371: Storage router effect node
"""

from __future__ import annotations

from enum import Enum


class EnumStorageRouteStatus(str, Enum):
    """Status of a storage routing operation."""

    ROUTED = "routed"
    """Event successfully routed to target backend."""

    STORED = "stored"
    """Event successfully stored in target backend."""

    FAILED = "failed"
    """Storage operation failed after retries."""

    DLQ = "dlq"
    """Event routed to dead letter queue after exhausting retries."""

    UNROUTABLE = "unroutable"
    """Event type has no configured routing rule."""


__all__ = [
    "EnumStorageRouteStatus",
]
