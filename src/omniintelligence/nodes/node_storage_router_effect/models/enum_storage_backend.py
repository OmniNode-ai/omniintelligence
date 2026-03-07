# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Enum for storage backend types.

Defines the target storage backends that the storage router can dispatch to.

Reference:
    - OMN-371: Storage router effect node
"""

from __future__ import annotations

from enum import Enum


class EnumStorageBackend(str, Enum):
    """Target storage backends for routed events.

    Each backend corresponds to a specific storage technology that
    handles a particular type of computed data.
    """

    QDRANT = "qdrant"
    """Vector storage for embeddings and similarity search."""

    MEMGRAPH = "memgraph"
    """Graph storage for entity relationships."""

    POSTGRESQL = "postgresql"
    """Relational storage for structured pattern data."""


__all__ = [
    "EnumStorageBackend",
]
