# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for is_current fix in pattern learning pipeline.

Verifies three fixes that unblock the pattern learning pipeline:
1. upsert_pattern SQL sets is_current=TRUE for version 1 patterns
2. SQL_UPDATE_PATTERN_STATUS sets is_current=TRUE during lifecycle transitions
3. Promotion handler can find version-1 candidate patterns

Root cause: upsert_pattern inserted all patterns with is_current=FALSE,
making them invisible to the promotion scheduler and projection queries.
"""

from __future__ import annotations

import importlib.resources
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import yaml

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.nodes.node_pattern_lifecycle_effect.handlers.handler_transition import (
    SQL_UPDATE_PATTERN_STATUS,
    apply_transition,
)

# =============================================================================
# Test 1: upsert_pattern SQL uses is_current = ($7 = 1) expression
# =============================================================================


@pytest.mark.unit
class TestUpsertPatternIsCurrentFix:
    """Verify upsert_pattern sets is_current=TRUE for version 1."""

    def test_upsert_pattern_sql_contains_version_conditional(self) -> None:
        """upsert_pattern SQL should use ($7 = 1) for is_current."""
        package_files = importlib.resources.files("omniintelligence.repositories")
        contract_file = package_files.joinpath("learned_patterns.repository.yaml")
        content = contract_file.read_text()
        contract = yaml.safe_load(content)

        upsert_sql = contract["db_repository"]["ops"]["upsert_pattern"]["sql"]

        # Must contain the version-conditional expression, not hardcoded FALSE
        assert "($7 = 1)" in upsert_sql, (
            "upsert_pattern SQL should use '($7 = 1)' for is_current "
            "so version-1 patterns are inserted with is_current=TRUE"
        )
        assert "'candidate', FALSE" not in upsert_sql, (
            "upsert_pattern SQL should NOT hardcode is_current=FALSE"
        )

    def test_upsert_pattern_description_documents_behavior(self) -> None:
        """upsert_pattern description should document the version-1 behavior."""
        package_files = importlib.resources.files("omniintelligence.repositories")
        contract_file = package_files.joinpath("learned_patterns.repository.yaml")
        content = contract_file.read_text()
        contract = yaml.safe_load(content)

        description = contract["db_repository"]["ops"]["upsert_pattern"]["description"]
        assert "version 1" in description.lower() or "Version 1" in description, (
            "upsert_pattern description should document the version-1 is_current behavior"
        )


# =============================================================================
# Test 2: SQL_UPDATE_PATTERN_STATUS sets is_current = TRUE
# =============================================================================


@pytest.mark.unit
class TestLifecycleTransitionIsCurrentFix:
    """Verify lifecycle transitions set is_current=TRUE."""

    def test_sql_update_pattern_status_includes_is_current(self) -> None:
        """SQL_UPDATE_PATTERN_STATUS must set is_current = TRUE."""
        assert "is_current = TRUE" in SQL_UPDATE_PATTERN_STATUS, (
            "SQL_UPDATE_PATTERN_STATUS must set is_current = TRUE "
            "so promoted patterns are visible to projection queries"
        )

    def test_sql_update_pattern_status_still_has_status_guard(self) -> None:
        """SQL_UPDATE_PATTERN_STATUS must still use status guard clause."""
        assert "AND status = $4" in SQL_UPDATE_PATTERN_STATUS, (
            "SQL_UPDATE_PATTERN_STATUS must retain the status guard "
            "for optimistic locking"
        )

    @pytest.mark.asyncio
    async def test_transition_sets_is_current_true(self) -> None:
        """Promoting a pattern must set is_current=TRUE in the mock repository."""
        from omniintelligence.nodes.node_pattern_lifecycle_effect.node_tests.conftest import (
            MockIdempotencyStore,
            MockPatternRepository,
        )

        repo = MockPatternRepository()
        pattern_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        repo.add_pattern(
            pattern_id,
            status="candidate",
            is_current=False,
            evidence_tier="observed",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=MockIdempotencyStore(),
            producer=None,
            request_id=uuid4(),
            correlation_id=uuid4(),
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.CANDIDATE,
            to_status=EnumPatternLifecycleStatus.PROVISIONAL,
            trigger="auto_promote",
            transition_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=UTC),
        )

        assert result.success is True
        assert repo.patterns[pattern_id]["status"] == "provisional"
        assert repo.patterns[pattern_id]["is_current"] is True, (
            "Lifecycle transition must set is_current=TRUE so the pattern "
            "becomes visible to projection queries and the promotion scheduler"
        )

    @pytest.mark.asyncio
    async def test_transition_provisional_to_validated_sets_is_current(self) -> None:
        """Promoting provisional->validated must also set is_current=TRUE."""
        from omniintelligence.nodes.node_pattern_lifecycle_effect.node_tests.conftest import (
            MockIdempotencyStore,
            MockPatternRepository,
        )

        repo = MockPatternRepository()
        pattern_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        repo.add_pattern(
            pattern_id,
            status="provisional",
            is_current=True,
            evidence_tier="measured",
        )

        result = await apply_transition(
            repository=repo,
            idempotency_store=MockIdempotencyStore(),
            producer=None,
            request_id=uuid4(),
            correlation_id=uuid4(),
            pattern_id=pattern_id,
            from_status=EnumPatternLifecycleStatus.PROVISIONAL,
            to_status=EnumPatternLifecycleStatus.VALIDATED,
            trigger="promote",
            transition_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=UTC),
        )

        assert result.success is True
        assert repo.patterns[pattern_id]["status"] == "validated"
        assert repo.patterns[pattern_id]["is_current"] is True


# =============================================================================
# Test 3: Auto-promote handler SQL queries expect is_current = TRUE
# =============================================================================


@pytest.mark.unit
class TestAutoPromoteQueriesAreConsistent:
    """Verify auto-promote queries align with the upsert_pattern fix."""

    def test_candidate_query_requires_is_current_true(self) -> None:
        """SQL_FETCH_CANDIDATE_PATTERNS must require is_current = TRUE."""
        from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_auto_promote import (
            SQL_FETCH_CANDIDATE_PATTERNS,
        )

        assert "is_current = TRUE" in SQL_FETCH_CANDIDATE_PATTERNS, (
            "SQL_FETCH_CANDIDATE_PATTERNS requires is_current = TRUE, "
            "which means upsert_pattern must insert version-1 patterns "
            "with is_current=TRUE"
        )

    def test_projection_query_requires_is_current_true(self) -> None:
        """query_patterns_projection must require is_current = TRUE."""
        package_files = importlib.resources.files("omniintelligence.repositories")
        contract_file = package_files.joinpath("learned_patterns.repository.yaml")
        content = contract_file.read_text()
        contract = yaml.safe_load(content)

        projection_sql = contract["db_repository"]["ops"]["query_patterns_projection"][
            "sql"
        ]
        assert "is_current = TRUE" in projection_sql, (
            "query_patterns_projection requires is_current = TRUE, "
            "which means lifecycle transitions must set is_current=TRUE"
        )
