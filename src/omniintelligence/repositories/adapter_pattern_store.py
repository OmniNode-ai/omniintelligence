"""Adapter bridging PostgresRepositoryRuntime to ProtocolPatternStore.

This adapter implements the ProtocolPatternStore interface using the
contract-driven PostgresRepositoryRuntime. It translates protocol method
calls to contract operation invocations.

Pattern:
    - Handler expects: ProtocolPatternStore
    - Runtime provides: PostgresRepositoryRuntime.call(op_name, **params)
    - This adapter: Implements protocol, delegates to runtime

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
    the SQL defined in the contract YAML.
    """

    def __init__(self, runtime: PostgresRepositoryRuntime) -> None:
        """Initialize adapter with runtime.

        Args:
            runtime: PostgresRepositoryRuntime configured with the
                learned_patterns contract.
        """
        self._runtime = runtime

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
        metadata: dict[str, Any] | None = None,
        conn: AsyncConnection,
    ) -> UUID:
        """Store a pattern using the contract runtime.

        Delegates to the 'store_pattern' operation in the contract.
        """
        # The contract's store_pattern operation uses different param names
        # Map protocol params to contract params
        result = await self._runtime.call(
            "store_pattern",
            id=str(pattern_id),
            signature=signature,
            domain_id=domain,
            # Default domain version for new patterns. The domain_version field tracks
            # schema evolution within a domain, not pattern versioning. Individual pattern
            # versions are tracked via the `version` field.
            domain_version="1.0",
            # Empty JSON array - domain candidates are populated during pattern
            # matching/classification, not at initial storage time.
            domain_candidates="[]",
            keywords=None,
            confidence=confidence,
            status=state.value,
            source_session_ids=f"{{{correlation_id}}}" if correlation_id else "{}",
            recurrence_count=1,
            version=version,
            supersedes=None,
            conn=conn,
        )

        # Return the stored pattern ID
        if result and hasattr(result, "id"):
            return result.id
        return pattern_id

    async def check_exists(
        self,
        domain: str,
        signature_hash: str,
        version: int,
        conn: AsyncConnection,
    ) -> bool:
        """Check if a pattern exists for the given lineage and version."""
        result = await self._runtime.call(
            "check_exists",
            domain_id=domain,
            signature=signature_hash,
            version=version,
            conn=conn,
        )

        # The query returns EXISTS which maps to a boolean-like result
        if result and hasattr(result, "exists"):
            return bool(result.exists)
        return False

    async def check_exists_by_id(
        self,
        pattern_id: UUID,
        signature_hash: str,
        conn: AsyncConnection,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key."""
        result = await self._runtime.call(
            "check_exists_by_id",
            pattern_id=str(pattern_id),
            signature=signature_hash,
            conn=conn,
        )

        if result and hasattr(result, "id"):
            return result.id
        return None

    async def set_previous_not_current(
        self,
        domain: str,
        signature_hash: str,
        conn: AsyncConnection,
    ) -> int:
        """Set is_current = false for all previous versions of this lineage."""
        result = await self._runtime.call(
            "set_not_current",
            signature=signature_hash,
            domain_id=domain,
            superseded_by=None,  # Will be set by subsequent store
            conn=conn,
        )

        # Return rows affected
        if result and hasattr(result, "rows_affected"):
            return result.rows_affected
        return 0

    async def get_latest_version(
        self,
        domain: str,
        signature_hash: str,
        conn: AsyncConnection,
    ) -> int | None:
        """Get the latest version number for a pattern lineage."""
        result = await self._runtime.call(
            "get_latest_version",
            domain_id=domain,
            signature=signature_hash,
            conn=conn,
        )

        if result and hasattr(result, "version"):
            return result.version
        return None

    async def get_stored_at(
        self,
        pattern_id: UUID,
        conn: AsyncConnection,
    ) -> datetime | None:
        """Get the original stored_at timestamp for a pattern."""
        result = await self._runtime.call(
            "get_stored_at",
            pattern_id=str(pattern_id),
            conn=conn,
        )

        if result and hasattr(result, "created_at"):
            return result.created_at
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
            if "default" in param and param["default"] is not None:
                # Convert plain value to ModelSchemaValue format
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
