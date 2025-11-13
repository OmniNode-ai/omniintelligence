#!/usr/bin/env python3
"""
Unit Tests: ONEX Compliance Validator Compute Node

Tests comprehensive ONEX compliance validation functionality.

Author: Archon Intelligence Team
Date: 2025-10-02
Target Coverage: >90%
"""

import pytest
from archon_services.pattern_learning.phase3_validation.model_contract_validation import (
    IssueCategory,
    IssueSeverity,
    NodeType,
)
from archon_services.pattern_learning.phase3_validation.node_onex_validator_compute import (
    ModelOnexValidationInput,
    NodeOnexValidatorCompute,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def validator():
    """Create validator instance"""
    return NodeOnexValidatorCompute()


@pytest.fixture
def valid_compute_node_code():
    """Valid ONEX Compute node code"""
    return '''#!/usr/bin/env python3
"""
Valid ONEX Compute Node

ONEX Compliance: >0.9
"""

from dataclasses import dataclass
from uuid import uuid4


@dataclass
class ModelExampleInput:
    """Input contract"""
    data: str
    correlation_id: str = ""


@dataclass
class ModelExampleOutput:
    """Output contract"""
    result: str
    processing_time_ms: float
    correlation_id: str


class NodeExampleCompute:
    """ONEX Compute Node"""

    async def execute_compute(
        self, input_state: ModelExampleInput
    ) -> ModelExampleOutput:
        """Execute computation"""
        try:
            result = self._transform_data(input_state.data)
            return ModelExampleOutput(
                result=result,
                processing_time_ms=0.0,
                correlation_id=input_state.correlation_id
            )
        except Exception as e:
            return ModelExampleOutput(
                result="",
                processing_time_ms=0.0,
                correlation_id=input_state.correlation_id
            )

    def _transform_data(self, data: str) -> str:
        """Pure transformation"""
        return data.upper()
'''


@pytest.fixture
def invalid_naming_code():
    """Code with naming convention violations"""
    return '''
class BadNodeName:
    """Wrong naming pattern"""

    async def execute_compute(self, input_state):
        return None
'''


@pytest.fixture
def compute_with_io_violations():
    """Compute node with I/O violations"""
    return '''
class NodeBadCompute:
    """Compute with I/O violations"""

    async def execute_compute(self, input_state):
        # Violation: File write in Compute node
        with open("file.txt", "w") as f:
            f.write("data")

        # Violation: HTTP request in Compute node
        import requests
        response = requests.get("http://example.com")

        return None
'''


@pytest.fixture
def missing_contracts_code():
    """Code without proper contracts"""
    return '''
class NodeExampleCompute:
    """Missing contracts"""

    async def execute_compute(self, data):
        return data
'''


# ============================================================================
# Test: Basic Validation
# ============================================================================


@pytest.mark.asyncio
async def test_validate_valid_compute_node(validator, valid_compute_node_code):
    """Test validation of valid Compute node"""
    input_state = ModelOnexValidationInput(
        code_content=valid_compute_node_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        strict_mode=True,
    )

    output = await validator.execute_compute(input_state)

    assert output.result.compliance_score >= 0.7
    assert output.result.node_type == NodeType.COMPUTE
    assert output.result.has_contracts is True
    assert output.processing_time_ms < 5000  # <5s requirement
    assert output.correlation_id == input_state.correlation_id


@pytest.mark.asyncio
async def test_validate_syntax_error(validator):
    """Test validation with syntax error"""
    invalid_code = "class BadCode\n    pass  # Missing colon"

    input_state = ModelOnexValidationInput(
        code_content=invalid_code,
        code_path="bad_code.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    assert output.result.compliance_score == 0.0
    assert len(output.result.issues) >= 1
    assert output.result.issues[0].severity == IssueSeverity.CRITICAL


# ============================================================================
# Test: Naming Convention Validation
# ============================================================================


@pytest.mark.asyncio
async def test_naming_convention_violations(validator, invalid_naming_code):
    """Test detection of naming convention violations"""
    input_state = ModelOnexValidationInput(
        code_content=invalid_naming_code,
        code_path="bad_name.py",  # Wrong filename pattern
        correlation_id="test-001",
        check_naming=True,
    )

    output = await validator.execute_compute(input_state)

    naming_issues = [
        i for i in output.result.issues if i.category == IssueCategory.NAMING_CONVENTION
    ]

    assert len(naming_issues) >= 1
    assert any(
        i.severity in [IssueSeverity.HIGH, IssueSeverity.CRITICAL]
        for i in naming_issues
    )


@pytest.mark.asyncio
async def test_correct_filename_pattern(validator, valid_compute_node_code):
    """Test correct filename pattern recognition"""
    input_state = ModelOnexValidationInput(
        code_content=valid_compute_node_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",  # Correct pattern
        check_naming=True,
    )

    output = await validator.execute_compute(input_state)

    naming_issues = [
        i for i in output.result.issues if i.category == IssueCategory.NAMING_CONVENTION
    ]

    # Should have no critical naming issues for correct pattern
    critical_naming = [i for i in naming_issues if i.severity == IssueSeverity.CRITICAL]
    assert len(critical_naming) == 0


# ============================================================================
# Test: Contract Usage Validation
# ============================================================================


@pytest.mark.asyncio
async def test_contract_usage_validation(validator, valid_compute_node_code):
    """Test contract usage validation"""
    input_state = ModelOnexValidationInput(
        code_content=valid_compute_node_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        check_contracts=True,
    )

    output = await validator.execute_compute(input_state)

    assert output.result.has_contracts is True

    contract_issues = [
        i for i in output.result.issues if i.category == IssueCategory.CONTRACT_USAGE
    ]

    # Valid code should have minimal contract issues
    critical_contract_issues = [
        i for i in contract_issues if i.severity == IssueSeverity.CRITICAL
    ]
    assert len(critical_contract_issues) == 0


@pytest.mark.asyncio
async def test_missing_contracts_detection(validator, missing_contracts_code):
    """Test detection of missing contracts"""
    input_state = ModelOnexValidationInput(
        code_content=missing_contracts_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        check_contracts=True,
    )

    output = await validator.execute_compute(input_state)

    contract_issues = [
        i for i in output.result.issues if i.category == IssueCategory.CONTRACT_USAGE
    ]

    assert len(contract_issues) >= 2  # Missing Input and Output


# ============================================================================
# Test: Node Type Compliance
# ============================================================================


@pytest.mark.asyncio
async def test_compute_node_io_violations(validator, compute_with_io_violations):
    """Test detection of I/O operations in Compute nodes"""
    input_state = ModelOnexValidationInput(
        code_content=compute_with_io_violations,
        code_path="node_bad_compute.py",
        correlation_id="test-001",
        check_node_type=True,
    )

    output = await validator.execute_compute(input_state)

    type_issues = [
        i
        for i in output.result.issues
        if i.category == IssueCategory.NODE_TYPE_COMPLIANCE
    ]

    assert len(type_issues) >= 1  # Should detect I/O violations
    assert any(i.severity == IssueSeverity.CRITICAL for i in type_issues)


@pytest.mark.asyncio
async def test_effect_node_detection(validator):
    """Test Effect node type detection"""
    effect_code = '''
class NodeDatabaseWriterEffect:
    """Effect node for database writes"""

    async def execute_effect(self, input_state):
        # I/O is OK in Effect nodes
        await self.db.save(input_state.data)
        return None
'''

    input_state = ModelOnexValidationInput(
        code_content=effect_code,
        code_path="node_database_writer_effect.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    assert output.result.node_type == NodeType.EFFECT


# ============================================================================
# Test: Architecture Patterns
# ============================================================================


@pytest.mark.asyncio
async def test_correlation_id_usage(validator, valid_compute_node_code):
    """Test correlation_id usage validation"""
    input_state = ModelOnexValidationInput(
        code_content=valid_compute_node_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        check_structure=True,
    )

    output = await validator.execute_compute(input_state)

    correlation_issues = [
        i for i in output.result.issues if i.category == IssueCategory.CORRELATION_ID
    ]

    # Valid code has correlation_id
    assert len(correlation_issues) == 0


@pytest.mark.asyncio
async def test_missing_correlation_id(validator):
    """Test detection of missing correlation_id"""
    code_without_correlation = '''
class NodeExampleCompute:
    """No correlation_id"""

    async def execute_compute(self, input_state):
        return {"result": "data"}
'''

    input_state = ModelOnexValidationInput(
        code_content=code_without_correlation,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        check_structure=True,
    )

    output = await validator.execute_compute(input_state)

    correlation_issues = [
        i for i in output.result.issues if i.category == IssueCategory.CORRELATION_ID
    ]

    assert len(correlation_issues) >= 1


@pytest.mark.asyncio
async def test_error_handling_validation(validator, valid_compute_node_code):
    """Test error handling pattern validation"""
    input_state = ModelOnexValidationInput(
        code_content=valid_compute_node_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        check_structure=True,
    )

    output = await validator.execute_compute(input_state)

    error_handling_issues = [
        i for i in output.result.issues if i.category == IssueCategory.ERROR_HANDLING
    ]

    # Valid code has try-except
    assert len(error_handling_issues) == 0


# ============================================================================
# Test: Compliance Score Calculation
# ============================================================================


@pytest.mark.asyncio
async def test_compliance_score_calculation(validator):
    """Test compliance score calculation"""
    # Perfect code
    perfect_code = '''
"""Perfect ONEX module"""

@dataclass
class ModelPerfectInput:
    data: str
    correlation_id: str = ""

@dataclass
class ModelPerfectOutput:
    result: str
    correlation_id: str

class NodePerfectCompute:
    async def execute_compute(self, input_state: ModelPerfectInput) -> ModelPerfectOutput:
        try:
            return ModelPerfectOutput(result="ok", correlation_id=input_state.correlation_id)
        except Exception:
            return ModelPerfectOutput(result="", correlation_id="")
'''

    input_state = ModelOnexValidationInput(
        code_content=perfect_code,
        code_path="node_perfect_compute.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    # Should have high compliance score
    assert output.result.compliance_score >= 0.6


@pytest.mark.asyncio
async def test_low_compliance_score(validator, compute_with_io_violations):
    """Test low compliance score for bad code"""
    input_state = ModelOnexValidationInput(
        code_content=compute_with_io_violations,
        code_path="node_bad_compute.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    # Should have low compliance score due to violations
    assert output.result.compliance_score < 0.8


# ============================================================================
# Test: Recommendations
# ============================================================================


@pytest.mark.asyncio
async def test_recommendations_generation(validator, compute_with_io_violations):
    """Test recommendation generation"""
    input_state = ModelOnexValidationInput(
        code_content=compute_with_io_violations,
        code_path="node_bad_compute.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    assert len(output.result.recommendations) >= 1
    assert any("pure" in r.lower() or "I/O" in r for r in output.result.recommendations)


# ============================================================================
# Test: Statistics
# ============================================================================


# TODO: Add statistics tracking to validator
# @pytest.mark.asyncio
# async def test_statistics_tracking(validator, valid_compute_node_code):
#     """Test statistics tracking"""
#     input_state = ModelOnexValidationInput(
#         code_content=valid_compute_node_code,
#         code_path="node_example_compute.py",
#         correlation_id="test-001",
#     )
#
#     # Run multiple validations
#     await validator.execute_compute(input_state)
#     await validator.execute_compute(input_state)
#
#     stats = validator.get_statistics()
#
#     assert stats["validation_count"] == 2
#     assert stats["avg_processing_time_ms"] > 0.0
#     assert stats["total_processing_time_ms"] > 0.0
#
#
# def test_statistics_reset(validator):
#     """Test statistics reset"""
#     validator._validation_count = 5
#     validator._total_processing_time = 100.0
#
#     validator.reset_statistics()
#
#     stats = validator.get_statistics()
#
#     assert stats["validation_count"] == 0
#     assert stats["avg_processing_time_ms"] == 0.0


# ============================================================================
# Test: Node Type Detection
# ============================================================================


@pytest.mark.asyncio
async def test_detect_compute_node_type(validator):
    """Test Compute node type detection"""
    code = "class NodeTestCompute:\n    pass"

    input_state = ModelOnexValidationInput(
        code_content=code,
        code_path="node_test_compute.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    assert output.result.node_type == NodeType.COMPUTE


@pytest.mark.asyncio
async def test_detect_orchestrator_node_type(validator):
    """Test Orchestrator node type detection"""
    code = "class NodeWorkflowOrchestrator:\n    pass"

    input_state = ModelOnexValidationInput(
        code_content=code,
        code_path="node_workflow_orchestrator.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    assert output.result.node_type == NodeType.ORCHESTRATOR


@pytest.mark.asyncio
async def test_detect_reducer_node_type(validator):
    """Test Reducer node type detection"""
    code = "class NodeDataAggregatorReducer:\n    pass"

    input_state = ModelOnexValidationInput(
        code_content=code,
        code_path="node_data_aggregator_reducer.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    assert output.result.node_type == NodeType.REDUCER


# ============================================================================
# Test: Selective Validation
# ============================================================================


@pytest.mark.asyncio
async def test_selective_validation_naming_only(validator, invalid_naming_code):
    """Test validation with only naming checks enabled"""
    input_state = ModelOnexValidationInput(
        code_content=invalid_naming_code,
        code_path="bad_name.py",
        correlation_id="test-001",
        check_naming=True,
        check_contracts=False,
        check_structure=False,
        check_methods=False,
    )

    output = await validator.execute_compute(input_state)

    # Should only have naming issues
    assert all(
        i.category == IssueCategory.NAMING_CONVENTION for i in output.result.issues
    )


@pytest.mark.asyncio
async def test_selective_validation_contracts_only(validator, missing_contracts_code):
    """Test validation with only contract checks enabled"""
    input_state = ModelOnexValidationInput(
        code_content=missing_contracts_code,
        code_path="node_example_compute.py",
        correlation_id="test-001",
        check_naming=False,
        check_contracts=True,
        check_structure=False,
        check_methods=False,
    )

    output = await validator.execute_compute(input_state)

    # Should only have contract issues
    assert all(i.category == IssueCategory.CONTRACT_USAGE for i in output.result.issues)


# ============================================================================
# Test: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_graceful_error_handling(validator):
    """Test graceful error handling for invalid input"""
    # Create input that will cause processing error
    input_state = ModelOnexValidationInput(
        code_content="",  # Empty code
        code_path="empty.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    # Should still return valid output
    assert output is not None
    assert output.result.compliance_score >= 0.0
    assert output.correlation_id == input_state.correlation_id


# ============================================================================
# Test: Performance
# ============================================================================


@pytest.mark.asyncio
async def test_performance_under_5_seconds(validator, valid_compute_node_code):
    """Test that validation completes in <5 seconds"""
    input_state = ModelOnexValidationInput(
        code_content=valid_compute_node_code * 10,  # Large code
        code_path="node_large_compute.py",
        correlation_id="test-001",
    )

    output = await validator.execute_compute(input_state)

    # <5000ms requirement
    assert output.processing_time_ms < 5000


# ============================================================================
# Test: Issue Serialization
# ============================================================================


def test_validation_issue_to_dict():
    """Test ValidationIssue serialization"""
    from archon_services.pattern_learning.phase3_validation.model_contract_validation import (
        ValidationIssue,
    )

    issue = ValidationIssue(
        severity=IssueSeverity.HIGH,
        category=IssueCategory.NAMING_CONVENTION,
        message="Test issue",
        recommendation="Fix it",
        file_path="test.py",
        line_number=10,
    )

    result = issue.to_dict()

    assert result["severity"] == "high"
    assert result["category"] == "naming_convention"
    assert result["message"] == "Test issue"
    assert result["file_path"] == "test.py"
    assert result["line_number"] == 10


def test_validation_result_to_dict():
    """Test ValidationResult serialization"""
    from archon_services.pattern_learning.phase3_validation.model_contract_validation import (
        ValidationIssue,
        ValidationResult,
    )

    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        category=IssueCategory.NODE_TYPE_COMPLIANCE,
        message="Critical issue",
        recommendation="Fix now",
    )

    result = ValidationResult(
        compliance_score=0.75,
        issues=[issue],
        passed_checks=15,
        total_checks=20,
        node_type=NodeType.COMPUTE,
        has_contracts=True,
    )

    result_dict = result.to_dict()

    assert result_dict["compliance_score"] == 0.75
    assert result_dict["compliance_percentage"] == 75.0
    assert result_dict["passed_checks"] == 15
    assert result_dict["total_checks"] == 20
    assert result_dict["node_type"] == "compute"
    assert result_dict["summary"]["critical"] == 1


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=src.services.pattern_learning.phase3_validation"]
    )
