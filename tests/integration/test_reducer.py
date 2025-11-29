"""
Integration tests for Intelligence Reducer.

Tests FSM state transitions, lease management, and intent emission.
"""

import pytest
import asyncio
from datetime import datetime

from src.omniintelligence.shared.enums import (
    EnumFSMType,
    EnumFSMAction,
    EnumIngestionState,
)
from src.omniintelligence.shared.models import (
    ModelReducerInput,
    ModelReducerConfig,
)
from src.omniintelligence.nodes.intelligence_reducer.v1_0_0.reducer import (
    IntelligenceReducer,
)


@pytest.fixture
async def reducer():
    """Create reducer instance for testing."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=True,
        lease_timeout_seconds=300,
        max_retry_attempts=3,
    )
    reducer = IntelligenceReducer(config)
    # Note: In real tests, would initialize with test database
    # await reducer.initialize()
    yield reducer
    # await reducer.shutdown()


@pytest.mark.asyncio
async def test_ingestion_fsm_transition():
    """Test ingestion FSM state transition."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=False,
    )
    reducer = IntelligenceReducer(config)

    # Test transition validation
    valid, target = reducer._validate_transition(
        EnumFSMType.INGESTION,
        EnumIngestionState.RECEIVED,
        EnumFSMAction.START_PROCESSING,
    )

    assert valid is True
    assert target == EnumIngestionState.PROCESSING


@pytest.mark.asyncio
async def test_invalid_transition():
    """Test invalid FSM transition is rejected."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
        enable_lease_management=False,
    )
    reducer = IntelligenceReducer(config)

    # Test invalid transition
    valid, target = reducer._validate_transition(
        EnumFSMType.INGESTION,
        EnumIngestionState.INDEXED,  # Final state
        EnumFSMAction.START_PROCESSING,  # Can't start processing from indexed
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

    # Test intent generation for PROCESSING state
    intents = reducer._generate_intents(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        old_state=EnumIngestionState.RECEIVED,
        new_state=EnumIngestionState.PROCESSING,
        correlation_id="corr_456",
        payload={"file_path": "test.py"},
    )

    assert len(intents) > 0
    # Should emit workflow trigger intent
    workflow_intents = [i for i in intents if i.intent_type.value == "WORKFLOW_TRIGGER"]
    assert len(workflow_intents) > 0


def test_fsm_definitions():
    """Test FSM definitions are properly initialized."""
    config = ModelReducerConfig(
        database_url="postgresql://postgres:test@localhost:5432/test_db",
    )
    reducer = IntelligenceReducer(config)

    # Check all FSM types have definitions
    assert EnumFSMType.INGESTION in reducer._fsm_transitions
    assert EnumFSMType.PATTERN_LEARNING in reducer._fsm_transitions
    assert EnumFSMType.QUALITY_ASSESSMENT in reducer._fsm_transitions

    # Check ingestion FSM has all states
    ingestion_fsm = reducer._fsm_transitions[EnumFSMType.INGESTION]
    assert EnumIngestionState.RECEIVED in ingestion_fsm
    assert EnumIngestionState.PROCESSING in ingestion_fsm
    assert EnumIngestionState.INDEXED in ingestion_fsm
    assert EnumIngestionState.FAILED in ingestion_fsm
