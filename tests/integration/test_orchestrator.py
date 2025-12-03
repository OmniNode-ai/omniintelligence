"""
Integration tests for Intelligence Orchestrator.

Tests workflow routing and execution.
"""

import pytest

from omnibase_core.models.container.model_onex_container import ModelONEXContainer

from omniintelligence.enums import EnumOperationType
from omniintelligence.models import ModelOrchestratorInput
from src.omniintelligence.nodes.intelligence_orchestrator.v1_0_0.orchestrator import (
    IntelligenceOrchestrator,
)


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for testing."""
    # Create a minimal container for testing
    container = ModelONEXContainer()
    return IntelligenceOrchestrator(container)


@pytest.mark.asyncio
async def test_workflow_definition_loading(orchestrator):
    """Test workflow definitions can be loaded for all operation types."""
    # Check all operation types can load their workflow definitions
    for operation_type in [
        EnumOperationType.DOCUMENT_INGESTION,
        EnumOperationType.PATTERN_LEARNING,
        EnumOperationType.QUALITY_ASSESSMENT,
        EnumOperationType.SEMANTIC_ANALYSIS,
        EnumOperationType.RELATIONSHIP_DETECTION,
    ]:
        workflow_def = orchestrator._load_workflow_definition(operation_type)
        assert workflow_def is not None
        assert workflow_def.workflow_metadata is not None
        # Check workflow is cached
        assert operation_type in orchestrator._workflow_cache


@pytest.mark.asyncio
async def test_document_ingestion_workflow(orchestrator):
    """Test document ingestion workflow execution."""
    input_data = ModelOrchestratorInput(
        operation_type=EnumOperationType.DOCUMENT_INGESTION,
        entity_id="doc_123",
        payload={
            "file_path": "test.py",
            "content": "def main(): pass",
            "metadata": {"language": "python"},
        },
        correlation_id="550e8400-e29b-41d4-a716-446655440001",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    assert "operation_type" in result.results
    assert result.results["operation_type"] == EnumOperationType.DOCUMENT_INGESTION.value
    assert result.results["entity_id"] == "doc_123"


@pytest.mark.asyncio
async def test_pattern_learning_workflow(orchestrator):
    """Test pattern learning workflow execution."""
    input_data = ModelOrchestratorInput(
        operation_type=EnumOperationType.PATTERN_LEARNING,
        entity_id="pattern_123",
        payload={
            "code_snippet": "def foo(): pass",
            "project_name": "test_project",
        },
        correlation_id="550e8400-e29b-41d4-a716-446655440002",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    assert "operation_type" in result.results
    assert result.results["operation_type"] == EnumOperationType.PATTERN_LEARNING.value
    assert result.results["entity_id"] == "pattern_123"


@pytest.mark.asyncio
async def test_quality_assessment_workflow(orchestrator):
    """Test quality assessment workflow execution."""
    input_data = ModelOrchestratorInput(
        operation_type=EnumOperationType.QUALITY_ASSESSMENT,
        entity_id="file_123",
        payload={
            "file_path": "test.py",
            "content": "def main(): pass",
            "language": "python",
            "project_name": "test_project",
        },
        correlation_id="550e8400-e29b-41d4-a716-446655440003",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    assert "operation_type" in result.results
    assert result.results["operation_type"] == EnumOperationType.QUALITY_ASSESSMENT.value
    assert result.results["entity_id"] == "file_123"


@pytest.mark.asyncio
async def test_unknown_operation_type(orchestrator):
    """Test handling of unknown operation type.

    The ModelOrchestratorInput enforces EnumOperationType validation at model creation.
    Invalid operation types raise a Pydantic ValidationError before reaching the orchestrator.
    """
    import pydantic

    # Pydantic validation should reject invalid enum values at model creation time
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ModelOrchestratorInput(
            operation_type="UNKNOWN_OPERATION",  # Invalid type
            entity_id="test_123",
            payload={},
            correlation_id="550e8400-e29b-41d4-a716-446655440004",
        )

    # Verify the error is about the operation_type field
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("operation_type",)
    assert error["type"] == "enum"


@pytest.mark.asyncio
async def test_workflow_result_contains_metadata(orchestrator):
    """Test workflow execution returns proper metadata."""
    input_data = ModelOrchestratorInput(
        operation_type=EnumOperationType.SEMANTIC_ANALYSIS,
        entity_id="code_123",
        payload={"code_snippet": "x = 1"},
        correlation_id="550e8400-e29b-41d4-a716-446655440005",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    # Check result metadata contains operation info
    assert "operation_type" in result.results
    assert result.results["operation_type"] == EnumOperationType.SEMANTIC_ANALYSIS.value
    assert "entity_id" in result.results
    assert result.results["entity_id"] == "code_123"
