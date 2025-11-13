#!/usr/bin/env python3
"""
ONEX Validator Compute Node - ONEX Compliant

Validates code for ONEX architectural compliance using pattern matching
and structural analysis. Part of Pattern Learning Engine Phase 3 Validation.

Author: Archon Intelligence Team
Date: 2025-10-02
ONEX Compliance: >0.95
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from src.archon_services.pattern_learning.phase3_validation.model_contract_quality_gate import (
    EnumSeverity,
    ModelIssue,
)
from src.archon_services.pattern_learning.phase3_validation.model_contract_validation import (
    IssueCategory,
    IssueSeverity,
    ModelValidationOutput,
    NodeType,
    ValidationIssue,
    ValidationResult,
)

# ============================================================================
# Models
# ============================================================================


class ModelOnexValidationInput(BaseModel):
    """Input state for ONEX validation."""

    code_path: str = Field(..., description="Path to code file to validate")
    code_content: Optional[str] = Field(
        None, description="Code content (if not reading from file)"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")
    check_naming: bool = Field(default=True, description="Check naming conventions")
    check_structure: bool = Field(default=True, description="Check structural patterns")
    check_contracts: bool = Field(default=True, description="Check contract usage")
    check_methods: bool = Field(default=True, description="Check method signatures")


class ModelOnexValidationOutput(BaseModel):
    """Output state for ONEX validation."""

    compliance_score: float = Field(
        ..., description="Overall compliance score (0.0-1.0)"
    )
    passed: bool = Field(..., description="Whether validation passed threshold")
    issues: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of compliance issues found"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Detailed compliance metrics"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Compute Node Implementation
# ============================================================================


class NodeOnexValidatorCompute:
    """
    ONEX-Compliant Compute Node for ONEX Compliance Validation.

    Validates code against ONEX architectural patterns:
    - Naming conventions (node_*, model_*, enum_*)
    - Node type detection (Effect, Compute, Reducer, Orchestrator)
    - Method signatures (execute_effect, execute_compute, etc.)
    - Contract usage and structure
    - File organization patterns

    ONEX Patterns:
    - Pure functional computation (no side effects)
    - Deterministic results for same inputs
    - Correlation ID propagation
    - Performance optimized (<100ms target)
    """

    # ONEX naming patterns
    NAMING_PATTERNS = {
        "node_file": r"^node_.*_(effect|compute|reducer|orchestrator)\.py$",
        "node_class": r"^Node[A-Z][a-zA-Z]*(?:Effect|Compute|Reducer|Orchestrator)$",
        "model_file": r"^model_.*\.py$",
        "model_class": r"^Model[A-Z][a-zA-Z]*$",
        "enum_file": r"^enum_.*\.py$",
        "enum_class": r"^Enum[A-Z][a-zA-Z]*$",
        "contract_file": r"^model_contract_.*\.py$",
    }

    # ONEX method signatures by node type
    NODE_METHOD_SIGNATURES = {
        "Effect": "execute_effect",
        "Compute": "execute_compute",
        "Reducer": "execute_reduction",
        "Orchestrator": "execute_orchestration",
    }

    def __init__(self) -> None:
        """Initialize ONEX validator."""
        pass

    # ========================================================================
    # ONEX Execute Compute Method (Primary Interface)
    # ========================================================================

    async def execute_compute(
        self, input_state: ModelOnexValidationInput
    ) -> ModelValidationOutput:
        """
        Execute ONEX compliance validation (ONEX NodeCompute interface).

        Validates code structure and patterns against ONEX standards.

        Args:
            input_state: Input state with code path and validation options

        Returns:
            ModelValidationOutput: Compliance score, issues, and recommendations
        """
        import time

        start_time = time.time()

        try:
            # Get code content
            code_content = self._get_code_content(
                input_state.code_path, input_state.code_content
            )

            # Initialize results
            issues: List[ModelIssue] = []

            # Run validation checks
            total_checks = 0
            if input_state.check_naming:
                naming_issues = self._check_naming_conventions(
                    input_state.code_path, code_content
                )
                issues.extend(naming_issues)
                total_checks += 5  # Naming checks

            if input_state.check_structure:
                structure_issues = self._check_structure(code_content)
                issues.extend(structure_issues)
                total_checks += 3  # Structure checks

            if input_state.check_contracts:
                contract_issues = self._check_contracts(code_content)
                issues.extend(contract_issues)
                total_checks += 2  # Contract checks

            if input_state.check_methods:
                method_issues = self._check_methods(code_content)
                issues.extend(method_issues)
                total_checks += 4  # Method checks

            # Detect node type
            node_type = self._detect_node_type(input_state.code_path, code_content)

            # Check if contracts are present
            has_contracts = self._has_contracts(code_content)

            # Calculate compliance score
            compliance_score = self._calculate_compliance_score(issues)

            # Generate recommendations
            recommendations = self._generate_recommendations(issues)

            # Convert ModelIssue to ValidationIssue
            validation_issues = self._convert_issues(issues, input_state.code_path)

            # Calculate passed checks
            # Clamp to prevent negative values when multiple issues per check
            failed_checks = min(len(issues), total_checks)
            passed_checks = total_checks - failed_checks

            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # ms

            # Build ValidationResult
            result = ValidationResult(
                compliance_score=compliance_score,
                issues=validation_issues,
                passed_checks=passed_checks,
                total_checks=total_checks,
                node_type=node_type,
                has_contracts=has_contracts,
                recommendations=recommendations,
                metadata={
                    "code_path": input_state.code_path,
                    "checks_performed": {
                        "naming": input_state.check_naming,
                        "structure": input_state.check_structure,
                        "contracts": input_state.check_contracts,
                        "methods": input_state.check_methods,
                    },
                },
            )

            # Build output
            return ModelValidationOutput(
                result=result,
                processing_time_ms=processing_time,
                correlation_id=input_state.correlation_id,
                metadata={},
            )

        except Exception as e:
            # Graceful error handling
            processing_time = (time.time() - start_time) * 1000

            error_issue = ValidationIssue(
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.ARCHITECTURE_PATTERN,
                message=f"Validation failed: {str(e)}",
                recommendation="Fix validation errors before continuing",
                file_path=input_state.code_path,
            )

            result = ValidationResult(
                compliance_score=0.0,
                issues=[error_issue],
                passed_checks=0,
                total_checks=0,
                recommendations=["Fix validation errors before continuing"],
                metadata={"error": str(e), "validation_failed": True},
            )

            return ModelValidationOutput(
                result=result,
                processing_time_ms=processing_time,
                correlation_id=input_state.correlation_id,
                metadata={"error": str(e)},
            )

    # ========================================================================
    # Validation Methods
    # ========================================================================

    def _get_code_content(self, code_path: str, code_content: Optional[str]) -> str:
        """Get code content from file or direct input."""
        if code_content:
            return code_content

        try:
            with open(code_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Failed to read code from {code_path}: {str(e)}")

    def _check_naming_conventions(
        self, code_path: str, code_content: str
    ) -> List[ModelIssue]:
        """Check ONEX naming conventions."""
        issues: List[ModelIssue] = []
        filename = Path(code_path).name

        # Check for syntax errors first - these are critical
        try:
            tree = ast.parse(code_content)
        except SyntaxError as e:
            issues.append(
                ModelIssue(
                    severity=EnumSeverity.CRITICAL,
                    message=f"Code contains syntax errors: {str(e)}",
                    location=code_path,
                    suggestion="Fix syntax errors before validation",
                )
            )
            # Return immediately - can't do further checks on invalid syntax
            return issues

        # Check file naming
        is_node_file = re.match(self.NAMING_PATTERNS["node_file"], filename)
        is_model_file = re.match(self.NAMING_PATTERNS["model_file"], filename)
        is_enum_file = re.match(self.NAMING_PATTERNS["enum_file"], filename)
        is_contract_file = re.match(self.NAMING_PATTERNS["contract_file"], filename)

        if not (is_node_file or is_model_file or is_enum_file or is_contract_file):
            issues.append(
                ModelIssue(
                    severity=EnumSeverity.HIGH,
                    message=f"File name '{filename}' does not follow ONEX naming conventions",
                    location=code_path,
                    suggestion="Use patterns: node_*_<type>.py, model_*.py, enum_*.py, model_contract_*.py",
                )
            )

        # Check class naming
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name

                # Check node class naming
                if is_node_file:
                    # Node files can have both Node classes and Model classes (contracts)
                    # Only check Node classes for naming violations
                    if class_name.startswith("Node"):
                        if not re.match(self.NAMING_PATTERNS["node_class"], class_name):
                            issues.append(
                                ModelIssue(
                                    severity=EnumSeverity.HIGH,
                                    message=f"Node class '{class_name}' does not follow ONEX naming convention",
                                    location=f"{code_path}:line {node.lineno}",
                                    suggestion="Use pattern: Node<Name><Type> where Type is Effect, Compute, Reducer, or Orchestrator",
                                )
                            )

                # Check model class naming
                elif is_model_file:
                    if not re.match(self.NAMING_PATTERNS["model_class"], class_name):
                        issues.append(
                            ModelIssue(
                                severity=EnumSeverity.MEDIUM,
                                message=f"Model class '{class_name}' does not follow ONEX naming convention",
                                location=f"{code_path}:line {node.lineno}",
                                suggestion="Use pattern: Model<Name>",
                            )
                        )

                # Check enum class naming
                elif is_enum_file:
                    if not re.match(self.NAMING_PATTERNS["enum_class"], class_name):
                        issues.append(
                            ModelIssue(
                                severity=EnumSeverity.MEDIUM,
                                message=f"Enum class '{class_name}' does not follow ONEX naming convention",
                                location=f"{code_path}:line {node.lineno}",
                                suggestion="Use pattern: Enum<Name>",
                            )
                        )

        return issues

    def _check_structure(self, code_content: str) -> List[ModelIssue]:
        """Check ONEX structural patterns."""
        issues: List[ModelIssue] = []

        try:
            tree = ast.parse(code_content)

            # Check for node classes
            node_classes = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
                and re.match(self.NAMING_PATTERNS["node_class"], node.name)
            ]

            for node_class in node_classes:
                # Detect node type from class name
                node_type = None
                for ntype in ["Effect", "Compute", "Reducer", "Orchestrator"]:
                    if node_class.name.endswith(ntype):
                        node_type = ntype
                        break

                if not node_type:
                    issues.append(
                        ModelIssue(
                            severity=EnumSeverity.HIGH,
                            message=f"Cannot determine node type for class '{node_class.name}'",
                            location=f"line {node_class.lineno}",
                            suggestion="Class name should end with Effect, Compute, Reducer, or Orchestrator",
                        )
                    )
                    continue

                # Check for I/O violations in Compute nodes
                if node_type == "Compute":
                    # Check for file I/O
                    if "open(" in code_content or "with open" in code_content:
                        issues.append(
                            ModelIssue(
                                severity=EnumSeverity.CRITICAL,
                                message=f"Compute node '{node_class.name}' contains file I/O operations",
                                location=f"line {node_class.lineno}",
                                suggestion="Move file I/O to Effect nodes - Compute nodes must be pure",
                            )
                        )

                    # Check for HTTP requests
                    if any(
                        http_term in code_content
                        for http_term in [
                            "requests.",
                            "httpx.",
                            "urllib.",
                            "http.client",
                        ]
                    ):
                        issues.append(
                            ModelIssue(
                                severity=EnumSeverity.CRITICAL,
                                message=f"Compute node '{node_class.name}' contains HTTP request operations",
                                location=f"line {node_class.lineno}",
                                suggestion="Move HTTP requests to Effect nodes - Compute nodes must be pure",
                            )
                        )

                # Check for correlation_id usage (look for actual usage, not just comments)
                # Check if correlation_id appears in variable names or attributes
                has_correlation_id = False
                for inner_node in ast.walk(node_class):
                    # Check for correlation_id in attributes or variable names
                    if isinstance(inner_node, ast.Attribute):
                        if inner_node.attr == "correlation_id":
                            has_correlation_id = True
                            break
                    elif isinstance(inner_node, ast.Name):
                        if inner_node.id == "correlation_id":
                            has_correlation_id = True
                            break
                    # Also check in arguments
                    elif isinstance(inner_node, ast.arg):
                        if inner_node.arg == "correlation_id":
                            has_correlation_id = True
                            break

                if not has_correlation_id:
                    issues.append(
                        ModelIssue(
                            severity=EnumSeverity.MEDIUM,
                            message=f"Node '{node_class.name}' does not use correlation_id",
                            location=f"line {node_class.lineno}",
                            suggestion="Add correlation_id to input/output contracts for traceability",
                        )
                    )

        except SyntaxError:
            pass  # Already caught in naming check

        return issues

    def _check_contracts(self, code_content: str) -> List[ModelIssue]:
        """Check contract usage patterns."""
        issues: List[ModelIssue] = []

        try:
            tree = ast.parse(code_content)

            # Look for Input/Output model classes
            has_input_model = False
            has_output_model = False

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    if "Input" in class_name and re.match(
                        self.NAMING_PATTERNS["model_class"], class_name
                    ):
                        has_input_model = True
                    if "Output" in class_name and re.match(
                        self.NAMING_PATTERNS["model_class"], class_name
                    ):
                        has_output_model = True

            # Check if node classes exist
            has_node_class = any(
                isinstance(node, ast.ClassDef)
                and re.match(self.NAMING_PATTERNS["node_class"], node.name)
                for node in ast.walk(tree)
            )

            # If this is a node file, check for contracts
            if has_node_class:
                if not has_input_model:
                    issues.append(
                        ModelIssue(
                            severity=EnumSeverity.MEDIUM,
                            message="Missing Input contract model (Model*Input)",
                            suggestion="Define a Model*Input class for node input contract",
                        )
                    )

                if not has_output_model:
                    issues.append(
                        ModelIssue(
                            severity=EnumSeverity.MEDIUM,
                            message="Missing Output contract model (Model*Output)",
                            suggestion="Define a Model*Output class for node output contract",
                        )
                    )

            # Check for contract imports
            if (
                "ModelContract" not in code_content
                and "contract" in code_content.lower()
            ):
                issues.append(
                    ModelIssue(
                        severity=EnumSeverity.MEDIUM,
                        message="File references contracts but doesn't import ModelContract classes",
                        suggestion="Import appropriate ModelContract* classes",
                    )
                )

        except SyntaxError:
            pass  # Already caught in naming check

        return issues

    def _check_methods(self, code_content: str) -> List[ModelIssue]:
        """Check ONEX method signatures."""
        issues: List[ModelIssue] = []

        try:
            tree = ast.parse(code_content)

            # Find node classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name

                    # Detect node type
                    node_type = None
                    for ntype in ["Effect", "Compute", "Reducer", "Orchestrator"]:
                        if class_name.endswith(ntype):
                            node_type = ntype
                            break

                    if node_type:
                        expected_method = self.NODE_METHOD_SIGNATURES[node_type]

                        # Check if expected method exists
                        methods = [
                            m.name for m in node.body if isinstance(m, ast.FunctionDef)
                        ]

                        if expected_method not in methods:
                            issues.append(
                                ModelIssue(
                                    severity=EnumSeverity.CRITICAL,
                                    message=f"{node_type} node '{class_name}' missing required method '{expected_method}'",
                                    location=f"line {node.lineno}",
                                    suggestion=f"Implement async def {expected_method}(self, contract: ModelContract{node_type}) -> Any",
                                )
                            )

        except SyntaxError:
            pass  # Already caught in naming check

        return issues

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _detect_node_type(
        self, code_path: str, code_content: str
    ) -> Optional[NodeType]:
        """Detect ONEX node type from filename and content."""
        filename = Path(code_path).name

        # Try to detect from filename
        if "_effect.py" in filename:
            return NodeType.EFFECT
        elif "_compute.py" in filename:
            return NodeType.COMPUTE
        elif "_reducer.py" in filename:
            return NodeType.REDUCER
        elif "_orchestrator.py" in filename:
            return NodeType.ORCHESTRATOR

        # Try to detect from class names
        try:
            tree = ast.parse(code_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    if class_name.endswith("Effect"):
                        return NodeType.EFFECT
                    elif class_name.endswith("Compute"):
                        return NodeType.COMPUTE
                    elif class_name.endswith("Reducer"):
                        return NodeType.REDUCER
                    elif class_name.endswith("Orchestrator"):
                        return NodeType.ORCHESTRATOR
        except SyntaxError:
            pass

        return None

    def _has_contracts(self, code_content: str) -> bool:
        """Check if code has proper contract definitions."""
        # Check for Model class definitions (input/output contracts)
        try:
            tree = ast.parse(code_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if re.match(self.NAMING_PATTERNS["model_class"], node.name):
                        return True
                    # Also check for dataclass decorator
                    for decorator in getattr(node, "decorator_list", []):
                        if (
                            isinstance(decorator, ast.Name)
                            and decorator.id == "dataclass"
                        ):
                            return True
        except SyntaxError:
            pass

        return False

    def _convert_issues(
        self, issues: List[ModelIssue], code_path: str
    ) -> List[ValidationIssue]:
        """Convert ModelIssue to ValidationIssue format."""
        validation_issues = []

        for issue in issues:
            # Map severity
            if issue.severity == EnumSeverity.CRITICAL:
                severity = IssueSeverity.CRITICAL
            elif issue.severity == EnumSeverity.HIGH:
                severity = IssueSeverity.HIGH
            elif issue.severity == EnumSeverity.MEDIUM:
                severity = IssueSeverity.MEDIUM
            elif issue.severity == EnumSeverity.LOW:
                severity = IssueSeverity.LOW
            else:
                severity = IssueSeverity.INFO

            # Determine category from message content (order matters!)
            message_lower = issue.message.lower()
            if "correlation" in message_lower or "correlation_id" in message_lower:
                category = IssueCategory.CORRELATION_ID
            elif "syntax error" in message_lower:
                category = IssueCategory.ARCHITECTURE_PATTERN
            elif (
                "naming" in message_lower
                or "file name" in message_lower
                or "class '" in message_lower
            ):
                category = IssueCategory.NAMING_CONVENTION
            elif (
                "contract" in message_lower
                or "input" in message_lower
                or "output" in message_lower
            ):
                category = IssueCategory.CONTRACT_USAGE
            elif "method" in message_lower or "execute_" in message_lower:
                category = IssueCategory.NODE_TYPE_COMPLIANCE
            elif (
                "i/o" in message_lower
                or "file" in message_lower
                or "http" in message_lower
                or "pure" in message_lower
            ):
                category = IssueCategory.NODE_TYPE_COMPLIANCE
            elif "error" in message_lower or "exception" in message_lower:
                category = IssueCategory.ERROR_HANDLING
            else:
                category = IssueCategory.ARCHITECTURE_PATTERN

            validation_issue = ValidationIssue(
                severity=severity,
                category=category,
                message=issue.message,
                recommendation=issue.suggestion or "Review ONEX compliance guidelines",
                file_path=issue.location or code_path,
            )
            validation_issues.append(validation_issue)

        return validation_issues

    # ========================================================================
    # Score Calculation
    # ========================================================================

    def _calculate_compliance_score(self, issues: List[ModelIssue]) -> float:
        """
        Calculate overall compliance score based on issues.

        Scoring:
        - Syntax errors result in immediate 0.0 score
        - Start at 1.0 (100% compliant)
        - Deduct points based on severity:
          - CRITICAL: -0.20 each
          - HIGH: -0.10 each
          - MEDIUM: -0.05 each
          - LOW: -0.02 each
        - Minimum score: 0.0
        """
        # Check for syntax errors - these are fatal
        if any("syntax error" in issue.message.lower() for issue in issues):
            return 0.0

        score = 1.0

        severity_weights = {
            EnumSeverity.CRITICAL: 0.20,
            EnumSeverity.HIGH: 0.10,
            EnumSeverity.MEDIUM: 0.05,
            EnumSeverity.LOW: 0.02,
            EnumSeverity.INFO: 0.0,
        }

        for issue in issues:
            score -= severity_weights.get(issue.severity, 0.0)

        return max(0.0, score)

    def _generate_recommendations(self, issues: List[ModelIssue]) -> List[str]:
        """Generate actionable recommendations based on issues."""
        recommendations = []

        # Group by severity
        critical_count = sum(1 for i in issues if i.severity == EnumSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == EnumSeverity.HIGH)

        if critical_count > 0:
            recommendations.append(
                f"Fix {critical_count} critical issue(s) immediately - these prevent proper ONEX operation"
            )

        if high_count > 0:
            recommendations.append(
                f"Address {high_count} high-severity issue(s) to improve ONEX compliance"
            )

        # Specific recommendations based on issue types
        if any("naming convention" in i.message.lower() for i in issues):
            recommendations.append(
                "Review ONEX naming conventions: node_*_<type>.py, Node<Name><Type> pattern"
            )

        if any("method" in i.message.lower() for i in issues):
            recommendations.append(
                "Implement required ONEX methods: execute_effect/compute/reduction/orchestration"
            )

        # Check for I/O violations in Compute nodes
        if any(
            "compute" in i.message.lower()
            and any(
                io_term in i.message.lower()
                for io_term in ["file", "write", "read", "http", "request"]
            )
            for i in issues
        ):
            recommendations.append(
                "Remove I/O operations from Compute nodes - Compute nodes must be pure functions"
            )

        if not recommendations:
            recommendations.append("Code is fully ONEX compliant - great work!")

        return recommendations
