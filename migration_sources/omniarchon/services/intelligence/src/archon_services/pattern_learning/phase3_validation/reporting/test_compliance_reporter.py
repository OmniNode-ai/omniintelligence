"""
Unit Tests for NodeComplianceReporterEffect

Tests compliance report generation in multiple formats (JSON, Markdown, HTML, CSV)
with comprehensive validation results, issues, and recommendations.

Test Coverage:
- Report generation from validation results
- Multiple output formats (JSON, Markdown, HTML, CSV)
- Export to file
- Format conversion
- Error handling
"""

import json
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .models.model_compliance_report import (
    ModelComplianceReport,
)
from .node_compliance_reporter_effect import (
    ModelContractComplianceReporter,
    NodeComplianceReporterEffect,
)


@pytest.fixture
# NOTE: correlation_id support enabled for tracing
def compliance_reporter():
    """Create compliance reporter instance."""
    return NodeComplianceReporterEffect()


@pytest.fixture
def sample_validation_results():
    """Create sample validation results."""
    return {
        "overall_score": 0.92,
        "overall_passed": True,
        "gates": {
            "onex_compliance": {
                "passed": True,
                "score": 0.95,
                "threshold": 0.85,
                "issues_count": 1,
                "warnings_count": 2,
                "execution_time_ms": 45.2,
            },
            "test_coverage": {
                "passed": True,
                "score": 0.88,
                "threshold": 0.80,
                "issues_count": 0,
                "warnings_count": 1,
                "execution_time_ms": 32.1,
            },
            "code_quality": {
                "passed": False,
                "score": 0.72,
                "threshold": 0.75,
                "issues_count": 3,
                "warnings_count": 5,
                "execution_time_ms": 67.8,
            },
        },
        "issues": [
            {
                "severity": "high",
                "gate_type": "onex_compliance",
                "title": "Missing ONEX node type suffix",
                "description": "Class name does not follow ONEX naming convention",
                "file_path": "src/validators/validator.py",
                "line_number": 42,
                "code_snippet": "class Validator:",
                "remediation": "Rename class to NodeValidatorCompute",
            },
            {
                "severity": "medium",
                "gate_type": "code_quality",
                "title": "Missing docstrings",
                "description": "Functions lack comprehensive documentation",
                "file_path": "src/validators/validator.py",
                "line_number": 55,
                "remediation": "Add docstrings to all public functions",
            },
        ],
        "recommendations": [
            {
                "category": "architecture",
                "priority": "medium",
                "title": "Consider using Reducer pattern",
                "description": "State aggregation could benefit from Reducer node",
                "rationale": "Improves maintainability and ONEX compliance",
                "action_items": [
                    "Extract aggregation logic to Reducer",
                    "Add proper state management",
                ],
                "estimated_effort": "2 hours",
                "impact": "Improved ONEX compliance and maintainability",
            }
        ],
        "validated_files_count": 5,
        "validated_lines_count": 432,
    }


@pytest.mark.asyncio
async def test_generate_json_report(compliance_reporter, sample_validation_results):
    """Test JSON report generation."""
    contract = ModelContractComplianceReporter(
        name="generate_json_report",
        operation="generate",
        validation_results=sample_validation_results,
        output_format="json",
        project_id="test-project",
        code_path="src/validators",
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True
    assert result.data is not None
    assert "report_id" in result.data
    assert result.data["overall_score"] == 0.92
    assert result.data["overall_passed"] is True
    assert result.data["total_issues"] == 2
    assert result.data["critical_issues"] == 0
    assert result.data["output_format"] == "json"

    # Verify JSON is valid
    report_json = result.data["report"]
    report_dict = json.loads(report_json)
    assert report_dict["overall_score"] == 0.92


@pytest.mark.asyncio
async def test_generate_markdown_report(compliance_reporter, sample_validation_results):
    """Test Markdown report generation."""
    contract = ModelContractComplianceReporter(
        name="generate_markdown_report",
        operation="generate",
        validation_results=sample_validation_results,
        output_format="markdown",
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True
    assert result.data is not None

    # Verify Markdown formatting
    report_md = result.data["report"]
    assert "# Compliance Report" in report_md
    assert "## Summary" in report_md
    assert "## Quality Gates" in report_md
    assert "## Issues" in report_md
    assert "✅ PASSED" in report_md  # For passed gates
    assert "❌ FAILED" in report_md  # For failed gates


@pytest.mark.asyncio
async def test_generate_html_report(compliance_reporter, sample_validation_results):
    """Test HTML report generation."""
    contract = ModelContractComplianceReporter(
        name="generate_html_report",
        operation="generate",
        validation_results=sample_validation_results,
        output_format="html",
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True
    assert result.data is not None

    # Verify HTML structure
    report_html = result.data["report"]
    assert "<!DOCTYPE html>" in report_html
    assert "<title>Compliance Report" in report_html
    assert "<body>" in report_html


@pytest.mark.asyncio
async def test_generate_csv_report(compliance_reporter, sample_validation_results):
    """Test CSV report generation."""
    contract = ModelContractComplianceReporter(
        name="generate_csv_report",
        operation="generate",
        validation_results=sample_validation_results,
        output_format="csv",
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True
    assert result.data is not None

    # Verify CSV structure
    report_csv = result.data["report"]
    lines = report_csv.split("\n")
    assert "Severity,Gate,Title,File,Line,Description,Remediation" in lines[0]
    assert len(lines) > 1  # Header + issues


@pytest.mark.asyncio
async def test_export_report_to_file(compliance_reporter, sample_validation_results):
    """Test exporting report to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = str(Path(tmpdir) / "compliance_report.json")

        contract = ModelContractComplianceReporter(
            name="export_report",
            operation="generate",
            validation_results=sample_validation_results,
            output_format="json",
            output_path=output_path,
        )

        result = await compliance_reporter.execute_effect(contract)

        assert result.success is True

        # Verify file was created
        assert Path(output_path).exists()

        # Verify file content
        with open(output_path, "r") as f:
            content = f.read()
            report_dict = json.loads(content)
            assert report_dict["overall_score"] == 0.92


@pytest.mark.asyncio
async def test_exclude_recommendations(compliance_reporter, sample_validation_results):
    """Test report generation without recommendations."""
    contract = ModelContractComplianceReporter(
        name="generate_no_recommendations",
        operation="generate",
        validation_results=sample_validation_results,
        output_format="json",
        include_recommendations=False,
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True

    report_json = result.data["report"]
    report_dict = json.loads(report_json)
    assert len(report_dict["recommendations"]) == 0


@pytest.mark.asyncio
async def test_exclude_code_snippets(compliance_reporter, sample_validation_results):
    """Test report generation without code snippets."""
    contract = ModelContractComplianceReporter(
        name="generate_no_snippets",
        operation="generate",
        validation_results=sample_validation_results,
        output_format="json",
        include_code_snippets=False,
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True

    report_json = result.data["report"]
    report_dict = json.loads(report_json)

    # Check issues don't have code snippets
    for issue in report_dict["issues"]:
        assert issue.get("code_snippet") is None


@pytest.mark.asyncio
async def test_invalid_operation(compliance_reporter):
    """Test invalid operation handling."""
    contract = ModelContractComplianceReporter(
        name="invalid_op",
        operation="invalid_operation",
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is False
    assert "Unsupported operation" in result.error


@pytest.mark.asyncio
async def test_missing_validation_results(compliance_reporter):
    """Test generate operation without validation results."""
    contract = ModelContractComplianceReporter(
        name="missing_results",
        operation="generate",
        validation_results=None,
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is False
    assert "validation_results required" in result.error


@pytest.mark.asyncio
async def test_convert_format_operation(compliance_reporter):
    """Test format conversion operation."""
    # Create a sample report
    report = ModelComplianceReport(
        overall_score=0.92,
        overall_passed=True,
        project_id="test-project",
    )

    contract = ModelContractComplianceReporter(
        name="convert_format",
        operation="format_convert",
        report_data=report,
        output_format="markdown",
    )

    result = await compliance_reporter.execute_effect(contract)

    assert result.success is True
    assert result.data["converted"] is True
    assert result.data["output_format"] == "markdown"
    assert "# Compliance Report" in result.data["report"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
