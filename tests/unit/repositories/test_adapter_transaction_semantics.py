"""Unit tests documenting AdapterPatternStore transaction isolation behavior.

This module tests the transaction semantics of AdapterPatternStore, specifically:

1. The adapter ignores the `conn` parameter and manages its own connections
2. A warning is logged when `conn` is passed (first time only)
3. The warning is rate-limited to once per adapter instance

Transaction Semantics Documentation
-----------------------------------
The AdapterPatternStore DOES NOT honor external transaction control:

- Each method call is an independent transaction
- The adapter manages its own connection pool via PostgresRepositoryRuntime
- Callers CANNOT control BEGIN/COMMIT/ROLLBACK boundaries
- The `conn` parameter exists ONLY for interface compatibility

This behavior is by design - see AdapterPatternStore class docstring for rationale.

If external transaction control is required, use a different ProtocolPatternStore
implementation that honors the `conn` parameter.
"""

import logging
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.models import EnumPatternState
from omniintelligence.repositories.adapter_pattern_store import AdapterPatternStore


def _create_adapter_with_mock_runtime() -> AdapterPatternStore:
    """Create an adapter with a mocked runtime for testing.

    The mock runtime:
    - Has a minimal contract with store_pattern operation
    - Returns a dict with 'id' on call() to simulate successful storage
    """
    mock_runtime = MagicMock()
    mock_runtime.contract = MagicMock()
    mock_runtime.contract.ops = {
        "store_pattern": MagicMock(
            params={
                "id": MagicMock(required=True, default=None),
                "signature": MagicMock(required=True, default=None),
                "domain_id": MagicMock(required=True, default=None),
                "confidence": MagicMock(required=True, default=None),
                "quality_score": MagicMock(required=True, default=None),
                "status": MagicMock(required=True, default=None),
                "source_session_ids": MagicMock(required=True, default=None),
                "version": MagicMock(required=True, default=None),
                "domain_version": MagicMock(
                    required=False, default=MagicMock(to_value=lambda: "1.0")
                ),
                "domain_candidates": MagicMock(
                    required=False, default=MagicMock(to_value=lambda: "[]")
                ),
                "keywords": MagicMock(required=False, default=None),
                "recurrence_count": MagicMock(
                    required=False, default=MagicMock(to_value=lambda: 1)
                ),
                "supersedes": MagicMock(required=False, default=None),
            }
        ),
        "store_with_version_transition": MagicMock(
            params={
                "id": MagicMock(required=True, default=None),
                "signature": MagicMock(required=True, default=None),
                "domain_id": MagicMock(required=True, default=None),
                "confidence": MagicMock(required=True, default=None),
                "quality_score": MagicMock(required=True, default=None),
                "status": MagicMock(required=True, default=None),
                "source_session_ids": MagicMock(required=True, default=None),
                "version": MagicMock(required=True, default=None),
                "domain_version": MagicMock(
                    required=False, default=MagicMock(to_value=lambda: "1.0")
                ),
                "domain_candidates": MagicMock(
                    required=False, default=MagicMock(to_value=lambda: "[]")
                ),
                "keywords": MagicMock(required=False, default=None),
                "recurrence_count": MagicMock(
                    required=False, default=MagicMock(to_value=lambda: 1)
                ),
            }
        ),
    }

    # Make call() return a dict with 'id' to simulate successful storage
    async def mock_call(_op_name: str, *_args):
        return {"id": str(uuid4())}

    mock_runtime.call = AsyncMock(side_effect=mock_call)

    return AdapterPatternStore(runtime=mock_runtime)


def _create_sample_store_kwargs(*, conn=None) -> dict:
    """Create sample keyword arguments for store_pattern().

    Args:
        conn: Connection parameter to pass (None or mock).

    Returns:
        Dict of kwargs suitable for store_pattern().
    """
    return {
        "pattern_id": uuid4(),
        "signature": "test_signature_content",
        "signature_hash": "abc123hash",
        "domain": "test_domain",
        "version": 1,
        "confidence": 0.85,
        "quality_score": 0.75,
        "state": EnumPatternState.CANDIDATE,
        "is_current": True,
        "stored_at": datetime.now(tz=UTC),
        "correlation_id": uuid4(),
        "conn": conn,
    }


@pytest.mark.unit
class TestAdapterTransactionSemantics:
    """Tests documenting AdapterPatternStore transaction behavior.

    These tests verify and document the adapter's transaction isolation
    characteristics, particularly around the `conn` parameter handling.
    """

    @pytest.mark.asyncio
    async def test_conn_warning_logged_once_on_store_pattern(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Adapter logs warning when conn passed to store_pattern, but only once.

        This test verifies the rate-limiting behavior: the warning about
        ignored `conn` parameter should only be logged ONCE per adapter instance,
        regardless of how many times store_pattern is called with a non-None conn.
        """
        # Arrange
        adapter = _create_adapter_with_mock_runtime()
        mock_conn = MagicMock()  # Simulate a real connection object

        # Act - Call store_pattern twice with conn
        with caplog.at_level(logging.WARNING):
            await adapter.store_pattern(**_create_sample_store_kwargs(conn=mock_conn))
            await adapter.store_pattern(**_create_sample_store_kwargs(conn=mock_conn))

        # Assert - Warning should appear exactly once
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        conn_warnings = [
            m for m in warning_messages if "conn parameter ignored" in m
        ]

        assert len(conn_warnings) == 1, (
            f"Expected exactly 1 conn warning, got {len(conn_warnings)}. "
            f"All warnings: {warning_messages}"
        )
        assert "AdapterPatternStore" in conn_warnings[0]
        assert "transaction semantics" in conn_warnings[0]

    @pytest.mark.asyncio
    async def test_conn_warning_not_logged_when_none(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No warning when conn is None.

        The warning is only intended to alert callers who explicitly pass
        a connection expecting it to be used. When conn is None (the typical
        case), no warning should be logged.
        """
        # Arrange
        adapter = _create_adapter_with_mock_runtime()

        # Act - Call store_pattern with conn=None
        with caplog.at_level(logging.WARNING):
            await adapter.store_pattern(**_create_sample_store_kwargs(conn=None))
            await adapter.store_pattern(**_create_sample_store_kwargs(conn=None))

        # Assert - No conn warnings should appear
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        conn_warnings = [
            m for m in warning_messages if "conn parameter ignored" in m
        ]

        assert len(conn_warnings) == 0, (
            f"Expected no conn warnings when conn=None, got: {conn_warnings}"
        )

    @pytest.mark.asyncio
    async def test_conn_warning_logged_once_on_store_with_version_transition(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Adapter logs warning when conn passed to store_with_version_transition.

        Same rate-limiting behavior applies to store_with_version_transition.
        """
        # Arrange
        adapter = _create_adapter_with_mock_runtime()
        mock_conn = MagicMock()

        # Act - Call store_with_version_transition twice with conn
        with caplog.at_level(logging.WARNING):
            await adapter.store_with_version_transition(
                **_create_sample_store_kwargs(conn=mock_conn)
            )
            await adapter.store_with_version_transition(
                **_create_sample_store_kwargs(conn=mock_conn)
            )

        # Assert - Warning should appear exactly once
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        conn_warnings = [
            m for m in warning_messages if "conn parameter ignored" in m
        ]

        assert len(conn_warnings) == 1, (
            f"Expected exactly 1 conn warning, got {len(conn_warnings)}. "
            f"All warnings: {warning_messages}"
        )

    @pytest.mark.asyncio
    async def test_warning_flag_shared_across_methods(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Warning flag is shared across all methods on same adapter instance.

        Once the warning is logged (by any method), it should not be logged
        again by any other method on the same adapter instance.
        """
        # Arrange
        adapter = _create_adapter_with_mock_runtime()
        mock_conn = MagicMock()

        # Act - Call store_pattern first, then store_with_version_transition
        with caplog.at_level(logging.WARNING):
            # First call triggers warning
            await adapter.store_pattern(**_create_sample_store_kwargs(conn=mock_conn))
            # Second call should NOT trigger warning (flag already set)
            await adapter.store_with_version_transition(
                **_create_sample_store_kwargs(conn=mock_conn)
            )

        # Assert - Warning should appear exactly once (from first call)
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        conn_warnings = [
            m for m in warning_messages if "conn parameter ignored" in m
        ]

        assert len(conn_warnings) == 1, (
            f"Expected exactly 1 conn warning shared across methods, "
            f"got {len(conn_warnings)}. All warnings: {warning_messages}"
        )

    @pytest.mark.asyncio
    async def test_separate_adapter_instances_log_independently(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each adapter instance maintains its own warning flag.

        Different adapter instances should log warnings independently.
        """
        # Arrange
        adapter1 = _create_adapter_with_mock_runtime()
        adapter2 = _create_adapter_with_mock_runtime()
        mock_conn = MagicMock()

        # Act - Call store_pattern on both adapters
        with caplog.at_level(logging.WARNING):
            await adapter1.store_pattern(**_create_sample_store_kwargs(conn=mock_conn))
            await adapter2.store_pattern(**_create_sample_store_kwargs(conn=mock_conn))

        # Assert - Each adapter should log its own warning (2 total)
        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        conn_warnings = [
            m for m in warning_messages if "conn parameter ignored" in m
        ]

        assert len(conn_warnings) == 2, (
            f"Expected 2 conn warnings (one per adapter), got {len(conn_warnings)}. "
            f"All warnings: {warning_messages}"
        )


@pytest.mark.unit
class TestAdapterTransactionIsolationDocumentation:
    """Documentation tests for transaction isolation behavior.

    These tests serve as executable documentation for the adapter's
    transaction handling characteristics. They don't test implementation
    details but rather document expected behavior.
    """

    def test_adapter_initializes_with_warning_flag_false(self) -> None:
        """New adapter instances start with warning flag unset.

        This ensures the first call with conn will trigger the warning.
        """
        adapter = _create_adapter_with_mock_runtime()

        assert adapter._conn_warning_logged is False

    @pytest.mark.asyncio
    async def test_warning_flag_set_after_first_conn_call(self) -> None:
        """Warning flag is set after first call with non-None conn.

        This is the mechanism that implements rate-limiting.
        """
        adapter = _create_adapter_with_mock_runtime()
        mock_conn = MagicMock()

        # Pre-condition
        assert adapter._conn_warning_logged is False

        # Act
        await adapter.store_pattern(**_create_sample_store_kwargs(conn=mock_conn))

        # Post-condition
        assert adapter._conn_warning_logged is True

    @pytest.mark.asyncio
    async def test_warning_flag_unchanged_when_conn_none(self) -> None:
        """Warning flag remains unset when conn is None.

        Calling with conn=None should not affect the warning flag state.
        """
        adapter = _create_adapter_with_mock_runtime()

        # Pre-condition
        assert adapter._conn_warning_logged is False

        # Act
        await adapter.store_pattern(**_create_sample_store_kwargs(conn=None))

        # Post-condition - flag still False
        assert adapter._conn_warning_logged is False

    def test_docstring_documents_transaction_semantics(self) -> None:
        """Verify AdapterPatternStore docstring documents transaction behavior.

        The class docstring should clearly explain that conn is ignored.
        """
        docstring = AdapterPatternStore.__doc__

        assert docstring is not None
        assert "conn" in docstring.lower()
        assert "transaction" in docstring.lower()
        assert "NOT used" in docstring or "ignored" in docstring.lower()
