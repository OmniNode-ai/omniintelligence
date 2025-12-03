"""
Unified Intelligence Reducer - Declarative FSM Pattern

Reducer handling all intelligence FSMs via YAML contracts and enum routing.
All state stored in PostgreSQL fsm_state table.
Emits intents to orchestrator and effect nodes.

Inherits from NodeReducerDeclarative for FSM execution via YAML contracts.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg

from omnibase_core.mixins.mixin_fsm_execution import MixinFSMExecution
from omnibase_core.models.contracts.subcontracts.model_fsm_subcontract import (
    ModelFSMSubcontract,
)
from omnibase_core.utils.util_safe_yaml_loader import load_and_validate_yaml_model

from omniintelligence.enums import (
    EnumFSMAction,
    EnumFSMType,
)
from omniintelligence.models import (
    ModelFSMState,
    ModelIntent,
    ModelReducerConfig,
    ModelReducerInput,
    ModelReducerOutput,
)
from omniintelligence.shared.intents import IntentFactory


# Contract directory path (relative to this file)
_CONTRACTS_DIR = Path(__file__).parent / "contracts"


class IntelligenceReducer(MixinFSMExecution):
    """
    Unified reducer for ALL intelligence FSMs.

    Uses declarative FSM pattern with YAML contracts for state transitions.
    Routes to appropriate FSM based on fsm_type enum:
    - INGESTION: Document ingestion (RECEIVED -> INDEXED)
    - PATTERN_LEARNING: 4-phase pattern learning (FOUNDATION -> COMPLETED)
    - QUALITY_ASSESSMENT: Quality scoring (RAW -> STORED)

    Pure reducer: All state in database, FSM definitions in YAML.
    """

    def __init__(self, config: ModelReducerConfig) -> None:
        """
        Initialize reducer with configuration.

        Args:
            config: Reducer configuration with database URL and settings
        """
        super().__init__()
        self.config = config
        self._db_pool: asyncpg.Pool | None = None

        # Load FSM contracts from YAML
        self._fsm_contracts: dict[EnumFSMType, ModelFSMSubcontract] = (
            self._load_fsm_contracts()
        )

    def _load_fsm_contracts(self) -> dict[EnumFSMType, ModelFSMSubcontract]:
        """
        Load FSM contracts from YAML files.

        Returns:
            Dictionary mapping FSM type to contract
        """
        return {
            EnumFSMType.INGESTION: load_and_validate_yaml_model(
                _CONTRACTS_DIR / "fsm_ingestion.yaml",
                ModelFSMSubcontract,
            ),
            EnumFSMType.PATTERN_LEARNING: load_and_validate_yaml_model(
                _CONTRACTS_DIR / "fsm_pattern_learning.yaml",
                ModelFSMSubcontract,
            ),
            EnumFSMType.QUALITY_ASSESSMENT: load_and_validate_yaml_model(
                _CONTRACTS_DIR / "fsm_quality_assessment.yaml",
                ModelFSMSubcontract,
            ),
        }

    def _get_fsm_contract(self, fsm_type: EnumFSMType) -> ModelFSMSubcontract:
        """
        Get FSM contract for the specified type.

        Args:
            fsm_type: Type of FSM

        Returns:
            FSM contract for the specified type

        Raises:
            KeyError: If FSM type not found
        """
        return self._fsm_contracts[fsm_type]

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        self._db_pool = await asyncpg.create_pool(
            self.config.database_url,
            min_size=5,
            max_size=20,
        )

    async def shutdown(self) -> None:
        """Shutdown database connection pool."""
        if self._db_pool:
            await self._db_pool.close()

    async def process(self, input_data: ModelReducerInput) -> ModelReducerOutput:
        """
        Process FSM state transition.

        Routes to appropriate FSM based on fsm_type and executes
        transition using declarative FSM contract.

        Args:
            input_data: Reducer input with FSM type, action, and entity info

        Returns:
            Reducer output with transition result and intents
        """
        try:
            # Get FSM contract for the specified type
            fsm_contract = self._get_fsm_contract(input_data.fsm_type)

            # Execute transition with database state management
            return await self._execute_transition(
                input_data,
                fsm_contract,
            )

        except KeyError:
            return ModelReducerOutput(
                success=False,
                current_state="UNKNOWN",
                errors=[f"Unknown FSM type: {input_data.fsm_type}"],
            )
        except Exception as e:
            return ModelReducerOutput(
                success=False,
                current_state="ERROR",
                errors=[str(e)],
            )

    async def _execute_transition(
        self,
        input_data: ModelReducerInput,
        fsm_contract: ModelFSMSubcontract,
    ) -> ModelReducerOutput:
        """
        Execute FSM state transition with database state management.

        Uses declarative FSM contract for transition validation.
        Persists state to database and emits intents.

        Args:
            input_data: Reducer input
            fsm_contract: FSM contract for validation

        Returns:
            Reducer output with transition result
        """
        if self._db_pool is None:
            return ModelReducerOutput(
                success=False,
                current_state="ERROR",
                errors=["Database pool not initialized"],
            )

        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                # Get current state from database
                current_state = await self._get_current_state(
                    conn,
                    input_data.fsm_type,
                    input_data.entity_id,
                    fsm_contract.initial_state,
                )

                # Check lease if required
                if self.config.enable_lease_management and input_data.lease_id:
                    lease_valid = await self._check_lease(
                        conn,
                        input_data.fsm_type,
                        input_data.entity_id,
                        input_data.lease_id,
                        input_data.epoch,
                    )
                    if not lease_valid:
                        return ModelReducerOutput(
                            success=False,
                            current_state=current_state.current_state,
                            errors=["Invalid or expired lease"],
                        )

                # Validate transition using FSM contract
                valid, target_state = self._validate_transition_from_contract(
                    fsm_contract,
                    current_state.current_state,
                    input_data.action,
                )

                if not valid or target_state is None:
                    return ModelReducerOutput(
                        success=False,
                        previous_state=current_state.current_state,
                        current_state=current_state.current_state,
                        errors=[
                            f"Invalid transition: {current_state.current_state} "
                            f"--{input_data.action.value}--> (no valid target)"
                        ],
                    )

                # Execute transition - update database
                await self._update_state(
                    conn,
                    input_data.fsm_type,
                    input_data.entity_id,
                    current_state.current_state,
                    target_state,
                    input_data.action,
                    input_data.payload or {},
                    input_data.correlation_id,
                )

                # Generate intents based on transition
                intents = self._generate_intents(
                    input_data.fsm_type,
                    input_data.entity_id,
                    current_state.current_state,
                    target_state,
                    input_data.correlation_id,
                    input_data.payload or {},
                )

                return ModelReducerOutput(
                    success=True,
                    previous_state=current_state.current_state,
                    current_state=target_state,
                    intents=intents,
                    metadata={
                        "action": input_data.action.value,
                        "transition_timestamp": datetime.now(UTC).isoformat(),
                        "fsm_type": input_data.fsm_type.value,
                    },
                )

    def _validate_transition_from_contract(
        self,
        fsm_contract: ModelFSMSubcontract,
        current_state: str,
        action: EnumFSMAction,
    ) -> tuple[bool, str | None]:
        """
        Validate transition using FSM contract.

        Args:
            fsm_contract: FSM contract with transition definitions
            current_state: Current state name
            action: Action trigger (maps to transition trigger)

        Returns:
            Tuple of (is_valid, target_state)
        """
        # Find matching transition in contract
        for transition in fsm_contract.transitions:
            # Check if transition matches current state and trigger
            if (
                transition.from_state == current_state
                and transition.trigger == action.value
            ):
                return True, transition.to_state

            # Also check wildcard transitions (from_state: '*')
            if transition.from_state == "*" and transition.trigger == action.value:
                return True, transition.to_state

        return False, None

    async def _get_current_state(
        self,
        conn: asyncpg.Connection,
        fsm_type: EnumFSMType,
        entity_id: str,
        initial_state: str,
    ) -> ModelFSMState:
        """
        Get current FSM state from database or initialize.

        Args:
            conn: Database connection
            fsm_type: FSM type
            entity_id: Entity identifier
            initial_state: Initial state from contract

        Returns:
            Current FSM state
        """
        row = await conn.fetchrow(
            """
            SELECT current_state, previous_state, transition_timestamp,
                   metadata, lease_id, lease_epoch, lease_expires_at
            FROM fsm_state
            WHERE fsm_type = $1 AND entity_id = $2
            """,
            fsm_type.value,
            entity_id,
        )

        if row:
            return ModelFSMState(
                fsm_type=fsm_type,
                entity_id=entity_id,
                current_state=row["current_state"],
                previous_state=row["previous_state"],
                transition_timestamp=row["transition_timestamp"],
                metadata=row["metadata"],
                lease_id=row["lease_id"],
                lease_epoch=row["lease_epoch"],
                lease_expires_at=row["lease_expires_at"],
            )
        else:
            # Initialize new entity with initial state from contract
            await conn.execute(
                """
                INSERT INTO fsm_state (fsm_type, entity_id, current_state, transition_timestamp)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (fsm_type, entity_id) DO NOTHING
                """,
                fsm_type.value,
                entity_id,
                initial_state,
            )
            return ModelFSMState(
                fsm_type=fsm_type,
                entity_id=entity_id,
                current_state=initial_state,
                transition_timestamp=datetime.now(UTC),
            )

    async def _check_lease(
        self,
        conn: asyncpg.Connection,
        fsm_type: EnumFSMType,
        entity_id: str,
        lease_id: str,
        epoch: int | None,
    ) -> bool:
        """
        Check if lease is valid.

        Args:
            conn: Database connection
            fsm_type: FSM type
            entity_id: Entity identifier
            lease_id: Lease identifier
            epoch: Lease epoch

        Returns:
            True if lease is valid
        """
        row = await conn.fetchrow(
            """
            SELECT lease_id, lease_epoch, lease_expires_at
            FROM fsm_state
            WHERE fsm_type = $1 AND entity_id = $2
            """,
            fsm_type.value,
            entity_id,
        )

        if not row or not row["lease_id"]:
            return True  # No lease held

        # Check lease matches and not expired
        return (
            row["lease_id"] == lease_id
            and row["lease_epoch"] == epoch
            and row["lease_expires_at"] > datetime.now(UTC)
        )

    async def _update_state(
        self,
        conn: asyncpg.Connection,
        fsm_type: EnumFSMType,
        entity_id: str,
        old_state: str,
        new_state: str,
        action: EnumFSMAction,
        payload: dict[str, Any],
        correlation_id: str,
    ) -> str:
        """
        Update FSM state in database.

        Args:
            conn: Database connection
            fsm_type: FSM type
            entity_id: Entity identifier
            old_state: Previous state
            new_state: New state
            action: Action that triggered transition
            payload: Action payload
            correlation_id: Correlation ID

        Returns:
            New state name
        """
        await conn.execute(
            """
            UPDATE fsm_state
            SET current_state = $3,
                previous_state = $4,
                transition_timestamp = NOW(),
                metadata = jsonb_build_object(
                    'last_action', $5,
                    'correlation_id', $6,
                    'payload', $7::jsonb
                )
            WHERE fsm_type = $1 AND entity_id = $2
            """,
            fsm_type.value,
            entity_id,
            new_state,
            old_state,
            action.value,
            correlation_id,
            payload,
        )
        return new_state

    def _generate_intents(
        self,
        fsm_type: EnumFSMType,
        entity_id: str,
        old_state: str,
        new_state: str,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> list[ModelIntent]:
        """
        Generate intents based on state transition.

        Args:
            fsm_type: FSM type
            entity_id: Entity identifier
            old_state: Previous state
            new_state: New state
            correlation_id: Correlation ID
            payload: Action payload

        Returns:
            List of intents to emit
        """
        intents: list[ModelIntent] = []

        # Emit workflow trigger for processing states
        if new_state in ["PROCESSING", "ASSESSING", "MATCHING"]:
            from omniintelligence.enums import EnumOperationType

            # Map FSM type to operation type
            operation_map = {
                EnumFSMType.INGESTION: EnumOperationType.DOCUMENT_INGESTION,
                EnumFSMType.PATTERN_LEARNING: EnumOperationType.PATTERN_LEARNING,
                EnumFSMType.QUALITY_ASSESSMENT: EnumOperationType.QUALITY_ASSESSMENT,
            }

            operation_type = operation_map.get(fsm_type)
            if operation_type:
                intents.append(
                    IntentFactory.create_workflow_trigger_intent(
                        operation_type=operation_type,
                        entity_id=entity_id,
                        payload=payload,
                        correlation_id=correlation_id,
                    )
                )

        # Emit event for completion or failure
        if new_state in ["INDEXED", "COMPLETED", "STORED", "FAILED"]:
            topic = (
                f"{fsm_type.value.lower()}."
                f"{'completed' if new_state != 'FAILED' else 'failed'}.v1"
            )
            intents.append(
                IntentFactory.create_event_publish_intent(
                    topic=topic,
                    event_type=f"FSM_{new_state}",
                    event_payload={
                        "fsm_type": fsm_type.value,
                        "entity_id": entity_id,
                        "previous_state": old_state,
                        "current_state": new_state,
                        **payload,
                    },
                    correlation_id=correlation_id,
                )
            )

        return intents
