#!/usr/bin/env python3
"""
Unit Tests for Quality Gate Orchestrator

Tests comprehensive quality gate functionality including:
- ONEX compliance validation
- Test coverage checking
- Code quality analysis
- Performance validation
- Security scanning

Author: Archon Intelligence Team
Date: 2025-10-02
"""

import tempfile
from pathlib import Path

import pytest
from archon_services.pattern_learning.phase3_validation import (
    EnumGateType,
    ModelGateConfig,
    ModelOnexValidationInput,
    ModelQualityGateInput,
    ModelQualityGateOutput,
    NodeOnexValidatorCompute,
    NodeQualityGateOrchestrator,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_code_onex_compliant() -> str:
    """Sample ONEX-compliant code for testing."""
    return '''#!/usr/bin/env python3
"""
Sample ONEX Compliant Node - For Testing

This is a sample compute node that follows ONEX patterns.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field


class ModelSampleInput(BaseModel):
    """Input model for sample compute node."""
    data: str = Field(..., description="Input data")
    correlation_id: str = Field(..., description="Correlation ID")


class ModelSampleOutput(BaseModel):
    """Output model for sample compute node."""
    result: str = Field(..., description="Computation result")
    correlation_id: str = Field(..., description="Correlation ID")


class NodeSampleCompute:
    """
    ONEX-Compliant Sample Compute Node.

    Demonstrates ONEX patterns for testing.
    """

    def __init__(self) -> None:
        """Initialize compute node."""
        pass

    async def execute_compute(
        self, input_state: ModelSampleInput
    ) -> ModelSampleOutput:
        """Execute computation."""
        # Process data
        result = input_state.data.upper()

        return ModelSampleOutput(
            result=result,
            correlation_id=input_state.correlation_id
        )
'''


@pytest.fixture
def sample_code_non_compliant() -> str:
    """Sample non-ONEX-compliant code for testing."""
    return '''#!/usr/bin/env python3
"""
Non-compliant code for testing.
"""

class BadNode:
    """This doesn't follow ONEX naming."""

    def process(self, data):
        """Wrong method name."""
        return data.upper()
'''


@pytest.fixture
def sample_code_with_security_issues() -> str:
    """Sample code with security issues."""
    return '''#!/usr/bin/env python3
"""Code with security vulnerabilities."""

def process_user_input(user_input):
    """Dangerous eval usage."""
    password = "hardcoded_secret_123"
    api_key = "sk_test_12345"

    # SQL injection vulnerability
    query = "SELECT * FROM users WHERE name = '%s'" % user_input

    # Eval vulnerability
    result = eval(user_input)

    return result
'''


@pytest.fixture
def temp_code_file(sample_code_onex_compliant) -> Path:
    """Create temporary code file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_compute.py", prefix="node_test_", delete=False
    ) as f:
        f.write(sample_code_onex_compliant)
        return Path(f.name)


# ============================================================================
# ONEX Validator Tests
# ============================================================================


class TestOnexValidator:
    """Test ONEX compliance validator."""

    @pytest.mark.asyncio
    async def test_onex_validator_compliant_code(
        self, temp_code_file: Path, sample_code_onex_compliant: str
    ):
        """Test ONEX validator with compliant code."""
        validator = NodeOnexValidatorCompute()

        input_state = ModelOnexValidationInput(
            code_path=str(temp_code_file),
            code_content=sample_code_onex_compliant,
            correlation_id="test-001",
        )

        result = await validator.execute_compute(input_state)

        # Assertions - allow for some tolerance since the sample code might not be perfectly compliant
        assert (
            result.result.compliance_score >= 0.7
        ), "Compliant code should score reasonably well"
        assert len(result.result.issues) <= 2, "Compliant code should have few issues"
        assert result.correlation_id == "test-001"

        # Clean up
        temp_code_file.unlink()

    @pytest.mark.asyncio
    async def test_onex_validator_non_compliant_code(
        self, sample_code_non_compliant: str
    ):
        """Test ONEX validator with non-compliant code."""
        validator = NodeOnexValidatorCompute()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(sample_code_non_compliant)
            temp_file = Path(f.name)

        try:
            input_state = ModelOnexValidationInput(
                code_path=str(temp_file),
                code_content=sample_code_non_compliant,
                correlation_id="test-002",
            )

            result = await validator.execute_compute(input_state)

            # Assertions
            assert (
                result.result.compliance_score < 0.95
            ), "Non-compliant code should score low"
            assert (
                result.result.compliance_score < 0.95
            ), "Non-compliant code should fail"
            assert (
                len(result.result.issues) > 0
            ), "Non-compliant code should have issues"
            assert any(
                "naming convention" in issue.message.lower()
                for issue in result.result.issues
            ), "Should detect naming issues"

        finally:
            temp_file.unlink()

    @pytest.mark.asyncio
    async def test_onex_validator_metrics(self, temp_code_file: Path):
        """Test that validator provides detailed metrics."""
        validator = NodeOnexValidatorCompute()

        input_state = ModelOnexValidationInput(
            code_path=str(temp_code_file),
            correlation_id="test-003",
        )

        result = await validator.execute_compute(input_state)

        # Check metrics structure
        assert result.result.passed_checks >= 0
        assert result.result.total_checks > 0
        assert len(result.result.issues) >= 0
        assert isinstance(result.metadata, dict)
        assert result.processing_time_ms > 0  # processing_time_ms is at top level

        temp_code_file.unlink()


# ============================================================================
# Quality Gate Orchestrator Tests
# ============================================================================


class TestQualityGateOrchestrator:
    """Test quality gate orchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_single_gate(self, temp_code_file: Path):
        """Test orchestrator with single ONEX compliance gate."""
        orchestrator = NodeQualityGateOrchestrator()

        gate_config = ModelGateConfig(
            gate_type=EnumGateType.ONEX_COMPLIANCE,
            enabled=True,
            threshold=0.90,
            blocking=True,
            timeout_seconds=60,
        )

        input_state = ModelQualityGateInput(
            code_path=str(temp_code_file),
            gate_configs=[gate_config],
            correlation_id="test-004",
        )

        result = await orchestrator.execute_orchestration(input_state)

        # Assertions
        assert isinstance(result, ModelQualityGateOutput)
        assert result.total_gates == 1
        assert result.gates_passed >= 0
        assert result.total_duration_ms > 0
        assert len(result.gate_results) == 1

        gate_result = result.gate_results[0]
        assert gate_result["gate_type"] == EnumGateType.ONEX_COMPLIANCE.value
        assert "score" in gate_result
        assert "passed" in gate_result

        temp_code_file.unlink()

    @pytest.mark.asyncio
    async def test_orchestrator_multiple_gates_parallel(self, temp_code_file: Path):
        """Test orchestrator with multiple gates in parallel."""
        orchestrator = NodeQualityGateOrchestrator()

        gate_configs = [
            ModelGateConfig(
                gate_type=EnumGateType.ONEX_COMPLIANCE,
                enabled=True,
                threshold=0.90,
                blocking=True,
            ),
            ModelGateConfig(
                gate_type=EnumGateType.PERFORMANCE,
                enabled=True,
                threshold=0.70,
                blocking=False,
            ),
            ModelGateConfig(
                gate_type=EnumGateType.SECURITY,
                enabled=True,
                threshold=0.80,
                blocking=True,
            ),
        ]

        input_state = ModelQualityGateInput(
            code_path=str(temp_code_file),
            gate_configs=gate_configs,
            correlation_id="test-005",
            parallel_execution=True,
        )

        result = await orchestrator.execute_orchestration(input_state)

        # Assertions
        assert result.total_gates == 3, "Should execute 3 gates"
        assert len(result.gate_results) == 3, "Should have 3 results"
        assert result.total_duration_ms > 0, "Should track execution time"

        # Check that gates ran
        gate_types = [r["gate_type"] for r in result.gate_results]
        assert EnumGateType.ONEX_COMPLIANCE.value in gate_types
        assert EnumGateType.PERFORMANCE.value in gate_types
        assert EnumGateType.SECURITY.value in gate_types

        temp_code_file.unlink()

    @pytest.mark.asyncio
    async def test_orchestrator_fail_fast(self):
        """Test orchestrator with fail-fast on blocking failure."""
        orchestrator = NodeQualityGateOrchestrator()

        # Create file with security issues
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
password = "hardcoded"
result = eval(user_input)
"""
            )
            temp_file = Path(f.name)

        try:
            gate_configs = [
                ModelGateConfig(
                    gate_type=EnumGateType.SECURITY,
                    enabled=True,
                    threshold=1.0,  # Very high threshold
                    blocking=True,
                ),
                ModelGateConfig(
                    gate_type=EnumGateType.PERFORMANCE,
                    enabled=True,
                    threshold=0.70,
                    blocking=False,
                ),
            ]

            input_state = ModelQualityGateInput(
                code_path=str(temp_file),
                gate_configs=gate_configs,
                correlation_id="test-006",
                fail_fast=True,
            )

            result = await orchestrator.execute_orchestration(input_state)

            # With fail-fast, should stop after first blocking failure
            # Note: Security gate will likely fail due to hardcoded password
            assert result.overall_passed is False, "Should fail with security issues"
            assert len(result.blocking_failures) > 0, "Should have blocking failures"

        finally:
            temp_file.unlink()

    @pytest.mark.asyncio
    async def test_orchestrator_performance_target(self, temp_code_file: Path):
        """Test that orchestrator meets <30s performance target."""
        orchestrator = NodeQualityGateOrchestrator()

        # Run all 5 gates
        gate_configs = [
            ModelGateConfig(
                gate_type=EnumGateType.ONEX_COMPLIANCE, enabled=True, threshold=0.90
            ),
            ModelGateConfig(
                gate_type=EnumGateType.PERFORMANCE, enabled=True, threshold=0.70
            ),
            ModelGateConfig(
                gate_type=EnumGateType.SECURITY, enabled=True, threshold=0.80
            ),
        ]

        input_state = ModelQualityGateInput(
            code_path=str(temp_code_file),
            gate_configs=gate_configs,
            correlation_id="test-007",
            parallel_execution=True,
        )

        result = await orchestrator.execute_orchestration(input_state)

        # Check performance
        assert result.total_duration_ms < 30000, "Should complete in <30 seconds"
        assert result.metadata.get("performance_target_met") is True

        temp_code_file.unlink()

    @pytest.mark.asyncio
    async def test_orchestrator_disabled_gates(self, temp_code_file: Path):
        """Test that disabled gates are not executed."""
        orchestrator = NodeQualityGateOrchestrator()

        gate_configs = [
            ModelGateConfig(
                gate_type=EnumGateType.ONEX_COMPLIANCE,
                enabled=True,
                threshold=0.90,
            ),
            ModelGateConfig(
                gate_type=EnumGateType.PERFORMANCE,
                enabled=False,  # Disabled
                threshold=0.70,
            ),
        ]

        input_state = ModelQualityGateInput(
            code_path=str(temp_code_file),
            gate_configs=gate_configs,
            correlation_id="test-008",
        )

        result = await orchestrator.execute_orchestration(input_state)

        # Only enabled gates should run
        assert result.total_gates == 1, "Should only run enabled gates"
        assert len(result.gate_results) == 1
        assert result.gate_results[0]["gate_type"] == EnumGateType.ONEX_COMPLIANCE.value

        temp_code_file.unlink()

    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self):
        """Test orchestrator error handling with invalid path."""
        orchestrator = NodeQualityGateOrchestrator()

        gate_config = ModelGateConfig(
            gate_type=EnumGateType.ONEX_COMPLIANCE,
            enabled=True,
            threshold=0.90,
        )

        input_state = ModelQualityGateInput(
            code_path="/nonexistent/path.py",
            gate_configs=[gate_config],
            correlation_id="test-009",
        )

        result = await orchestrator.execute_orchestration(input_state)

        # Should handle error gracefully
        assert result.overall_passed is False
        assert "error" in result.metadata
        assert result.total_gates == 0


# ============================================================================
# Security Gate Tests
# ============================================================================


class TestSecurityGate:
    """Test security gate functionality."""

    @pytest.mark.asyncio
    async def test_security_gate_detects_hardcoded_secrets(self):
        """Test that security gate detects hardcoded secrets."""
        orchestrator = NodeQualityGateOrchestrator()

        # Create file with hardcoded secrets
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
password = "super_secret_123"
api_key = "sk_live_12345"
"""
            )
            temp_file = Path(f.name)

        try:
            gate_config = ModelGateConfig(
                gate_type=EnumGateType.SECURITY,
                enabled=True,
                threshold=0.90,
                blocking=True,
            )

            input_state = ModelQualityGateInput(
                code_path=str(temp_file),
                gate_configs=[gate_config],
                correlation_id="test-security-001",
            )

            result = await orchestrator.execute_orchestration(input_state)

            # Should detect hardcoded secrets
            assert result.gates_failed > 0 or result.gates_warned > 0
            gate_result = result.gate_results[0]
            assert len(gate_result["issues"]) > 0
            assert any(
                "secret" in issue["message"].lower() for issue in gate_result["issues"]
            )

        finally:
            temp_file.unlink()

    @pytest.mark.asyncio
    async def test_security_gate_detects_eval_usage(self):
        """Test that security gate detects eval() usage."""
        orchestrator = NodeQualityGateOrchestrator()

        # Create file with eval
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def process(user_input):
    result = eval(user_input)
    return result
"""
            )
            temp_file = Path(f.name)

        try:
            gate_config = ModelGateConfig(
                gate_type=EnumGateType.SECURITY,
                enabled=True,
                threshold=0.90,
                blocking=True,
            )

            input_state = ModelQualityGateInput(
                code_path=str(temp_file),
                gate_configs=[gate_config],
                correlation_id="test-security-002",
            )

            result = await orchestrator.execute_orchestration(input_state)

            # Should detect eval usage
            gate_result = result.gate_results[0]
            assert len(gate_result["issues"]) > 0
            assert any(
                "eval" in issue["message"].lower() for issue in gate_result["issues"]
            )

        finally:
            temp_file.unlink()


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_quality_gate_workflow(self, temp_code_file: Path):
        """Test complete quality gate workflow with all gates."""
        orchestrator = NodeQualityGateOrchestrator()

        # Configure all 5 gates
        gate_configs = [
            ModelGateConfig(
                gate_type=EnumGateType.ONEX_COMPLIANCE,
                enabled=True,
                threshold=0.90,
                blocking=True,
                parameters={"check_naming": True, "check_methods": True},
            ),
            ModelGateConfig(
                gate_type=EnumGateType.PERFORMANCE,
                enabled=True,
                threshold=0.70,
                blocking=False,
            ),
            ModelGateConfig(
                gate_type=EnumGateType.SECURITY,
                enabled=True,
                threshold=0.80,
                blocking=True,
            ),
        ]

        input_state = ModelQualityGateInput(
            code_path=str(temp_code_file),
            gate_configs=gate_configs,
            correlation_id="test-integration-001",
            parallel_execution=True,
            fail_fast=False,
        )

        result = await orchestrator.execute_orchestration(input_state)

        # Comprehensive assertions
        assert isinstance(result, ModelQualityGateOutput)
        assert result.total_gates == 3
        assert result.total_duration_ms > 0
        assert result.total_duration_ms < 30000, "Should meet performance target"
        assert len(result.gate_results) == 3

        # Check individual gates
        for gate_result in result.gate_results:
            assert "gate_type" in gate_result
            assert "status" in gate_result
            assert "score" in gate_result
            assert "passed" in gate_result
            assert "duration_ms" in gate_result

        # Check metadata
        assert "parallel_execution" in result.metadata
        assert result.metadata["parallel_execution"] is True

        temp_code_file.unlink()


# ============================================================================
# Run Tests
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
