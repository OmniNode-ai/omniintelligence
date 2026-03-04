# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for project_scope field support (OMN-1607).

Tests cover:
1. ModelLearnedPatternRow accepts project_scope (optional, defaults to None)
2. ModelPatternSummary accepts project_scope (optional, defaults to None)
3. Contract YAML includes project_scope in store/upsert/query operations
4. AdapterPatternStore.query_patterns passes project_scope to contract
5. AdapterPatternStore.upsert_pattern passes project_scope to contract
6. Migration SQL is syntactically correct (basic validation)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.enums import EnumPatternLifecycleStatus
from omniintelligence.models.repository.model_learned_pattern_row import (
    ModelLearnedPatternRow,
)
from omniintelligence.models.repository.model_pattern_summary import (
    ModelPatternSummary,
)
from omniintelligence.repositories.adapter_pattern_store import (
    AdapterPatternStore,
    load_contract,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=UTC)
_PATTERN_ID = uuid4()
_SESSION_ID = uuid4()


def _make_full_row(**overrides: object) -> dict:
    """Build a minimal valid dict for ModelLearnedPatternRow."""
    base = {
        "id": _PATTERN_ID,
        "pattern_signature": "def foo(): pass",
        "signature_hash": "abc123" * 10 + "abcd",
        "domain_id": "python",
        "domain_version": "1.0",
        "domain_candidates": [],
        "keywords": None,
        "confidence": 0.8,
        "quality_score": 0.7,
        "status": EnumPatternLifecycleStatus.CANDIDATE,
        "promoted_at": None,
        "deprecated_at": None,
        "deprecation_reason": None,
        "source_session_ids": [_SESSION_ID],
        "recurrence_count": 1,
        "first_seen_at": _NOW,
        "last_seen_at": _NOW,
        "distinct_days_seen": 1,
        "injection_count_rolling_20": 0,
        "success_count_rolling_20": 0,
        "failure_count_rolling_20": 0,
        "failure_streak": 0,
        "version": 1,
        "is_current": True,
        "supersedes": None,
        "superseded_by": None,
        "compiled_snippet": None,
        "compiled_token_count": None,
        "compiled_at": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return base


def _make_summary(**overrides: object) -> dict:
    """Build a minimal valid dict for ModelPatternSummary."""
    base = {
        "id": _PATTERN_ID,
        "pattern_signature": "def foo(): pass",
        "signature_hash": "abc123" * 10 + "abcd",
        "domain_id": "python",
        "quality_score": 0.7,
        "confidence": 0.8,
        "status": "validated",
        "is_current": True,
        "version": 1,
        "created_at": _NOW,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestModelProjectScope:
    """Test project_scope field on Pydantic models."""

    @pytest.mark.unit
    def test_learned_pattern_row_default_project_scope_is_none(self) -> None:
        """ModelLearnedPatternRow.project_scope defaults to None (global)."""
        row = ModelLearnedPatternRow(**_make_full_row())
        assert row.project_scope is None

    @pytest.mark.unit
    def test_learned_pattern_row_accepts_project_scope(self) -> None:
        """ModelLearnedPatternRow accepts a non-null project_scope."""
        row = ModelLearnedPatternRow(**_make_full_row(project_scope="omniclaude"))
        assert row.project_scope == "omniclaude"

    @pytest.mark.unit
    def test_learned_pattern_row_project_scope_max_length(self) -> None:
        """ModelLearnedPatternRow enforces max_length=255 on project_scope."""
        # Exactly 255 should work
        row = ModelLearnedPatternRow(**_make_full_row(project_scope="a" * 255))
        assert len(row.project_scope) == 255

        # 256 should fail
        with pytest.raises(Exception):  # noqa: B017 - Pydantic validation
            ModelLearnedPatternRow(**_make_full_row(project_scope="a" * 256))

    @pytest.mark.unit
    def test_pattern_summary_default_project_scope_is_none(self) -> None:
        """ModelPatternSummary.project_scope defaults to None."""
        summary = ModelPatternSummary(**_make_summary())
        assert summary.project_scope is None

    @pytest.mark.unit
    def test_pattern_summary_accepts_project_scope(self) -> None:
        """ModelPatternSummary accepts a non-null project_scope."""
        summary = ModelPatternSummary(**_make_summary(project_scope="omniarchon"))
        assert summary.project_scope == "omniarchon"


# ---------------------------------------------------------------------------
# Contract YAML Tests
# ---------------------------------------------------------------------------


class TestContractProjectScope:
    """Test that the repository contract YAML includes project_scope."""

    @pytest.mark.unit
    def test_store_pattern_has_project_scope_param(self) -> None:
        """store_pattern operation has project_scope as optional param."""
        contract = load_contract()
        op = contract.ops["store_pattern"]
        assert "project_scope" in op.params
        param = op.params["project_scope"]
        assert param.required is False

    @pytest.mark.unit
    def test_store_with_version_transition_has_project_scope_param(self) -> None:
        """store_with_version_transition has project_scope as optional param."""
        contract = load_contract()
        op = contract.ops["store_with_version_transition"]
        assert "project_scope" in op.params
        param = op.params["project_scope"]
        assert param.required is False

    @pytest.mark.unit
    def test_upsert_pattern_has_project_scope_param(self) -> None:
        """upsert_pattern has project_scope as optional param."""
        contract = load_contract()
        op = contract.ops["upsert_pattern"]
        assert "project_scope" in op.params
        param = op.params["project_scope"]
        assert param.required is False

    @pytest.mark.unit
    def test_query_patterns_has_project_scope_param(self) -> None:
        """query_patterns has project_scope as optional filter param."""
        contract = load_contract()
        op = contract.ops["query_patterns"]
        assert "project_scope" in op.params
        param = op.params["project_scope"]
        assert param.required is False

    @pytest.mark.unit
    def test_query_patterns_sql_references_project_scope(self) -> None:
        """query_patterns SQL uses $6 for project_scope filtering."""
        contract = load_contract()
        op = contract.ops["query_patterns"]
        assert "$6" in op.sql
        assert "project_scope" in op.sql

    @pytest.mark.unit
    def test_list_by_domain_selects_project_scope(self) -> None:
        """list_by_domain SELECT includes project_scope column."""
        contract = load_contract()
        op = contract.ops["list_by_domain"]
        assert "project_scope" in op.sql

    @pytest.mark.unit
    def test_store_pattern_sql_includes_project_scope_column(self) -> None:
        """store_pattern INSERT includes project_scope in column list."""
        contract = load_contract()
        op = contract.ops["store_pattern"]
        assert "project_scope" in op.sql


# ---------------------------------------------------------------------------
# Adapter Tests
# ---------------------------------------------------------------------------


class TestAdapterProjectScope:
    """Test AdapterPatternStore passes project_scope through correctly."""

    @pytest.mark.unit
    async def test_query_patterns_passes_project_scope(self) -> None:
        """query_patterns passes project_scope to _build_positional_args."""
        contract = load_contract()
        mock_runtime = MagicMock()
        mock_runtime.contract = contract
        mock_runtime.call = AsyncMock(return_value=[])
        adapter = AdapterPatternStore(runtime=mock_runtime)

        await adapter.query_patterns(
            domain="python",
            project_scope="omniclaude",
        )

        # Verify call was made with the correct operation
        mock_runtime.call.assert_called_once()
        call_args = mock_runtime.call.call_args
        assert call_args[0][0] == "query_patterns"
        # The positional args should include "omniclaude" for project_scope
        # It's the 6th positional param ($6)
        positional_args = call_args[0][1:]
        assert "omniclaude" in positional_args

    @pytest.mark.unit
    async def test_query_patterns_default_project_scope_is_none(self) -> None:
        """query_patterns passes None for project_scope when not specified."""
        contract = load_contract()
        mock_runtime = MagicMock()
        mock_runtime.contract = contract
        mock_runtime.call = AsyncMock(return_value=[])
        adapter = AdapterPatternStore(runtime=mock_runtime)

        await adapter.query_patterns(domain="python")

        call_args = mock_runtime.call.call_args
        positional_args = call_args[0][1:]
        # Last positional arg should be None (project_scope)
        assert positional_args[-1] is None

    @pytest.mark.unit
    async def test_upsert_pattern_passes_project_scope(self) -> None:
        """upsert_pattern passes project_scope when provided."""
        contract = load_contract()
        mock_runtime = MagicMock()
        mock_runtime.contract = contract
        mock_runtime.call = AsyncMock(return_value={"id": str(uuid4())})
        adapter = AdapterPatternStore(runtime=mock_runtime)

        await adapter.upsert_pattern(
            pattern_id=uuid4(),
            signature="test pattern",
            signature_hash="hash123",
            domain_id="python",
            confidence=0.8,
            version=1,
            source_session_ids=[uuid4()],
            project_scope="omniclaude",
        )

        call_args = mock_runtime.call.call_args
        positional_args = call_args[0][1:]
        assert "omniclaude" in positional_args

    @pytest.mark.unit
    async def test_upsert_pattern_default_project_scope_is_none(self) -> None:
        """upsert_pattern passes None for project_scope when not specified."""
        contract = load_contract()
        mock_runtime = MagicMock()
        mock_runtime.contract = contract
        mock_runtime.call = AsyncMock(return_value={"id": str(uuid4())})
        adapter = AdapterPatternStore(runtime=mock_runtime)

        await adapter.upsert_pattern(
            pattern_id=uuid4(),
            signature="test pattern",
            signature_hash="hash123",
            domain_id="python",
            confidence=0.8,
            version=1,
            source_session_ids=[uuid4()],
        )

        call_args = mock_runtime.call.call_args
        positional_args = call_args[0][1:]
        # Last positional arg should be None (project_scope)
        assert positional_args[-1] is None


# ---------------------------------------------------------------------------
# Migration Tests
# ---------------------------------------------------------------------------


class TestMigrationFile:
    """Basic validation of the migration SQL file."""

    @pytest.mark.unit
    def test_migration_file_exists(self) -> None:
        """Migration 022 exists."""
        migration_path = (
            Path(__file__).parents[3]
            / "deployment"
            / "database"
            / "migrations"
            / "022_add_project_scope_to_learned_patterns.sql"
        )
        assert migration_path.exists(), f"Migration not found at {migration_path}"

    @pytest.mark.unit
    def test_migration_contains_alter_table(self) -> None:
        """Migration adds project_scope column via ALTER TABLE."""
        migration_path = (
            Path(__file__).parents[3]
            / "deployment"
            / "database"
            / "migrations"
            / "022_add_project_scope_to_learned_patterns.sql"
        )
        content = migration_path.read_text()
        assert "ALTER TABLE learned_patterns" in content
        assert "project_scope" in content
        assert "VARCHAR(255)" in content

    @pytest.mark.unit
    def test_migration_creates_index(self) -> None:
        """Migration creates index on project_scope."""
        migration_path = (
            Path(__file__).parents[3]
            / "deployment"
            / "database"
            / "migrations"
            / "022_add_project_scope_to_learned_patterns.sql"
        )
        content = migration_path.read_text()
        assert "idx_learned_patterns_project_scope" in content

    @pytest.mark.unit
    def test_rollback_file_exists(self) -> None:
        """Rollback for migration 022 exists."""
        rollback_path = (
            Path(__file__).parents[3]
            / "deployment"
            / "database"
            / "migrations"
            / "rollback"
            / "022_rollback.sql"
        )
        assert rollback_path.exists(), f"Rollback not found at {rollback_path}"

    @pytest.mark.unit
    def test_rollback_drops_column(self) -> None:
        """Rollback drops the project_scope column."""
        rollback_path = (
            Path(__file__).parents[3]
            / "deployment"
            / "database"
            / "migrations"
            / "rollback"
            / "022_rollback.sql"
        )
        content = rollback_path.read_text()
        assert "DROP" in content
        assert "project_scope" in content
