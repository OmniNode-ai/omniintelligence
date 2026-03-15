# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adapter bridging PostgresRepositoryRuntime to ProtocolDebugStore.

This adapter implements the ProtocolDebugStore interface using the
contract-driven PostgresRepositoryRuntime. It translates protocol method
calls to contract operation invocations.

Pattern:
    - Handler expects: ProtocolDebugStore
    - Runtime provides: PostgresRepositoryRuntime.call(op_name, *args)
    - This adapter: Implements protocol, delegates to runtime with positional args

The runtime expects positional arguments in the order defined by the contract's
params dict. This adapter builds positional args from kwargs, applying contract
defaults for any omitted optional params.

Ticket: OMN-3556
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml
from omnibase_core.models.contracts import ModelDbRepositoryContract
from omnibase_infra.runtime.db import PostgresRepositoryRuntime

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# Path to the contract YAML
CONTRACT_PATH = Path(__file__).parent / "debug_store.repository.yaml"


class AdapterDebugStore:
    """Adapter implementing ProtocolDebugStore via contract runtime.

    This class bridges the gap between:
    - The ProtocolDebugStore interface (used by handlers)
    - The PostgresRepositoryRuntime (contract-driven execution)

    All database operations are delegated to the runtime, which executes
    the SQL defined in the contract YAML. Contract defaults are applied
    automatically for optional params not explicitly provided.

    Transaction Semantics
    ---------------------
    This adapter manages its own connections via the
    PostgresRepositoryRuntime's connection pool. Each method call is an
    independent transaction. External transaction control is not supported.

    Structural Typing
    -----------------
    This class does NOT inherit from ProtocolDebugStore. It satisfies the
    protocol structurally (duck typing). isinstance(adapter, ProtocolDebugStore)
    works at runtime because ProtocolDebugStore uses @runtime_checkable.
    """

    def __init__(self, runtime: PostgresRepositoryRuntime) -> None:
        """Initialize adapter with runtime.

        Args:
            runtime: PostgresRepositoryRuntime configured with the
                debug_store contract.
        """
        self._runtime = runtime

    def _build_positional_args(
        self,
        op_name: str,
        provided: dict[str, Any],  # any-ok: heterogeneous param values from caller
    ) -> tuple[Any, ...]:
        """Build positional args for runtime.call() from provided kwargs.

        The runtime expects positional arguments in the order defined by
        the contract's params dict. This method:
        1. Looks up the operation's param definitions in the contract
        2. For each param (in order), uses provided value or contract default
        3. Returns tuple of args in correct positional order

        Args:
            op_name: Operation name in the contract.
            provided: Dict of param_name -> value for explicitly provided params.

        Returns:
            Tuple of positional args in contract param order.

        Raises:
            ValueError: If required param missing and has no default.
        """
        contract = self._runtime.contract
        operation = contract.ops.get(op_name)
        if operation is None:
            msg = f"Unknown operation: {op_name}"
            raise ValueError(msg)

        args = []
        for param_name, param_spec in operation.params.items():
            if param_name in provided:
                args.append(provided[param_name])
            elif param_spec.default is not None:
                # Use contract default - extract the actual value
                args.append(param_spec.default.to_value())
            elif not param_spec.required:
                # Optional with no default - use None
                args.append(None)
            else:
                msg = f"Required param '{param_name}' not provided for operation '{op_name}'"
                raise ValueError(msg)

        return tuple(args)

    async def upsert_streak(
        self,
        *,
        repo: str,
        branch: str,
        sha: str,
    ) -> dict[str, Any]:
        """Increment (or insert) the streak count for (repo, branch)."""
        args = self._build_positional_args(
            "upsert_streak",
            {"repo": repo, "branch": branch, "sha": sha},
        )
        result = await self._runtime.call("upsert_streak", *args)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return {}

    async def reset_streak(
        self,
        *,
        repo: str,
        branch: str,
    ) -> None:
        """Reset streak_count to 0 for (repo, branch) on CI recovery."""
        args = self._build_positional_args(
            "reset_streak",
            {"repo": repo, "branch": branch},
        )
        await self._runtime.call("reset_streak", *args)

    async def get_streak(
        self,
        *,
        repo: str,
        branch: str,
    ) -> dict[str, Any] | None:
        """Return the current streak row for (repo, branch), or None if absent."""
        args = self._build_positional_args(
            "get_streak",
            {"repo": repo, "branch": branch},
        )
        result = await self._runtime.call("get_streak", *args)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return None

    async def insert_ci_failure_event(
        self,
        *,
        repo: str,
        branch: str,
        sha: str,
        failure_fingerprint: str,
        error_classification: str,
        streak_snapshot: int,
        pr_number: int | None = None,
    ) -> dict[str, Any]:
        """Insert a CI failure event log entry."""
        args = self._build_positional_args(
            "insert_ci_failure_event",
            {
                "repo": repo,
                "branch": branch,
                "sha": sha,
                "pr_number": pr_number,
                "error_fingerprint": failure_fingerprint,
                "error_classification": error_classification,
                "streak_snapshot": streak_snapshot,
            },
        )
        result = await self._runtime.call("insert_ci_failure_event", *args)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return {}

    async def insert_trigger_record(
        self,
        *,
        repo: str,
        branch: str,
        failure_fingerprint: str,
        error_classification: str,
        observed_bad_sha: str,
        streak_count_at_trigger: int,
    ) -> dict[str, Any]:
        """Create a TriggerRecord when streak threshold is crossed."""
        args = self._build_positional_args(
            "insert_trigger_record",
            {
                "repo": repo,
                "branch": branch,
                "failure_fingerprint": failure_fingerprint,
                "error_classification": error_classification,
                "observed_bad_sha": observed_bad_sha,
                "streak_count_at_trigger": streak_count_at_trigger,
            },
        )
        result = await self._runtime.call("insert_trigger_record", *args)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return {}

    async def find_open_trigger_record(
        self,
        *,
        repo: str,
        branch: str,
    ) -> dict[str, Any] | None:
        """Find the most recent unresolved TriggerRecord for (repo, branch)."""
        args = self._build_positional_args(
            "find_open_trigger_record",
            {"repo": repo, "branch": branch},
        )
        result = await self._runtime.call("find_open_trigger_record", *args)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return None

    async def try_mark_trigger_resolved(
        self,
        *,
        trigger_record_id: str,
        fix_record_id: str,
    ) -> bool:
        """Atomically mark trigger as resolved and link fix record.

        Returns True if the update succeeded (we won the race).
        Returns False if the trigger was already resolved (race lost).
        """
        args = self._build_positional_args(
            "try_mark_trigger_resolved",
            {
                "trigger_record_id": trigger_record_id,
                "fix_record_id": fix_record_id,
            },
        )
        result = await self._runtime.call("try_mark_trigger_resolved", *args)
        # Returns a row with "id" if update succeeded, None if no row matched
        return result is not None and isinstance(result, dict) and "id" in result

    async def insert_fix_record(
        self,
        *,
        trigger_record_id: str,
        repo: str,
        sha: str,
        regression_test_added: bool,
        pr_number: int | None = None,
    ) -> dict[str, Any]:
        """Create a FixRecord when CI recovers."""
        args = self._build_positional_args(
            "insert_fix_record",
            {
                "trigger_record_id": trigger_record_id,
                "repo": repo,
                "sha": sha,
                "pr_number": pr_number,
                "regression_test_added": regression_test_added,
            },
        )
        result = await self._runtime.call("insert_fix_record", *args)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
        return {}

    async def query_fix_records(
        self,
        *,
        failure_fingerprint: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query fix records for a fingerprint, ordered by recency (newest first)."""
        args = self._build_positional_args(
            "query_fix_records",
            {
                "failure_fingerprint": failure_fingerprint,
                "limit": limit,
            },
        )
        result = await self._runtime.call("query_fix_records", *args)
        if isinstance(result, list):
            return cast(list[dict[str, Any]], result)
        if result is None:
            return []
        # Single dict result — wrap in list
        if isinstance(result, dict):
            return [cast(dict[str, Any], result)]
        return []


def _convert_defaults_to_schema_value(
    contract_dict: dict[
        str, Any
    ],  # any-ok: YAML-loaded contract data is dynamically typed
) -> dict[str, Any]:
    """Convert plain default values to ModelSchemaValue format.

    The Pydantic schema expects `default` to be a ModelSchemaValue object,
    but YAML files use plain values for readability. This function converts
    plain values to the structured format expected by the schema.

    Args:
        contract_dict: Raw contract dictionary from YAML.

    Returns:
        Contract dictionary with defaults converted to ModelSchemaValue format.
    """
    from omnibase_core.models.common.model_schema_value import ModelSchemaValue

    def convert_value(
        value: Any,
    ) -> dict[str, Any]:  # any-ok: YAML values are dynamically typed
        """Convert a plain value to ModelSchemaValue dict format."""
        schema_value = ModelSchemaValue.from_value(value)
        return schema_value.model_dump(mode="json")

    # Deep copy to avoid mutating input
    result = copy.deepcopy(contract_dict)

    # Process each operation's params
    ops = result.get("ops", {})
    for _op_name, op in ops.items():
        params = op.get("params", {})
        for _param_name, param in params.items():
            if "default" in param:
                plain_value = param["default"]
                param["default"] = convert_value(plain_value)

    return result


def load_contract() -> ModelDbRepositoryContract:
    """Load the debug_store repository contract.

    Returns:
        Parsed contract model ready for runtime initialization.

    Raises:
        FileNotFoundError: If contract YAML doesn't exist.
        ValueError: If contract YAML is invalid.
    """
    if not CONTRACT_PATH.exists():
        msg = f"Contract file not found: {CONTRACT_PATH}"
        raise FileNotFoundError(msg)

    with open(CONTRACT_PATH) as f:
        raw = yaml.safe_load(f)

    contract_dict = raw.get("db_repository")
    if not contract_dict:
        msg = "Contract YAML missing 'db_repository' key"
        raise ValueError(msg)

    # Convert plain default values to ModelSchemaValue format
    contract_dict = _convert_defaults_to_schema_value(contract_dict)

    return ModelDbRepositoryContract.model_validate(contract_dict)


async def create_debug_store_adapter(pool: asyncpg.Pool) -> AdapterDebugStore:
    """Factory function to create a debug store adapter.

    This is the main entry point for obtaining a ProtocolDebugStore
    implementation backed by the contract-driven runtime.

    Args:
        pool: asyncpg connection pool for database access.

    Returns:
        AdapterDebugStore implementing ProtocolDebugStore.
    """
    contract = load_contract()
    runtime = PostgresRepositoryRuntime(pool=pool, contract=contract)
    return AdapterDebugStore(runtime)


__all__ = [
    "AdapterDebugStore",
    "create_debug_store_adapter",
    "load_contract",
]
