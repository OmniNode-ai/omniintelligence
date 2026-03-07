# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Models for Storage Router Effect node.

This module exports all models used by the NodeStorageRouterEffect,
including input, output, and supporting enums for storage routing.

Key Models:
    - ModelStorageRouteInput: Input from compute-completed events
    - ModelStorageRouteOutput: Output for storage.completed/storage.failed events
    - EnumStorageBackend: Target storage backends (qdrant, memgraph, postgresql)
    - EnumStorageRouteStatus: Routing operation status

Reference:
    - OMN-371: Storage router effect node
"""

from omniintelligence.nodes.node_storage_router_effect.models.enum_storage_backend import (
    EnumStorageBackend,
)
from omniintelligence.nodes.node_storage_router_effect.models.enum_storage_route_status import (
    EnumStorageRouteStatus,
)
from omniintelligence.nodes.node_storage_router_effect.models.model_storage_route_input import (
    ModelStorageRouteInput,
)
from omniintelligence.nodes.node_storage_router_effect.models.model_storage_route_output import (
    ModelStorageRouteOutput,
)

__all__ = [
    "EnumStorageBackend",
    "EnumStorageRouteStatus",
    "ModelStorageRouteInput",
    "ModelStorageRouteOutput",
]
