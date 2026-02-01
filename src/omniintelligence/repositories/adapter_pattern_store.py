# ruff: noqa: ARG002
# ARG002 disabled: Protocol adapter has unused params required by interface contract
"""Adapter bridging PostgresRepositoryRuntime to ProtocolPatternStore.

This adapter implements the ProtocolPatternStore interface using the
contract-driven PostgresRepositoryRuntime. It translates protocol method
calls to contract operation invocations.

Pattern:
    - Handler expects: ProtocolPatternStore
    - Runtime provides: PostgresRepositoryRuntime.call(op_name, *args)
    - This adapter: Implements protocol, delegates to runtime with positional args

The runtime expects positional arguments in the order defined by the contract's
params dict. This adapter builds positional args from kwargs, applying contract
defaults for any omitted optional params.

Usage:
    >>> from omniintelligence.repositories import create_pattern_store_adapter
    >>> adapter = await create_pattern_store_adapter(pool)
    >>> # Now use adapter where ProtocolPatternStore is expected
    >>> await handler(input_data, pattern_store=adapter, conn=conn)
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import yaml

from omnibase_core.models.contracts import ModelDbRepositoryContract
from omnibase_core.types import TypedDictPatternStorageMetadata
from omnibase_infra.runtime.db import PostgresRepositoryRuntime

from omniintelligence.nodes.pattern_storage_effect.models import EnumPatternState

if TYPE_CHECKING:
    from asyncpg import Pool
    from psycopg import AsyncConnection

logger = logging.getLogger(__name__)

# Path to the contract YAML
CONTRACT_PATH = Path(__file__).parent / "learned_patterns.repository.yaml"


class AdapterPatternStore:
    """Adapter implementing ProtocolPatternStore via contract runtime.

    This class bridges the gap between:
    - The existing ProtocolPatternStore interface (used by handlers)
    - The new PostgresRepositoryRuntime (contract-driven execution)

    All database operations are delegated to the runtime, which executes
    the SQL defined in the contract YAML. Contract defaults are applied
    automatically for optional params not explicitly provided.
    """

    def __init__(self, runtime: PostgresRepositoryRuntime) -> None:
        """Initialize adapter with runtime.

        Args:
            runtime: PostgresRepositoryRuntime configured with the
                learned_patterns contract.
        """
        self._runtime = runtime

    def _build_positional_args(
        self,
        op_name: str,
        provided: dict[str, Any],
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

    async def store_pattern(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain: str,
        version: int,
        confidence: float,
        state: EnumPatternState,
        is_current: bool,
        stored_at: datetime,
        actor: str | None = None,
        source_run_id: str | None = None,
        correlation_id: UUID | None = None,
        metadata: TypedDictPatternStorageMetadata | None = None,
        conn: AsyncConnection,
    ) -> UUID:
        """Store a pattern using the contract runtime.

        Delegates to the 'store_pattern' operation in the contract.
        Contract defaults are applied for optional params not explicitly provided:
        - domain_version: defaults to "1.0" (schema version, not pattern version)
        - domain_candidates: defaults to "[]"
        - status: defaults to "candidate" (overridden by state param here)
        - recurrence_count: defaults to 1
        """
        # Build positional args - contract defaults apply for omitted optional params
        args = self._build_positional_args(
            "store_pattern",
            {
                "id": str(pattern_id),
                "signature": signature,
                "domain_id": domain,
                # domain_version: omitted - uses contract default "1.0"
                # domain_candidates: omitted - uses contract default "[]"
                # keywords: omitted - optional with no default, will be None
                "confidence": confidence,
                "status": state.value,
                "source_session_ids": f"{{{correlation_id}}}" if correlation_id else "{}",
                # recurrence_count: omitted - uses contract default 1
                "version": version,
                # supersedes: omitted - optional with no default, will be None
            },
        )

        result = await self._runtime.call("store_pattern", *args)

        # Return the stored pattern ID
        if result and isinstance(result, dict) and "id" in result:
            return UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
        return pattern_id

    async def check_exists(
        self,
        domain: str,
        signature: str,
        version: int,
        conn: AsyncConnection,
    ) -> bool:
        """Check if a pattern exists for the given lineage and version."""
        args = self._build_positional_args(
            "check_exists",
            {
                "domain_id": domain,
                "signature": signature,
                "version": version,
            },
        )
        result = await self._runtime.call("check_exists", *args)

        # The query returns EXISTS which maps to a boolean-like result
        if result and isinstance(result, dict) and "exists" in result:
            return bool(result["exists"])
        return False

    async def check_exists_by_id(
        self,
        pattern_id: UUID,
        signature: str,
        conn: AsyncConnection,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key."""
        args = self._build_positional_args(
            "check_exists_by_id",
            {
                "pattern_id": str(pattern_id),
                "signature": signature,
            },
        )
        result = await self._runtime.call("check_exists_by_id", *args)

        if result and isinstance(result, dict) and "id" in result:
            return UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
        return None

    async def set_previous_not_current(
        self,
        domain: str,
        signature: str,
        conn: AsyncConnection,
    ) -> int:
        """Set is_current = false for all previous versions of this lineage."""
        args = self._build_positional_args(
            "set_not_current",
            {
                "signature": signature,
                "domain_id": domain,
                # superseded_by: omitted - optional, will be None
            },
        )
        result = await self._runtime.call("set_not_current", *args)

        # For write operations returning multiple rows, count results
        if isinstance(result, list):
            return len(result)
        return 0

    async def get_latest_version(
        self,
        domain: str,
        signature: str,
        conn: AsyncConnection,
    ) -> int | None:
        """Get the latest version number for a pattern lineage."""
        args = self._build_positional_args(
            "get_latest_version",
            {
                "domain_id": domain,
                "signature": signature,
            },
        )
        result = await self._runtime.call("get_latest_version", *args)

        if result and isinstance(result, dict) and "version" in result:
            return result["version"]
        return None

    async def get_stored_at(
        self,
        pattern_id: UUID,
        conn: AsyncConnection,
    ) -> datetime | None:
        """Get the original stored_at timestamp for a pattern."""
        args = self._build_positional_args(
            "get_stored_at",
            {
                "pattern_id": str(pattern_id),
            },
        )
        result = await self._runtime.call("get_stored_at", *args)

        if result and isinstance(result, dict) and "created_at" in result:
            return result["created_at"]
        return None


def _convert_defaults_to_schema_value(contract_dict: dict[str, Any]) -> dict[str, Any]:
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

    def convert_value(value: Any) -> dict[str, Any]:
        """Convert a plain value to ModelSchemaValue dict format."""
        schema_value = ModelSchemaValue.from_value(value)
        return schema_value.model_dump()

    # Deep copy to avoid mutating input
    result = copy.deepcopy(contract_dict)

    # Process each operation's params
    ops = result.get("ops", {})
    for op_name, op in ops.items():
        params = op.get("params", {})
        for param_name, param in params.items():
            if "default" in param:
                # Convert plain value to ModelSchemaValue format
                # Handles both non-null values and explicit null defaults
                plain_value = param["default"]
                param["default"] = convert_value(plain_value)

    return result


def load_contract() -> ModelDbRepositoryContract:
    """Load the learned_patterns repository contract.

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


async def create_pattern_store_adapter(pool: Pool) -> AdapterPatternStore:
    """Factory function to create a pattern store adapter.

    This is the main entry point for obtaining a ProtocolPatternStore
    implementation backed by the contract-driven runtime.

    Args:
        pool: asyncpg connection pool for database access.

    Returns:
        AdapterPatternStore implementing ProtocolPatternStore.

    Example:
        >>> pool = await asyncpg.create_pool(...)
        >>> adapter = await create_pattern_store_adapter(pool)
        >>> await handle_store_pattern(input_data, pattern_store=adapter, conn=conn)
    """
    contract = load_contract()
    runtime = PostgresRepositoryRuntime(pool=pool, contract=contract)
    return AdapterPatternStore(runtime)


__all__ = [
    "AdapterPatternStore",
    "create_pattern_store_adapter",
    "load_contract",
]
