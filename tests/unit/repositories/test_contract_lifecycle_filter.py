# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for lifecycle_state filter enforcement in learned_patterns repository contract.

Tests verify that injection-eligible queries enforce the lifecycle_state filter:
- status IN ('validated', 'provisional') for injection queries
- CANDIDATE and DEPRECATED patterns are NEVER returned by injection queries
- Administrative queries are intentionally exempt

Ticket: OMN-1894
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml


@dataclass
class ContractOp:
    """Lightweight representation of a contract operation."""

    name: str
    sql: str
    description: str


@dataclass
class Contract:
    """Lightweight representation of the repository contract."""

    ops: dict[str, ContractOp]


def load_contract() -> Contract:
    """Load the learned_patterns repository contract from YAML.

    Returns a lightweight Contract object with just the fields needed for testing.
    """
    contract_path = (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "omniintelligence"
        / "repositories"
        / "learned_patterns.repository.yaml"
    )

    with open(contract_path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    ops_data = data["db_repository"]["ops"]
    ops = {
        name: ContractOp(
            name=name,
            sql=op_data.get("sql", ""),
            description=op_data.get("description", ""),
        )
        for name, op_data in ops_data.items()
    }

    return Contract(ops=ops)


class TestInjectionQueriesEnforceLifecycleFilter:
    """Tests that injection-eligible queries enforce lifecycle_state filter.

    OMN-1894: These queries MUST include WHERE status IN ('validated', 'provisional')
    to prevent CANDIDATE or DEPRECATED patterns from being injected.
    """

    # Queries that MUST filter by lifecycle_state for injection safety
    INJECTION_QUERIES = (
        "list_validated_patterns",
        "list_by_domain",
        "get_pattern",
    )

    @pytest.mark.unit
    def test_injection_queries_filter_by_status(self) -> None:
        """Verify injection queries include status IN ('validated', 'provisional').

        This is the core enforcement check. Without this filter, CANDIDATE and
        DEPRECATED patterns could be injected, making the lifecycle state machine
        meaningless.
        """
        contract = load_contract()

        queries_missing_filter: list[str] = []
        for op_name in self.INJECTION_QUERIES:
            assert op_name in contract.ops, (
                f"Expected operation '{op_name}' not found in contract. "
                f"Available operations: {sorted(contract.ops.keys())}"
            )

            operation = contract.ops[op_name]
            sql = operation.sql

            # Check for status IN ('validated', 'provisional') pattern
            has_lifecycle_filter = re.search(
                r"status\s+IN\s*\(\s*'validated'\s*,\s*'provisional'\s*\)",
                sql,
                re.IGNORECASE,
            )

            if not has_lifecycle_filter:
                queries_missing_filter.append(op_name)

        assert not queries_missing_filter, (
            f"Queries missing lifecycle_state filter: {queries_missing_filter}\n"
            "All injection queries MUST include: WHERE status IN ('validated', 'provisional')\n"
            "See OMN-1894 for requirements."
        )

    @pytest.mark.unit
    def test_injection_queries_exclude_candidate_status(self) -> None:
        """Verify injection queries do NOT allow 'candidate' status.

        CANDIDATE patterns are newly discovered and under evaluation.
        They MUST NOT be injected until promoted to at least PROVISIONAL.
        """
        contract = load_contract()

        for op_name in self.INJECTION_QUERIES:
            operation = contract.ops[op_name]
            sql = operation.sql

            # Check that 'candidate' is not in any status filter
            # This would match: status = 'candidate' or status IN (...'candidate'...)
            has_candidate_allowed = re.search(
                r"status\s*(?:=|IN\s*\([^)]*)\s*'candidate'",
                sql,
                re.IGNORECASE,
            )

            assert not has_candidate_allowed, (
                f"Operation '{op_name}': CANDIDATE status should NOT be allowed.\n"
                f"CANDIDATE patterns are under evaluation and must not be injected.\n"
                f"SQL: {sql}"
            )

    @pytest.mark.unit
    def test_injection_queries_exclude_deprecated_status(self) -> None:
        """Verify injection queries do NOT allow 'deprecated' status.

        DEPRECATED patterns have been demoted and should no longer be used.
        They MUST NOT be injected.
        """
        contract = load_contract()

        for op_name in self.INJECTION_QUERIES:
            operation = contract.ops[op_name]
            sql = operation.sql

            # Check that 'deprecated' is not in any status filter
            has_deprecated_allowed = re.search(
                r"status\s*(?:=|IN\s*\([^)]*)\s*'deprecated'",
                sql,
                re.IGNORECASE,
            )

            assert not has_deprecated_allowed, (
                f"Operation '{op_name}': DEPRECATED status should NOT be allowed.\n"
                f"DEPRECATED patterns should not be injected.\n"
                f"SQL: {sql}"
            )


class TestValidatedPatternsPriorityOrdering:
    """Tests that validated patterns are prioritized over provisional.

    OMN-1894: VALIDATED patterns should be returned before PROVISIONAL.
    PROVISIONAL patterns serve as a bootstrap fallback only.
    """

    @pytest.mark.unit
    def test_list_validated_patterns_prefers_validated_status(self) -> None:
        """Verify list_validated_patterns orders validated before provisional.

        The ORDER BY clause should include a CASE expression that ranks
        'validated' (0) higher than 'provisional' (1).
        """
        contract = load_contract()
        operation = contract.ops["list_validated_patterns"]
        sql = operation.sql

        # Check for CASE WHEN status = 'validated' THEN 0 ELSE 1 END pattern
        has_priority_ordering = re.search(
            r"ORDER\s+BY\s+.*CASE\s+WHEN\s+status\s*=\s*'validated'\s+THEN\s+0\s+ELSE\s+1\s+END",
            sql,
            re.IGNORECASE | re.DOTALL,
        )

        assert has_priority_ordering, (
            "list_validated_patterns: Should order validated patterns before provisional.\n"
            "Expected ORDER BY clause with: CASE WHEN status = 'validated' THEN 0 ELSE 1 END\n"
            f"SQL: {sql}"
        )

    @pytest.mark.unit
    def test_list_by_domain_prefers_validated_status(self) -> None:
        """Verify list_by_domain orders validated before provisional.

        Same priority ordering requirement as list_validated_patterns.
        """
        contract = load_contract()
        operation = contract.ops["list_by_domain"]
        sql = operation.sql

        # Check for CASE WHEN status = 'validated' THEN 0 ELSE 1 END pattern
        has_priority_ordering = re.search(
            r"ORDER\s+BY\s+.*CASE\s+WHEN\s+status\s*=\s*'validated'\s+THEN\s+0\s+ELSE\s+1\s+END",
            sql,
            re.IGNORECASE | re.DOTALL,
        )

        assert has_priority_ordering, (
            "list_by_domain: Should order validated patterns before provisional.\n"
            "Expected ORDER BY clause with: CASE WHEN status = 'validated' THEN 0 ELSE 1 END\n"
            f"SQL: {sql}"
        )


class TestExemptQueriesNotFiltered:
    """Tests that exempt queries are intentionally unfiltered.

    OMN-1894 EXEMPTIONS: These queries are NOT filtered by lifecycle_state:
    - list_promotion_candidates: needs to see candidate/provisional
    - list_demotion_candidates: needs to see validated (to demote them)
    - get_latest_by_lineage: used for version management across all states
    - get_pattern_admin: administrative access (intentionally unrestricted)
    """

    PROMOTION_DEMOTION_QUERIES = (
        "list_promotion_candidates",
        "list_demotion_candidates",
    )

    @pytest.mark.unit
    def test_promotion_candidates_query_allows_candidate_status(self) -> None:
        """Verify list_promotion_candidates can see CANDIDATE patterns.

        This query finds patterns eligible for promotion, which are
        currently CANDIDATE or PROVISIONAL.
        """
        contract = load_contract()
        operation = contract.ops["list_promotion_candidates"]
        sql = operation.sql

        # Should include 'candidate' in status filter
        has_candidate = re.search(
            r"status\s+IN\s*\([^)]*'candidate'[^)]*\)",
            sql,
            re.IGNORECASE,
        )

        assert has_candidate, (
            "list_promotion_candidates: Should allow 'candidate' status.\n"
            "This query needs to find candidates for promotion."
        )

    @pytest.mark.unit
    def test_demotion_candidates_query_allows_validated_status(self) -> None:
        """Verify list_demotion_candidates can see VALIDATED patterns.

        This query finds patterns that may need demotion, which are
        currently VALIDATED but failing.
        """
        contract = load_contract()
        operation = contract.ops["list_demotion_candidates"]
        sql = operation.sql

        # Should filter by 'validated' status
        has_validated = re.search(
            r"status\s*=\s*'validated'",
            sql,
            re.IGNORECASE,
        )

        assert has_validated, (
            "list_demotion_candidates: Should filter by 'validated' status.\n"
            "This query finds validated patterns that may need demotion."
        )

    @pytest.mark.unit
    def test_get_latest_by_lineage_is_unfiltered(self) -> None:
        """Verify get_latest_by_lineage does NOT filter by status.

        This query is used for lineage management and must see patterns
        in ANY lifecycle state to properly manage version transitions.
        """
        contract = load_contract()
        operation = contract.ops["get_latest_by_lineage"]
        sql = operation.sql

        # Should NOT have status filter
        has_status_filter = re.search(
            r"status\s*(?:=|IN)",
            sql,
            re.IGNORECASE,
        )

        assert not has_status_filter, (
            "get_latest_by_lineage: Should NOT filter by status.\n"
            "This query is for lineage management and must see all states.\n"
            f"SQL: {sql}"
        )

    @pytest.mark.unit
    def test_get_pattern_admin_exists_and_is_unfiltered(self) -> None:
        """Verify get_pattern_admin exists for unrestricted admin access.

        This administrative query allows fetching any pattern regardless
        of lifecycle state (for debugging, metrics, etc.).
        """
        contract = load_contract()

        assert "get_pattern_admin" in contract.ops, (
            "Expected 'get_pattern_admin' operation for administrative access.\n"
            f"Available operations: {sorted(contract.ops.keys())}"
        )

        operation = contract.ops["get_pattern_admin"]
        sql = operation.sql

        # Should NOT have status filter
        has_status_filter = re.search(
            r"status\s*(?:=|IN)",
            sql,
            re.IGNORECASE,
        )

        assert not has_status_filter, (
            "get_pattern_admin: Should NOT filter by status.\n"
            "This is an administrative query for unrestricted access.\n"
            f"SQL: {sql}"
        )


class TestContractDocumentation:
    """Tests that contract documentation reflects OMN-1894 changes."""

    @pytest.mark.unit
    def test_list_validated_patterns_description_mentions_filter(self) -> None:
        """Verify list_validated_patterns description documents lifecycle filter.

        Documentation should clearly state that only validated/provisional
        patterns are returned.
        """
        contract = load_contract()
        operation = contract.ops["list_validated_patterns"]
        description = operation.description.lower()

        assert "omn-1894" in description or (
            "validated" in description and "provisional" in description
        ), (
            "list_validated_patterns: Description should mention lifecycle filtering.\n"
            f"Description: {operation.description}"
        )

    @pytest.mark.unit
    def test_injection_queries_document_exclusions(self) -> None:
        """Verify injection queries document that CANDIDATE/DEPRECATED are excluded.

        Clear documentation helps developers understand the enforcement.
        """
        contract = load_contract()

        for op_name in ("list_validated_patterns", "list_by_domain", "get_pattern"):
            operation = contract.ops[op_name]
            description = operation.description.lower()

            # Should mention either OMN-1894 or explicitly state what's excluded
            mentions_enforcement = (
                "omn-1894" in description
                or "candidate" in description
                or "deprecated" in description
                or "injectable" in description
            )

            assert mentions_enforcement, (
                f"Operation '{op_name}': Description should document lifecycle enforcement.\n"
                f"Description: {operation.description}"
            )


__all__ = [
    "TestContractDocumentation",
    "TestExemptQueriesNotFiltered",
    "TestInjectionQueriesEnforceLifecycleFilter",
    "TestValidatedPatternsPriorityOrdering",
]
