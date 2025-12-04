"""
Unit tests for Intelligence Reducer.

Tests FSM state transitions, intent emission, error handling,
and database interactions with mocked dependencies.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omniintelligence.enums import (
    EnumFSMAction,
    EnumFSMType,
    EnumIntentType,
)
from omniintelligence.models import (
    ModelReducerConfig,
    ModelReducerInput,
    ModelReducerOutput,
)
from omniintelligence.models.model_fsm_state import ModelFSMState
from src.omniintelligence.nodes.intelligence_reducer.v1_0_0.reducer import (
    IntelligenceReducer,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def reducer_config():
    """Create reducer configuration for testing."""
    return ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=False,
        lease_timeout_seconds=300,
        max_retry_attempts=3,
    )


@pytest.fixture
def reducer_config_with_lease():
    """Create reducer configuration with lease management enabled."""
    return ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=True,
        lease_timeout_seconds=300,
        max_retry_attempts=3,
    )


@pytest.fixture
def reducer(reducer_config):
    """Create reducer instance for testing."""
    return IntelligenceReducer(reducer_config)


@pytest.fixture
def reducer_with_lease(reducer_config_with_lease):
    """Create reducer instance with lease management."""
    return IntelligenceReducer(reducer_config_with_lease)


@pytest.fixture
def mock_db_pool():
    """Create a mock database pool."""
    pool = AsyncMock()
    pool.close = AsyncMock()
    return pool


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection with transaction context."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.execute = AsyncMock()

    # Create a proper async context manager for transaction
    transaction_ctx = AsyncMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    return conn


@pytest.fixture
def sample_reducer_input():
    """Create sample reducer input."""
    return ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )


@pytest.fixture
def sample_fsm_state():
    """Create sample FSM state."""
    return ModelFSMState(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        current_state="RECEIVED",
        previous_state=None,
        transition_timestamp=datetime.now(UTC),
    )


# =========================================================================
# Initialization and Shutdown Tests (Lines 109, 117-118)
# =========================================================================


@pytest.mark.asyncio
async def test_initialize_creates_db_pool(reducer):
    """Test initialize() creates database connection pool."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        await reducer.initialize()

        mock_create_pool.assert_called_once_with(
            reducer.config.database_url,
            min_size=5,
            max_size=20,
        )
        assert reducer._db_pool is mock_pool


@pytest.mark.asyncio
async def test_shutdown_closes_db_pool(reducer, mock_db_pool):
    """Test shutdown() closes database connection pool."""
    reducer._db_pool = mock_db_pool

    await reducer.shutdown()

    mock_db_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_with_no_pool(reducer):
    """Test shutdown() handles case when pool not initialized."""
    reducer._db_pool = None

    # Should not raise
    await reducer.shutdown()


# =========================================================================
# Process Method Tests (Lines 133-150)
# =========================================================================


@pytest.mark.asyncio
async def test_process_returns_error_for_unknown_fsm_type(reducer):
    """Test process() returns error for unknown FSM type."""
    # Create input with a mocked unknown FSM type
    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
    )

    # Mock _get_fsm_contract to raise KeyError
    with patch.object(reducer, "_get_fsm_contract", side_effect=KeyError("UNKNOWN")):
        result = await reducer.process(input_data)

    assert result.success is False
    assert result.current_state == "UNKNOWN"
    assert "Unknown FSM type" in result.errors[0]


@pytest.mark.asyncio
async def test_process_returns_error_for_general_exception(reducer, sample_reducer_input):
    """Test process() returns error for general exceptions."""
    # Mock _get_fsm_contract to raise general exception
    with patch.object(reducer, "_get_fsm_contract", side_effect=Exception("Test error")):
        result = await reducer.process(sample_reducer_input)

    assert result.success is False
    assert result.current_state == "ERROR"
    assert "Test error" in result.errors[0]


@pytest.mark.asyncio
async def test_process_routes_to_execute_transition(reducer, sample_reducer_input, mock_db_pool, mock_db_connection):
    """Test process() routes to _execute_transition correctly."""
    reducer._db_pool = mock_db_pool

    # Mock _execute_transition
    expected_output = ModelReducerOutput(
        success=True,
        previous_state="RECEIVED",
        current_state="PROCESSING",
        intents=[],
    )

    with patch.object(reducer, "_execute_transition", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = expected_output
        result = await reducer.process(sample_reducer_input)

    assert result.success is True
    assert result.current_state == "PROCESSING"


# =========================================================================
# Execute Transition Tests (Lines 174-247)
# =========================================================================


@pytest.mark.asyncio
async def test_execute_transition_returns_error_when_pool_not_initialized(reducer, sample_reducer_input):
    """Test _execute_transition returns error when database pool not initialized."""
    reducer._db_pool = None

    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)
    result = await reducer._execute_transition(sample_reducer_input, fsm_contract)

    assert result.success is False
    assert result.current_state == "ERROR"
    assert "Database pool not initialized" in result.errors[0]


@pytest.mark.asyncio
async def test_execute_transition_invalid_transition(reducer, mock_db_pool, mock_db_connection):
    """Test _execute_transition returns error for invalid transition."""
    reducer._db_pool = mock_db_pool

    # Setup mock connection
    mock_db_pool.acquire = MagicMock(return_value=AsyncContextManager(mock_db_connection))

    # Return a state where START_PROCESSING is invalid
    mock_db_connection.fetchrow.return_value = {
        "current_state": "INDEXED",  # Can't START_PROCESSING from INDEXED
        "previous_state": "PROCESSING",
        "transition_timestamp": datetime.now(UTC),
        "metadata": None,
        "lease_id": None,
        "lease_epoch": None,
        "lease_expires_at": None,
    }

    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
    )

    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)
    result = await reducer._execute_transition(input_data, fsm_contract)

    assert result.success is False
    assert result.current_state == "INDEXED"
    assert "Invalid transition" in result.errors[0]


@pytest.mark.asyncio
async def test_execute_transition_successful(reducer, mock_db_pool, mock_db_connection):
    """Test _execute_transition completes successfully."""
    reducer._db_pool = mock_db_pool

    # Setup mock connection
    mock_db_pool.acquire = MagicMock(return_value=AsyncContextManager(mock_db_connection))

    # Return RECEIVED state
    mock_db_connection.fetchrow.return_value = {
        "current_state": "RECEIVED",
        "previous_state": None,
        "transition_timestamp": datetime.now(UTC),
        "metadata": None,
        "lease_id": None,
        "lease_epoch": None,
        "lease_expires_at": None,
    }

    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )

    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)
    result = await reducer._execute_transition(input_data, fsm_contract)

    assert result.success is True
    assert result.previous_state == "RECEIVED"
    assert result.current_state == "PROCESSING"
    assert result.metadata is not None
    assert result.metadata["action"] == "START_PROCESSING"
    assert result.metadata["fsm_type"] == "INGESTION"
    # Should have workflow trigger intent for PROCESSING state
    assert len(result.intents) > 0


# =========================================================================
# Lease Validation Tests (Lines 192-205, 373-387)
# =========================================================================


@pytest.mark.asyncio
async def test_execute_transition_invalid_lease(reducer_with_lease, mock_db_pool, mock_db_connection):
    """Test _execute_transition returns error for invalid lease."""
    reducer_with_lease._db_pool = mock_db_pool

    # Setup mock connection
    mock_db_pool.acquire = MagicMock(return_value=AsyncContextManager(mock_db_connection))

    # Return state with current_state
    mock_db_connection.fetchrow.side_effect = [
        # First call for _get_current_state
        {
            "current_state": "RECEIVED",
            "previous_state": None,
            "transition_timestamp": datetime.now(UTC),
            "metadata": None,
            "lease_id": "other_lease",
            "lease_epoch": 1,
            "lease_expires_at": datetime.now(UTC) + timedelta(hours=1),
        },
        # Second call for _check_lease
        {
            "lease_id": "other_lease",
            "lease_epoch": 1,
            "lease_expires_at": datetime.now(UTC) + timedelta(hours=1),
        },
    ]

    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
        lease_id="my_lease",  # Different from stored lease
        epoch=1,
    )

    fsm_contract = reducer_with_lease._get_fsm_contract(EnumFSMType.INGESTION)
    result = await reducer_with_lease._execute_transition(input_data, fsm_contract)

    assert result.success is False
    assert "Invalid or expired lease" in result.errors[0]


@pytest.mark.asyncio
async def test_check_lease_no_existing_lease(reducer_with_lease, mock_db_connection):
    """Test _check_lease returns True when no lease exists."""
    mock_db_connection.fetchrow.return_value = None

    result = await reducer_with_lease._check_lease(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        "lease_123",
        1,
    )

    assert result is True


@pytest.mark.asyncio
async def test_check_lease_no_lease_id_in_row(reducer_with_lease, mock_db_connection):
    """Test _check_lease returns True when row has no lease_id."""
    mock_db_connection.fetchrow.return_value = {
        "lease_id": None,
        "lease_epoch": None,
        "lease_expires_at": None,
    }

    result = await reducer_with_lease._check_lease(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        "lease_123",
        1,
    )

    assert result is True


@pytest.mark.asyncio
async def test_check_lease_valid_lease(reducer_with_lease, mock_db_connection):
    """Test _check_lease returns True for valid lease."""
    mock_db_connection.fetchrow.return_value = {
        "lease_id": "lease_123",
        "lease_epoch": 1,
        "lease_expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    result = await reducer_with_lease._check_lease(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        "lease_123",
        1,
    )

    assert result is True


@pytest.mark.asyncio
async def test_check_lease_expired_lease(reducer_with_lease, mock_db_connection):
    """Test _check_lease returns False for expired lease."""
    mock_db_connection.fetchrow.return_value = {
        "lease_id": "lease_123",
        "lease_epoch": 1,
        "lease_expires_at": datetime.now(UTC) - timedelta(hours=1),  # Expired
    }

    result = await reducer_with_lease._check_lease(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        "lease_123",
        1,
    )

    assert result is False


@pytest.mark.asyncio
async def test_check_lease_wrong_epoch(reducer_with_lease, mock_db_connection):
    """Test _check_lease returns False for wrong epoch."""
    mock_db_connection.fetchrow.return_value = {
        "lease_id": "lease_123",
        "lease_epoch": 2,  # Different epoch
        "lease_expires_at": datetime.now(UTC) + timedelta(hours=1),
    }

    result = await reducer_with_lease._check_lease(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        "lease_123",
        1,  # Expecting epoch 1
    )

    assert result is False


# =========================================================================
# Get Current State Tests (Lines 310-345)
# =========================================================================


@pytest.mark.asyncio
async def test_get_current_state_existing(reducer, mock_db_connection):
    """Test _get_current_state returns existing state."""
    mock_db_connection.fetchrow.return_value = {
        "current_state": "PROCESSING",
        "previous_state": "RECEIVED",
        "transition_timestamp": datetime.now(UTC),
        "metadata": {"key": "value"},
        "lease_id": None,
        "lease_epoch": None,
        "lease_expires_at": None,
    }

    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)
    result = await reducer._get_current_state(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        fsm_contract.initial_state,
    )

    assert result.current_state == "PROCESSING"
    assert result.previous_state == "RECEIVED"
    assert result.entity_id == "doc_123"
    assert result.fsm_type == EnumFSMType.INGESTION


@pytest.mark.asyncio
async def test_get_current_state_new_entity(reducer, mock_db_connection):
    """Test _get_current_state initializes new entity."""
    # First call returns None (no existing state)
    mock_db_connection.fetchrow.return_value = None

    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)
    result = await reducer._get_current_state(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "new_doc_123",
        fsm_contract.initial_state,
    )

    assert result.current_state == "RECEIVED"  # Initial state from contract
    assert result.entity_id == "new_doc_123"

    # Verify INSERT was called
    mock_db_connection.execute.assert_called_once()
    call_args = mock_db_connection.execute.call_args[0]
    assert "INSERT INTO fsm_state" in call_args[0]


# =========================================================================
# Update State Tests (Lines 420-441)
# =========================================================================


@pytest.mark.asyncio
async def test_update_state_executes_correctly(reducer, mock_db_connection):
    """Test _update_state executes database update correctly."""
    result = await reducer._update_state(
        mock_db_connection,
        EnumFSMType.INGESTION,
        "doc_123",
        "RECEIVED",
        "PROCESSING",
        EnumFSMAction.START_PROCESSING,
        {"file_path": "test.py"},
        "corr_456",
    )

    assert result == "PROCESSING"

    # Verify UPDATE was called with correct parameters
    mock_db_connection.execute.assert_called_once()
    call_args = mock_db_connection.execute.call_args[0]
    assert "UPDATE fsm_state" in call_args[0]
    assert call_args[1] == "INGESTION"  # fsm_type
    assert call_args[2] == "doc_123"  # entity_id
    assert call_args[3] == "PROCESSING"  # new_state
    assert call_args[4] == "RECEIVED"  # old_state


# =========================================================================
# Validate Transition Tests (Lines 276-289, including wildcard)
# =========================================================================


def test_validate_wildcard_transition(reducer):
    """Test _validate_transition_from_contract handles wildcard from_state."""
    from omnibase_core.models.contracts.subcontracts.model_fsm_subcontract import (
        ModelFSMStateTransition,
        ModelFSMSubcontract,
    )

    # Create a mock contract with a wildcard transition
    mock_contract = MagicMock(spec=ModelFSMSubcontract)
    mock_contract.initial_state = "INIT"
    mock_contract.transitions = [
        # Regular transition (won't match)
        MagicMock(
            spec=ModelFSMStateTransition,
            from_state="INIT",
            to_state="PROCESSING",
            trigger="START",
        ),
        # Wildcard transition - should match any state
        MagicMock(
            spec=ModelFSMStateTransition,
            from_state="*",  # Wildcard
            to_state="ERROR",
            trigger="FAIL",
        ),
    ]

    # Test wildcard matches from any state
    valid, target = reducer._validate_transition_from_contract(
        mock_contract,
        "ANY_STATE_HERE",  # Any current state
        EnumFSMAction.FAIL,  # Matches wildcard trigger
    )

    assert valid is True
    assert target == "ERROR"


def test_validate_wildcard_transition_not_matching_trigger(reducer):
    """Test wildcard transition doesn't match when trigger is different."""
    mock_contract = MagicMock()
    mock_contract.initial_state = "INIT"
    mock_contract.transitions = [
        # Wildcard transition
        MagicMock(
            from_state="*",
            to_state="ERROR",
            trigger="FAIL",
        ),
    ]

    # Wildcard won't match because trigger is different
    valid, target = reducer._validate_transition_from_contract(
        mock_contract,
        "ANY_STATE",
        EnumFSMAction.START_PROCESSING,  # Different trigger
    )

    assert valid is False
    assert target is None


def test_validate_transition_valid(reducer):
    """Test _validate_transition_from_contract for valid transition."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "RECEIVED",
        EnumFSMAction.START_PROCESSING,
    )

    assert valid is True
    assert target == "PROCESSING"


def test_validate_transition_invalid(reducer):
    """Test _validate_transition_from_contract for invalid transition."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "INDEXED",
        EnumFSMAction.START_PROCESSING,  # Can't start processing from INDEXED
    )

    assert valid is False
    assert target is None


def test_validate_transition_from_processing_to_indexed(reducer):
    """Test transition from PROCESSING to INDEXED."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "PROCESSING",
        EnumFSMAction.COMPLETE_INDEXING,
    )

    assert valid is True
    assert target == "INDEXED"


def test_validate_transition_fail_action(reducer):
    """Test FAIL action from various states."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    # FAIL from RECEIVED
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "RECEIVED",
        EnumFSMAction.FAIL,
    )

    assert valid is True
    assert target == "FAILED"

    # FAIL from PROCESSING
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "PROCESSING",
        EnumFSMAction.FAIL,
    )

    assert valid is True
    assert target == "FAILED"


def test_validate_transition_retry_from_failed(reducer):
    """Test RETRY action from FAILED state."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "FAILED",
        EnumFSMAction.RETRY,
    )

    assert valid is True
    assert target == "PROCESSING"


def test_validate_transition_reindex(reducer):
    """Test REINDEX action from INDEXED state."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "INDEXED",
        EnumFSMAction.REINDEX,
    )

    assert valid is True
    assert target == "PROCESSING"


# =========================================================================
# Pattern Learning FSM Transitions
# =========================================================================


def test_pattern_learning_fsm_transitions(reducer):
    """Test pattern learning FSM transitions through all phases."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.PATTERN_LEARNING)

    # FOUNDATION -> MATCHING
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "FOUNDATION",
        EnumFSMAction.ADVANCE_TO_MATCHING,
    )
    assert valid is True
    assert target == "MATCHING"

    # MATCHING -> VALIDATION
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "MATCHING",
        EnumFSMAction.ADVANCE_TO_VALIDATION,
    )
    assert valid is True
    assert target == "VALIDATION"

    # VALIDATION -> TRACEABILITY
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "VALIDATION",
        EnumFSMAction.ADVANCE_TO_TRACEABILITY,
    )
    assert valid is True
    assert target == "TRACEABILITY"

    # TRACEABILITY -> COMPLETED
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "TRACEABILITY",
        EnumFSMAction.COMPLETE_LEARNING,
    )
    assert valid is True
    assert target == "COMPLETED"


# =========================================================================
# Quality Assessment FSM Transitions
# =========================================================================


def test_quality_assessment_fsm_transitions(reducer):
    """Test quality assessment FSM transitions."""
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.QUALITY_ASSESSMENT)

    # RAW -> ASSESSING
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "RAW",
        EnumFSMAction.START_ASSESSMENT,
    )
    assert valid is True
    assert target == "ASSESSING"

    # ASSESSING -> SCORED
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "ASSESSING",
        EnumFSMAction.COMPLETE_SCORING,
    )
    assert valid is True
    assert target == "SCORED"

    # SCORED -> STORED
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "SCORED",
        EnumFSMAction.STORE_RESULTS,
    )
    assert valid is True
    assert target == "STORED"


# =========================================================================
# Intent Generation Tests (Lines 469-509, 492-496)
# =========================================================================


def test_generate_intents_processing_state(reducer):
    """Test intent generation for PROCESSING state."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        old_state="RECEIVED",
        new_state="PROCESSING",
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )

    assert len(intents) > 0
    workflow_intents = [i for i in intents if i.intent_type == EnumIntentType.WORKFLOW_TRIGGER]
    assert len(workflow_intents) == 1
    assert workflow_intents[0].target == "intelligence_orchestrator"


def test_generate_intents_assessing_state(reducer):
    """Test intent generation for ASSESSING state."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.QUALITY_ASSESSMENT,
        entity_id="doc_123",
        old_state="RAW",
        new_state="ASSESSING",
        correlation_id="corr_456",
        payload={},
    )

    assert len(intents) > 0
    workflow_intents = [i for i in intents if i.intent_type == EnumIntentType.WORKFLOW_TRIGGER]
    assert len(workflow_intents) == 1


def test_generate_intents_matching_state(reducer):
    """Test intent generation for MATCHING state."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.PATTERN_LEARNING,
        entity_id="pattern_123",
        old_state="FOUNDATION",
        new_state="MATCHING",
        correlation_id="corr_456",
        payload={},
    )

    assert len(intents) > 0
    workflow_intents = [i for i in intents if i.intent_type == EnumIntentType.WORKFLOW_TRIGGER]
    assert len(workflow_intents) == 1


def test_generate_intents_indexed_completion(reducer):
    """Test intent generation for INDEXED completion state."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        old_state="PROCESSING",
        new_state="INDEXED",
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )

    # Should have event publish intent for completion
    event_intents = [i for i in intents if i.intent_type == EnumIntentType.EVENT_PUBLISH]
    assert len(event_intents) == 1
    assert event_intents[0].target == "kafka_event_effect"
    assert "completed" in event_intents[0].payload["topic"]


def test_generate_intents_completed_state(reducer):
    """Test intent generation for COMPLETED state (pattern learning)."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.PATTERN_LEARNING,
        entity_id="pattern_123",
        old_state="TRACEABILITY",
        new_state="COMPLETED",
        correlation_id="corr_456",
        payload={},
    )

    event_intents = [i for i in intents if i.intent_type == EnumIntentType.EVENT_PUBLISH]
    assert len(event_intents) == 1
    assert "completed" in event_intents[0].payload["topic"]


def test_generate_intents_stored_state(reducer):
    """Test intent generation for STORED state (quality assessment)."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.QUALITY_ASSESSMENT,
        entity_id="qa_123",
        old_state="SCORED",
        new_state="STORED",
        correlation_id="corr_456",
        payload={},
    )

    event_intents = [i for i in intents if i.intent_type == EnumIntentType.EVENT_PUBLISH]
    assert len(event_intents) == 1
    assert "completed" in event_intents[0].payload["topic"]


def test_generate_intents_failed_state(reducer):
    """Test intent generation for FAILED state."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        old_state="PROCESSING",
        new_state="FAILED",
        correlation_id="corr_456",
        payload={"error": "Processing failed"},
    )

    event_intents = [i for i in intents if i.intent_type == EnumIntentType.EVENT_PUBLISH]
    assert len(event_intents) == 1
    assert "failed" in event_intents[0].payload["topic"]
    assert event_intents[0].payload["event_type"] == "FSM_FAILED"


def test_generate_intents_no_intents_for_intermediate_states(reducer):
    """Test no intents generated for intermediate states."""
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.QUALITY_ASSESSMENT,
        entity_id="qa_123",
        old_state="ASSESSING",
        new_state="SCORED",  # Intermediate state, not final
        correlation_id="corr_456",
        payload={},
    )

    # SCORED is not in workflow trigger states and not in completion states
    assert len(intents) == 0


def test_generate_intents_payload_included(reducer):
    """Test payload is included in event publish intent."""
    payload = {"file_path": "test.py", "custom_key": "custom_value"}

    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        old_state="PROCESSING",
        new_state="INDEXED",
        correlation_id="corr_456",
        payload=payload,
    )

    event_intents = [i for i in intents if i.intent_type == EnumIntentType.EVENT_PUBLISH]
    assert len(event_intents) == 1

    event_payload = event_intents[0].payload["payload"]
    assert event_payload["file_path"] == "test.py"
    assert event_payload["custom_key"] == "custom_value"
    assert event_payload["entity_id"] == "doc_123"
    assert event_payload["fsm_type"] == "INGESTION"


# =========================================================================
# FSM Contract Loading Tests
# =========================================================================


def test_fsm_contracts_all_loaded(reducer):
    """Test all FSM contracts are loaded."""
    assert EnumFSMType.INGESTION in reducer._fsm_contracts
    assert EnumFSMType.PATTERN_LEARNING in reducer._fsm_contracts
    assert EnumFSMType.QUALITY_ASSESSMENT in reducer._fsm_contracts


def test_fsm_contract_initial_states(reducer):
    """Test FSM contracts have correct initial states."""
    ingestion = reducer._get_fsm_contract(EnumFSMType.INGESTION)
    pattern_learning = reducer._get_fsm_contract(EnumFSMType.PATTERN_LEARNING)
    quality = reducer._get_fsm_contract(EnumFSMType.QUALITY_ASSESSMENT)

    assert ingestion.initial_state == "RECEIVED"
    assert pattern_learning.initial_state == "FOUNDATION"
    assert quality.initial_state == "RAW"


def test_get_fsm_contract_raises_for_unknown(reducer):
    """Test _get_fsm_contract raises KeyError for unknown FSM type."""
    # Access internal dict directly with invalid key
    with pytest.raises(KeyError):
        reducer._fsm_contracts["INVALID_TYPE"]


# =========================================================================
# Full Process Flow Integration Tests (With Mocked DB)
# =========================================================================


@pytest.mark.asyncio
async def test_full_process_flow_ingestion(reducer, mock_db_pool, mock_db_connection):
    """Test full process flow for ingestion FSM."""
    reducer._db_pool = mock_db_pool
    mock_db_pool.acquire = MagicMock(return_value=AsyncContextManager(mock_db_connection))

    # Setup mock to return RECEIVED state
    mock_db_connection.fetchrow.return_value = {
        "current_state": "RECEIVED",
        "previous_state": None,
        "transition_timestamp": datetime.now(UTC),
        "metadata": None,
        "lease_id": None,
        "lease_epoch": None,
        "lease_expires_at": None,
    }

    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )

    result = await reducer.process(input_data)

    assert result.success is True
    assert result.previous_state == "RECEIVED"
    assert result.current_state == "PROCESSING"
    assert len(result.intents) > 0  # Should have workflow trigger


@pytest.mark.asyncio
async def test_full_process_flow_completion(reducer, mock_db_pool, mock_db_connection):
    """Test full process flow for completion transition."""
    reducer._db_pool = mock_db_pool
    mock_db_pool.acquire = MagicMock(return_value=AsyncContextManager(mock_db_connection))

    # Setup mock to return PROCESSING state
    mock_db_connection.fetchrow.return_value = {
        "current_state": "PROCESSING",
        "previous_state": "RECEIVED",
        "transition_timestamp": datetime.now(UTC),
        "metadata": None,
        "lease_id": None,
        "lease_epoch": None,
        "lease_expires_at": None,
    }

    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.COMPLETE_INDEXING,
        correlation_id="corr_456",
        payload={},
    )

    result = await reducer.process(input_data)

    assert result.success is True
    assert result.previous_state == "PROCESSING"
    assert result.current_state == "INDEXED"
    # Should have event publish intent for completion
    event_intents = [i for i in result.intents if i.intent_type == EnumIntentType.EVENT_PUBLISH]
    assert len(event_intents) == 1


# =========================================================================
# Helper Classes
# =========================================================================


class AsyncContextManager:
    """Helper to create async context manager from mock."""

    def __init__(self, mock_obj):
        self.mock_obj = mock_obj

    async def __aenter__(self):
        return self.mock_obj

    async def __aexit__(self, *args):
        pass
