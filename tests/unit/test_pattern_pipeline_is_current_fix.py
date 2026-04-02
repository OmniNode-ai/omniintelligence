"""Tests for is_current removal from pattern pipeline queries.

Root cause: patterns were inserted with is_current=FALSE, but every downstream
query filtered on is_current=TRUE — making all patterns invisible to projection,
promotion, and demotion.

Fix: remove is_current from all read-path WHERE clauses and insert with TRUE.
Version-swap UPDATE mechanics (set_not_current, store_with_version_transition)
are preserved since they correctly need is_current in their WHERE clause.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src" / "omniintelligence"
_REPO_YAML = _SRC / "repositories" / "learned_patterns.repository.yaml"
_HANDLER_AUTO_PROMOTE = (
    _SRC
    / "nodes"
    / "node_pattern_promotion_effect"
    / "handlers"
    / "handler_auto_promote.py"
)
_HANDLER_PROMOTION = (
    _SRC
    / "nodes"
    / "node_pattern_promotion_effect"
    / "handlers"
    / "handler_promotion.py"
)
_HANDLER_DEMOTION = (
    _SRC
    / "nodes"
    / "node_pattern_demotion_effect"
    / "handlers"
    / "handler_demotion.py"
)


@pytest.fixture(scope="module")
def repo_contract() -> dict:
    """Load the learned_patterns repository YAML once."""
    return yaml.safe_load(_REPO_YAML.read_text())


def _get_op_sql(contract: dict, op_name: str) -> str:
    """Extract SQL string for a repository operation."""
    ops = contract["db_repository"]["ops"]
    assert op_name in ops, f"Operation '{op_name}' not found in repository YAML"
    return ops[op_name]["sql"]


# ===========================================================================
# 1. is_current removed from all read-path WHERE clauses in repository YAML
# ===========================================================================
_READ_OPS_THAT_MUST_NOT_FILTER_IS_CURRENT = [
    "query_patterns_projection",
    "get_latest_by_lineage",
    "list_by_domain",
    "query_patterns",
    "list_validated_patterns",
    "list_promotion_candidates",
    "list_demotion_candidates",
]


class TestIsCurrentRemovedFromQueryFilters:
    """All read queries must NOT filter on is_current."""

    @pytest.mark.parametrize("op_name", _READ_OPS_THAT_MUST_NOT_FILTER_IS_CURRENT)
    def test_no_is_current_in_where(self, repo_contract: dict, op_name: str) -> None:
        sql = _get_op_sql(repo_contract, op_name)
        assert "is_current = TRUE" not in sql, (
            f"Operation '{op_name}' still filters on is_current = TRUE in WHERE clause"
        )


# ===========================================================================
# 2. is_current preserved in version-swap UPDATE mechanics
# ===========================================================================
_VERSION_SWAP_OPS = [
    "set_not_current",
    "store_with_version_transition",
]


class TestIsCurrentPreservedInVersionSwap:
    """Version-swap operations MUST still use is_current in their UPDATE WHERE."""

    @pytest.mark.parametrize("op_name", _VERSION_SWAP_OPS)
    def test_is_current_still_in_update(
        self, repo_contract: dict, op_name: str
    ) -> None:
        sql = _get_op_sql(repo_contract, op_name)
        assert "is_current" in sql, (
            f"Version-swap operation '{op_name}' should still reference is_current"
        )


# ===========================================================================
# 3. upsert_pattern inserts with is_current=TRUE
# ===========================================================================
class TestUpsertPatternIsCurrentTrue:
    def test_upsert_inserts_true(self, repo_contract: dict) -> None:
        sql = _get_op_sql(repo_contract, "upsert_pattern")
        # The VALUES clause should contain TRUE (not FALSE) for is_current
        assert "'candidate', TRUE" in sql, (
            "upsert_pattern should insert with is_current=TRUE"
        )
        assert "'candidate', FALSE" not in sql, (
            "upsert_pattern should NOT insert with is_current=FALSE"
        )


# ===========================================================================
# 4. Handler SQL constants don't filter on is_current
# ===========================================================================
class TestHandlerSqlNoIsCurrentFilter:
    """Inline SQL in handler files must not filter on is_current."""

    def _extract_sql_constants(self, filepath: Path) -> dict[str, str]:
        """Extract SQL_* constants from a Python file (handles both ''' and f-strings)."""
        text = filepath.read_text()
        results = {}
        for match in re.finditer(
            r'^(SQL_\w+)\s*=\s*f?"""(.*?)"""', text, re.MULTILINE | re.DOTALL
        ):
            results[match.group(1)] = match.group(2)
        return results

    def test_auto_promote_candidate_query(self) -> None:
        sqls = self._extract_sql_constants(_HANDLER_AUTO_PROMOTE)
        sql = sqls.get("SQL_FETCH_CANDIDATE_PATTERNS", "")
        assert sql, "SQL_FETCH_CANDIDATE_PATTERNS not found"
        assert "is_current" not in sql

    def test_auto_promote_provisional_query(self) -> None:
        sqls = self._extract_sql_constants(_HANDLER_AUTO_PROMOTE)
        sql = sqls.get("SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER", "")
        assert sql, "SQL_FETCH_PROVISIONAL_PATTERNS_WITH_TIER not found"
        assert "is_current" not in sql

    def test_promotion_provisional_query(self) -> None:
        sqls = self._extract_sql_constants(_HANDLER_PROMOTION)
        sql = sqls.get("SQL_FETCH_PROVISIONAL_PATTERNS", "")
        assert sql, "SQL_FETCH_PROVISIONAL_PATTERNS not found"
        assert "is_current" not in sql

    def test_demotion_validated_query(self) -> None:
        sqls = self._extract_sql_constants(_HANDLER_DEMOTION)
        sql = sqls.get("SQL_FETCH_VALIDATED_PATTERNS", "")
        assert sql, "SQL_FETCH_VALIDATED_PATTERNS not found"
        assert "is_current" not in sql
