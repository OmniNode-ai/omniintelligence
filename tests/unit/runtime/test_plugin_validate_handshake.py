# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for PluginIntelligence.validate_handshake().

Validates:
    - Raises RuntimeHostError when pool is None (initialize() did not run)
    - B1 failure path: DbOwnershipMismatchError propagates and appends check
    - B2 failure path: SchemaFingerprintMismatchError propagates and appends check
    - Happy path: both checks pass, returns ModelHandshakeResult.all_passed()

Related:
    - OMN-2435: omniintelligence missing boot-time handshake despite owning its own DB
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from omnibase_infra.errors import (
    DbOwnershipMismatchError,
    DbOwnershipMissingError,
    RuntimeHostError,
    SchemaFingerprintMismatchError,
    SchemaFingerprintMissingError,
)
from omnibase_infra.runtime.models.model_handshake_result import ModelHandshakeResult
from omnibase_infra.runtime.protocol_domain_plugin import ModelDomainPluginConfig

from omniintelligence.runtime.plugin import (
    _STAMP_SCHEMA_FINGERPRINT_QUERY,
    PluginIntelligence,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OWNERSHIP_PATH = "omniintelligence.runtime.plugin.validate_db_ownership"
_FINGERPRINT_PATH = "omniintelligence.runtime.plugin.validate_schema_fingerprint"


def _make_config() -> ModelDomainPluginConfig:
    """Build a minimal ModelDomainPluginConfig for test use."""
    return ModelDomainPluginConfig(
        container=MagicMock(),
        event_bus=MagicMock(),
        correlation_id=uuid4(),
        input_topic="test.input",
        output_topic="test.output",
        consumer_group="test-group",
    )


def _make_plugin_with_pool() -> PluginIntelligence:
    """Return a PluginIntelligence with a fake pool set."""
    plugin = PluginIntelligence()
    plugin._pool = MagicMock()  # non-None pool
    return plugin


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_pool_none_raises() -> None:
    """validate_handshake raises RuntimeHostError when _pool is None."""
    plugin = PluginIntelligence()
    config = _make_config()

    with pytest.raises(RuntimeHostError) as exc_info:
        await plugin.validate_handshake(config)

    assert "pool not initialized" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b1_mismatch_raises_and_records_check() -> None:
    """B1 DbOwnershipMismatchError propagates and records a failed check."""
    plugin = _make_plugin_with_pool()
    config = _make_config()

    error = DbOwnershipMismatchError(
        "DB owned by other-service, expected omniintelligence",
        actual_owner="other-service",
        expected_owner="omniintelligence",
        correlation_id=config.correlation_id,
    )

    mock_fingerprint = AsyncMock()
    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(side_effect=error)),
        patch(_FINGERPRINT_PATH, new=mock_fingerprint),
    ):
        with pytest.raises(DbOwnershipMismatchError) as exc_info:
            await plugin.validate_handshake(config)

    # B2 must not be attempted when B1 fails (intentional short-circuit)
    mock_fingerprint.assert_not_called()

    # The exception type (DbOwnershipMismatchError) identifies which check failed.
    assert isinstance(exc_info.value, DbOwnershipMismatchError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b1_missing_raises_and_records_check() -> None:
    """B1 DbOwnershipMissingError propagates (db_metadata table absent)."""
    plugin = _make_plugin_with_pool()
    config = _make_config()

    error = DbOwnershipMissingError(
        "db_metadata table not found",
        expected_owner="omniintelligence",
        correlation_id=config.correlation_id,
    )

    mock_fingerprint = AsyncMock()
    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(side_effect=error)),
        patch(_FINGERPRINT_PATH, new=mock_fingerprint),
    ):
        with pytest.raises(DbOwnershipMissingError) as exc_info:
            await plugin.validate_handshake(config)

    # B2 must not be attempted when B1 fails (intentional short-circuit)
    mock_fingerprint.assert_not_called()

    # The exception type (DbOwnershipMissingError) identifies which check failed.
    assert isinstance(exc_info.value, DbOwnershipMissingError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b2_mismatch_raises_and_records_check() -> None:
    """B2 SchemaFingerprintMismatchError propagates after B1 passes and records check."""
    plugin = _make_plugin_with_pool()
    config = _make_config()

    error = SchemaFingerprintMismatchError(
        "Schema drift detected",
        expected_fingerprint="abc123",
        actual_fingerprint="def456",
        diff_summary="~ changed: learned_patterns",
        correlation_id=config.correlation_id,
    )

    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(return_value=None)),
        patch(_FINGERPRINT_PATH, new=AsyncMock(side_effect=error)),
    ):
        with pytest.raises(SchemaFingerprintMismatchError) as exc_info:
            await plugin.validate_handshake(config)

    # The exception type (SchemaFingerprintMismatchError) identifies which check failed.
    assert isinstance(exc_info.value, SchemaFingerprintMismatchError)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b2_missing_auto_stamps_on_first_boot() -> None:
    """B2 SchemaFingerprintMissingError (NULL fingerprint) triggers auto-stamp on first boot.

    validate_handshake intercepts SchemaFingerprintMissingError, computes the live
    fingerprint, stamps it to db_metadata, and returns a passed result.
    No exception is raised — first boot proceeds normally.
    """
    from omnibase_infra.runtime.model_schema_fingerprint_result import (
        ModelSchemaFingerprintResult,
    )

    plugin = _make_plugin_with_pool()
    config = _make_config()

    error = SchemaFingerprintMissingError(
        "expected_schema_fingerprint is NULL in db_metadata",
        expected_owner="omniintelligence",
        correlation_id=config.correlation_id,
    )

    fake_fingerprint_result = ModelSchemaFingerprintResult(
        fingerprint="a" * 64,
        table_count=12,
        column_count=80,
        constraint_count=20,
        per_table_hashes=(),
    )

    # Mock pool.acquire() context manager for the stamp UPDATE
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    plugin._pool.acquire = MagicMock(return_value=mock_acquire)

    _COMPUTE_PATCH = "omniintelligence.runtime.plugin.compute_schema_fingerprint"

    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(return_value=None)),
        patch(_FINGERPRINT_PATH, new=AsyncMock(side_effect=error)),
        patch(_COMPUTE_PATCH, new=AsyncMock(return_value=fake_fingerprint_result)),
    ):
        result = await plugin.validate_handshake(config)

    # Auto-stamp path: no exception, result is passed
    assert isinstance(result, ModelHandshakeResult)
    assert result.passed
    # schema_fingerprint check is present and passed
    fp_checks = [c for c in result.checks if c.check_name == "schema_fingerprint"]
    assert len(fp_checks) == 1
    assert fp_checks[0].passed is True
    assert "first boot" in fp_checks[0].message.lower()
    # The stamp UPDATE was executed on the connection with the correct query and fingerprint
    mock_conn.execute.assert_called_once_with(
        _STAMP_SCHEMA_FINGERPRINT_QUERY, fake_fingerprint_result.fingerprint
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_auto_stamp_unexpected_error_propagates() -> None:
    """Unexpected errors from compute_schema_fingerprint propagate uncaught.

    Documents the known behavior: only SchemaFingerprintMissingError and
    SchemaFingerprintMismatchError are handled in the B2 path.  An unexpected
    error (e.g., RuntimeError from a programming bug) is not wrapped in a typed
    handshake error and propagates directly to the caller.
    """
    plugin = _make_plugin_with_pool()
    config = _make_config()

    missing_error = SchemaFingerprintMissingError(
        "expected_schema_fingerprint is NULL in db_metadata",
        expected_owner="omniintelligence",
        correlation_id=config.correlation_id,
    )
    unexpected_error = RuntimeError("unexpected failure in compute_schema_fingerprint")

    _COMPUTE_PATCH = "omniintelligence.runtime.plugin.compute_schema_fingerprint"

    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(return_value=None)),
        patch(_FINGERPRINT_PATH, new=AsyncMock(side_effect=missing_error)),
        patch(_COMPUTE_PATCH, new=AsyncMock(side_effect=unexpected_error)),
    ):
        with pytest.raises(RuntimeError, match="unexpected failure"):
            await plugin.validate_handshake(config)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_happy_path_returns_all_passed() -> None:
    """Both B1 and B2 pass: returns ModelHandshakeResult with all_passed()."""
    plugin = _make_plugin_with_pool()
    config = _make_config()

    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(return_value=None)),
        patch(_FINGERPRINT_PATH, new=AsyncMock(return_value=None)),
    ):
        result = await plugin.validate_handshake(config)

    assert isinstance(result, ModelHandshakeResult)
    assert result.passed
    assert result.plugin_id == "intelligence"
    assert len(result.checks) == 2
    assert all(c.passed for c in result.checks)
    check_names = [c.check_name for c in result.checks]
    assert "db_ownership" in check_names
    assert "schema_fingerprint" in check_names


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wire_handlers_raises_when_handshake_not_validated() -> None:
    """wire_handlers() raises RuntimeError when validate_handshake() has not been called."""
    plugin = PluginIntelligence()
    # Default initial state: _handshake_validated is False
    assert not plugin._handshake_validated
    config = _make_config()

    with pytest.raises(RuntimeError) as exc_info:
        await plugin.wire_handlers(config)

    assert "validate_handshake" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wire_dispatchers_raises_when_handshake_not_validated() -> None:
    """wire_dispatchers() raises RuntimeError when validate_handshake() has not been called."""
    plugin = PluginIntelligence()
    # Default initial state: _handshake_validated is False
    assert not plugin._handshake_validated
    config = _make_config()

    with pytest.raises(RuntimeError) as exc_info:
        await plugin.wire_dispatchers(config)

    assert "validate_handshake" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b1_failure_cleans_up_pool() -> None:
    """validate_handshake B1 failure calls _cleanup_on_failure(), clearing _pool.

    After a B1 failure, _cleanup_on_failure() resets _pool to None so that a
    retry of the bootstrap sequence starts clean (re-initialize() required).
    A second call to validate_handshake() therefore raises RuntimeHostError
    (pool not initialized) rather than the original ownership error.
    """
    plugin = _make_plugin_with_pool()
    config = _make_config()

    error = DbOwnershipMismatchError(
        "DB owned by other-service, expected omniintelligence",
        actual_owner="other-service",
        expected_owner="omniintelligence",
        correlation_id=config.correlation_id,
    )

    with patch(_OWNERSHIP_PATH, new=AsyncMock(side_effect=error)):
        with pytest.raises(DbOwnershipMismatchError):
            await plugin.validate_handshake(config)

    # After B1 failure, _cleanup_on_failure() clears _pool.
    assert plugin._pool is None

    # Second call without re-initializing raises RuntimeHostError (pool is None).
    with pytest.raises(RuntimeHostError, match="pool not initialized"):
        await plugin.validate_handshake(config)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_consumers_raises_when_handshake_not_validated() -> None:
    """start_consumers() raises RuntimeError when validate_handshake() has not been called."""
    plugin = PluginIntelligence()
    # Default initial state: _handshake_validated is False
    assert not plugin._handshake_validated
    config = _make_config()

    with pytest.raises(RuntimeError) as exc_info:
        await plugin.start_consumers(config)

    assert "validate_handshake" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_resets_handshake_validated() -> None:
    """shutdown() resets _handshake_validated to False."""
    plugin = PluginIntelligence()
    plugin._handshake_validated = True
    config = _make_config()

    # Shutdown with no pool/idempotency_store initialised: runs _do_shutdown()
    # which unconditionally sets _handshake_validated = False at the end.
    await plugin.shutdown(config)

    assert plugin._handshake_validated is False
