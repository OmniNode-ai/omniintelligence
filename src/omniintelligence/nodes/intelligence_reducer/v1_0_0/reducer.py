"""
Unified Intelligence Reducer

Pure reducer handling all intelligence FSMs via enum routing.
All state stored in PostgreSQL fsm_state table.
Emits intents to orchestrator and effect nodes.
"""

from typing import Dict, List, Optional, Any
import asyncpg
from datetime import datetime, timedelta

from omnibase_core.node import NodeOmniAgentReducer

from ....shared.enums import (
    EnumFSMType,
    EnumFSMAction,
    EnumIngestionState,
    EnumPatternLearningState,
    EnumQualityAssessmentState,
    EnumIntentType,
)
from ....shared.models import (
    ModelReducerInput,
    ModelReducerOutput,
    ModelReducerConfig,
    ModelIntent,
    ModelFSMState,
)
from ....shared.intents import IntentFactory, generate_correlation_id


class IntelligenceReducer(NodeOmniAgentReducer[
    ModelReducerInput,
    ModelReducerOutput,
    ModelReducerConfig
]):
    """
    Unified reducer for ALL intelligence FSMs.

    Handles multiple FSMs via fsm_type enum:
    - INGESTION: Document ingestion (RECEIVED → INDEXED)
    - PATTERN_LEARNING: Pattern learning (FOUNDATION → TRACEABILITY → COMPLETED)
    - QUALITY_ASSESSMENT: Quality scoring (RAW → STORED)

    Pure reducer: All state in database, zero instance state.
    """

    def __init__(self, config: ModelReducerConfig):
        super().__init__(config)
        self.config = config
        self._db_pool: Optional[asyncpg.Pool] = None

        # FSM definitions
        self._fsm_transitions = self._init_fsm_definitions()

    def _init_fsm_definitions(self) -> Dict[EnumFSMType, Dict[str, List[Dict]]]:
        """Initialize FSM transition definitions."""
        return {
            EnumFSMType.INGESTION: {
                EnumIngestionState.RECEIVED: [
                    {"to": EnumIngestionState.PROCESSING, "action": EnumFSMAction.START_PROCESSING},
                    {"to": EnumIngestionState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumIngestionState.PROCESSING: [
                    {"to": EnumIngestionState.INDEXED, "action": EnumFSMAction.COMPLETE_INDEXING},
                    {"to": EnumIngestionState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumIngestionState.INDEXED: [
                    {"to": EnumIngestionState.PROCESSING, "action": EnumFSMAction.REINDEX},
                ],
                EnumIngestionState.FAILED: [
                    {"to": EnumIngestionState.PROCESSING, "action": EnumFSMAction.RETRY},
                ],
            },
            EnumFSMType.PATTERN_LEARNING: {
                EnumPatternLearningState.FOUNDATION: [
                    {"to": EnumPatternLearningState.MATCHING, "action": EnumFSMAction.ADVANCE_TO_MATCHING},
                    {"to": EnumPatternLearningState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumPatternLearningState.MATCHING: [
                    {"to": EnumPatternLearningState.VALIDATION, "action": EnumFSMAction.ADVANCE_TO_VALIDATION},
                    {"to": EnumPatternLearningState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumPatternLearningState.VALIDATION: [
                    {"to": EnumPatternLearningState.TRACEABILITY, "action": EnumFSMAction.ADVANCE_TO_TRACEABILITY},
                    {"to": EnumPatternLearningState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumPatternLearningState.TRACEABILITY: [
                    {"to": EnumPatternLearningState.COMPLETED, "action": EnumFSMAction.COMPLETE_LEARNING},
                    {"to": EnumPatternLearningState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumPatternLearningState.COMPLETED: [
                    {"to": EnumPatternLearningState.FOUNDATION, "action": EnumFSMAction.RELEARN},
                ],
                EnumPatternLearningState.FAILED: [
                    {"to": EnumPatternLearningState.FOUNDATION, "action": EnumFSMAction.RETRY},
                ],
            },
            EnumFSMType.QUALITY_ASSESSMENT: {
                EnumQualityAssessmentState.RAW: [
                    {"to": EnumQualityAssessmentState.ASSESSING, "action": EnumFSMAction.START_ASSESSMENT},
                    {"to": EnumQualityAssessmentState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumQualityAssessmentState.ASSESSING: [
                    {"to": EnumQualityAssessmentState.SCORED, "action": EnumFSMAction.COMPLETE_SCORING},
                    {"to": EnumQualityAssessmentState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumQualityAssessmentState.SCORED: [
                    {"to": EnumQualityAssessmentState.STORED, "action": EnumFSMAction.STORE_RESULTS},
                    {"to": EnumQualityAssessmentState.FAILED, "action": EnumFSMAction.FAIL},
                ],
                EnumQualityAssessmentState.STORED: [
                    {"to": EnumQualityAssessmentState.ASSESSING, "action": EnumFSMAction.REASSESS},
                ],
                EnumQualityAssessmentState.FAILED: [
                    {"to": EnumQualityAssessmentState.ASSESSING, "action": EnumFSMAction.RETRY},
                ],
            },
        }

    async def initialize(self):
        """Initialize database connection pool."""
        self._db_pool = await asyncpg.create_pool(
            self.config.database_url,
            min_size=5,
            max_size=20,
        )

    async def shutdown(self):
        """Shutdown database connection pool."""
        if self._db_pool:
            await self._db_pool.close()

    async def process(self, input_data: ModelReducerInput) -> ModelReducerOutput:
        """
        Process FSM state transition.

        Pure function - all state from/to database.
        """
        try:
            # Route to appropriate FSM handler
            if input_data.fsm_type == EnumFSMType.INGESTION:
                return await self._process_ingestion_fsm(input_data)
            elif input_data.fsm_type == EnumFSMType.PATTERN_LEARNING:
                return await self._process_pattern_learning_fsm(input_data)
            elif input_data.fsm_type == EnumFSMType.QUALITY_ASSESSMENT:
                return await self._process_quality_assessment_fsm(input_data)
            else:
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

    async def _process_ingestion_fsm(
        self,
        input_data: ModelReducerInput,
    ) -> ModelReducerOutput:
        """Process ingestion FSM state transition."""
        return await self._execute_transition(
            input_data,
            EnumIngestionState.RECEIVED,  # initial state
        )

    async def _process_pattern_learning_fsm(
        self,
        input_data: ModelReducerInput,
    ) -> ModelReducerOutput:
        """Process pattern learning FSM state transition."""
        return await self._execute_transition(
            input_data,
            EnumPatternLearningState.FOUNDATION,  # initial state
        )

    async def _process_quality_assessment_fsm(
        self,
        input_data: ModelReducerInput,
    ) -> ModelReducerOutput:
        """Process quality assessment FSM state transition."""
        return await self._execute_transition(
            input_data,
            EnumQualityAssessmentState.RAW,  # initial state
        )

    async def _execute_transition(
        self,
        input_data: ModelReducerInput,
        initial_state: str,
    ) -> ModelReducerOutput:
        """
        Execute FSM state transition with lease management.

        Pure function - reads state from DB, validates transition,
        writes new state to DB, emits intents.
        """
        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                # Get current state
                current_state = await self._get_current_state(
                    conn,
                    input_data.fsm_type,
                    input_data.entity_id,
                    initial_state,
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

                # Validate transition
                valid, target_state = self._validate_transition(
                    input_data.fsm_type,
                    current_state.current_state,
                    input_data.action,
                )

                if not valid:
                    return ModelReducerOutput(
                        success=False,
                        previous_state=current_state.current_state,
                        current_state=current_state.current_state,
                        errors=[
                            f"Invalid transition: {current_state.current_state} --{input_data.action}--> (no valid target)"
                        ],
                    )

                # Execute transition
                new_state = await self._update_state(
                    conn,
                    input_data.fsm_type,
                    input_data.entity_id,
                    current_state.current_state,
                    target_state,
                    input_data.action,
                    input_data.payload or {},
                    input_data.correlation_id,
                )

                # Emit intents
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
                        "transition_timestamp": datetime.utcnow().isoformat(),
                    },
                )

    async def _get_current_state(
        self,
        conn: asyncpg.Connection,
        fsm_type: EnumFSMType,
        entity_id: str,
        initial_state: str,
    ) -> ModelFSMState:
        """Get current FSM state from database or initialize."""
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
            # Initialize new entity
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
                transition_timestamp=datetime.utcnow(),
            )

    async def _check_lease(
        self,
        conn: asyncpg.Connection,
        fsm_type: EnumFSMType,
        entity_id: str,
        lease_id: str,
        epoch: int,
    ) -> bool:
        """Check if lease is valid."""
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
            and row["lease_expires_at"] > datetime.utcnow()
        )

    def _validate_transition(
        self,
        fsm_type: EnumFSMType,
        current_state: str,
        action: EnumFSMAction,
    ) -> tuple[bool, Optional[str]]:
        """Validate if transition is allowed."""
        fsm_def = self._fsm_transitions.get(fsm_type, {})
        transitions = fsm_def.get(current_state, [])

        for transition in transitions:
            if transition["action"] == action:
                return True, transition["to"]

        return False, None

    async def _update_state(
        self,
        conn: asyncpg.Connection,
        fsm_type: EnumFSMType,
        entity_id: str,
        old_state: str,
        new_state: str,
        action: EnumFSMAction,
        payload: Dict[str, Any],
        correlation_id: str,
    ) -> str:
        """Update FSM state in database."""
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
        payload: Dict[str, Any],
    ) -> List[ModelIntent]:
        """Generate intents based on state transition."""
        intents = []

        # Emit workflow trigger for processing states
        if new_state in ["PROCESSING", "ASSESSING", "MATCHING"]:
            from ....shared.enums import EnumOperationType

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
            topic = f"{fsm_type.value.lower()}.{'completed' if new_state != 'FAILED' else 'failed'}.v1"
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
