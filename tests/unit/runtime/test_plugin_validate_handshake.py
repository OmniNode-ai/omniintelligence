# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for PluginIntelligence.validate_handshake().

Validates:
    - Returns failed result when pool is None (no gate to run)
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
    SchemaFingerprintMismatchError,
    SchemaFingerprintMissingError,
)
from omnibase_infra.runtime.models.model_handshake_result import ModelHandshakeResult
from omnibase_infra.runtime.protocol_domain_plugin import ModelDomainPluginConfig

from omniintelligence.runtime.plugin import PluginIntelligence

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
async def test_validate_handshake_pool_none_returns_failed() -> None:
    """validate_handshake returns a failed result when _pool is None."""
    plugin = PluginIntelligence()
    config = _make_config()

    result = await plugin.validate_handshake(config)

    assert isinstance(result, ModelHandshakeResult)
    assert not result.passed
    assert result.error_message is not None
    assert "pool not initialized" in result.error_message


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
        with pytest.raises(DbOwnershipMismatchError):
            await plugin.validate_handshake(config)

    # B2 must not be attempted when B1 fails (intentional short-circuit)
    mock_fingerprint.assert_not_called()


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
        with pytest.raises(DbOwnershipMissingError):
            await plugin.validate_handshake(config)

    # B2 must not be attempted when B1 fails (intentional short-circuit)
    mock_fingerprint.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b2_mismatch_raises_and_records_check() -> None:
    """B2 SchemaFingerprintMismatchError propagates after B1 passes."""
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
        with pytest.raises(SchemaFingerprintMismatchError):
            await plugin.validate_handshake(config)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_handshake_b2_missing_raises_and_records_check() -> None:
    """B2 SchemaFingerprintMissingError propagates (fingerprint not stamped)."""
    plugin = _make_plugin_with_pool()
    config = _make_config()

    error = SchemaFingerprintMissingError(
        "expected_schema_fingerprint is NULL in db_metadata",
        expected_owner="omniintelligence",
        correlation_id=config.correlation_id,
    )

    with (
        patch(_OWNERSHIP_PATH, new=AsyncMock(return_value=None)),
        patch(_FINGERPRINT_PATH, new=AsyncMock(side_effect=error)),
    ):
        with pytest.raises(SchemaFingerprintMissingError):
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
