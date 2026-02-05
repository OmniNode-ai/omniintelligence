"""Unit tests for signature_hash parameter in learned_patterns repository contract.

Tests verify that signature_hash is properly defined in the contract YAML for:
1. Parameter definitions in relevant operations
2. INSERT statements for store operations
3. WHERE clauses for lineage operations
4. SELECT column lists for list operations

Ticket: OMN-1780
"""

import re

import pytest

from omniintelligence.repositories.adapter_pattern_store import load_contract


class TestContractSignatureHashParamDefinitions:
    """Tests for signature_hash param existence in contract operations."""

    # Operations that MUST have signature_hash param defined
    OPERATIONS_REQUIRING_SIGNATURE_HASH = (
        "store_pattern",
        "store_with_version_transition",
        "check_exists",
        "check_exists_by_id",
        "get_latest_version",
        "set_not_current",
        "get_latest_by_lineage",
    )

    @pytest.mark.unit
    def test_contract_has_signature_hash_param_definitions(self) -> None:
        """Verify signature_hash param exists in all required operations.

        These operations use signature_hash for lineage identity and MUST
        have the param defined with proper metadata.
        """
        contract = load_contract()

        missing_operations: list[str] = []
        for op_name in self.OPERATIONS_REQUIRING_SIGNATURE_HASH:
            # Verify operation exists
            assert op_name in contract.ops, (
                f"Expected operation '{op_name}' not found in contract. "
                f"Available operations: {sorted(contract.ops.keys())}"
            )

            operation = contract.ops[op_name]
            if "signature_hash" not in operation.params:
                missing_operations.append(op_name)

        assert not missing_operations, (
            f"Operations missing signature_hash param: {missing_operations}\n"
            "All lineage operations must include signature_hash for stable identity."
        )

    @pytest.mark.unit
    def test_signature_hash_param_is_required(self) -> None:
        """Verify signature_hash param is marked as required where appropriate.

        For lineage operations, signature_hash is essential and should be required.
        """
        contract = load_contract()

        for op_name in self.OPERATIONS_REQUIRING_SIGNATURE_HASH:
            operation = contract.ops[op_name]
            param = operation.params.get("signature_hash")

            assert (
                param is not None
            ), f"Operation '{op_name}' missing signature_hash param"
            assert param.required is True, (
                f"Operation '{op_name}': signature_hash param should be required, "
                f"but required={param.required}"
            )

    @pytest.mark.unit
    def test_signature_hash_param_has_description(self) -> None:
        """Verify signature_hash param has descriptive documentation.

        Good documentation helps developers understand the param's purpose.
        """
        contract = load_contract()

        for op_name in self.OPERATIONS_REQUIRING_SIGNATURE_HASH:
            operation = contract.ops[op_name]
            param = operation.params.get("signature_hash")

            assert param is not None
            assert (
                param.description
            ), f"Operation '{op_name}': signature_hash param should have a description"
            # Verify description mentions lineage or identity
            description_lower = param.description.lower()
            assert any(
                keyword in description_lower
                for keyword in ("lineage", "identity", "sha256", "hash")
            ), (
                f"Operation '{op_name}': signature_hash description should mention "
                f"lineage/identity purpose. Got: {param.description}"
            )


class TestStoreOperationsIncludeSignatureHash:
    """Tests for signature_hash in store operation SQL INSERT statements."""

    STORE_OPERATIONS = (
        "store_pattern",
        "store_with_version_transition",
    )

    @pytest.mark.unit
    def test_store_operations_include_signature_hash_in_insert(self) -> None:
        """Verify signature_hash appears in INSERT column list and VALUES.

        Store operations must persist signature_hash to the database for
        lineage tracking.
        """
        contract = load_contract()

        for op_name in self.STORE_OPERATIONS:
            operation = contract.ops[op_name]
            sql = operation.sql

            # Check INSERT column list contains signature_hash
            # Pattern: INSERT INTO ... (... signature_hash ...) VALUES
            insert_match = re.search(
                r"INSERT\s+INTO\s+\w+\s*\(([^)]+)\)",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            assert (
                insert_match
            ), f"Operation '{op_name}': Could not find INSERT INTO ... () pattern"

            column_list = insert_match.group(1)
            assert "signature_hash" in column_list, (
                f"Operation '{op_name}': INSERT column list missing 'signature_hash'.\n"
                f"Columns found: {column_list.strip()}"
            )

            # Check VALUES contains :signature_hash placeholder
            values_match = re.search(
                r"VALUES\s*\(([^)]+)\)",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            assert (
                values_match
            ), f"Operation '{op_name}': Could not find VALUES (...) pattern"

            values_list = values_match.group(1)
            assert ":signature_hash" in values_list, (
                f"Operation '{op_name}': VALUES list missing ':signature_hash' placeholder.\n"
                f"Values found: {values_list.strip()}"
            )


class TestLineageOperationsWhereClauseUsesSignatureHash:
    """Tests for signature_hash in WHERE clauses of lineage operations."""

    LINEAGE_OPERATIONS_WITH_WHERE = (
        "check_exists",
        "get_latest_version",
        "set_not_current",
        "get_latest_by_lineage",
        "check_exists_by_id",
    )

    @pytest.mark.unit
    def test_lineage_operations_where_clause_uses_signature_hash(self) -> None:
        """Verify WHERE clause references signature_hash column.

        Lineage operations must use signature_hash (not pattern_signature)
        for stable identity lookups.
        """
        contract = load_contract()

        for op_name in self.LINEAGE_OPERATIONS_WITH_WHERE:
            operation = contract.ops[op_name]
            sql = operation.sql

            # Check WHERE clause exists and contains signature_hash
            where_match = re.search(
                r"WHERE\s+(.+?)(?:RETURNING|ORDER\s+BY|LIMIT|$)",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            assert where_match, f"Operation '{op_name}': Could not find WHERE clause"

            where_clause = where_match.group(1)
            # Check for signature_hash = :signature_hash pattern
            assert re.search(
                r"signature_hash\s*=\s*:signature_hash",
                where_clause,
                re.IGNORECASE,
            ), (
                f"Operation '{op_name}': WHERE clause should use "
                f"'signature_hash = :signature_hash' for lineage lookup.\n"
                f"WHERE clause: {where_clause.strip()}"
            )

    @pytest.mark.unit
    def test_lineage_operations_do_not_use_pattern_signature_for_lookup(self) -> None:
        """Verify lineage operations don't use pattern_signature in WHERE.

        pattern_signature is for display only. Lineage lookups must use
        signature_hash for stable identity.
        """
        contract = load_contract()

        for op_name in self.LINEAGE_OPERATIONS_WITH_WHERE:
            operation = contract.ops[op_name]
            sql = operation.sql

            where_match = re.search(
                r"WHERE\s+(.+?)(?:RETURNING|ORDER\s+BY|LIMIT|$)",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            if not where_match:
                continue

            where_clause = where_match.group(1)
            # Ensure pattern_signature is NOT used in WHERE clause
            assert not re.search(
                r"pattern_signature\s*=",
                where_clause,
                re.IGNORECASE,
            ), (
                f"Operation '{op_name}': WHERE clause should NOT use pattern_signature "
                f"for lookups. Use signature_hash for stable lineage identity.\n"
                f"WHERE clause: {where_clause.strip()}"
            )


class TestSelectOperationsIncludeSignatureHash:
    """Tests for signature_hash in SELECT column lists of list operations."""

    SELECT_OPERATIONS = (
        "list_validated_patterns",
        "list_by_domain",
    )

    @pytest.mark.unit
    def test_select_operations_include_signature_hash(self) -> None:
        """Verify SELECT column list includes signature_hash.

        List operations should return signature_hash so callers can
        use it for lineage operations.
        """
        contract = load_contract()

        for op_name in self.SELECT_OPERATIONS:
            operation = contract.ops[op_name]
            sql = operation.sql

            # Extract SELECT column list
            select_match = re.search(
                r"SELECT\s+(.+?)\s+FROM",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            assert (
                select_match
            ), f"Operation '{op_name}': Could not find SELECT ... FROM pattern"

            column_list = select_match.group(1)
            assert "signature_hash" in column_list, (
                f"Operation '{op_name}': SELECT column list missing 'signature_hash'.\n"
                f"Columns found: {column_list.strip()}"
            )

    @pytest.mark.unit
    def test_select_operations_include_both_signature_fields(self) -> None:
        """Verify SELECT includes both pattern_signature and signature_hash.

        Both fields serve different purposes:
        - pattern_signature: human-readable display
        - signature_hash: stable lineage identity
        """
        contract = load_contract()

        for op_name in self.SELECT_OPERATIONS:
            operation = contract.ops[op_name]
            sql = operation.sql

            select_match = re.search(
                r"SELECT\s+(.+?)\s+FROM",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            assert select_match

            column_list = select_match.group(1)

            # Check for SELECT * which includes both fields
            if column_list.strip() == "*":
                continue  # SELECT * includes everything

            assert "pattern_signature" in column_list, (
                f"Operation '{op_name}': SELECT should include 'pattern_signature' "
                f"for display purposes."
            )
            assert "signature_hash" in column_list, (
                f"Operation '{op_name}': SELECT should include 'signature_hash' "
                f"for lineage tracking."
            )


class TestCTEOperationsUseSignatureHash:
    """Tests for signature_hash in CTE (WITH clause) operations."""

    @pytest.mark.unit
    def test_store_with_version_transition_cte_uses_signature_hash(self) -> None:
        """Verify CTE UPDATE uses signature_hash for version deactivation.

        The store_with_version_transition operation uses a CTE to atomically
        deactivate old versions. This MUST use signature_hash for lineage matching.
        """
        contract = load_contract()
        operation = contract.ops["store_with_version_transition"]
        sql = operation.sql

        # Extract CTE UPDATE clause
        cte_match = re.search(
            r"WITH\s+\w+\s+AS\s*\(\s*UPDATE\s+.+?WHERE\s+(.+?)RETURNING",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert (
            cte_match
        ), "store_with_version_transition: Could not find CTE UPDATE pattern"

        cte_where = cte_match.group(1)
        assert re.search(
            r"signature_hash\s*=\s*:signature_hash",
            cte_where,
            re.IGNORECASE,
        ), (
            "store_with_version_transition: CTE UPDATE WHERE clause should use "
            f"'signature_hash = :signature_hash'.\nCTE WHERE: {cte_where.strip()}"
        )
