"""
ONEX Effect Node: Compliance Report Generator

Purpose: Generate comprehensive compliance reports in multiple formats
Node Type: Effect (I/O operations for report generation and export)
File: node_compliance_reporter_effect.py
Class: NodeComplianceReporterEffect

Pattern: ONEX 4-Node Architecture - Effect
Track: Track 3-3.7 - Phase 3 Compliance Reporting
ONEX Compliant: Suffix naming (Node*Effect), file pattern (node_*_effect.py)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from src.archon_services.pattern_learning.phase3_validation.reporting.models.model_compliance_report import (
    EnumGateType,
    EnumSeverity,
    ModelComplianceReport,
    ModelGateResult,
    ModelIssue,
    ModelRecommendation,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Contract Model
# ============================================================================


class ModelContractComplianceReporter(BaseModel):
    """
    Contract for compliance report generation operations.

    Defines the input structure for generating compliance reports
    in various formats (JSON, Markdown, HTML, CSV).
    """

    name: str = Field(..., description="Operation name")
    operation: str = Field(
        ..., description="Operation type: generate, export, format_convert"
    )
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Correlation ID for tracking"
    )

    # Report generation inputs
    validation_results: dict[str, Any] | None = Field(
        default=None, description="Raw validation results from quality gates"
    )
    report_data: ModelComplianceReport | None = Field(
        default=None, description="Existing report to export/convert"
    )

    # Output configuration
    output_format: str = Field(
        default="json", description="Output format: json, markdown, html, csv"
    )
    output_path: str | None = Field(
        default=None, description="Optional output file path"
    )
    include_recommendations: bool = Field(
        default=True, description="Include recommendations in report"
    )
    include_code_snippets: bool = Field(
        default=True, description="Include code snippets in issues"
    )

    # Context metadata
    project_id: str | None = Field(default=None, description="Project identifier")
    code_path: str | None = Field(default=None, description="Code path validated")
    commit_hash: str | None = Field(default=None, description="Git commit hash")
    branch: str | None = Field(default=None, description="Git branch name")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ModelResult(BaseModel):
    """Result model for Effect operations."""

    success: bool = Field(..., description="Operation success status")
    data: dict[str, Any] | None = Field(default=None, description="Result data")
    error: str | None = Field(default=None, description="Error message if failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


# ============================================================================
# ONEX Effect Node: Compliance Reporter
# ============================================================================


class NodeComplianceReporterEffect:
    """
    ONEX Effect Node for compliance report generation.

    Implements:
    - ONEX naming convention: Node<Name>Effect
    - File pattern: node_*_effect.py
    - Method signature: async def execute_effect(contract) -> ModelResult
    - Pure I/O operations for report generation
    - Multiple output formats (JSON, Markdown, HTML, CSV)

    Responsibilities:
    - Generate comprehensive compliance reports
    - Export reports in multiple formats
    - Include quality gate results, issues, recommendations
    - Calculate trends and historical comparisons
    - Generate actionable insights

    Performance Targets:
    - Report generation: <200ms
    - Export to file: <100ms
    - Format conversion: <150ms

    Example:
        >>> node = NodeComplianceReporterEffect()
        >>> contract = ModelContractComplianceReporter(
        ...     name="generate_report",
        ...     operation="generate",
        ...     validation_results={...},
        ...     output_format="json"
        ... )
        >>> result = await node.execute_effect(contract)
        >>> print(result.success, result.data)
    """

    def __init__(self):
        """Initialize compliance reporter Effect node."""
        self.logger = logging.getLogger("NodeComplianceReporterEffect")

    async def execute_effect(
        self, contract: ModelContractComplianceReporter
    ) -> ModelResult:
        """
        Execute compliance report generation operation.

        ONEX Method Signature: async def execute_effect(contract) -> ModelResult

        Args:
            contract: ModelContractComplianceReporter with operation details

        Returns:
            ModelResult with generated report and metadata

        Operations:
            - generate: Generate new compliance report from validation results
            - export: Export existing report to file
            - format_convert: Convert report to different format

        Performance:
            - Generation: <200ms
            - Export: <100ms
        """
        start_time = datetime.now(timezone.utc)
        operation_name = contract.operation

        try:
            self.logger.info(
                f"Executing compliance report operation: {operation_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )

            # Route to appropriate handler
            if operation_name == "generate":
                result_data = await self._generate_report(contract)
            elif operation_name == "export":
                result_data = await self._export_report(contract)
            elif operation_name == "format_convert":
                result_data = await self._convert_format(contract)
            else:
                return ModelResult(
                    success=False,
                    error=f"Unsupported operation: {operation_name}",
                    metadata={"correlation_id": str(contract.correlation_id)},
                )

            # Calculate operation duration
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000

            self.logger.info(
                f"Compliance report operation completed: {operation_name}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "duration_ms": duration_ms,
                    "operation": operation_name,
                },
            )

            return ModelResult(
                success=True,
                data=result_data,
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        except ValueError as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Validation error: {e}",
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Validation error: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": "validation_error",
                },
            )

        except Exception as e:
            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            self.logger.error(
                f"Compliance report operation failed: {e}",
                exc_info=True,
                extra={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                },
            )
            return ModelResult(
                success=False,
                error=f"Operation failed: {str(e)}",
                metadata={
                    "correlation_id": str(contract.correlation_id),
                    "operation": operation_name,
                    "duration_ms": round(duration_ms, 2),
                    "error_type": type(e).__name__,
                },
            )

    # ========================================================================
    # Private Operation Handlers
    # ========================================================================

    async def _generate_report(
        self, contract: ModelContractComplianceReporter
    ) -> dict[str, Any]:
        """
        Generate comprehensive compliance report from validation results.

        Args:
            contract: Contract with validation results

        Returns:
            Dict with generated report in requested format

        Raises:
            ValueError: If validation_results missing or invalid
        """
        if not contract.validation_results:
            raise ValueError("validation_results required for generate operation")

        validation_results = contract.validation_results

        # Build compliance report
        report = ModelComplianceReport(
            project_id=contract.project_id,
            code_path=contract.code_path,
            commit_hash=contract.commit_hash,
            branch=contract.branch,
            overall_score=validation_results.get("overall_score", 0.0),
            overall_passed=validation_results.get("overall_passed", False),
        )

        # Process quality gates
        gates_data = validation_results.get("gates", {})
        for gate_name, gate_result in gates_data.items():
            gate = ModelGateResult(
                gate_type=EnumGateType(gate_name),
                passed=gate_result.get("passed", False),
                score=gate_result.get("score", 0.0),
                threshold=gate_result.get("threshold", 0.8),
                issues_count=gate_result.get("issues_count", 0),
                warnings_count=gate_result.get("warnings_count", 0),
                execution_time_ms=gate_result.get("execution_time_ms", 0.0),
                metadata=gate_result.get("metadata", {}),
            )
            report.gates[gate_name] = gate

        # Process issues
        issues_data = validation_results.get("issues", [])
        for issue_data in issues_data:
            issue = ModelIssue(
                severity=EnumSeverity(issue_data.get("severity", "info")),
                gate_type=EnumGateType(issue_data.get("gate_type", "code_quality")),
                title=issue_data.get("title", "Unknown issue"),
                description=issue_data.get("description", ""),
                file_path=issue_data.get("file_path"),
                line_number=issue_data.get("line_number"),
                code_snippet=(
                    issue_data.get("code_snippet")
                    if contract.include_code_snippets
                    else None
                ),
                remediation=issue_data.get("remediation"),
                metadata=issue_data.get("metadata", {}),
            )
            report.issues.append(issue)

        # Process recommendations
        if contract.include_recommendations:
            recommendations_data = validation_results.get("recommendations", [])
            for rec_data in recommendations_data:
                recommendation = ModelRecommendation(
                    category=rec_data.get("category", "general"),
                    priority=EnumSeverity(rec_data.get("priority", "info")),
                    title=rec_data.get("title", ""),
                    description=rec_data.get("description", ""),
                    rationale=rec_data.get("rationale", ""),
                    action_items=rec_data.get("action_items", []),
                    estimated_effort=rec_data.get("estimated_effort"),
                    impact=rec_data.get("impact"),
                )
                report.recommendations.append(recommendation)

        # Calculate summary statistics
        report.total_issues = len(report.issues)
        report.critical_issues = len(
            report.get_issues_by_severity(EnumSeverity.CRITICAL)
        )
        report.high_issues = len(report.get_issues_by_severity(EnumSeverity.HIGH))

        # Calculate execution metadata
        report.execution_time_ms = sum(
            gate.execution_time_ms for gate in report.gates.values()
        )
        report.validated_files_count = validation_results.get(
            "validated_files_count", 0
        )
        report.validated_lines_count = validation_results.get(
            "validated_lines_count", 0
        )

        # Add historical comparison if available
        report.previous_score = validation_results.get("previous_score")
        if report.previous_score is not None:
            report.score_delta = report.overall_score - report.previous_score
            report.trend = report.calculate_trend()

        # Format output
        formatted_report = await self._format_report(report, contract.output_format)

        # Export to file if path provided
        if contract.output_path:
            await self._write_to_file(
                formatted_report, contract.output_path, contract.output_format
            )

        return {
            "report_id": str(report.report_id),
            "timestamp": report.timestamp.isoformat(),
            "overall_score": report.overall_score,
            "overall_passed": report.overall_passed,
            "total_issues": report.total_issues,
            "critical_issues": report.critical_issues,
            "output_format": contract.output_format,
            "report": formatted_report,
        }

    async def _export_report(
        self, contract: ModelContractComplianceReporter
    ) -> dict[str, Any]:
        """
        Export existing compliance report to file.

        Args:
            contract: Contract with existing report

        Returns:
            Dict with export status and file path

        Raises:
            ValueError: If report_data or output_path missing
        """
        if not contract.report_data:
            raise ValueError("report_data required for export operation")

        if not contract.output_path:
            raise ValueError("output_path required for export operation")

        formatted_report = await self._format_report(
            contract.report_data, contract.output_format
        )

        await self._write_to_file(
            formatted_report, contract.output_path, contract.output_format
        )

        return {
            "exported": True,
            "output_path": contract.output_path,
            "output_format": contract.output_format,
            "file_size_bytes": len(formatted_report.encode("utf-8")),
        }

    async def _convert_format(
        self, contract: ModelContractComplianceReporter
    ) -> dict[str, Any]:
        """
        Convert report to different format.

        Args:
            contract: Contract with report and target format

        Returns:
            Dict with converted report

        Raises:
            ValueError: If report_data missing
        """
        if not contract.report_data:
            raise ValueError("report_data required for format_convert operation")

        formatted_report = await self._format_report(
            contract.report_data, contract.output_format
        )

        return {
            "converted": True,
            "output_format": contract.output_format,
            "report": formatted_report,
        }

    # ========================================================================
    # Format Handlers
    # ========================================================================

    async def _format_report(
        self, report: ModelComplianceReport, format_type: str
    ) -> str:
        """Format report in specified format."""
        if format_type == "json":
            return json.dumps(report.to_dict(), indent=2, default=str)
        elif format_type == "markdown":
            return self._format_markdown(report)
        elif format_type == "html":
            return self._format_html(report)
        elif format_type == "csv":
            return self._format_csv(report)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _format_markdown(self, report: ModelComplianceReport) -> str:
        """Format report as Markdown."""
        lines = [
            "# Compliance Report",
            "",
            f"**Report ID:** `{report.report_id}`",
            f"**Generated:** {report.timestamp.isoformat()}",
            f"**Overall Score:** {report.overall_score:.2%} ({'PASSED' if report.overall_passed else 'FAILED'})",
            "",
            "## Summary",
            "",
            f"- **Total Issues:** {report.total_issues}",
            f"- **Critical Issues:** {report.critical_issues}",
            f"- **High Issues:** {report.high_issues}",
            f"- **Files Validated:** {report.validated_files_count}",
            f"- **Execution Time:** {report.execution_time_ms:.2f}ms",
            "",
        ]

        # Quality gates
        lines.extend(["## Quality Gates", ""])
        for gate_name, gate in report.gates.items():
            status = "✅ PASSED" if gate.passed else "❌ FAILED"
            lines.append(f"### {gate_name.replace('_', ' ').title()} {status}")
            lines.append(
                f"- **Score:** {gate.score:.2%} (threshold: {gate.threshold:.2%})"
            )
            lines.append(f"- **Issues:** {gate.issues_count}")
            lines.append(f"- **Warnings:** {gate.warnings_count}")
            lines.append("")

        # Issues
        if report.issues:
            lines.extend(["## Issues", ""])
            for issue in report.issues:
                lines.append(f"### [{issue.severity.value.upper()}] {issue.title}")
                lines.append(f"**Gate:** {issue.gate_type.value}")
                if issue.file_path:
                    lines.append(f"**File:** `{issue.file_path}`")
                    if issue.line_number:
                        lines.append(f"**Line:** {issue.line_number}")
                lines.append(f"**Description:** {issue.description}")
                if issue.remediation:
                    lines.append(f"**Remediation:** {issue.remediation}")
                lines.append("")

        # Recommendations
        if report.recommendations:
            lines.extend(["## Recommendations", ""])
            for rec in report.recommendations:
                lines.append(f"### {rec.title}")
                lines.append(f"**Priority:** {rec.priority.value}")
                lines.append(f"**Category:** {rec.category}")
                lines.append(f"{rec.description}")
                if rec.action_items:
                    lines.append("**Action Items:**")
                    for item in rec.action_items:
                        lines.append(f"- {item}")
                lines.append("")

        return "\n".join(lines)

    def _format_html(self, report: ModelComplianceReport) -> str:
        """Format report as HTML."""
        # Simple HTML template
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Compliance Report - {report.report_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .gate {{ margin: 15px 0; padding: 10px; border-left: 3px solid #ccc; }}
        .issue {{ margin: 10px 0; padding: 10px; background: #fff5f5; border-radius: 3px; }}
        .critical {{ border-left: 3px solid #d32f2f; }}
        .high {{ border-left: 3px solid #f57c00; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Compliance Report</h1>
        <p><strong>Report ID:</strong> {report.report_id}</p>
        <p><strong>Generated:</strong> {report.timestamp.isoformat()}</p>
        <p><strong>Overall Score:</strong> <span class="{'passed' if report.overall_passed else 'failed'}">{report.overall_score:.2%}</span></p>
    </div>
    <div class="summary">
        <h2>Summary</h2>
        <ul>
            <li><strong>Total Issues:</strong> {report.total_issues}</li>
            <li><strong>Critical Issues:</strong> {report.critical_issues}</li>
            <li><strong>High Issues:</strong> {report.high_issues}</li>
        </ul>
    </div>
</body>
</html>
"""

    def _format_csv(self, report: ModelComplianceReport) -> str:
        """Format report as CSV (issues list)."""
        lines = ["Severity,Gate,Title,File,Line,Description,Remediation"]

        for issue in report.issues:
            lines.append(
                f'"{issue.severity.value}","{issue.gate_type.value}","{issue.title}","{issue.file_path or ""}","{issue.line_number or ""}","{issue.description}","{issue.remediation or ""}"'
            )

        return "\n".join(lines)

    async def _write_to_file(
        self, content: str, output_path: str, format_type: str
    ) -> None:
        """Write report content to file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info(f"Report written to: {output_path}")
