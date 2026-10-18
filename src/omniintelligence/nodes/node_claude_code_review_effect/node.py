# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Declarative shell for host account-pool Claude Code reviews."""

from omnibase_core.nodes.node_effect import NodeEffect


class NodeClaudeCodeReviewEffect(NodeEffect):
    """Review through Claude Code; routing and I/O live in the contract/handler."""
