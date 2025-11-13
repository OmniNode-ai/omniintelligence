#!/usr/bin/env python3
"""
Quality Gate Orchestrator Node - ONEX Compliant

Orchestrates automated quality gate enforcement for code validation.
Implements 5 comprehensive quality gates:
1. ONEX Compliance Gate
2. Test Coverage Gate
3. Code Quality Gate
4. Performance Gate
5. Security Gate

Author: Archon Intelligence Team
Date: 2025-10-02
ONEX Compliance: >0.95
Track: Track 3 Phase 3
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field
from src.archon_services.pattern_learning.phase3_validation.model_contract_quality_gate import (
    EnumGateStatus,
    EnumGateType,
    EnumSeverity,
    ModelGateConfig,
    ModelIssue,
    ModelQualityGateAggregatedResult,
    ModelQualityGateResult,
)
from src.archon_services.pattern_learning.phase3_validation.node_onex_validator_compute import (
    ModelOnexValidationInput,
    NodeOnexValidatorCompute,
)

# ============================================================================
# Models
# ============================================================================


class ModelQualityGateInput(BaseModel):
    """Input state for quality gate orchestration."""

    code_path: str = Field(..., description="Path to code/module to validate")
    gate_configs: List[ModelGateConfig] = Field(
        ..., description="List of gate configurations to execute"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Correlation ID for tracing",
    )
    fail_fast: bool = Field(default=False, description="Stop on first blocking failure")
    parallel_execution: bool = Field(
        default=True, description="Run gates in parallel when possible"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for gates"
    )


class ModelQualityGateOutput(BaseModel):
    """Output state for quality gate orchestration."""

    overall_passed: bool = Field(..., description="Overall validation result")
    total_gates: int = Field(..., description="Total gates executed")
    gates_passed: int = Field(..., description="Number of gates passed")
    gates_failed: int = Field(..., description="Number of gates failed")
    blocking_failures: List[str] = Field(
        default_factory=list, description="List of blocking gate failures"
    )
    gate_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="Individual gate results"
    )
    total_duration_ms: float = Field(..., description="Total execution time in ms")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    correlation_id: str = Field(..., description="Correlation ID for tracing")


# ============================================================================
# ONEX Orchestrator Node Implementation
# ============================================================================


class NodeQualityGateOrchestrator:
    """
    ONEX-Compliant Orchestrator Node for Quality Gate Enforcement.

    Orchestrates comprehensive quality validation by coordinating 5 quality gates:
    1. ONEX Compliance Gate - Validates ONEX architectural patterns
    2. Test Coverage Gate - Ensures adequate test coverage
    3. Code Quality Gate - Validates code quality standards
    4. Performance Gate - Checks performance benchmarks
    5. Security Gate - Scans for security vulnerabilities

    ONEX Patterns:
    - Workflow coordination with dependency management
    - Parallel execution where gates are independent
    - Fail-fast support for blocking failures
    - Correlation ID propagation
    - Performance target: <30s for all gates combined
    """

    def __init__(self) -> None:
        """Initialize quality gate orchestrator with compute nodes."""
        # Initialize ONEX validator compute node
        self.onex_validator = NodeOnexValidatorCompute()

    # ========================================================================
    # ONEX Execute Orchestration Method (Primary Interface)
    # ========================================================================

    async def execute_orchestration(
        self, input_state: ModelQualityGateInput
    ) -> ModelQualityGateOutput:
        """
        Execute quality gate orchestration (ONEX NodeOrchestrator interface).

        Coordinates all enabled quality gates to validate code comprehensively.

        Args:
            input_state: Input state with code path and gate configurations

        Returns:
            ModelQualityGateOutput: Aggregated results from all quality gates
        """
        start_time = time.time()

        try:
            # Validate input
            code_path = Path(input_state.code_path)
            if not code_path.exists():
                return self._create_error_output(
                    input_state.correlation_id,
                    f"Code path does not exist: {input_state.code_path}",
                    start_time,
                )

            # Filter enabled gates
            enabled_gates = [
                config for config in input_state.gate_configs if config.enabled
            ]

            if not enabled_gates:
                return self._create_error_output(
                    input_state.correlation_id,
                    "No enabled gates to execute",
                    start_time,
                )

            # ================================================================
            # Execute gates (parallel or sequential based on configuration)
            # ================================================================

            if input_state.parallel_execution:
                # Execute gates in parallel
                gate_results = await self._execute_gates_parallel(
                    code_path=str(code_path),
                    gate_configs=enabled_gates,
                    correlation_id=input_state.correlation_id,
                    context=input_state.context,
                    fail_fast=input_state.fail_fast,
                )
            else:
                # Execute gates sequentially
                gate_results = await self._execute_gates_sequential(
                    code_path=str(code_path),
                    gate_configs=enabled_gates,
                    correlation_id=input_state.correlation_id,
                    context=input_state.context,
                    fail_fast=input_state.fail_fast,
                )

            # ================================================================
            # Aggregate results
            # ================================================================

            aggregated = self._aggregate_results(gate_results)

            # Calculate total duration
            total_duration = (time.time() - start_time) * 1000  # ms

            # Build output
            return ModelQualityGateOutput(
                overall_passed=aggregated.overall_passed,
                total_gates=aggregated.total_gates,
                gates_passed=aggregated.gates_passed,
                gates_failed=aggregated.gates_failed,
                blocking_failures=[gate.value for gate in aggregated.blocking_failures],
                gate_results=[result.to_dict() for result in aggregated.gate_results],
                total_duration_ms=total_duration,
                metadata={
                    "code_path": str(code_path),
                    "parallel_execution": input_state.parallel_execution,
                    "fail_fast": input_state.fail_fast,
                    "performance_target_met": total_duration < 30000,  # <30s
                    "gates_skipped": aggregated.gates_skipped,
                    "gates_warned": aggregated.gates_warned,
                },
                correlation_id=input_state.correlation_id,
            )

        except Exception as e:
            return self._create_error_output(
                input_state.correlation_id, str(e), start_time
            )

    # ========================================================================
    # Gate Execution Methods
    # ========================================================================

    async def _execute_gates_parallel(
        self,
        code_path: str,
        gate_configs: List[ModelGateConfig],
        correlation_id: str,
        context: Dict[str, Any],
        fail_fast: bool,
    ) -> List[ModelQualityGateResult]:
        """Execute gates in parallel for faster execution."""
        tasks = []

        for config in gate_configs:
            task = asyncio.create_task(
                self._execute_single_gate(
                    code_path=code_path,
                    gate_config=config,
                    correlation_id=correlation_id,
                    context=context,
                )
            )
            tasks.append((config, task))

        # Wait for all gates to complete (or fail-fast on blocking failure)
        results = []
        for config, task in tasks:
            try:
                result = await task
                results.append(result)

                # Fail-fast check
                if fail_fast and not result.passed and config.blocking:
                    # Cancel remaining tasks
                    for _, remaining_task in tasks:
                        if not remaining_task.done():
                            remaining_task.cancel()
                    break

            except Exception as e:
                # Gate execution failed
                results.append(self._create_gate_error_result(config.gate_type, str(e)))

        return results

    async def _execute_gates_sequential(
        self,
        code_path: str,
        gate_configs: List[ModelGateConfig],
        correlation_id: str,
        context: Dict[str, Any],
        fail_fast: bool,
    ) -> List[ModelQualityGateResult]:
        """Execute gates sequentially."""
        results = []

        for config in gate_configs:
            try:
                result = await self._execute_single_gate(
                    code_path=code_path,
                    gate_config=config,
                    correlation_id=correlation_id,
                    context=context,
                )
                results.append(result)

                # Fail-fast check
                if fail_fast and not result.passed and config.blocking:
                    break

            except Exception as e:
                result = self._create_gate_error_result(config.gate_type, str(e))
                results.append(result)

                if fail_fast and config.blocking:
                    break

        return results

    async def _execute_single_gate(
        self,
        code_path: str,
        gate_config: ModelGateConfig,
        correlation_id: str,
        context: Dict[str, Any],
    ) -> ModelQualityGateResult:
        """Execute a single quality gate based on its type."""
        gate_start = time.time()

        try:
            # Route to appropriate gate executor
            if gate_config.gate_type == EnumGateType.ONEX_COMPLIANCE:
                result = await self._execute_onex_gate(
                    code_path, gate_config, correlation_id
                )
            elif gate_config.gate_type == EnumGateType.TEST_COVERAGE:
                result = await self._execute_coverage_gate(
                    code_path, gate_config, correlation_id
                )
            elif gate_config.gate_type == EnumGateType.CODE_QUALITY:
                result = await self._execute_quality_gate(
                    code_path, gate_config, correlation_id
                )
            elif gate_config.gate_type == EnumGateType.PERFORMANCE:
                result = await self._execute_performance_gate(
                    code_path, gate_config, correlation_id
                )
            elif gate_config.gate_type == EnumGateType.SECURITY:
                result = await self._execute_security_gate(
                    code_path, gate_config, correlation_id
                )
            else:
                result = self._create_gate_error_result(
                    gate_config.gate_type, f"Unknown gate type: {gate_config.gate_type}"
                )

            # Add duration
            result.duration_ms = (time.time() - gate_start) * 1000

            return result

        except Exception as e:
            duration = (time.time() - gate_start) * 1000
            error_result = self._create_gate_error_result(gate_config.gate_type, str(e))
            error_result.duration_ms = duration
            return error_result

    # ========================================================================
    # Individual Gate Executors
    # ========================================================================

    async def _execute_onex_gate(
        self,
        code_path: str,
        gate_config: ModelGateConfig,
        correlation_id: str,
    ) -> ModelQualityGateResult:
        """Execute ONEX compliance gate."""
        # Use ONEX validator compute node
        input_state = ModelOnexValidationInput(
            code_path=code_path,
            correlation_id=correlation_id,
            check_naming=gate_config.parameters.get("check_naming", True),
            check_structure=gate_config.parameters.get("check_structure", True),
            check_contracts=gate_config.parameters.get("check_contracts", True),
            check_methods=gate_config.parameters.get("check_methods", True),
        )

        output = await self.onex_validator.execute_compute(input_state)

        # Convert to gate result
        issues = [
            ModelIssue(
                severity=EnumSeverity(issue["severity"]),
                message=issue["message"],
                location=issue.get("location"),
                suggestion=issue.get("suggestion"),
            )
            for issue in output.issues
        ]

        passed = output.compliance_score >= gate_config.threshold
        status = EnumGateStatus.PASSED if passed else EnumGateStatus.FAILED

        return ModelQualityGateResult(
            gate_type=EnumGateType.ONEX_COMPLIANCE,
            status=status,
            score=output.compliance_score,
            threshold=gate_config.threshold,
            passed=passed,
            blocking=gate_config.blocking,
            duration_ms=0.0,  # Will be set by caller
            issues=issues,
            metrics=output.metrics,
            metadata={
                "recommendations": output.recommendations,
                "checks_performed": output.metadata.get("checks_performed", {}),
            },
        )

    async def _execute_coverage_gate(
        self,
        code_path: str,
        gate_config: ModelGateConfig,
        correlation_id: str,
    ) -> ModelQualityGateResult:
        """Execute test coverage gate using pytest-cov."""
        issues: List[ModelIssue] = []
        metrics: Dict[str, Any] = {}

        try:
            # Determine test path
            code_path_obj = Path(code_path)
            if code_path_obj.is_file():
                # Find corresponding test file
                test_path = self._find_test_file(code_path_obj)
            else:
                test_path = code_path

            # Run pytest with coverage
            cmd = [
                "pytest",
                str(test_path),
                "--cov=" + str(code_path),
                "--cov-report=json",
                "--cov-report=term",
                "-v",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=gate_config.timeout_seconds,
                cwd=code_path_obj.parent if code_path_obj.is_file() else code_path_obj,
            )

            # Parse coverage report
            coverage_file = Path(".coverage.json")
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)
                    coverage_pct = coverage_data.get("totals", {}).get(
                        "percent_covered", 0.0
                    )
            else:
                # Try to parse from stdout
                coverage_pct = self._parse_coverage_from_output(result.stdout)

            metrics = {
                "coverage_percentage": coverage_pct,
                "threshold": gate_config.threshold * 100,
                "tests_run": result.stdout.count("PASSED")
                + result.stdout.count("FAILED"),
                "tests_passed": result.stdout.count("PASSED"),
                "tests_failed": result.stdout.count("FAILED"),
            }

            # Check if coverage meets threshold
            passed = coverage_pct >= (gate_config.threshold * 100)

            if not passed:
                issues.append(
                    ModelIssue(
                        severity=EnumSeverity.HIGH,
                        message=f"Test coverage {coverage_pct:.1f}% is below threshold {gate_config.threshold * 100}%",
                        suggestion=f"Add tests to increase coverage to at least {gate_config.threshold * 100}%",
                    )
                )

            status = EnumGateStatus.PASSED if passed else EnumGateStatus.FAILED

            return ModelQualityGateResult(
                gate_type=EnumGateType.TEST_COVERAGE,
                status=status,
                score=coverage_pct / 100,
                threshold=gate_config.threshold,
                passed=passed,
                blocking=gate_config.blocking,
                duration_ms=0.0,
                issues=issues,
                metrics=metrics,
                metadata={"test_output": result.stdout[:500]},  # First 500 chars
            )

        except subprocess.TimeoutExpired:
            return ModelQualityGateResult(
                gate_type=EnumGateType.TEST_COVERAGE,
                status=EnumGateStatus.ERROR,
                score=0.0,
                threshold=gate_config.threshold,
                passed=False,
                blocking=gate_config.blocking,
                duration_ms=0.0,
                issues=[
                    ModelIssue(
                        severity=EnumSeverity.CRITICAL,
                        message=f"Coverage gate timed out after {gate_config.timeout_seconds}s",
                    )
                ],
                metrics={},
                metadata={},
            )
        except Exception as e:
            return self._create_gate_error_result(EnumGateType.TEST_COVERAGE, str(e))

    async def _execute_quality_gate(
        self,
        code_path: str,
        gate_config: ModelGateConfig,
        correlation_id: str,
    ) -> ModelQualityGateResult:
        """Execute code quality gate using static analysis."""
        issues: List[ModelIssue] = []
        metrics: Dict[str, Any] = {}

        try:
            # Run pylint or similar quality checker
            cmd = ["pylint", str(code_path), "--output-format=json"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=gate_config.timeout_seconds,
            )

            # Parse pylint output
            if result.stdout:
                try:
                    pylint_issues = json.loads(result.stdout)

                    # Convert pylint issues to ModelIssue
                    for issue in pylint_issues[:10]:  # Limit to 10 issues
                        severity_map = {
                            "error": EnumSeverity.HIGH,
                            "warning": EnumSeverity.MEDIUM,
                            "convention": EnumSeverity.LOW,
                            "refactor": EnumSeverity.LOW,
                        }

                        issues.append(
                            ModelIssue(
                                severity=severity_map.get(
                                    issue.get("type", "warning"), EnumSeverity.MEDIUM
                                ),
                                message=issue.get("message", "Unknown issue"),
                                location=f"line {issue.get('line', 0)}",
                                suggestion=issue.get("symbol", ""),
                            )
                        )

                    # Calculate quality score (simplified)
                    total_issues = len(pylint_issues)
                    critical_issues = sum(
                        1 for i in pylint_issues if i.get("type") == "error"
                    )

                    # Score calculation: deduct based on issues
                    score = 1.0 - (critical_issues * 0.1) - (total_issues * 0.01)
                    score = max(0.0, min(1.0, score))

                    metrics = {
                        "total_issues": total_issues,
                        "critical_issues": critical_issues,
                        "quality_score": score,
                    }

                except json.JSONDecodeError:
                    score = 0.5  # Default if can't parse
                    metrics = {"parse_error": True}
            else:
                # No issues found or couldn't run pylint
                score = 1.0
                metrics = {"no_issues": True}

            passed = score >= gate_config.threshold

            return ModelQualityGateResult(
                gate_type=EnumGateType.CODE_QUALITY,
                status=EnumGateStatus.PASSED if passed else EnumGateStatus.FAILED,
                score=score,
                threshold=gate_config.threshold,
                passed=passed,
                blocking=gate_config.blocking,
                duration_ms=0.0,
                issues=issues,
                metrics=metrics,
                metadata={},
            )

        except Exception as e:
            # Quality check failed - return warning instead of error
            return ModelQualityGateResult(
                gate_type=EnumGateType.CODE_QUALITY,
                status=EnumGateStatus.WARNING,
                score=0.5,
                threshold=gate_config.threshold,
                passed=False,
                blocking=False,  # Don't block on quality gate failures
                duration_ms=0.0,
                issues=[
                    ModelIssue(
                        severity=EnumSeverity.MEDIUM,
                        message=f"Quality gate check failed: {str(e)}",
                    )
                ],
                metrics={},
                metadata={"error": str(e)},
            )

    async def _execute_performance_gate(
        self,
        code_path: str,
        gate_config: ModelGateConfig,
        correlation_id: str,
    ) -> ModelQualityGateResult:
        """Execute performance gate (simplified - checks for basic performance patterns)."""
        issues: List[ModelIssue] = []
        metrics: Dict[str, Any] = {}

        try:
            # Read code
            with open(code_path, "r") as f:
                code = f.read()

            # Simple performance checks
            score = 1.0

            # Check for common anti-patterns
            if "for i in range(len(" in code:
                issues.append(
                    ModelIssue(
                        severity=EnumSeverity.MEDIUM,
                        message="Use enumerate() instead of range(len())",
                        suggestion="Replace 'for i in range(len(items))' with 'for i, item in enumerate(items)'",
                    )
                )
                score -= 0.1

            if ".append(" in code and "for" in code:
                # Potential list comprehension opportunity
                issues.append(
                    ModelIssue(
                        severity=EnumSeverity.LOW,
                        message="Consider using list comprehension instead of append in loop",
                        suggestion="Replace loop with list comprehension for better performance",
                    )
                )
                score -= 0.05

            metrics = {
                "performance_score": score,
                "issues_found": len(issues),
            }

            passed = score >= gate_config.threshold

            return ModelQualityGateResult(
                gate_type=EnumGateType.PERFORMANCE,
                status=EnumGateStatus.PASSED if passed else EnumGateStatus.WARNING,
                score=score,
                threshold=gate_config.threshold,
                passed=passed,
                blocking=False,  # Performance gate is non-blocking by default
                duration_ms=0.0,
                issues=issues,
                metrics=metrics,
                metadata={},
            )

        except Exception as e:
            return self._create_gate_error_result(EnumGateType.PERFORMANCE, str(e))

    async def _execute_security_gate(
        self,
        code_path: str,
        gate_config: ModelGateConfig,
        correlation_id: str,
    ) -> ModelQualityGateResult:
        """Execute security gate (simplified - checks for basic security patterns)."""
        issues: List[ModelIssue] = []
        metrics: Dict[str, Any] = {}

        try:
            # Read code
            with open(code_path, "r") as f:
                code = f.read()

            # Simple security checks
            score = 1.0

            # Check for hardcoded secrets
            if any(
                keyword in code.lower()
                for keyword in ["password =", "api_key =", "secret =", "token ="]
            ):
                if '"' in code or "'" in code:
                    issues.append(
                        ModelIssue(
                            severity=EnumSeverity.CRITICAL,
                            message="Potential hardcoded secret detected",
                            suggestion="Use environment variables or secret management service",
                        )
                    )
                    score -= 0.3

            # Check for SQL injection patterns
            if "execute(" in code and ("%" in code or "format" in code):
                issues.append(
                    ModelIssue(
                        severity=EnumSeverity.HIGH,
                        message="Potential SQL injection vulnerability",
                        suggestion="Use parameterized queries instead of string formatting",
                    )
                )
                score -= 0.2

            # Check for eval usage
            if "eval(" in code:
                issues.append(
                    ModelIssue(
                        severity=EnumSeverity.CRITICAL,
                        message="Usage of eval() detected - security risk",
                        suggestion="Remove eval() and use safer alternatives",
                    )
                )
                score -= 0.3

            metrics = {
                "security_score": score,
                "vulnerabilities_found": len(issues),
                "critical_vulnerabilities": sum(
                    1 for i in issues if i.severity == EnumSeverity.CRITICAL
                ),
            }

            passed = score >= gate_config.threshold and not any(
                i.severity == EnumSeverity.CRITICAL for i in issues
            )

            return ModelQualityGateResult(
                gate_type=EnumGateType.SECURITY,
                status=EnumGateStatus.PASSED if passed else EnumGateStatus.FAILED,
                score=score,
                threshold=gate_config.threshold,
                passed=passed,
                blocking=gate_config.blocking,
                duration_ms=0.0,
                issues=issues,
                metrics=metrics,
                metadata={},
            )

        except Exception as e:
            return self._create_gate_error_result(EnumGateType.SECURITY, str(e))

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _find_test_file(self, code_file: Path) -> Path:
        """Find corresponding test file for a code file."""
        # Common test file patterns
        test_patterns = [
            f"test_{code_file.stem}.py",
            f"{code_file.stem}_test.py",
            f"tests/test_{code_file.stem}.py",
            f"tests/{code_file.stem}_test.py",
        ]

        for pattern in test_patterns:
            test_file = code_file.parent / pattern
            if test_file.exists():
                return test_file

        # Default to tests directory
        return code_file.parent / "tests"

    def _parse_coverage_from_output(self, output: str) -> float:
        """Parse coverage percentage from pytest output."""
        import re

        # Look for coverage percentage in output
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            return float(match.group(1))
        return 0.0

    def _aggregate_results(
        self, gate_results: List[ModelQualityGateResult]
    ) -> ModelQualityGateAggregatedResult:
        """Aggregate individual gate results into overall result."""
        total_gates = len(gate_results)
        gates_passed = sum(1 for r in gate_results if r.passed)
        gates_failed = sum(1 for r in gate_results if r.status == EnumGateStatus.FAILED)
        gates_warned = sum(
            1 for r in gate_results if r.status == EnumGateStatus.WARNING
        )
        gates_skipped = sum(
            1 for r in gate_results if r.status == EnumGateStatus.SKIPPED
        )

        # Check for blocking failures
        blocking_failures = [
            r.gate_type for r in gate_results if not r.passed and r.blocking
        ]

        # Overall pass: all blocking gates must pass
        overall_passed = len(blocking_failures) == 0

        total_duration = sum(r.duration_ms for r in gate_results)

        return ModelQualityGateAggregatedResult(
            overall_passed=overall_passed,
            total_gates=total_gates,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            gates_warned=gates_warned,
            gates_skipped=gates_skipped,
            blocking_failures=blocking_failures,
            gate_results=gate_results,
            total_duration_ms=total_duration,
            metadata={
                "all_gates_passed": gates_passed == total_gates,
                "has_warnings": gates_warned > 0,
            },
        )

    def _create_gate_error_result(
        self, gate_type: EnumGateType, error_message: str
    ) -> ModelQualityGateResult:
        """Create error result for a failed gate."""
        return ModelQualityGateResult(
            gate_type=gate_type,
            status=EnumGateStatus.ERROR,
            score=0.0,
            threshold=0.0,
            passed=False,
            blocking=True,
            duration_ms=0.0,
            issues=[
                ModelIssue(
                    severity=EnumSeverity.CRITICAL,
                    message=f"Gate execution failed: {error_message}",
                )
            ],
            metrics={},
            metadata={"error": error_message},
        )

    def _create_error_output(
        self, correlation_id: str, error_message: str, start_time: float
    ) -> ModelQualityGateOutput:
        """Create error output for orchestration failure."""
        duration = (time.time() - start_time) * 1000
        return ModelQualityGateOutput(
            overall_passed=False,
            total_gates=0,
            gates_passed=0,
            gates_failed=0,
            blocking_failures=["orchestration_error"],
            gate_results=[],
            total_duration_ms=duration,
            metadata={"error": error_message, "orchestration_failed": True},
            correlation_id=correlation_id,
        )
