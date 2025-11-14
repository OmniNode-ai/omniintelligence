"""
Unit tests for shared models.

Tests Pydantic model validation and serialization.
"""

import pytest
from datetime import datetime

from src.omniintelligence.shared.models import (
    ModelIntent,
    ModelReducerInput,
    ModelReducerOutput,
    ModelOrchestratorInput,
    ModelOrchestratorOutput,
    ModelFSMState,
)
from src.omniintelligence.shared.enums import (
    EnumIntentType,
    EnumFSMType,
    EnumFSMAction,
)


def test_model_intent_creation():
    """Test ModelIntent creation and validation."""
    intent = ModelIntent(
        intent_type=EnumIntentType.WORKFLOW_TRIGGER,
        target="intelligence_orchestrator",
        payload={"test": "data"},
        correlation_id="corr_123",
    )

    assert intent.intent_type == EnumIntentType.WORKFLOW_TRIGGER
    assert intent.target == "intelligence_orchestrator"
    assert intent.payload["test"] == "data"
    assert intent.correlation_id == "corr_123"
    assert isinstance(intent.timestamp, datetime)


def test_reducer_input_validation():
    """Test ModelReducerInput validation."""
    input_data = ModelReducerInput(
        fsm_type=EnumFSMType.INGESTION,
        entity_id="doc_123",
        action=EnumFSMAction.START_PROCESSING,
        correlation_id="corr_456",
    )

    assert input_data.fsm_type == EnumFSMType.INGESTION
    assert input_data.entity_id == "doc_123"
    assert input_data.action == EnumFSMAction.START_PROCESSING
    assert input_data.payload is None


def test_reducer_output_with_intents():
    """Test ModelReducerOutput with intents."""
    intent = ModelIntent(
        intent_type=EnumIntentType.EVENT_PUBLISH,
        target="kafka_event_effect",
        payload={},
        correlation_id="corr_789",
    )

    output = ModelReducerOutput(
        success=True,
        previous_state="RECEIVED",
        current_state="PROCESSING",
        intents=[intent],
    )

    assert output.success is True
    assert output.previous_state == "RECEIVED"
    assert output.current_state == "PROCESSING"
    assert len(output.intents) == 1
    assert output.intents[0].intent_type == EnumIntentType.EVENT_PUBLISH


def test_fsm_state_model():
    """Test ModelFSMState creation."""
    state = ModelFSMState(
        fsm_type=EnumFSMType.PATTERN_LEARNING,
        entity_id="pattern_123",
        current_state="FOUNDATION",
        previous_state=None,
        transition_timestamp=datetime.utcnow(),
    )

    assert state.fsm_type == EnumFSMType.PATTERN_LEARNING
    assert state.entity_id == "pattern_123"
    assert state.current_state == "FOUNDATION"
    assert state.previous_state is None


def test_model_serialization():
    """Test model JSON serialization."""
    intent = ModelIntent(
        intent_type=EnumIntentType.CACHE_INVALIDATE,
        target="cache_service",
        payload={"key": "test"},
        correlation_id="corr_101",
    )

    # Serialize to JSON
    json_str = intent.model_dump_json()
    assert isinstance(json_str, str)

    # Deserialize from JSON
    intent_copy = ModelIntent.model_validate_json(json_str)
    assert intent_copy.intent_type == intent.intent_type
    assert intent_copy.target == intent.target
    assert intent_copy.correlation_id == intent.correlation_id
