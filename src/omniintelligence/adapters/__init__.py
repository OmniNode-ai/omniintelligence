# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Protocol handler adapter implementations.

Concrete implementations of the ProtocolHandler protocol for various
transport/wire protocols. These live outside the nodes/ directory to
comply with ONEX I/O audit and cross-repo validation policies.

Adapters:
    - HttpRestHandler: HTTP/REST via httpx
    - BoltHandler: Neo4j/Memgraph via Bolt protocol
    - PostgresHandler: PostgreSQL via asyncpg
    - KafkaHandler: Kafka via confluent-kafka

These adapters are injected into the node handler via
ProtocolHandlerRegistry during runtime wiring.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from omniintelligence.adapters.adapter_bolt import BoltHandler
from omniintelligence.adapters.adapter_http_rest import HttpRestHandler
from omniintelligence.adapters.adapter_kafka import KafkaHandler
from omniintelligence.adapters.adapter_postgres import PostgresHandler

__all__ = [
    "BoltHandler",
    "HttpRestHandler",
    "KafkaHandler",
    "PostgresHandler",
]
