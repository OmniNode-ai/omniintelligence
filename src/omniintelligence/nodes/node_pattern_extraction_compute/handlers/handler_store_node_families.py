# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Convert NodeFamily instances to learned_patterns row dicts.

Bridges the pattern extraction output (NodeFamily) to the learned_patterns
table format for storage via AdapterPatternStore.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    NodeFamily,
)


def node_family_to_pattern_row(family: NodeFamily) -> dict:
    """Convert a NodeFamily to a dict compatible with learned_patterns INSERT.

    Confidence scoring:
    - Base: 0.6 (AST-verified existence)
    - +0.1 per additional role (multi-role = more complete pattern)
    - Cap at 0.95

    Args:
        family: The node family to convert.

    Returns:
        Dict with keys matching learned_patterns columns.
    """
    roles_sorted = sorted(family.roles)
    sig = f"{family.source_repo}:{family.directory_name}:{','.join(roles_sorted)}"
    sig_hash = hashlib.sha256(sig.encode()).hexdigest()[:16]

    # Confidence: base 0.6 + 0.1 per role, capped at 0.95
    confidence = min(0.95, 0.6 + 0.1 * len(roles_sorted))

    # Compiled snippet: human-readable summary for agent injection
    role_lines = []
    for occ in family.occurrences:
        role_lines.append(
            f"  - {occ.matched_role}: {occ.entity_name} ({occ.file_path})"
        )
    snippet = (
        f"Pattern: {family.directory_name}\n"
        f"Repo: {family.source_repo}\n"
        f"Roles: {', '.join(roles_sorted)}\n"
        f"Instances:\n" + "\n".join(role_lines)
    )

    now = datetime.now(timezone.utc)

    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, sig)),
        "pattern_signature": sig,
        "signature_hash": sig_hash,
        "domain_id": "architecture",
        "domain_version": "1.0.0",
        "domain_candidates": [{"domain": "architecture", "confidence": 1.0}],
        "keywords": [family.directory_name, family.source_repo] + roles_sorted,
        "confidence": confidence,
        "status": "validated",
        "promoted_at": now,
        "source_session_ids": [],
        "recurrence_count": 1,
        "first_seen_at": now,
        "last_seen_at": now,
        "distinct_days_seen": 1,
        "quality_score": confidence,
        "evidence_tier": "measured",
        "version": 1,
        "is_current": True,
        "compiled_snippet": snippet,
        "compiled_token_count": len(snippet.split()),
        "compiled_at": now,
    }
