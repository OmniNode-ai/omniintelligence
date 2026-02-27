# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Evidence collection effect node (OMN-2578).

Wires objective evaluation into the agent execution trace by constructing
ModelEvidenceBundle from ChangeFrame check results at session end, then
feeding the bundle into the scoring pipeline.

Public API:
    NodeEvidenceCollectionEffect: The ONEX EFFECT node class.
    collect_and_evaluate: Top-level async function for session-end wiring.
    EvidenceCollector: Extracts ModelEvidenceItem instances from session data.
    DisallowedEvidenceSourceError: Raised when free-text sources are injected.
"""

from omniintelligence.nodes.node_evidence_collection_effect.errors import (
    DisallowedEvidenceSourceError,
)
from omniintelligence.nodes.node_evidence_collection_effect.handlers.handler_evidence_collection import (
    EvidenceCollector,
    collect_and_evaluate,
)

try:
    from omniintelligence.nodes.node_evidence_collection_effect.node import (
        NodeEvidenceCollectionEffect,
    )
except ImportError:
    # omnibase_core not yet installed — NodeEvidenceCollectionEffect unavailable.
    # The handler functions (EvidenceCollector, collect_and_evaluate) are still importable.
    NodeEvidenceCollectionEffect = None  # type: ignore[assignment,misc]

__all__ = [
    "NodeEvidenceCollectionEffect",
    "EvidenceCollector",
    "collect_and_evaluate",
    "DisallowedEvidenceSourceError",
]
