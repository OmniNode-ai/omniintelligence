"""
Unit tests for shared enums.

Tests enum definitions and values.
"""

from omniintelligence._legacy.enums import (
    EnumEntityType,
    EnumFSMType,
    EnumIngestionState,
    EnumIntentType,
    EnumOperationType,
    EnumPatternLearningState,
    EnumQualityAssessmentState,
    EnumRelationshipType,
)


def test_fsm_type_enum():
    """Test EnumFSMType enum values."""
    assert EnumFSMType.INGESTION.value == "INGESTION"
    assert EnumFSMType.PATTERN_LEARNING.value == "PATTERN_LEARNING"
    assert EnumFSMType.QUALITY_ASSESSMENT.value == "QUALITY_ASSESSMENT"


def test_operation_type_enum():
    """Test EnumOperationType enum values."""
    assert EnumOperationType.DOCUMENT_INGESTION.value == "DOCUMENT_INGESTION"
    assert EnumOperationType.PATTERN_LEARNING.value == "PATTERN_LEARNING"
    assert EnumOperationType.QUALITY_ASSESSMENT.value == "QUALITY_ASSESSMENT"
    assert EnumOperationType.SEMANTIC_ANALYSIS.value == "SEMANTIC_ANALYSIS"
    assert EnumOperationType.RELATIONSHIP_DETECTION.value == "RELATIONSHIP_DETECTION"


def test_intent_type_enum():
    """Test EnumIntentType enum values."""
    assert EnumIntentType.STATE_UPDATE.value == "STATE_UPDATE"
    assert EnumIntentType.WORKFLOW_TRIGGER.value == "WORKFLOW_TRIGGER"
    assert EnumIntentType.EVENT_PUBLISH.value == "EVENT_PUBLISH"
    assert EnumIntentType.CACHE_INVALIDATE.value == "CACHE_INVALIDATE"


def test_ingestion_state_enum():
    """Test EnumIngestionState enum values."""
    states = [
        EnumIngestionState.RECEIVED,
        EnumIngestionState.PROCESSING,
        EnumIngestionState.INDEXED,
        EnumIngestionState.FAILED,
    ]
    assert len(states) == 4
    assert EnumIngestionState.RECEIVED.value == "RECEIVED"


def test_pattern_learning_state_enum():
    """Test EnumPatternLearningState enum values."""
    states = [
        EnumPatternLearningState.FOUNDATION,
        EnumPatternLearningState.MATCHING,
        EnumPatternLearningState.VALIDATION,
        EnumPatternLearningState.TRACEABILITY,
        EnumPatternLearningState.COMPLETED,
        EnumPatternLearningState.FAILED,
    ]
    assert len(states) == 6


def test_quality_assessment_state_enum():
    """Test EnumQualityAssessmentState enum values."""
    states = [
        EnumQualityAssessmentState.RAW,
        EnumQualityAssessmentState.ASSESSING,
        EnumQualityAssessmentState.SCORED,
        EnumQualityAssessmentState.STORED,
        EnumQualityAssessmentState.FAILED,
    ]
    assert len(states) == 5


def test_entity_type_enum():
    """Test EnumEntityType has common entity types."""
    assert EnumEntityType.DOCUMENT.value == "DOCUMENT"
    assert EnumEntityType.CLASS.value == "CLASS"
    assert EnumEntityType.FUNCTION.value == "FUNCTION"
    assert EnumEntityType.MODULE.value == "MODULE"


def test_relationship_type_enum():
    """Test EnumRelationshipType has common relationships."""
    assert EnumRelationshipType.CONTAINS.value == "CONTAINS"
    assert EnumRelationshipType.IMPORTS.value == "IMPORTS"
    assert EnumRelationshipType.CALLS.value == "CALLS"
    assert EnumRelationshipType.EXTENDS.value == "EXTENDS"
