# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the query_patterns contract operation.

Validates the contract YAML definition for the query_patterns operation
matches the expected schema and parameter definitions.

Ticket: OMN-2253
"""

from __future__ import annotations

import pytest
from omnibase_core.models.contracts import ModelDbRepositoryContract

from omniintelligence.repositories.adapter_pattern_store import load_contract


@pytest.mark.unit
class TestQueryPatternsContract:
    """Tests for query_patterns operation in the repository contract."""

    @pytest.fixture
    def contract(self) -> ModelDbRepositoryContract:
        """Load the repository contract."""
        return load_contract()

    def test_query_patterns_operation_exists(self, contract) -> None:
        """Contract defines the query_patterns operation."""
        assert "query_patterns" in contract.ops

    def test_query_patterns_is_read_operation(self, contract) -> None:
        """query_patterns is a read-only operation."""
        op = contract.ops["query_patterns"]
        assert op.mode == "read"

    def test_query_patterns_has_all_params(self, contract) -> None:
        """query_patterns defines all expected parameters."""
        op = contract.ops["query_patterns"]
        param_names = set(op.params.keys())
        assert "domain_id" in param_names
        assert "language" in param_names
        assert "min_confidence" in param_names
        assert "limit" in param_names
        assert "offset" in param_names

    def test_domain_id_is_optional(self, contract) -> None:
        """domain_id parameter is optional for broad queries."""
        op = contract.ops["query_patterns"]
        domain_param = op.params["domain_id"]
        assert not domain_param.required

    def test_language_is_optional(self, contract) -> None:
        """language parameter is optional."""
        op = contract.ops["query_patterns"]
        language_param = op.params["language"]
        assert not language_param.required

    def test_min_confidence_default(self, contract) -> None:
        """min_confidence defaults to 0.7."""
        op = contract.ops["query_patterns"]
        param = op.params["min_confidence"]
        assert not param.required
        assert param.default is not None
        assert param.default.to_value() == 0.7

    def test_limit_default(self, contract) -> None:
        """limit defaults to 50."""
        op = contract.ops["query_patterns"]
        param = op.params["limit"]
        assert not param.required
        assert param.default is not None
        assert param.default.to_value() == 50

    def test_offset_default(self, contract) -> None:
        """offset defaults to 0."""
        op = contract.ops["query_patterns"]
        param = op.params["offset"]
        assert not param.required
        assert param.default is not None
        assert param.default.to_value() == 0

    def test_returns_many(self, contract) -> None:
        """query_patterns returns multiple rows."""
        op = contract.ops["query_patterns"]
        assert op.returns.many

    def test_returns_pattern_summary_model(self, contract) -> None:
        """query_patterns returns PatternSummary model references."""
        op = contract.ops["query_patterns"]
        assert op.returns.model_ref == "PatternSummary"

    def test_sql_filters_validated_provisional_only(self, contract) -> None:
        """SQL only returns validated and provisional patterns."""
        op = contract.ops["query_patterns"]
        sql = op.sql
        assert "status IN ('validated', 'provisional')" in sql

    def test_sql_filters_current_only(self, contract) -> None:
        """SQL only returns current versions."""
        op = contract.ops["query_patterns"]
        sql = op.sql
        assert "is_current = TRUE" in sql

    def test_sql_has_order_by(self, contract) -> None:
        """SQL includes ORDER BY for deterministic results."""
        op = contract.ops["query_patterns"]
        sql = op.sql
        assert "ORDER BY" in sql

    def test_sql_uses_positional_params(self, contract) -> None:
        """query_patterns SQL uses asyncpg-compatible $N positional params, not :name syntax."""
        op = contract.ops["query_patterns"]
        sql = op.sql
        # Must have all 5 positional placeholders
        assert "$1" in sql, "domain_id should be $1"
        assert "$2" in sql, "language should be $2"
        assert "$3" in sql, "min_confidence should be $3"
        assert "$4" in sql, "limit should be $4"
        assert "$5" in sql, "offset should be $5"

    def test_sql_no_named_params(self, contract) -> None:
        """query_patterns SQL has no :name-style params that break asyncpg."""
        import re

        op = contract.ops["query_patterns"]
        sql = op.sql
        # Match :word but not ::cast — asyncpg throws SyntaxError on these
        named_params = re.findall(r"(?<!:):([a-z_][a-z0-9_]*)", sql)
        assert named_params == [], (
            f"query_patterns SQL still has named params that break asyncpg: {named_params}. "
            "Use $N positional syntax instead."
        )

    def test_query_patterns_positional_arg_order(self, contract) -> None:
        """Adapter _build_positional_args produces correct arg tuple for query_patterns.

        The param order in the YAML dict determines positional index:
          $1 = domain_id, $2 = language, $3 = min_confidence, $4 = limit, $5 = offset
        """
        from unittest.mock import MagicMock

        from omniintelligence.repositories.adapter_pattern_store import (
            AdapterPatternStore,
        )

        mock_runtime = MagicMock()
        mock_runtime.contract = contract
        adapter = AdapterPatternStore(runtime=mock_runtime)

        # Call with all params explicit
        args = adapter._build_positional_args(
            "query_patterns",
            {
                "domain_id": "python",
                "language": "Python",
                "min_confidence": 0.85,
                "limit": 10,
                "offset": 20,
            },
        )

        # Verify positional order: domain_id=$1, language=$2, min_confidence=$3, limit=$4, offset=$5, project_scope=$6
        assert args == ("python", "Python", 0.85, 10, 20, None)

    def test_query_patterns_positional_args_with_defaults(self, contract) -> None:
        """_build_positional_args applies contract defaults for omitted optional params."""
        from unittest.mock import MagicMock

        from omniintelligence.repositories.adapter_pattern_store import (
            AdapterPatternStore,
        )

        mock_runtime = MagicMock()
        mock_runtime.contract = contract
        adapter = AdapterPatternStore(runtime=mock_runtime)

        # Omit all optional params — contract defaults should fill in
        args = adapter._build_positional_args("query_patterns", {})

        # All params are optional with defaults or nullable:
        # domain_id=None, language=None, min_confidence=0.7, limit=50, offset=0, project_scope=None
        assert args == (None, None, 0.7, 50, 0, None)
