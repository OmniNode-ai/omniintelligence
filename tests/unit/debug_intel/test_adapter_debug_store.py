# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for AdapterDebugStore (omniintelligence.debug_intel.adapter_debug_store).

The adapter bridges ProtocolDebugStore method calls to the contract-driven
PostgresRepositoryRuntime. These tests exercise the adapter's real behavior with
NO live database:

    - ``_build_positional_args`` builds args in the contract's declared param
      order, applies contract defaults for omitted optional params, substitutes
      ``None`` for optional params with no default, and raises ``ValueError``
      for unknown ops or missing-required params.
    - Every protocol method delegates to ``runtime.call(op_name, *args)`` with
      the correct positional arguments and coerces the runtime result into its
      declared return shape (dict / dict|None / list / bool).
    - Contract loading helpers (``load_contract``,
      ``_convert_defaults_to_schema_value``) and the ``create_debug_store_adapter``
      factory.

The runtime is mocked so we assert against the *positional args the adapter
produces* — the load-bearing contract-order translation — rather than merely
that a call happened. Where possible we assert against exists-but-wrong
behavior (wrong ordering, wrong default, un-coerced return type), not mere
import or "a call was made".

Ticket: OMN-7911 (coverage — module was 0%). The auto-generated acceptance
criteria mention "TTL expiry / eviction / in-memory store"; the real module is
a Postgres-contract adapter with none of those concepts, so these tests cover
the adapter's actual surface.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from omnibase_core.models.contracts import ModelDbRepositoryContract

from omniintelligence.debug_intel import adapter_debug_store
from omniintelligence.debug_intel.adapter_debug_store import (
    AdapterDebugStore,
    _convert_defaults_to_schema_value,
    create_debug_store_adapter,
    load_contract,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_contract() -> ModelDbRepositoryContract:
    """The real debug_store contract, loaded from the shipped YAML."""
    return load_contract()


def _make_adapter(
    real_contract: Any,
    call_return: Any = None,
) -> tuple[AdapterDebugStore, AsyncMock]:
    """Build an AdapterDebugStore backed by the real contract + a mocked call.

    Returns (adapter, call_mock). ``call_mock`` is an AsyncMock standing in for
    ``PostgresRepositoryRuntime.call`` so we can inspect the positional args the
    adapter produced and control the returned row(s).
    """
    runtime = MagicMock()
    runtime.contract = real_contract
    call_mock = AsyncMock(return_value=call_return)
    runtime.call = call_mock
    return AdapterDebugStore(runtime), call_mock


def _positional_args(call_mock: AsyncMock) -> tuple[Any, ...]:
    """Return the positional args (excluding op_name) of the last call()."""
    args = call_mock.call_args.args
    return args[1:]


# ---------------------------------------------------------------------------
# _build_positional_args
# ---------------------------------------------------------------------------


def test_build_positional_args_respects_contract_order(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """Args come out in the contract's declared param order, not kwargs order.

    upsert_streak declares [repo, branch, sha]. Providing them in a scrambled
    dict must still yield contract order — a wrong (insertion-order) impl would
    return them shuffled.
    """
    adapter, _ = _make_adapter(real_contract)
    args = adapter._build_positional_args(
        "upsert_streak",
        {"sha": "deadbeef", "repo": "OmniNode-ai/x", "branch": "main"},
    )
    assert args == ("OmniNode-ai/x", "main", "deadbeef")


def test_build_positional_args_applies_contract_default(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """An omitted optional param with a contract default gets that default.

    query_fix_records.limit declares default 10. Omitting it must inject 10 in
    the correct (second) position, not None and not drop the slot.
    """
    adapter, _ = _make_adapter(real_contract)
    args = adapter._build_positional_args(
        "query_fix_records",
        {"failure_fingerprint": "fp-123"},
    )
    assert args == ("fp-123", 10)


def test_build_positional_args_optional_without_default_is_none(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """An optional param with no default becomes None in its declared slot.

    insert_ci_failure_event.pr_number is required=false with no default. Omitting
    it must place None at pr_number's position (index 3), while the defaulted
    error_classification/streak_snapshot slots keep their supplied values.
    """
    adapter, _ = _make_adapter(real_contract)
    args = adapter._build_positional_args(
        "insert_ci_failure_event",
        {
            "repo": "r",
            "branch": "b",
            "sha": "s",
            "error_fingerprint": "fp",
            "error_classification": "flaky",
            "streak_snapshot": 3,
        },
    )
    # param_order: repo, branch, sha, pr_number, error_fingerprint,
    #              error_classification, streak_snapshot
    assert args == ("r", "b", "s", None, "fp", "flaky", 3)


def test_build_positional_args_unknown_op_raises(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, _ = _make_adapter(real_contract)
    with pytest.raises(ValueError, match="Unknown operation: does_not_exist"):
        adapter._build_positional_args("does_not_exist", {})


def test_build_positional_args_missing_required_raises(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """A required param with no default and no provided value raises ValueError."""
    adapter, _ = _make_adapter(real_contract)
    with pytest.raises(ValueError, match="Required param 'sha' not provided"):
        adapter._build_positional_args("upsert_streak", {"repo": "r", "branch": "b"})


# ---------------------------------------------------------------------------
# Write ops — argument translation + return coercion
# ---------------------------------------------------------------------------


async def test_upsert_streak_delegates_and_returns_row(
    real_contract: ModelDbRepositoryContract,
) -> None:
    row = {"repo": "r", "branch": "b", "streak_count": 2}
    adapter, call_mock = _make_adapter(real_contract, call_return=row)

    result = await adapter.upsert_streak(repo="r", branch="b", sha="s")

    assert result == row
    assert call_mock.call_args.args[0] == "upsert_streak"
    assert _positional_args(call_mock) == ("r", "b", "s")


async def test_upsert_streak_non_dict_result_coerced_to_empty(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """A non-dict runtime result must coerce to {} (not leak None to callers)."""
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert await adapter.upsert_streak(repo="r", branch="b", sha="s") == {}


async def test_reset_streak_delegates_with_repo_branch(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, call_mock = _make_adapter(real_contract, call_return=None)
    result = await adapter.reset_streak(repo="r", branch="b")
    assert result is None
    assert call_mock.call_args.args[0] == "reset_streak"
    assert _positional_args(call_mock) == ("r", "b")


async def test_get_streak_returns_row_when_present(
    real_contract: ModelDbRepositoryContract,
) -> None:
    row = {"streak_count": 5}
    adapter, call_mock = _make_adapter(real_contract, call_return=row)
    assert await adapter.get_streak(repo="r", branch="b") == row
    assert _positional_args(call_mock) == ("r", "b")


async def test_get_streak_returns_none_when_absent(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """Absent row (runtime returns None) must surface as None, not {}."""
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert await adapter.get_streak(repo="r", branch="b") is None


async def test_insert_ci_failure_event_maps_fingerprint_kwarg(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """failure_fingerprint kwarg maps to the contract's error_fingerprint slot.

    The Python kwarg name (failure_fingerprint) differs from the contract param
    (error_fingerprint); the value must land in error_fingerprint's position and
    the omitted pr_number must be None.
    """
    row = {"id": "evt-1"}
    adapter, call_mock = _make_adapter(real_contract, call_return=row)

    result = await adapter.insert_ci_failure_event(
        repo="r",
        branch="b",
        sha="s",
        failure_fingerprint="fp",
        error_classification="oom",
        streak_snapshot=4,
    )

    assert result == row
    # repo, branch, sha, pr_number(None), error_fingerprint, error_classification, streak_snapshot
    assert _positional_args(call_mock) == ("r", "b", "s", None, "fp", "oom", 4)


async def test_insert_ci_failure_event_passes_pr_number(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, call_mock = _make_adapter(real_contract, call_return={})
    await adapter.insert_ci_failure_event(
        repo="r",
        branch="b",
        sha="s",
        failure_fingerprint="fp",
        error_classification="oom",
        streak_snapshot=4,
        pr_number=99,
    )
    assert _positional_args(call_mock)[3] == 99


async def test_insert_ci_failure_event_non_dict_coerced(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert (
        await adapter.insert_ci_failure_event(
            repo="r",
            branch="b",
            sha="s",
            failure_fingerprint="fp",
            error_classification="oom",
            streak_snapshot=4,
        )
        == {}
    )


async def test_insert_trigger_record_delegates(
    real_contract: ModelDbRepositoryContract,
) -> None:
    row = {"id": "trig-1"}
    adapter, call_mock = _make_adapter(real_contract, call_return=row)
    result = await adapter.insert_trigger_record(
        repo="r",
        branch="b",
        failure_fingerprint="fp",
        error_classification="oom",
        observed_bad_sha="bad",
        streak_count_at_trigger=7,
    )
    assert result == row
    assert call_mock.call_args.args[0] == "insert_trigger_record"
    assert _positional_args(call_mock) == ("r", "b", "fp", "oom", "bad", 7)


async def test_insert_trigger_record_non_dict_coerced(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, _ = _make_adapter(real_contract, call_return="oops")
    assert (
        await adapter.insert_trigger_record(
            repo="r",
            branch="b",
            failure_fingerprint="fp",
            error_classification="oom",
            observed_bad_sha="bad",
            streak_count_at_trigger=7,
        )
        == {}
    )


async def test_find_open_trigger_record_returns_row(
    real_contract: ModelDbRepositoryContract,
) -> None:
    row = {"id": "trig-9"}
    adapter, call_mock = _make_adapter(real_contract, call_return=row)
    assert await adapter.find_open_trigger_record(repo="r", branch="b") == row
    assert _positional_args(call_mock) == ("r", "b")


async def test_find_open_trigger_record_none_when_absent(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert await adapter.find_open_trigger_record(repo="r", branch="b") is None


# ---------------------------------------------------------------------------
# try_mark_trigger_resolved — race-outcome boolean semantics
# ---------------------------------------------------------------------------


async def test_try_mark_trigger_resolved_true_on_updated_row(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """A returned row containing 'id' means we won the race -> True."""
    adapter, call_mock = _make_adapter(real_contract, call_return={"id": "trig-1"})
    assert (
        await adapter.try_mark_trigger_resolved(
            trigger_record_id="trig-1", fix_record_id="fix-1"
        )
        is True
    )
    assert _positional_args(call_mock) == ("trig-1", "fix-1")


async def test_try_mark_trigger_resolved_false_when_no_row(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """None result (no row matched) means the race was lost -> False."""
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert (
        await adapter.try_mark_trigger_resolved(
            trigger_record_id="trig-1", fix_record_id="fix-1"
        )
        is False
    )


async def test_try_mark_trigger_resolved_false_when_row_missing_id(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """A dict without an 'id' key must not be read as success."""
    adapter, _ = _make_adapter(real_contract, call_return={"other": 1})
    assert (
        await adapter.try_mark_trigger_resolved(
            trigger_record_id="trig-1", fix_record_id="fix-1"
        )
        is False
    )


# ---------------------------------------------------------------------------
# insert_fix_record + query_fix_records
# ---------------------------------------------------------------------------


async def test_insert_fix_record_delegates(
    real_contract: ModelDbRepositoryContract,
) -> None:
    row = {"id": "fix-1"}
    adapter, call_mock = _make_adapter(real_contract, call_return=row)
    result = await adapter.insert_fix_record(
        trigger_record_id="trig-1",
        repo="r",
        sha="s",
        regression_test_added=True,
    )
    assert result == row
    # param_order: trigger_record_id, repo, sha, pr_number(None), regression_test_added
    assert _positional_args(call_mock) == ("trig-1", "r", "s", None, True)


async def test_insert_fix_record_non_dict_coerced(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert (
        await adapter.insert_fix_record(
            trigger_record_id="trig-1",
            repo="r",
            sha="s",
            regression_test_added=False,
        )
        == {}
    )


async def test_query_fix_records_returns_list(
    real_contract: ModelDbRepositoryContract,
) -> None:
    rows = [{"id": "fix-1"}, {"id": "fix-2"}]
    adapter, call_mock = _make_adapter(real_contract, call_return=rows)
    result = await adapter.query_fix_records(failure_fingerprint="fp", limit=5)
    assert result == rows
    assert _positional_args(call_mock) == ("fp", 5)


async def test_query_fix_records_default_limit(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """The Python default limit=10 is forwarded when not supplied."""
    adapter, call_mock = _make_adapter(real_contract, call_return=[])
    await adapter.query_fix_records(failure_fingerprint="fp")
    assert _positional_args(call_mock) == ("fp", 10)


async def test_query_fix_records_none_becomes_empty_list(
    real_contract: ModelDbRepositoryContract,
) -> None:
    adapter, _ = _make_adapter(real_contract, call_return=None)
    assert await adapter.query_fix_records(failure_fingerprint="fp") == []


async def test_query_fix_records_single_dict_wrapped_in_list(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """A single-dict result is wrapped into a one-element list."""
    row = {"id": "fix-solo"}
    adapter, _ = _make_adapter(real_contract, call_return=row)
    assert await adapter.query_fix_records(failure_fingerprint="fp") == [row]


async def test_query_fix_records_unexpected_scalar_becomes_empty(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """A non-list/non-dict/non-None result degrades to []."""
    adapter, _ = _make_adapter(real_contract, call_return=42)
    assert await adapter.query_fix_records(failure_fingerprint="fp") == []


# ---------------------------------------------------------------------------
# Contract loading helpers
# ---------------------------------------------------------------------------


def test_load_contract_returns_expected_ops(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """The real contract exposes the debug-store operation surface."""
    expected = {
        "upsert_streak",
        "reset_streak",
        "get_streak",
        "insert_ci_failure_event",
        "insert_trigger_record",
        "find_open_trigger_record",
        "try_mark_trigger_resolved",
        "insert_fix_record",
        "query_fix_records",
    }
    assert expected <= set(real_contract.ops.keys())


def test_load_contract_default_is_parsed_value(
    real_contract: ModelDbRepositoryContract,
) -> None:
    """query_fix_records.limit default round-trips to the integer 10.

    Guards the YAML-default -> ModelSchemaValue conversion in load_contract:
    a broken conversion would leave the default as None or a raw dict.
    """
    limit_param = real_contract.ops["query_fix_records"].params["limit"]
    assert limit_param.default is not None
    assert limit_param.default.to_value() == 10


def test_load_contract_missing_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        adapter_debug_store,
        "CONTRACT_PATH",
        tmp_path / "nonexistent.yaml",
    )
    with pytest.raises(FileNotFoundError, match="Contract file not found"):
        load_contract()


def test_load_contract_missing_db_repository_key_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("some_other_key: {}\n")
    monkeypatch.setattr(adapter_debug_store, "CONTRACT_PATH", bad)
    with pytest.raises(ValueError, match="missing 'db_repository' key"):
        load_contract()


def test_convert_defaults_to_schema_value_converts_and_is_pure() -> None:
    """Plain defaults are converted to ModelSchemaValue dict form; input intact."""
    contract_dict: dict[str, Any] = {
        "ops": {
            "op1": {
                "params": {
                    "p_with_default": {"name": "p_with_default", "default": 7},
                    "p_plain": {"name": "p_plain"},
                }
            }
        }
    }
    original = copy.deepcopy(contract_dict)

    result = _convert_defaults_to_schema_value(contract_dict)

    # Input not mutated (deep copy semantics)
    assert contract_dict == original
    # Defaulted param converted to a structured dict carrying the value 7
    converted = result["ops"]["op1"]["params"]["p_with_default"]["default"]
    assert isinstance(converted, dict)
    from omnibase_core.models.common.model_schema_value import ModelSchemaValue

    assert ModelSchemaValue.model_validate(converted).to_value() == 7
    # Param without a default is left untouched
    assert "default" not in result["ops"]["op1"]["params"]["p_plain"]


# ---------------------------------------------------------------------------
# create_debug_store_adapter factory
# ---------------------------------------------------------------------------


async def test_create_debug_store_adapter_wires_runtime() -> None:
    """Factory returns an AdapterDebugStore whose runtime carries the contract."""
    pool = MagicMock()
    adapter = await create_debug_store_adapter(pool)
    assert isinstance(adapter, AdapterDebugStore)
    # The adapter can build positional args -> its runtime holds the real contract.
    assert adapter._runtime.contract.ops["upsert_streak"] is not None
    assert adapter._build_positional_args(
        "upsert_streak", {"repo": "r", "branch": "b", "sha": "s"}
    ) == ("r", "b", "s")


def test_public_exports_present() -> None:
    for name in ("AdapterDebugStore", "create_debug_store_adapter", "load_contract"):
        assert name in adapter_debug_store.__all__


def test_contract_path_points_at_shipped_yaml() -> None:
    assert isinstance(adapter_debug_store.CONTRACT_PATH, Path)
    assert adapter_debug_store.CONTRACT_PATH.name == "debug_store.repository.yaml"
    assert adapter_debug_store.CONTRACT_PATH.exists()
