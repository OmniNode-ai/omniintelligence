"""
Compliance Report Models - Comprehensive validation result structures.

Provides data models for compliance reports including:
- Gate results (ONEX, tests, quality, performance, security)
- Issues with severity and recommendations
- Historical tracking metadata
- Multiple format support (JSON, Markdown, HTML, CSV)

ONEX Compliance: Pure data models, no business logic
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# NOTE: correlation_id support enabled for tracing
class EnumSeverity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EnumGateType(str, Enum):
    """Quality gate types."""

    ONEX_COMPLIANCE = "onex_compliance"
    TEST_COVERAGE = "test_coverage"
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DOCUMENTATION = "documentation"


class ModelIssue(BaseModel):
    """
    Compliance issue or violation.

    Represents a single validation issue with context and remediation guidance.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique issue identifier")
    severity: EnumSeverity = Field(..., description="Issue severity level")
    gate_type: EnumGateType = Field(..., description="Gate type where issue was found")
    title: str = Field(..., description="Short issue description")
    description: str = Field(..., description="Detailed issue description")
    file_path: str | None = Field(
        default=None, description="File where issue was found"
    )
    line_number: int | None = Field(default=None, description="Line number of issue")
    code_snippet: str | None = Field(default=None, description="Relevant code snippet")
    remediation: str | None = Field(
        default=None, description="Suggested fix or remediation"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional issue metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "severity": "high",
                "gate_type": "onex_compliance",
                "title": "Missing ONEX node type suffix",
                "description": "Class name does not follow ONEX naming convention",
                "file_path": "src/services/validator.py",
                "line_number": 42,
                "remediation": "Rename class to NodeValidatorCompute",
            }
        }
    )


class ModelRecommendation(BaseModel):
    """
    Improvement recommendation.

    Provides actionable suggestions for code quality improvement.
    """

    id: UUID = Field(
        default_factory=uuid4, description="Unique recommendation identifier"
    )
    category: str = Field(..., description="Recommendation category")
    priority: EnumSeverity = Field(
        default=EnumSeverity.INFO, description="Recommendation priority"
    )
    title: str = Field(..., description="Short recommendation title")
    description: str = Field(..., description="Detailed recommendation description")
    rationale: str = Field(..., description="Why this recommendation matters")
    action_items: list[str] = Field(
        default_factory=list, description="Specific action items"
    )
    estimated_effort: str | None = Field(
        default=None, description="Estimated implementation effort"
    )
    impact: str | None = Field(default=None, description="Expected impact")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "architecture",
                "priority": "medium",
                "title": "Consider using Reducer pattern",
                "description": "State aggregation could benefit from Reducer node",
                "rationale": "Improves maintainability and ONEX compliance",
                "action_items": [
                    "Extract aggregation logic to Reducer",
                    "Add proper state management",
                ],
            }
        }
    )


class ModelGateResult(BaseModel):
    """
    Quality gate validation result.

    Represents the outcome of a single quality gate validation.
    """

    gate_type: EnumGateType = Field(..., description="Type of quality gate")
    passed: bool = Field(..., description="Whether gate passed")
    score: float = Field(..., description="Gate score (0.0-1.0)", ge=0.0, le=1.0)
    threshold: float = Field(
        ..., description="Required threshold (0.0-1.0)", ge=0.0, le=1.0
    )
    issues_count: int = Field(default=0, description="Number of issues found", ge=0)
    warnings_count: int = Field(default=0, description="Number of warnings", ge=0)
    execution_time_ms: float = Field(
        default=0.0, description="Gate execution time in milliseconds", ge=0.0
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional gate metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gate_type": "onex_compliance",
                "passed": True,
                "score": 0.95,
                "threshold": 0.85,
                "issues_count": 2,
                "warnings_count": 5,
            }
        }
    )


class ModelComplianceReport(BaseModel):
    """
    Comprehensive compliance validation report.

    Contains complete validation results across all quality gates with
    issues, recommendations, and historical tracking metadata.
    """

    # Report identification
    report_id: UUID = Field(
        default_factory=uuid4, description="Unique report identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation timestamp"
    )
    version: str = Field(default="1.0.0", description="Report format version")

    # Validation context
    project_id: str | None = Field(default=None, description="Project identifier")
    code_path: str | None = Field(default=None, description="Code path validated")
    commit_hash: str | None = Field(default=None, description="Git commit hash")
    branch: str | None = Field(default=None, description="Git branch name")

    # Overall results
    overall_score: float = Field(
        ..., description="Overall compliance score (0.0-1.0)", ge=0.0, le=1.0
    )
    overall_passed: bool = Field(..., description="Whether all gates passed")
    total_issues: int = Field(
        default=0, description="Total issues across all gates", ge=0
    )
    critical_issues: int = Field(default=0, description="Critical issues count", ge=0)
    high_issues: int = Field(default=0, description="High severity issues count", ge=0)

    # Quality gates
    gates: dict[str, ModelGateResult] = Field(
        default_factory=dict, description="Quality gate results"
    )

    # Issues and recommendations
    issues: list[ModelIssue] = Field(
        default_factory=list, description="All validation issues"
    )
    recommendations: list[ModelRecommendation] = Field(
        default_factory=list, description="Improvement recommendations"
    )

    # Execution metadata
    execution_time_ms: float = Field(
        default=0.0, description="Total validation execution time", ge=0.0
    )
    validated_files_count: int = Field(
        default=0, description="Number of files validated", ge=0
    )
    validated_lines_count: int = Field(
        default=0, description="Number of lines validated", ge=0
    )

    # Historical tracking
    previous_score: float | None = Field(
        default=None, description="Previous validation score"
    )
    score_delta: float | None = Field(
        default=None, description="Score change from previous"
    )
    trend: str | None = Field(
        default=None, description="Trend indicator (improving, declining, stable)"
    )

    # Additional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional report metadata"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return self.model_dump(mode="python")

    def get_issues_by_severity(self, severity: EnumSeverity) -> list[ModelIssue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]

    def get_issues_by_gate(self, gate_type: EnumGateType) -> list[ModelIssue]:
        """Get all issues for a specific gate."""
        return [issue for issue in self.issues if issue.gate_type == gate_type]

    def get_failed_gates(self) -> list[ModelGateResult]:
        """Get all failed quality gates."""
        return [gate for gate in self.gates.values() if not gate.passed]

    def calculate_trend(self) -> str:
        """Calculate trend based on score delta."""
        if self.score_delta is None or self.previous_score is None:
            return "unknown"
        if self.score_delta > 0.05:
            return "improving"
        elif self.score_delta < -0.05:
            return "declining"
        else:
            return "stable"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_score": 0.92,
                "overall_passed": True,
                "total_issues": 7,
                "critical_issues": 0,
                "high_issues": 2,
                "gates": {
                    "onex_compliance": {
                        "passed": True,
                        "score": 0.95,
                        "threshold": 0.85,
                    },
                    "test_coverage": {"passed": True, "score": 0.92, "threshold": 0.80},
                },
            }
        }
    )
