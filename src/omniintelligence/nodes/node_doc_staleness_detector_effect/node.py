# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Node DocStalenessDetectorEffect -- Stream C staleness detection and re-ingestion.

Detects when a ContextItem's version_hash no longer matches the current
document content, and triggers atomic re-ingestion following the staleness
policy.

This node follows the ONEX declarative pattern:
    - DECLARATIVE effect driven by contract.yaml
    - I/O effect: reads PG staleness state, triggers re-ingestion, blacklists items
    - Lightweight shell that delegates to handle_staleness_detection

Responsibilities:
    - Classify staleness cases (FILE_DELETED, CONTENT_CHANGED_*, FILE_MOVED)
    - Atomic 3-step sequence for CONTENT_CHANGED (index new, verify, blacklist old)
    - Crash-safe resume via staleness_transition_log
    - Stat carry (70%) when embedding similarity >= 0.85 for REPO_DERIVED

Does NOT:
    - Own connection pool lifecycle (injected via protocols)
    - Consume events directly (caller provides candidates)
    - Compute embeddings (received via input candidates)

Related:
    - OMN-2394: This node implementation
    - OMN-2393: ContextItemWriterEffect (upstream, writes new items)
    - OMN-2383: DB migrations for context_items tables
"""

from __future__ import annotations

from omnibase_core.nodes.node_effect import NodeEffect


class NodeDocStalenessDetectorEffect(NodeEffect):
    """Declarative effect node for document staleness detection and re-ingestion.

    This node is a pure declarative shell. All handler dispatch is defined
    in contract.yaml via ``handler_routing``. The node itself contains NO
    custom routing code.

    All store and trigger dependencies are injected via protocol interfaces
    defined in handler_staleness_detector.py.

    Supported Operations (defined in contract.yaml handler_routing):
        - detect_staleness: Evaluate candidates and apply staleness policies

    Example:
        ```python
        from omniintelligence.nodes.node_doc_staleness_detector_effect.handlers import (
            handle_staleness_detection,
        )
        from omniintelligence.nodes.node_doc_staleness_detector_effect.models import (
            ModelStalenessDetectInput,
            ModelStalenessCandidate,
        )

        result = await handle_staleness_detection(
            ModelStalenessDetectInput(candidates=(candidate,)),
            staleness_store=pg_store,
            reingestion_trigger=trigger,
        )
        ```
    """

    # Pure declarative shell -- all behavior defined in contract.yaml


__all__ = ["NodeDocStalenessDetectorEffect"]
