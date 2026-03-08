# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Enum for protocol handler operation status.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

from enum import Enum


class EnumHandlerStatus(str, Enum):
    """Status of a protocol handler operation."""

    SUCCESS = "success"
    """Operation completed successfully."""

    FAILED = "failed"
    """Operation failed (potentially retryable)."""

    CONNECTION_ERROR = "connection_error"
    """Could not establish or maintain connection."""

    TIMEOUT = "timeout"
    """Operation timed out."""

    NOT_CONNECTED = "not_connected"
    """Handler is not connected to its backend."""


__all__ = [
    "EnumHandlerStatus",
]
