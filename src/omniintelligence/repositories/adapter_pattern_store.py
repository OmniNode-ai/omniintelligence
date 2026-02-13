# Note: Methods in this module use noqa: ARG002 on individual parameters
# for interface compatibility with ProtocolPatternStore. See class docstring.
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
from typing import TYPE_CHECKING
from uuid import UUID

import yaml
from omnibase_core.models.contracts import ModelDbRepositoryContract
from omnibase_core.types.typed_dict_pattern_storage_metadata import (
    TypedDictPatternStorageMetadata,
)
from omnibase_infra.runtime.db import PostgresRepositoryRuntime

from omniintelligence.nodes.node_pattern_storage_effect.models import EnumPatternState

if TYPE_CHECKING:
    from asyncpg import Pool
    from psycopg import AsyncConnection

    from omniintelligence.nodes.node_pattern_storage_effect.handlers.handler_store_pattern import (
        ProtocolPatternStore,
    )

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

    Transaction Semantics
    ---------------------
    **IMPORTANT**: This adapter manages its own connections via the
    PostgresRepositoryRuntime's connection pool. The `conn` parameters
    on all methods exist ONLY for interface compatibility with
    ProtocolPatternStore and are NOT used.

    The runtime acquires connections from its pool per-operation and
    commits/releases them automatically. This means:

    - Callers CANNOT control transaction boundaries with this adapter
    - Each method call is an independent transaction
    - External transaction control (BEGIN/COMMIT/ROLLBACK) is not supported
    - If you need external transaction control, use a different
      ProtocolPatternStore implementation that honors the `conn` parameter

    This design trades external transaction control for:
    - Simpler connection management (no connection passing)
    - Automatic connection pooling and release
    - Contract-driven operation execution

    See Also:
        Methods use `# noqa: ARG002` on individual parameters to suppress
        "unused argument" linter warnings for interface-compatibility
        parameters (conn, is_current, stored_at, actor, source_run_id, metadata).
    """

    def __init__(self, runtime: PostgresRepositoryRuntime) -> None:
        """Initialize adapter with runtime.

        Args:
            runtime: PostgresRepositoryRuntime configured with the
                learned_patterns contract.
        """
        self._runtime = runtime
        self._conn_warning_logged = False

    def _build_positional_args(
        self,
        op_name: str,
        provided: dict[str, object],
    ) -> tuple[object, ...]:
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
        quality_score: float = 0.5,
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

        Args:
            signature: The pattern signature text (stored in pattern_signature column).
            signature_hash: SHA256 hash of the signature for identity lookups.
            quality_score: Initial quality score for the pattern (0.0-1.0).
                Defaults to 0.5 (neutral). Used for quality-weighted searches
                and pattern ranking.

        Unused Parameters (Interface Compatibility)
        --------------------------------------------
        The following parameters are accepted for ProtocolPatternStore interface
        compatibility but are NOT used by this adapter:

        - **is_current**: Not passed to contract. Version currency is managed by
          calling ``set_previous_not_current()`` before storing new versions.
        - **stored_at**: Not used. The database schema uses ``created_at`` with a
          server-side ``NOW()`` default for timestamp consistency.
        - **actor**: Reserved for future audit trail features (who stored pattern).
        - **source_run_id**: Reserved for future audit trail (originating CI run).
        - **metadata**: Reserved for future extensibility (arbitrary key-value data).
        - **conn**: See class docstring. Runtime manages its own connection pool.
        """
        if conn is not None and not self._conn_warning_logged:
            logger.warning(
                "conn parameter ignored by AdapterPatternStore - this adapter manages "
                "its own connections. See class docstring for transaction semantics."
            )
            self._conn_warning_logged = True

        # Future: Implement metadata persistence when contract supports JSONB
        # Future: Add actor/source_run_id for audit trail when lineage tracking is complete

        # Build positional args - contract defaults apply for omitted optional params
        args = self._build_positional_args(
            "store_pattern",
            {
                "id": str(pattern_id),
                "signature": signature,
                "signature_hash": signature_hash,
                "domain_id": domain,
                # domain_version: omitted - uses contract default "1.0"
                # domain_candidates: omitted - uses contract default "[]"
                # keywords: omitted - optional with no default, will be None
                "confidence": confidence,
                "quality_score": quality_score,
                "status": state.value,
                "source_session_ids": f"{{{correlation_id}}}"
                if correlation_id
                else "{}",
                # recurrence_count: omitted - uses contract default 1
                "version": version,
                # supersedes: omitted - optional with no default, will be None
            },
        )

        result = await self._runtime.call("store_pattern", *args)

        # Return the stored pattern ID
        if result and isinstance(result, dict) and "id" in result:
            return UUID(result["id"]) if isinstance(result["id"], str) else result["id"]

        # Defensive: log if result is empty/invalid to help diagnose INSERT failures
        logger.warning(
            "store_pattern returned unexpected result, using provided pattern_id. "
            "Result: %s, pattern_id: %s",
            result,
            pattern_id,
        )
        return pattern_id

    async def check_exists(
        self,
        domain: str,
        signature_hash: str,
        version: int,
        conn: AsyncConnection,
    ) -> bool:
        """Check if a pattern exists for the given lineage and version.

        Args:
            domain: Domain identifier for the pattern.
            signature_hash: SHA256 hash of the pattern signature for lineage lookup.
            version: Version number to check for existence.
            conn: Interface compatibility only (see class docstring).

        Returns:
            True if a pattern with this lineage and version exists.

        Note:
            The ``conn`` parameter is accepted for interface compatibility
            but is NOT used. See class docstring for transaction semantics.
        """
        args = self._build_positional_args(
            "check_exists",
            {
                "domain_id": domain,
                "signature_hash": signature_hash,
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
        signature_hash: str,
        conn: AsyncConnection,
    ) -> UUID | None:
        """Check if a pattern exists by idempotency key (pattern_id + signature_hash).

        Args:
            pattern_id: UUID of the pattern to check.
            signature_hash: SHA256 hash of the pattern signature for idempotency verification.
            conn: Interface compatibility only (see class docstring).

        Returns:
            The pattern UUID if it exists with matching id and signature_hash, else None.

        Note:
            The ``conn`` parameter is accepted for interface compatibility
            but is NOT used. See class docstring for transaction semantics.
        """
        args = self._build_positional_args(
            "check_exists_by_id",
            {
                "pattern_id": str(pattern_id),
                "signature_hash": signature_hash,
            },
        )
        result = await self._runtime.call("check_exists_by_id", *args)

        if result and isinstance(result, dict) and "id" in result:
            return UUID(result["id"]) if isinstance(result["id"], str) else result["id"]
        return None

    async def set_previous_not_current(
        self,
        domain: str,
        signature_hash: str,
        conn: AsyncConnection,
    ) -> int:
        """Set is_current = false for all previous versions of this lineage.

        Args:
            domain: Domain identifier for the pattern lineage.
            signature_hash: SHA256 hash of the pattern signature identifying the lineage.
            conn: Interface compatibility only (see class docstring).

        Returns:
            Count of rows updated (previous versions marked non-current).

        Note:
            The ``conn`` parameter is accepted for interface compatibility
            but is NOT used. See class docstring for transaction semantics.
        """
        args = self._build_positional_args(
            "set_not_current",
            {
                "signature_hash": signature_hash,
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
        signature_hash: str,
        conn: AsyncConnection,
    ) -> int | None:
        """Get the latest version number for a pattern lineage.

        Args:
            domain: Domain identifier for the pattern lineage.
            signature_hash: SHA256 hash of the pattern signature identifying the lineage.
            conn: Interface compatibility only (see class docstring).

        Returns:
            The highest version number for this lineage, or None if no patterns exist.

        Note:
            The ``conn`` parameter is accepted for interface compatibility
            but is NOT used. See class docstring for transaction semantics.
        """
        args = self._build_positional_args(
            "get_latest_version",
            {
                "domain_id": domain,
                "signature_hash": signature_hash,
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
        """Get the original stored_at timestamp for a pattern.

        Note:
            The ``conn`` parameter is accepted for interface compatibility
            but is NOT used. See class docstring for transaction semantics.
        """
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

    async def store_with_version_transition(
        self,
        *,
        pattern_id: UUID,
        signature: str,
        signature_hash: str,
        domain: str,
        version: int,
        confidence: float,
        quality_score: float = 0.5,
        state: EnumPatternState,
        is_current: bool,
        stored_at: datetime,
        actor: str | None = None,
        source_run_id: str | None = None,
        correlation_id: UUID | None = None,
        metadata: TypedDictPatternStorageMetadata | None = None,
        conn: AsyncConnection,
    ) -> UUID:
        """Atomically transition previous version(s) and store new pattern.

        This is the PREFERRED method for storing new versions of existing patterns.
        It combines set_previous_not_current and store_pattern into a single atomic
        SQL operation using a CTE (Common Table Expression).

        Atomicity Guarantee
        -------------------
        This method guarantees that either:
        - Both the UPDATE (set previous versions non-current) AND INSERT succeed, OR
        - Neither operation takes effect (full rollback)

        This prevents the critical invariant violation where a lineage has ZERO
        current versions (which occurs if set_previous_not_current succeeds but
        store_pattern fails in separate calls).

        When to Use This Method
        -----------------------
        Use this method when:
        - Storing a new version of an existing pattern (version > 1)
        - You need atomicity guarantees for version transitions
        - You want to avoid the race condition between UPDATE and INSERT

        Use store_pattern instead when:
        - Storing a brand new pattern (first version, no previous versions exist)
        - You have already called set_previous_not_current within a transaction

        Unused Parameters (Interface Compatibility)
        --------------------------------------------
        Same as store_pattern - see that method's docstring for details on
        is_current, stored_at, actor, source_run_id, and metadata.

        Args:
            pattern_id: Unique identifier for this pattern instance.
            signature: The pattern signature text (stored in pattern_signature column).
            signature_hash: SHA256 hash of the signature for identity lookups.
            domain: Domain where the pattern was learned.
            version: Version number (MUST be > latest existing version).
            confidence: Confidence score at storage time.
            quality_score: Initial quality score (0.0-1.0, default 0.5).
            state: Initial state of the pattern.
            is_current: Ignored - always stored as TRUE.
            stored_at: Ignored - uses database NOW() default.
            actor: Reserved for future audit trail.
            source_run_id: Reserved for future audit trail.
            correlation_id: Correlation ID for distributed tracing.
            metadata: Reserved for future extensibility.
            conn: Interface compatibility only (see class docstring).

        Returns:
            UUID of the stored pattern.

        Raises:
            ValueError: If required parameters are missing.
        """
        if conn is not None and not self._conn_warning_logged:
            logger.warning(
                "conn parameter ignored by AdapterPatternStore - this adapter manages "
                "its own connections. See class docstring for transaction semantics."
            )
            self._conn_warning_logged = True

        # Build positional args - contract defaults apply for omitted optional params
        args = self._build_positional_args(
            "store_with_version_transition",
            {
                "id": str(pattern_id),
                "signature": signature,
                "signature_hash": signature_hash,
                "domain_id": domain,
                # domain_version: omitted - uses contract default "1.0"
                # domain_candidates: omitted - uses contract default "[]"
                # keywords: omitted - optional with no default, will be None
                "confidence": confidence,
                "quality_score": quality_score,
                "status": state.value,
                "source_session_ids": f"{{{correlation_id}}}"
                if correlation_id
                else "{}",
                # recurrence_count: omitted - uses contract default 1
                "version": version,
            },
        )

        result = await self._runtime.call("store_with_version_transition", *args)

        # Return the stored pattern ID
        if result and isinstance(result, dict) and "id" in result:
            return UUID(result["id"]) if isinstance(result["id"], str) else result["id"]

        # Defensive: log if result is empty/invalid to help diagnose INSERT failures
        logger.warning(
            "store_with_version_transition returned unexpected result, using provided pattern_id. "
            "Result: %s, pattern_id: %s",
            result,
            pattern_id,
        )
        return pattern_id


def _convert_defaults_to_schema_value(contract_dict: dict[str, object]) -> dict[str, object]:
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

    def convert_value(value: object) -> dict[str, object]:
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


# =============================================================================
# Protocol Conformance Check
# =============================================================================
# This static type check verifies that AdapterPatternStore implements
# ProtocolPatternStore at import time, catching protocol drift early.
# The actual runtime check happens when the adapter is used with isinstance().

if TYPE_CHECKING:
    _adapter_protocol_check: ProtocolPatternStore = AdapterPatternStore(
        None  # type: ignore[arg-type]
    )


__all__ = [
    "AdapterPatternStore",
    "create_pattern_store_adapter",
    "load_contract",
]
