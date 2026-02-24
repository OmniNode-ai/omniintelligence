# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Schema manifest constant for omniintelligence.

Declares the canonical list of tables owned by the omniintelligence service.
Used by the schema fingerprint utility (B2 handshake check, OMN-2435) to
compute and validate fingerprints against the expected set of tables at
kernel boot time.

Related:
    - OMN-2435: omniintelligence missing boot-time handshake despite owning its own DB
    - OMN-2087: Handshake hardening -- Schema fingerprint manifest + startup assertion
"""

from __future__ import annotations

from omnibase_infra.runtime.model_schema_manifest import ModelSchemaManifest

# Code constant -- the canonical table list for omniintelligence.
# Keep sorted alphabetically for deterministic fingerprint computation.
OMNIINTELLIGENCE_SCHEMA_MANIFEST = ModelSchemaManifest(
    owner_service="omniintelligence",
    schema_name="public",
    tables=(
        "db_metadata",
        "domain_taxonomy",
        "fsm_state",
        "fsm_state_history",
        "idempotency_records",  # owned and migrated by omnibase_infra, not this repo's migrations; expected to exist at service start
        "learned_patterns",
        "pattern_disable_events",
        "pattern_injections",
        "pattern_lifecycle_transitions",
        "pattern_measured_attributions",
        "routing_feedback_scores",
        "workflow_executions",
    ),
)


__all__: list[str] = [
    "OMNIINTELLIGENCE_SCHEMA_MANIFEST",
]
