"""
Integration tests for Intelligence Orchestrator.

Tests workflow routing and execution.
"""

import pytest
import asyncio

from src.omniintelligence.shared.enums import EnumOperationType
from src.omniintelligence.shared.models import (
    ModelOrchestratorInput,
    ModelOrchestratorConfig,
)
from src.omniintelligence.nodes.intelligence_orchestrator.v1_0_0.orchestrator import (
    IntelligenceOrchestrator,
)


@pytest.fixture
async def orchestrator():
    """Create orchestrator instance for testing."""
    config = ModelOrchestratorConfig(
        max_concurrent_workflows=10,
        workflow_timeout_seconds=300,
        enable_caching=True,
        cache_ttl_seconds=300,
    )
    orchestrator = IntelligenceOrchestrator(config)
    await orchestrator.initialize()
    yield orchestrator


@pytest.mark.asyncio
async def test_workflow_initialization(orchestrator):
    """Test workflow initialization."""
    # Check all workflows are registered
    assert EnumOperationType.DOCUMENT_INGESTION in orchestrator._workflows
    assert EnumOperationType.PATTERN_LEARNING in orchestrator._workflows
    assert EnumOperationType.QUALITY_ASSESSMENT in orchestrator._workflows
    assert EnumOperationType.SEMANTIC_ANALYSIS in orchestrator._workflows
    assert EnumOperationType.RELATIONSHIP_DETECTION in orchestrator._workflows


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
        correlation_id="corr_456",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    assert "workflow_type" in result.results
    assert result.results["workflow_type"] == "document_ingestion"


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
        correlation_id="corr_789",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    assert "workflow_type" in result.results
    assert result.results["workflow_type"] == "pattern_learning"


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
        correlation_id="corr_101",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id is not None
    assert "overall_score" in result.results
    assert 0.0 <= result.results["overall_score"] <= 1.0


@pytest.mark.asyncio
async def test_unknown_operation_type(orchestrator):
    """Test handling of unknown operation type."""
    input_data = ModelOrchestratorInput(
        operation_type="UNKNOWN_OPERATION",  # Invalid type
        entity_id="test_123",
        payload={},
        correlation_id="corr_202",
    )

    result = await orchestrator.process(input_data)

    assert result.success is False
    assert len(result.errors) > 0
    assert "Unknown operation type" in result.errors[0]


@pytest.mark.asyncio
async def test_workflow_tracking(orchestrator):
    """Test workflow execution tracking."""
    input_data = ModelOrchestratorInput(
        operation_type=EnumOperationType.SEMANTIC_ANALYSIS,
        entity_id="code_123",
        payload={"code_snippet": "x = 1"},
        correlation_id="corr_303",
    )

    result = await orchestrator.process(input_data)

    assert result.success is True
    assert result.workflow_id in orchestrator._active_workflows
    assert orchestrator._active_workflows[result.workflow_id]["status"] == "COMPLETED"
