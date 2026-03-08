# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Enum for protocol handler types.

Defines the protocol types supported by the protocol handler effect node.
Each type corresponds to a specific transport/wire protocol used by
declarative effect nodes.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

from enum import Enum


class EnumProtocolType(str, Enum):
    """Supported protocol types for declarative effect nodes.

    Each value maps to a concrete handler implementation that
    abstracts protocol-specific I/O details.
    """

    HTTP_REST = "http_rest"
    """HTTP/REST API protocol via httpx."""

    BOLT = "bolt"
    """Neo4j/Memgraph Bolt protocol via neo4j driver."""

    POSTGRESQL = "postgresql"
    """PostgreSQL wire protocol via asyncpg."""

    KAFKA = "kafka"
    """Apache Kafka protocol via confluent-kafka."""


__all__ = [
    "EnumProtocolType",
]
