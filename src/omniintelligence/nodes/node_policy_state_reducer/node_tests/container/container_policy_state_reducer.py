# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binding site for NodePolicyStateReducer in the node_policy_state_reducer tests.

The node is built here, the one binding site, and the tests resolve it through
``resolve_policy_state_reducer`` instead of constructing it (OMN-21785).
"""

from __future__ import annotations

from omniintelligence.nodes.node_policy_state_reducer.handlers.protocols import (
    ProtocolAlertPublisher,
    ProtocolPolicyStateRepository,
)
from omniintelligence.nodes.node_policy_state_reducer.node import (
    NodePolicyStateReducer,
)


def resolve_policy_state_reducer(
    *,
    repository: ProtocolPolicyStateRepository,
    alert_publisher: ProtocolAlertPublisher,
) -> NodePolicyStateReducer:
    """Resolve the NodePolicyStateReducer bound to the given collaborators."""
    return NodePolicyStateReducer(
        repository=repository,
        alert_publisher=alert_publisher,
    )
