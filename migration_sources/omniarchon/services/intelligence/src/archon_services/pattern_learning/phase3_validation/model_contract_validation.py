"""
ONEX Contract Models: Validation Operations

Purpose: Define contracts for ONEX compliance validation operations
Pattern: ONEX 4-Node Architecture - Contract Models
File: model_contract_validation.py

Track: Track 3 Phase 3 - ONEX Compliance Validation
ONEX Compliant: Contract naming convention (model_contract_*)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

# ============================================================================
# Enumerations
# ============================================================================


class IssueSeverity(str, Enum):
    """Validation issue severity levels"""

    CRITICAL = "critical"  # Must fix - breaks ONEX compliance
    HIGH = "high"  # Should fix - violates best practices
    MEDIUM = "medium"  # Consider fixing - deviates from patterns
    LOW = "low"  # Optional - minor style issues
    INFO = "info"  # Informational - no action needed


class IssueCategory(str, Enum):
    """Validation issue categories"""

    NAMING_CONVENTION = "naming_convention"  # Node/file naming violations
    CONTRACT_USAGE = "contract_usage"  # Missing or invalid contracts
    NODE_TYPE_COMPLIANCE = "node_type_compliance"  # Wrong node type usage
    ARCHITECTURE_PATTERN = "architecture_pattern"  # Architecture violations
    ERROR_HANDLING = "error_handling"  # Missing error handling
    CORRELATION_ID = "correlation_id"  # Missing correlation ID
    DOCUMENTATION = "documentation"  # Missing/incomplete docs
    PERFORMANCE = "performance"  # Performance anti-patterns


class NodeType(str, Enum):
    """ONEX node types"""

    EFFECT = "effect"  # External I/O, side effects
    COMPUTE = "compute"  # Pure transformations
    REDUCER = "reducer"  # Aggregation, persistence
    ORCHESTRATOR = "orchestrator"  # Workflow coordination


# ============================================================================
# Validation Models
# ============================================================================


@dataclass
class ValidationIssue:
    """
    Single validation issue found in code.

    Attributes:
        severity: Issue severity level
        category: Issue category
        message: Human-readable issue description
        file_path: Path to file with issue (optional)
        line_number: Line number where issue occurs (optional)
        code_snippet: Relevant code snippet (optional)
        recommendation: How to fix the issue
        auto_fixable: Whether issue can be auto-fixed
    """

    severity: IssueSeverity
    category: IssueCategory
    message: str
    recommendation: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "recommendation": self.recommendation,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class ValidationResult:
    """
    Complete validation result for a code file/module.

    Attributes:
        compliance_score: Overall compliance score (0.0-1.0)
        issues: List of validation issues found
        passed_checks: Number of checks that passed
        total_checks: Total number of checks performed
        node_type: Detected node type (optional)
        has_contracts: Whether contracts are properly defined
        recommendations: General improvement recommendations
        metadata: Additional validation metadata
    """

    compliance_score: float
    issues: List[ValidationIssue]
    passed_checks: int
    total_checks: int
    node_type: Optional[NodeType] = None
    has_contracts: bool = False
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "compliance_score": self.compliance_score,
            "compliance_percentage": self.compliance_score * 100,
            "issues": [issue.to_dict() for issue in self.issues],
            "passed_checks": self.passed_checks,
            "total_checks": self.total_checks,
            "node_type": self.node_type.value if self.node_type else None,
            "has_contracts": self.has_contracts,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
            "summary": {
                "critical": sum(
                    1 for i in self.issues if i.severity == IssueSeverity.CRITICAL
                ),
                "high": sum(1 for i in self.issues if i.severity == IssueSeverity.HIGH),
                "medium": sum(
                    1 for i in self.issues if i.severity == IssueSeverity.MEDIUM
                ),
                "low": sum(1 for i in self.issues if i.severity == IssueSeverity.LOW),
                "info": sum(1 for i in self.issues if i.severity == IssueSeverity.INFO),
            },
        }


# ============================================================================
# Input/Output Contracts
# ============================================================================


@dataclass
class ModelValidationInput:
    """
    Input contract for ONEX validation compute node.

    Attributes:
        code_content: Source code content to validate
        file_path: Path to the file being validated
        strict_mode: Enable strict validation (fails on warnings)
        check_naming: Check naming conventions
        check_contracts: Check contract usage
        check_node_type: Check node type compliance
        check_architecture: Check architecture patterns
        correlation_id: Correlation ID for tracing
    """

    code_content: str
    file_path: str
    strict_mode: bool = True
    check_naming: bool = True
    check_contracts: bool = True
    check_node_type: bool = True
    check_architecture: bool = True
    correlation_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class ModelValidationOutput:
    """
    Output contract for ONEX validation compute node.

    Attributes:
        result: Validation result with compliance score and issues
        processing_time_ms: Processing time in milliseconds
        correlation_id: Correlation ID for tracing
        metadata: Additional output metadata
    """

    result: ValidationResult
    processing_time_ms: float
    correlation_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "result": self.result.to_dict(),
            "processing_time_ms": self.processing_time_ms,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


# ============================================================================
# Contract Model (ONEX Standard Base)
# ============================================================================


@dataclass
class ModelContractValidation:
    """
    ONEX Compute contract for validation operations.

    Compute nodes handle:
    - Pure functional operations
    - Deterministic transformations
    - No side effects
    - No external I/O

    Attributes:
        name: Operation name
        description: Operation description
        version: Contract version
        node_type: Fixed as 'compute' for Compute nodes
        correlation_id: Correlation ID for tracing
        created_at: Contract creation timestamp
    """

    name: str = "onex_validation"
    description: str = "ONEX compliance validation operation"
    version: str = "1.0.0"
    node_type: str = "compute"
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate contract after initialization."""
        if self.node_type != "compute":
            raise ValueError(f"Invalid node_type for validation: {self.node_type}")
