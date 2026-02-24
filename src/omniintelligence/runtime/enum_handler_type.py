# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler type enum for runtime configuration."""

from enum import StrEnum


class EnumHandlerType(StrEnum):
    """Handler types available for runtime configuration.

    These correspond to handler protocols defined in omnibase_spi
    and implementations in omnibase_infra.
    """

    KAFKA_PRODUCER = "kafka_producer"
    VECTOR_STORE = "vector_store"
    GRAPH_DATABASE = "graph_database"
    RELATIONAL_DATABASE = "relational_database"
    EMBEDDING = "embedding"
    HTTP_CLIENT = "http_client"


__all__ = ["EnumHandlerType"]
