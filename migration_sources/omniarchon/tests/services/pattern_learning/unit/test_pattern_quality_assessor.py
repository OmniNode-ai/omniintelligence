"""
Unit Tests: Pattern Quality Assessor Compute Node

Tests for NodePatternQualityAssessorCompute quality assessment logic.

Test Coverage:
- Quality assessment execution
- Complexity calculation
- Maintainability scoring
- Performance scoring
- Confidence calculation
- Success rate estimation
- Error handling

Created: 2025-10-28
ONEX Pattern: Test Suite for Compute Node
"""

# Import components to test
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "services" / "intelligence" / "src"))

from services.pattern_learning.phase1_foundation.quality import (
    ModelContractPatternQuality,
    ModelQualityMetrics,
    NodePatternQualityAssessorCompute,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def quality_assessor():
    """Create quality assessor instance."""
    return NodePatternQualityAssessorCompute()


@pytest.fixture
def simple_pattern_code():
    """Simple pattern code for testing."""
    return '''
async def execute_effect(self, contract):
    """Simple effect node."""
    async with self.pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM table")
    return ModelResult(success=True, data=result)
'''


@pytest.fixture
def complex_pattern_code():
    """Complex pattern code with high complexity."""
    return '''
async def execute_effect(self, contract):
    """Complex effect node with multiple decision points."""
    try:
        if contract.data:
            for item in contract.data:
                if item.type == "A":
                    result = await self._process_a(item)
                elif item.type == "B":
                    result = await self._process_b(item)
                else:
                    result = await self._process_default(item)

                if result.success:
                    await self._save(result)
                else:
                    await self._log_error(result)
        else:
            raise ValueError("No data")
    except Exception as e:
        logger.error(f"Failed: {e}")
        return ModelResult(success=False)
    return ModelResult(success=True)
'''


@pytest.fixture
def onex_compliant_code():
    """ONEX-compliant modern pattern code."""
    return '''
"""
ONEX Effect Node: Database Writer

Purpose: Write data to database
Node Type: Effect (External I/O)
"""

from omnibase.protocols import ProtocolBase
from omnibase_core.models import ModelONEXContainer

class NodeDatabaseWriterEffect(NodeBaseEffect):
    """Database writer effect node."""

    def __init__(self, registry: BaseOnexRegistry):
        """Initialize with registry injection."""
        super().__init__()
        self.registry = registry

    async def execute_effect(self, contract: ModelContractDatabaseWrite) -> ModelResult:
        """Write data to database."""
        async with self.transaction_manager.begin(contract.correlation_id):
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    result = await conn.execute(
                        "INSERT INTO patterns ...",
                        contract.data
                    )

        return ModelResult(success=True, data=result)
'''


# ==============================================================================
# Test Cases: Basic Quality Assessment
# ==============================================================================


@pytest.mark.asyncio
async def test_quality_assessment_success(quality_assessor, simple_pattern_code):
    """Test successful quality assessment."""
    contract = ModelContractPatternQuality(
        name="test_assessment",
        pattern_name="TestPattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
        description="Test pattern for quality assessment",
    )

    result = await quality_assessor.execute_compute(contract)

    assert result.success is True
    assert isinstance(result.data, ModelQualityMetrics)
    assert 0.0 <= result.data.quality_score <= 1.0
    assert 0.0 <= result.data.confidence_score <= 1.0
    assert result.data.complexity_score >= 1
    assert "correlation_id" in result.metadata
    assert result.metadata["duration_ms"] > 0


@pytest.mark.asyncio
async def test_quality_metrics_structure(quality_assessor, simple_pattern_code):
    """Test quality metrics structure and types."""
    contract = ModelContractPatternQuality(
        name="test_metrics",
        pattern_name="TestPattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Verify all required fields
    assert hasattr(metrics, "confidence_score")
    assert hasattr(metrics, "usage_count")
    assert hasattr(metrics, "success_rate")
    assert hasattr(metrics, "complexity_score")
    assert hasattr(metrics, "maintainability_score")
    assert hasattr(metrics, "performance_score")
    assert hasattr(metrics, "quality_score")
    assert hasattr(metrics, "onex_compliance_score")

    # Verify ranges
    assert 0.0 <= metrics.confidence_score <= 1.0
    assert metrics.usage_count == 0  # Initial value
    assert 0.0 <= metrics.success_rate <= 1.0
    assert metrics.complexity_score >= 1
    assert 0.0 <= metrics.maintainability_score <= 1.0
    assert 0.0 <= metrics.performance_score <= 1.0
    assert 0.0 <= metrics.quality_score <= 1.0
    assert 0.0 <= metrics.onex_compliance_score <= 1.0


# ==============================================================================
# Test Cases: Complexity Calculation
# ==============================================================================


@pytest.mark.asyncio
async def test_complexity_simple_code(quality_assessor, simple_pattern_code):
    """Test complexity calculation for simple code."""
    contract = ModelContractPatternQuality(
        name="test_complexity_simple",
        pattern_name="SimplePattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Simple code should have low complexity (typically 1-5)
    assert 1 <= metrics.complexity_score <= 10


@pytest.mark.asyncio
async def test_complexity_complex_code(quality_assessor, complex_pattern_code):
    """Test complexity calculation for complex code."""
    contract = ModelContractPatternQuality(
        name="test_complexity_complex",
        pattern_name="ComplexPattern",
        pattern_type="code",
        language="python",
        pattern_code=complex_pattern_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Complex code should have higher complexity
    assert metrics.complexity_score > 5


# ==============================================================================
# Test Cases: ONEX Compliance
# ==============================================================================


@pytest.mark.asyncio
async def test_onex_compliance_modern_code(quality_assessor, onex_compliant_code):
    """Test ONEX compliance scoring for modern ONEX code."""
    contract = ModelContractPatternQuality(
        name="test_onex_compliance",
        pattern_name="ONEXPattern",
        pattern_type="code",
        language="python",
        pattern_code=onex_compliant_code,
        description="Modern ONEX-compliant pattern",
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Modern ONEX code should have high compliance score
    assert metrics.onex_compliance_score >= 0.6


@pytest.mark.asyncio
async def test_onex_compliance_legacy_code(quality_assessor):
    """Test ONEX compliance scoring for legacy code."""
    legacy_code = """
from typing import Any

def main():
    db = Database()  # Direct instantiation
    result = db.query("SELECT * FROM table")
    return result
"""

    contract = ModelContractPatternQuality(
        name="test_legacy",
        pattern_name="LegacyPattern",
        pattern_type="code",
        language="python",
        pattern_code=legacy_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Legacy code should have low compliance score
    assert metrics.onex_compliance_score < 0.5


# ==============================================================================
# Test Cases: Performance Scoring
# ==============================================================================


@pytest.mark.asyncio
async def test_performance_async_code(quality_assessor):
    """Test performance scoring for async code."""
    async_code = '''
async def execute_effect(self, contract):
    """Async effect node."""
    async with self.pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM table")
    return ModelResult(success=True, data=result)
'''

    contract = ModelContractPatternQuality(
        name="test_performance_async",
        pattern_name="AsyncPattern",
        pattern_type="code",
        language="python",
        pattern_code=async_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Async code should score well on performance
    assert metrics.performance_score >= 0.5


@pytest.mark.asyncio
async def test_performance_sync_code(quality_assessor):
    """Test performance scoring for synchronous code."""
    sync_code = '''
def execute_operation(self, data):
    """Synchronous operation."""
    result = self.database.query("SELECT * FROM table")
    return result
'''

    contract = ModelContractPatternQuality(
        name="test_performance_sync",
        pattern_name="SyncPattern",
        pattern_type="code",
        language="python",
        pattern_code=sync_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Sync code should score lower on performance
    assert metrics.performance_score < 0.8


# ==============================================================================
# Test Cases: Confidence Scoring
# ==============================================================================


@pytest.mark.asyncio
async def test_confidence_with_description(quality_assessor, simple_pattern_code):
    """Test confidence scoring with description provided."""
    contract = ModelContractPatternQuality(
        name="test_confidence_with_desc",
        pattern_name="DocumentedPattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
        description="This is a well-documented pattern with comprehensive description",
    )

    result = await quality_assessor.execute_compute(contract)
    metrics_with_desc = result.data

    # Test without description
    contract_no_desc = ModelContractPatternQuality(
        name="test_confidence_no_desc",
        pattern_name="UndocumentedPattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
    )

    result_no_desc = await quality_assessor.execute_compute(contract_no_desc)
    metrics_no_desc = result_no_desc.data

    # Confidence should be higher with description
    assert metrics_with_desc.confidence_score >= metrics_no_desc.confidence_score


@pytest.mark.asyncio
async def test_confidence_with_todos(quality_assessor):
    """Test confidence scoring for code with TODOs."""
    code_with_todos = '''
async def execute_effect(self, contract):
    """Effect node with TODOs."""
    # TODO: Implement error handling
    # FIXME: This is broken
    result = await self.process(contract)
    return ModelResult(success=True)
'''

    contract = ModelContractPatternQuality(
        name="test_confidence_todos",
        pattern_name="TodoPattern",
        pattern_type="code",
        language="python",
        pattern_code=code_with_todos,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Confidence should be lower with TODOs
    assert metrics.confidence_score < 0.7


# ==============================================================================
# Test Cases: Error Handling
# ==============================================================================


@pytest.mark.asyncio
async def test_assessment_invalid_python(quality_assessor):
    """Test quality assessment with invalid Python code."""
    invalid_code = """
def broken_function(
    # Missing closing parenthesis and body
"""

    contract = ModelContractPatternQuality(
        name="test_invalid_code",
        pattern_name="BrokenPattern",
        pattern_type="code",
        language="python",
        pattern_code=invalid_code,
    )

    result = await quality_assessor.execute_compute(contract)

    # Should still return a result (with penalties for invalid syntax)
    assert result.success is True
    metrics = result.data
    assert metrics.complexity_score >= 1  # Should have fallback complexity


# ==============================================================================
# Test Cases: Metadata
# ==============================================================================


@pytest.mark.asyncio
async def test_metadata_content(quality_assessor, simple_pattern_code):
    """Test metadata content in quality metrics."""
    contract = ModelContractPatternQuality(
        name="test_metadata",
        pattern_name="TestPattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
    )

    result = await quality_assessor.execute_compute(contract)
    metrics = result.data

    # Verify metadata structure
    assert "relevance_score" in metrics.metadata
    assert "architectural_era" in metrics.metadata
    assert "legacy_indicators" in metrics.metadata
    assert "assessment_timestamp" in metrics.metadata


# ==============================================================================
# Test Cases: Performance
# ==============================================================================


@pytest.mark.asyncio
async def test_assessment_performance(quality_assessor, simple_pattern_code):
    """Test that assessment completes within performance target."""
    contract = ModelContractPatternQuality(
        name="test_performance",
        pattern_name="TestPattern",
        pattern_type="code",
        language="python",
        pattern_code=simple_pattern_code,
    )

    result = await quality_assessor.execute_compute(contract)

    # Performance target: <500ms
    assert result.metadata["duration_ms"] < 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
