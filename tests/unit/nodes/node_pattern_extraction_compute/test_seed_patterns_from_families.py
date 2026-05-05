# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for seed_patterns_from_families.py — dry-run pipeline validation.

Verifies that collect_all_families() produces well-formed learned_patterns
row dicts from the live codebase, matching the acceptance criterion:
"Dry run shows N patterns that would be inserted."
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


# Resolve omni_home for real-codebase tests
def _omni_home() -> Path:
    env = os.environ.get("OMNI_HOME")
    if env:
        return Path(env)
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "omnibase_core").is_dir() and (p / "omniintelligence").is_dir():
            return p
        p = p.parent
    raise RuntimeError(
        "Cannot resolve omni_home root. Set OMNI_HOME or run from within the workspace."
    )


OMNI_HOME = _omni_home()

# Import after path resolution so sys.path tricks in the script aren't needed
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    NodeFamily,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    RoleOccurrence,
    scan_directory_for_role_occurrences,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_store_node_families import (
    node_family_to_pattern_row,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_pattern_definition import (
    ModelPatternDefinition,
    ModelPatternRole,
)

_FOUR_NODE_PATTERN = ModelPatternDefinition(
    pattern_name="onex-four-node",
    pattern_type="architectural",
    description="ONEX four-node pattern",
    roles=[
        ModelPatternRole(
            role_name="compute",
            base_class="NodeCompute",
            distinguishing_mixin="MixinHandlerRouting",
            required=True,
            description="Pure computation",
        ),
        ModelPatternRole(
            role_name="effect",
            base_class="NodeEffect",
            distinguishing_mixin="MixinEffectExecution",
            required=True,
            description="External I/O",
        ),
        ModelPatternRole(
            role_name="orchestrator",
            base_class="NodeOrchestrator",
            distinguishing_mixin="MixinWorkflowExecution",
            required=False,
            description="Workflow",
        ),
        ModelPatternRole(
            role_name="reducer",
            base_class="NodeReducer",
            distinguishing_mixin="MixinFSMExecution",
            required=False,
            description="FSM state",
        ),
    ],
    when_to_use="When building a new Kafka-connected processing node",
    canonical_instance="omniintelligence/src/omniintelligence/nodes/node_pattern_storage_effect/",
)

_REQUIRED_ROW_KEYS = {
    "id",
    "pattern_signature",
    "signature_hash",
    "domain_id",
    "domain_version",
    "domain_candidates",
    "keywords",
    "confidence",
    "status",
    "promoted_at",
    "source_session_ids",
    "recurrence_count",
    "first_seen_at",
    "last_seen_at",
    "distinct_days_seen",
    "quality_score",
    "evidence_tier",
    "version",
    "is_current",
    "compiled_snippet",
    "compiled_token_count",
    "compiled_at",
}


def _collect_omniintelligence_rows() -> list[dict]:
    """Run the real scan against omniintelligence nodes, mirroring seed script logic."""
    from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
        group_into_node_families,
    )

    nodes_dir = OMNI_HOME / "omniintelligence" / "src" / "omniintelligence" / "nodes"
    repo_root = OMNI_HOME / "omniintelligence"
    occurrences = scan_directory_for_role_occurrences(
        nodes_dir,
        _FOUR_NODE_PATTERN,
        source_repo="omniintelligence",
        repo_root=repo_root,
    )
    families = group_into_node_families(occurrences)
    return [node_family_to_pattern_row(f) for f in families]


@pytest.mark.unit
class TestSeedPatternsDryRun:
    """Verify collect_all_families dry-run produces valid learned_patterns rows."""

    def test_dry_run_produces_at_least_one_row(self) -> None:
        """Scanning omniintelligence produces at least 1 pattern row."""
        rows = _collect_omniintelligence_rows()
        assert len(rows) >= 1, (
            f"Expected at least 1 row from dry-run scan, got {len(rows)}"
        )

    def test_all_rows_have_required_schema_keys(self) -> None:
        """Every pattern row includes all columns required by the INSERT statement."""
        rows = _collect_omniintelligence_rows()
        for row in rows:
            missing = _REQUIRED_ROW_KEYS - set(row.keys())
            assert not missing, (
                f"Row for '{row.get('pattern_signature', '?')}' "
                f"is missing keys: {missing}"
            )

    def test_all_rows_have_architecture_domain(self) -> None:
        """All rows produced by the seed script use domain_id='architecture'."""
        rows = _collect_omniintelligence_rows()
        for row in rows:
            assert row["domain_id"] == "architecture", (
                f"Expected domain_id='architecture', got '{row['domain_id']}' "
                f"for signature '{row.get('pattern_signature')}'"
            )

    def test_all_rows_have_valid_confidence(self) -> None:
        """Confidence scores are in [0.5, 1.0] for real codebase patterns."""
        rows = _collect_omniintelligence_rows()
        for row in rows:
            assert 0.5 <= row["confidence"] <= 1.0, (
                f"Confidence {row['confidence']} out of range for "
                f"'{row.get('pattern_signature')}'"
            )

    def test_all_rows_are_idempotency_safe(self) -> None:
        """No two rows share the same (pattern_signature, domain_id, version) triple."""
        rows = _collect_omniintelligence_rows()
        seen: set[tuple] = set()
        for row in rows:
            key = (row["pattern_signature"], row["domain_id"], row["version"])
            assert key not in seen, f"Duplicate conflict key detected: {key}"
            seen.add(key)

    def test_compiled_snippet_contains_repo_and_roles(self) -> None:
        """compiled_snippet includes repo name and at least one role."""
        rows = _collect_omniintelligence_rows()
        for row in rows:
            snippet = row["compiled_snippet"]
            assert "omniintelligence" in snippet or "Repo:" in snippet, (
                f"compiled_snippet for '{row.get('pattern_signature')}' "
                f"does not reference the repo"
            )
            assert any(
                role in snippet
                for role in ("compute", "effect", "orchestrator", "reducer")
            ), (
                f"compiled_snippet for '{row.get('pattern_signature')}' "
                f"contains no recognized role"
            )

    def test_node_family_to_pattern_row_is_deterministic(self) -> None:
        """Calling node_family_to_pattern_row twice on the same family yields identical id and signature."""
        occ = RoleOccurrence(
            pattern_name="onex-four-node",
            matched_role="effect",
            entity_name="NodePatternStorageEffect",
            qualified_name="omniintelligence.nodes.node_pattern_storage_effect.node.NodePatternStorageEffect",
            file_path="src/omniintelligence/nodes/node_pattern_storage_effect/node.py",
            source_repo="omniintelligence",
            bases=["NodeEffect"],
        )
        family = NodeFamily(
            directory_name="node_pattern_storage_effect",
            directory_path="src/omniintelligence/nodes/node_pattern_storage_effect",
            source_repo="omniintelligence",
            roles=frozenset({"effect"}),
            occurrences=(occ,),
        )
        row_a = node_family_to_pattern_row(family)
        row_b = node_family_to_pattern_row(family)
        assert row_a["id"] == row_b["id"]
        assert row_a["pattern_signature"] == row_b["pattern_signature"]
        assert row_a["signature_hash"] == row_b["signature_hash"]
