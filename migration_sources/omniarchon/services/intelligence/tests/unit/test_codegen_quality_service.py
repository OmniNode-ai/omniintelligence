"""
Unit tests for Codegen Quality Service

Tests validation logic, issue classification, and aggregate reporting.
"""

import sys
from pathlib import Path

import pytest
from archon_services.quality.codegen_quality_service import CodegenQualityService
from archon_services.quality.onex_quality_scorer import ONEXQualityScorer

# Add src directory to path for imports


class TestCodegenQualityService:
    """Test suite for Codegen Quality Service."""

    @pytest.fixture
    def service(self):
        """Create quality service instance."""
        return CodegenQualityService(quality_scorer=ONEXQualityScorer())

    @pytest.mark.asyncio
    async def test_validate_good_code(self, service):
        """Test validation of high-quality code."""
        good_code = """
from omnibase.protocols import ProtocolToolBase
from omnibase.logging import emit_log_event

class ModelUserService(BaseModel):
    user_id: str
    email: str

class NodeUserEffect(NodeBase):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)
        self.container: ModelONEXContainer = registry.get_container()

    @standard_error_handling
    async def process(self):
        emit_log_event("Processing user effect")
        try:
            result = await self.execute()
        except OnexError as e:
            raise CoreErrorCode.EXECUTION_FAILED
        """

        result = await service.validate_generated_code(
            code_content=good_code, node_type="effect"
        )

        assert result["is_valid"] is True
        assert result["quality_score"] >= 0.7
        assert result["onex_compliance_score"] >= 0.6
        assert len(result["violations"]) == 0
        assert "details" in result

    @pytest.mark.asyncio
    async def test_validate_bad_code(self, service):
        """Test validation of low-quality code."""
        bad_code = """
from typing import Any

class myservice:  # Non-CamelCase
    def process(self, data: Any):  # Any type (forbidden)
        import os  # Direct import
        return data
        """

        result = await service.validate_generated_code(
            code_content=bad_code, node_type="effect"
        )

        assert result["is_valid"] is False
        assert result["quality_score"] < 0.7
        assert len(result["violations"]) > 0
        assert any("CRITICAL" in v for v in result["violations"])

    @pytest.mark.asyncio
    async def test_node_type_suggestions(self, service):
        """Test that suggestions are tailored to node type."""
        code = "class Service: pass"

        result_effect = await service.validate_generated_code(
            code_content=code, node_type="effect"
        )

        result_compute = await service.validate_generated_code(
            code_content=code, node_type="compute"
        )

        # Both should have suggestions
        assert len(result_effect["suggestions"]) > 0
        assert len(result_compute["suggestions"]) > 0

        # Check node-specific suggestions exist
        effect_suggestions = " ".join(result_effect["suggestions"])
        compute_suggestions = " ".join(result_compute["suggestions"])

        assert "EFFECT" in effect_suggestions or "effect" in effect_suggestions.lower()
        assert (
            "COMPUTE" in compute_suggestions or "compute" in compute_suggestions.lower()
        )

    @pytest.mark.asyncio
    async def test_validation_with_contracts(self, service):
        """Test validation with contract definitions."""
        code = "class NodeService(NodeBase): pass"

        contracts = [
            {"name": "ServiceContract", "version": "1.0.0"},
        ]

        result = await service.validate_generated_code(
            code_content=code,
            node_type="effect",
            contracts=contracts,
        )

        assert result is not None
        assert "quality_score" in result
        # Contracts are stored in details for future use
        assert "details" in result

    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        """Test error handling in validation."""
        # Pass None as code content (should handle gracefully)
        result = await service.validate_generated_code(
            code_content=None,  # Invalid input
            node_type="effect",
        )

        # Should return error result, not crash
        assert result is not None
        assert result["is_valid"] is False
        assert len(result["violations"]) > 0

    @pytest.mark.asyncio
    async def test_validation_report_aggregate(self, service):
        """Test aggregate validation reporting."""
        validation_results = [
            {
                "is_valid": True,
                "quality_score": 0.8,
                "onex_compliance_score": 0.9,
                "violations": [],
                "warnings": ["Minor issue"],
            },
            {
                "is_valid": False,
                "quality_score": 0.5,
                "onex_compliance_score": 0.4,
                "violations": ["Critical issue"],
                "warnings": [],
            },
            {
                "is_valid": True,
                "quality_score": 0.85,
                "onex_compliance_score": 0.85,
                "violations": [],
                "warnings": [],
            },
        ]

        report = await service.get_validation_report(validation_results)

        assert report["total_validations"] == 3
        assert report["success_rate"] == 2 / 3  # 2 valid out of 3
        assert 0.7 <= report["average_quality_score"] <= 0.75
        assert report["total_violations"] == 1
        assert report["total_warnings"] == 1

    @pytest.mark.asyncio
    async def test_empty_validation_report(self, service):
        """Test validation report with no results."""
        report = await service.get_validation_report([])

        assert report["total_validations"] == 0
        assert report["success_rate"] == 0.0
        assert report["average_quality_score"] == 0.0

    @pytest.mark.asyncio
    async def test_violation_classification(self, service):
        """Test that violations are classified correctly."""
        code_with_forbidden = """
from typing import Any

def process(data: Any):  # Forbidden Any type
    return data
        """

        result = await service.validate_generated_code(
            code_content=code_with_forbidden, node_type="effect"
        )

        # Should have critical violations
        assert len(result["violations"]) > 0
        assert any("CRITICAL" in v for v in result["violations"])
        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_warning_classification(self, service):
        """Test that warnings are classified correctly."""
        code_with_warnings = """
class myService:  # Non-CamelCase (warning, not critical)
    def process(self):
        import os  # Direct import (warning)
        return True
        """

        result = await service.validate_generated_code(
            code_content=code_with_warnings, node_type="effect"
        )

        # Should have warnings but might still pass basic validation
        assert len(result["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_architectural_era_in_result(self, service):
        """Test that architectural era is included in result."""
        modern_code = """
from omnibase.protocols import ProtocolToolBase
from omnibase.logging import emit_log_event

class ModelService(BaseModel):
    name: str

class NodeService(NodeBase):
    def __init__(self, registry: BaseOnexRegistry):
        super().__init__(registry)
        self.container: ModelONEXContainer = registry.get_container()

    @standard_error_handling
    async def process(self):
        emit_log_event("Processing service")
        """

        result = await service.validate_generated_code(
            code_content=modern_code, node_type="effect"
        )

        assert "architectural_era" in result
        assert result["architectural_era"] == "modern_onex"

    @pytest.mark.asyncio
    async def test_validation_details_timestamp(self, service):
        """Test that validation includes timestamp in details."""
        code = "class Service: pass"

        result = await service.validate_generated_code(
            code_content=code, node_type="effect"
        )

        assert "details" in result
        assert "validation_timestamp" in result["details"]
        assert "node_type" in result["details"]
        assert result["details"]["node_type"] == "effect"


@pytest.mark.asyncio
class TestCodegenQualityServicePerformance:
    """Performance tests for Codegen Quality Service."""

    @pytest.fixture
    def service(self):
        """Create quality service instance."""
        return CodegenQualityService()

    async def test_validation_performance(self, service):
        """Test that validation completes within performance target."""
        import time

        code = "class NodeService(NodeBase): pass\n" * 50

        start = time.time()
        result = await service.validate_generated_code(
            code_content=code, node_type="effect"
        )
        elapsed = time.time() - start

        assert elapsed < 0.5, "Validation should complete in < 500ms"
        assert result is not None

    async def test_batch_validation_performance(self, service):
        """Test batch validation performance."""
        import asyncio
        import time

        code_samples = [f"class Service{i}(NodeBase): pass" for i in range(10)]

        start = time.time()
        tasks = [
            service.validate_generated_code(code, "effect") for code in code_samples
        ]
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        assert len(results) == 10
        assert elapsed < 2.0, "10 validations should complete in < 2s"
        assert all(r is not None for r in results)
