"""Unit tests for AdapterPatternStore signature_hash parameter mappings.

Tests verify that:
1. store_pattern maps both `signature` and `signature_hash` correctly
2. All lineage operations use `signature_hash` (not `signature`) for lookups
3. The parameter names match what the contract SQL expects

Background:
    Previously signature and signature_hash were conflated (hash stored in
    pattern_signature column). Now they are separate:
    - signature: Raw pattern text (stored in pattern_signature column)
    - signature_hash: SHA256 hash for stable lineage identity
"""

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from omniintelligence.nodes.node_pattern_storage_effect.models import EnumPatternState
from omniintelligence.repositories.adapter_pattern_store import AdapterPatternStore

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_runtime() -> MagicMock:
    """Create a mock PostgresRepositoryRuntime with minimal contract."""
    runtime = MagicMock()
    runtime.call = AsyncMock(
        return_value={"id": "00000000-0000-0000-0000-000000000001"}
    )
    return runtime


@pytest.fixture
def adapter(mock_runtime: MagicMock) -> AdapterPatternStore:
    """Create an AdapterPatternStore with mocked runtime."""
    return AdapterPatternStore(runtime=mock_runtime)


@pytest.fixture
def sample_pattern_id() -> UUID:
    """Sample pattern UUID for tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Sample correlation UUID for tests."""
    return UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef")


@pytest.fixture
def sample_signature() -> str:
    """Sample raw pattern signature text."""
    return "def example_pattern(x: int) -> str: ..."


@pytest.fixture
def sample_signature_hash() -> str:
    """Sample SHA256 hash of the signature."""
    return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _make_capture_fn(
    captured_args: dict[str, object],
) -> Callable[[str, dict[str, object]], tuple[object, ...]]:
    """Create a capture function for _build_positional_args."""

    def capture_build_args(
        _op_name: str, provided: dict[str, object]
    ) -> tuple[object, ...]:
        captured_args.update(provided)
        return tuple(provided.values())

    return capture_build_args


def _make_capture_op_fn(
    captured_op: list[str],
) -> Callable[[str, dict[str, object]], tuple[object, ...]]:
    """Create a capture function that also records operation name."""

    def capture_build_args(
        op_name: str, provided: dict[str, object]
    ) -> tuple[object, ...]:
        captured_op.append(op_name)
        return tuple(provided.values())

    return capture_build_args


# =============================================================================
# Test: store_pattern maps both signature fields
# =============================================================================


class TestStorePatternSignatureMapping:
    """Tests for store_pattern signature field mapping."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_pattern_maps_both_signature_fields(
        self,
        adapter: AdapterPatternStore,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
        sample_signature: str,
        sample_signature_hash: str,
    ) -> None:
        """store_pattern passes both signature and signature_hash to runtime args."""
        # Arrange
        captured_args: dict[str, object] = {}

        # Patch _build_positional_args to capture what's passed
        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            # Act
            await adapter.store_pattern(
                pattern_id=sample_pattern_id,
                signature=sample_signature,
                signature_hash=sample_signature_hash,
                domain="test-domain",
                version=1,
                confidence=0.85,
                quality_score=0.75,
                state=EnumPatternState.CANDIDATE,
                is_current=True,
                stored_at=datetime.now(UTC),
                correlation_id=sample_correlation_id,
                conn=None,  # type: ignore[arg-type]
            )

        # Assert - verify both signature fields are passed correctly
        assert "signature" in captured_args, "signature key missing from args"
        assert "signature_hash" in captured_args, "signature_hash key missing from args"
        assert captured_args["signature"] == sample_signature
        assert captured_args["signature_hash"] == sample_signature_hash

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_pattern_signature_maps_to_signature_key(
        self,
        adapter: AdapterPatternStore,
        sample_pattern_id: UUID,
        sample_signature: str,
        sample_signature_hash: str,
    ) -> None:
        """Verify signature param maps to 'signature' key (not 'pattern_signature')."""
        captured_args: dict[str, object] = {}

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.store_pattern(
                pattern_id=sample_pattern_id,
                signature=sample_signature,
                signature_hash=sample_signature_hash,
                domain="test-domain",
                version=1,
                confidence=0.85,
                state=EnumPatternState.CANDIDATE,
                is_current=True,
                stored_at=datetime.now(UTC),
                conn=None,  # type: ignore[arg-type]
            )

        # The key should be 'signature' to match the contract param name
        # NOT 'pattern_signature' (that's the column name)
        assert "signature" in captured_args
        assert "pattern_signature" not in captured_args


# =============================================================================
# Test: check_exists uses signature_hash
# =============================================================================


class TestCheckExistsSignatureHash:
    """Tests for check_exists using signature_hash."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exists_uses_signature_hash(
        self,
        adapter: AdapterPatternStore,
        mock_runtime: MagicMock,
        sample_signature_hash: str,
    ) -> None:
        """check_exists passes signature_hash (not signature) to the runtime."""
        captured_args: dict[str, object] = {}

        mock_runtime.call = AsyncMock(return_value={"exists": True})

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.check_exists(
                domain="test-domain",
                signature_hash=sample_signature_hash,
                version=1,
                conn=None,  # type: ignore[arg-type]
            )

        # Assert signature_hash is passed, signature is NOT
        assert "signature_hash" in captured_args
        assert captured_args["signature_hash"] == sample_signature_hash
        assert "signature" not in captured_args

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exists_does_not_use_signature(
        self,
        adapter: AdapterPatternStore,
        mock_runtime: MagicMock,
        sample_signature_hash: str,
    ) -> None:
        """check_exists should NOT have a 'signature' key in args (uses hash only)."""
        captured_args: dict[str, object] = {}

        mock_runtime.call = AsyncMock(return_value={"exists": False})

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.check_exists(
                domain="test-domain",
                signature_hash=sample_signature_hash,
                version=1,
                conn=None,  # type: ignore[arg-type]
            )

        # Explicitly verify 'signature' is NOT in the args
        assert (
            "signature" not in captured_args
        ), "check_exists should use signature_hash, not signature"


# =============================================================================
# Test: check_exists_by_id uses signature_hash
# =============================================================================


class TestCheckExistsByIdSignatureHash:
    """Tests for check_exists_by_id using signature_hash."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_check_exists_by_id_uses_signature_hash(
        self,
        adapter: AdapterPatternStore,
        mock_runtime: MagicMock,
        sample_pattern_id: UUID,
        sample_signature_hash: str,
    ) -> None:
        """check_exists_by_id passes signature_hash to the runtime."""
        captured_args: dict[str, object] = {}

        mock_runtime.call = AsyncMock(return_value={"id": str(sample_pattern_id)})

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.check_exists_by_id(
                pattern_id=sample_pattern_id,
                signature_hash=sample_signature_hash,
                conn=None,  # type: ignore[arg-type]
            )

        # Assert signature_hash is passed correctly
        assert "signature_hash" in captured_args
        assert captured_args["signature_hash"] == sample_signature_hash
        assert "signature" not in captured_args


# =============================================================================
# Test: set_previous_not_current uses signature_hash
# =============================================================================


class TestSetPreviousNotCurrentSignatureHash:
    """Tests for set_previous_not_current using signature_hash."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_set_previous_not_current_uses_signature_hash(
        self,
        adapter: AdapterPatternStore,
        mock_runtime: MagicMock,
        sample_signature_hash: str,
    ) -> None:
        """set_previous_not_current passes signature_hash to the runtime."""
        captured_args: dict[str, object] = {}

        mock_runtime.call = AsyncMock(return_value=[])

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.set_previous_not_current(
                domain="test-domain",
                signature_hash=sample_signature_hash,
                conn=None,  # type: ignore[arg-type]
            )

        # Assert signature_hash is passed correctly
        assert "signature_hash" in captured_args
        assert captured_args["signature_hash"] == sample_signature_hash
        assert "signature" not in captured_args


# =============================================================================
# Test: get_latest_version uses signature_hash
# =============================================================================


class TestGetLatestVersionSignatureHash:
    """Tests for get_latest_version using signature_hash."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_latest_version_uses_signature_hash(
        self,
        adapter: AdapterPatternStore,
        mock_runtime: MagicMock,
        sample_signature_hash: str,
    ) -> None:
        """get_latest_version passes signature_hash to the runtime."""
        captured_args: dict[str, object] = {}

        mock_runtime.call = AsyncMock(return_value={"version": 3})

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.get_latest_version(
                domain="test-domain",
                signature_hash=sample_signature_hash,
                conn=None,  # type: ignore[arg-type]
            )

        # Assert signature_hash is passed correctly
        assert "signature_hash" in captured_args
        assert captured_args["signature_hash"] == sample_signature_hash
        assert "signature" not in captured_args


# =============================================================================
# Test: store_with_version_transition maps both fields
# =============================================================================


class TestStoreWithVersionTransitionSignatureMapping:
    """Tests for store_with_version_transition signature field mapping."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_with_version_transition_maps_both_fields(
        self,
        adapter: AdapterPatternStore,
        sample_pattern_id: UUID,
        sample_correlation_id: UUID,
        sample_signature: str,
        sample_signature_hash: str,
    ) -> None:
        """store_with_version_transition passes both signature and signature_hash."""
        captured_args: dict[str, object] = {}

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_fn(captured_args),
        ):
            await adapter.store_with_version_transition(
                pattern_id=sample_pattern_id,
                signature=sample_signature,
                signature_hash=sample_signature_hash,
                domain="test-domain",
                version=2,
                confidence=0.90,
                quality_score=0.80,
                state=EnumPatternState.PROVISIONAL,
                is_current=True,
                stored_at=datetime.now(UTC),
                correlation_id=sample_correlation_id,
                conn=None,  # type: ignore[arg-type]
            )

        # Assert both signature fields are passed correctly
        assert "signature" in captured_args, "signature key missing from args"
        assert "signature_hash" in captured_args, "signature_hash key missing from args"
        assert captured_args["signature"] == sample_signature
        assert captured_args["signature_hash"] == sample_signature_hash

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_store_with_version_transition_uses_correct_operation(
        self,
        adapter: AdapterPatternStore,
        sample_pattern_id: UUID,
        sample_signature: str,
        sample_signature_hash: str,
    ) -> None:
        """Verify store_with_version_transition calls the correct contract operation."""
        captured_op: list[str] = []

        with patch.object(
            adapter,
            "_build_positional_args",
            side_effect=_make_capture_op_fn(captured_op),
        ):
            await adapter.store_with_version_transition(
                pattern_id=sample_pattern_id,
                signature=sample_signature,
                signature_hash=sample_signature_hash,
                domain="test-domain",
                version=2,
                confidence=0.90,
                state=EnumPatternState.PROVISIONAL,
                is_current=True,
                stored_at=datetime.now(UTC),
                conn=None,  # type: ignore[arg-type]
            )

        # Verify the operation name
        assert captured_op == ["store_with_version_transition"]
