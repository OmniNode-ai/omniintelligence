"""
ONEX Contract Models: Quality Gate Orchestration

Purpose: Define contracts for quality gate validation operations
Pattern: ONEX 4-Node Architecture - Contract Models
File: model_contract_quality_gate.py

Track: Track 3-3 - Phase 3 Validation Layer
ONEX Compliant: Contract naming convention (model_contract_*)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ============================================================================
# Enums
# ============================================================================


class EnumGateType(str, Enum):
    """Quality gate types."""

    ONEX_COMPLIANCE = "onex_compliance"
    TEST_COVERAGE = "test_coverage"
    CODE_QUALITY = "code_quality"
    PERFORMANCE = "performance"
    SECURITY = "security"


class EnumGateStatus(str, Enum):
    """Quality gate status."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


class EnumSeverity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ============================================================================
# Base Result Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelResult:
    """
    Standard ONEX result format for all operations.

    Attributes:
        success: Operation success status
        data: Operation result data (optional)
        error: Error message if operation failed (optional)
        metadata: Additional operation metadata (correlation_id, duration_ms, etc.)
    """

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


# ============================================================================
# Base Contract Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelContractBase:
    """
    Base ONEX contract with common fields.

    All ONEX contracts extend this base with:
    - name: Contract/operation identifier
    - version: Contract version for compatibility
    - description: Human-readable operation description
    - correlation_id: Request tracing across services
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    correlation_id: UUID = field(default_factory=uuid4)


# ============================================================================
# Orchestrator Contract Model (ONEX Standard)
# ============================================================================


@dataclass
class ModelContractOrchestrator(ModelContractBase):
    """
    ONEX Orchestrator contract for workflow orchestration.

    Orchestrator nodes handle:
    - Workflow coordination
    - Dependency management
    - Parallel execution
    - Result aggregation

    Attributes:
        operation: Specific operation to execute
        node_type: Fixed as 'orchestrator' for Orchestrator nodes
    """

    operation: str = "orchestrate"
    node_type: str = "orchestrator"


# ============================================================================
# Gate Configuration Models
# ============================================================================


@dataclass
class ModelGateConfig:
    """Configuration for a single quality gate."""

    gate_type: EnumGateType
    enabled: bool = True
    threshold: float = 0.0  # Minimum passing score/percentage
    blocking: bool = True  # Whether failure blocks the pipeline
    timeout_seconds: int = 60
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "gate_type": self.gate_type.value,
            "enabled": self.enabled,
            "threshold": self.threshold,
            "blocking": self.blocking,
            "timeout_seconds": self.timeout_seconds,
            "parameters": self.parameters,
        }


@dataclass
class ModelIssue:
    """Represents a validation issue found by a quality gate."""

    severity: EnumSeverity
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
            "metadata": self.metadata,
        }


# ============================================================================
# Gate Result Models
# ============================================================================


@dataclass
class ModelQualityGateResult:
    """Result from a single quality gate execution."""

    gate_type: EnumGateType
    status: EnumGateStatus
    score: float  # 0.0-1.0 or percentage
    threshold: float
    passed: bool
    blocking: bool
    duration_ms: float
    issues: List[ModelIssue] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "gate_type": self.gate_type.value,
            "status": self.status.value,
            "score": self.score,
            "threshold": self.threshold,
            "passed": self.passed,
            "blocking": self.blocking,
            "duration_ms": self.duration_ms,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
            "metadata": self.metadata,
        }


# ============================================================================
# Quality Gate Contract (Specialized Orchestrator Contract)
# ============================================================================


@dataclass
class ModelContractQualityGate(ModelContractOrchestrator):
    """
    Specialized contract for quality gate orchestration.

    Extends ModelContractOrchestrator with quality gate-specific fields
    for comprehensive validation orchestration.

    Operations:
        - validate: Run all enabled quality gates
        - validate_gate: Run a specific quality gate
        - validate_parallel: Run gates in parallel (default)

    Attributes:
        operation: One of [validate, validate_gate, validate_parallel]
        code_path: Path to code/module to validate
        gate_configs: List of gate configurations to execute
        fail_fast: Stop on first blocking failure
        parallel_execution: Run gates in parallel when possible

    Example - Validate All Gates:
        >>> contract = ModelContractQualityGate(
        ...     name="validate_module",
        ...     operation="validate",
        ...     code_path="/path/to/module.py",
        ...     gate_configs=[
        ...         ModelGateConfig(
        ...             gate_type=EnumGateType.ONEX_COMPLIANCE,
        ...             threshold=0.95,
        ...             blocking=True
        ...         ),
        ...         ModelGateConfig(
        ...             gate_type=EnumGateType.TEST_COVERAGE,
        ...             threshold=0.90,
        ...             blocking=True,
        ...             parameters={"include_branches": True}
        ...         )
        ...     ],
        ...     fail_fast=False,
        ...     parallel_execution=True
        ... )

    Example - Validate Single Gate:
        >>> contract = ModelContractQualityGate(
        ...     name="validate_onex_compliance",
        ...     operation="validate_gate",
        ...     code_path="/path/to/module.py",
        ...     gate_configs=[
        ...         ModelGateConfig(
        ...             gate_type=EnumGateType.ONEX_COMPLIANCE,
        ...             threshold=0.95
        ...         )
        ...     ]
        ... )
    """

    # Quality gate-specific fields
    code_path: str = ""
    gate_configs: List[ModelGateConfig] = field(default_factory=list)
    fail_fast: bool = False
    parallel_execution: bool = True
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate contract after initialization."""
        # Set default name if not provided
        if not self.name:
            self.name = f"quality_gate_{self.operation}"

        # Set default description
        if not self.description:
            self.description = f"Quality gate operation: {self.operation}"

        # Validate operation-specific requirements
        if self.operation in ["validate", "validate_gate", "validate_parallel"]:
            if not self.code_path:
                raise ValueError(
                    f"{self.operation} operation requires 'code_path' field"
                )
            if not self.gate_configs:
                raise ValueError(
                    f"{self.operation} operation requires at least one gate config"
                )

        # Validate gate configs
        if self.operation == "validate_gate" and len(self.gate_configs) > 1:
            raise ValueError("validate_gate operation accepts only one gate config")


# ============================================================================
# Aggregated Results Model
# ============================================================================


@dataclass
class ModelQualityGateAggregatedResult:
    """Aggregated results from all quality gate executions."""

    overall_passed: bool
    total_gates: int
    gates_passed: int
    gates_failed: int
    gates_warned: int
    gates_skipped: int
    blocking_failures: List[EnumGateType] = field(default_factory=list)
    gate_results: List[ModelQualityGateResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "overall_passed": self.overall_passed,
            "total_gates": self.total_gates,
            "gates_passed": self.gates_passed,
            "gates_failed": self.gates_failed,
            "gates_warned": self.gates_warned,
            "gates_skipped": self.gates_skipped,
            "blocking_failures": [gate.value for gate in self.blocking_failures],
            "gate_results": [result.to_dict() for result in self.gate_results],
            "total_duration_ms": self.total_duration_ms,
            "metadata": self.metadata,
        }
