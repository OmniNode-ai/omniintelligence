"""
Integration tests for Intelligence Reducer.

Tests FSM state transitions, lease management, and intent emission.
"""

import pytest

from omniintelligence.enums import (
    EnumFSMAction,
    EnumFSMType,
)
from omniintelligence.models import (
    ModelReducerConfig,
)
from src.omniintelligence.nodes.intelligence_reducer.v1_0_0.reducer import (
    IntelligenceReducer,
)


@pytest.fixture
def reducer():
    """Create reducer instance for testing."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=True,
        lease_timeout_seconds=300,
        max_retry_attempts=3,
    )
    return IntelligenceReducer(config)


@pytest.mark.asyncio
async def test_ingestion_fsm_transition():
    """Test ingestion FSM state transition using contract-based validation."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=False,
    )
    reducer = IntelligenceReducer(config)

    # Get the FSM contract for ingestion
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    # Test transition validation using contract-based method
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "RECEIVED",  # Current state as string
        EnumFSMAction.START_PROCESSING,
    )

    assert valid is True
    assert target == "PROCESSING"


@pytest.mark.asyncio
async def test_invalid_transition():
    """Test invalid FSM transition is rejected."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=False,
    )
    reducer = IntelligenceReducer(config)

    # Get the FSM contract for ingestion
    fsm_contract = reducer._get_fsm_contract(EnumFSMType.INGESTION)

    # Test invalid transition - can't start processing from INDEXED state
    valid, target = reducer._validate_transition_from_contract(
        fsm_contract,
        "INDEXED",  # Not a valid state to start processing from
        EnumFSMAction.START_PROCESSING,
    )

    assert valid is False
    assert target is None


@pytest.mark.asyncio
async def test_intent_emission():
    """Test intent emission on state transitions."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=False,
    )
    reducer = IntelligenceReducer(config)

    # Test intent generation for PROCESSING state (using string states)
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        old_state="RECEIVED",
        new_state="PROCESSING",
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )

    assert len(intents) > 0
    # Should emit workflow trigger intent
    workflow_intents = [i for i in intents if i.intent_type.value == "WORKFLOW_TRIGGER"]
    assert len(workflow_intents) > 0


def test_fsm_contracts_loaded():
    """Test FSM contracts are properly loaded from YAML files."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
    )
    reducer = IntelligenceReducer(config)

    # Check all FSM types have contracts loaded
    assert EnumFSMType.INGESTION in reducer._fsm_contracts
    assert EnumFSMType.PATTERN_LEARNING in reducer._fsm_contracts
    assert EnumFSMType.QUALITY_ASSESSMENT in reducer._fsm_contracts

    # Check ingestion FSM contract has proper structure
    ingestion_contract = reducer._fsm_contracts[EnumFSMType.INGESTION]
    assert ingestion_contract.initial_state == "RECEIVED"
    assert len(ingestion_contract.states) > 0
    assert len(ingestion_contract.transitions) > 0

    # Verify expected states exist in contract
    state_names = [s.state_name for s in ingestion_contract.states]
    assert "RECEIVED" in state_names
    assert "PROCESSING" in state_names
    assert "INDEXED" in state_names
    assert "FAILED" in state_names
