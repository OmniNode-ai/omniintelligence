# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Session check result models for the evidence collection node (OMN-2578).

These models represent the structured, ledger-backed outputs from the agent
execution pipeline. They are the raw inputs to the EvidenceCollector and
are the only valid sources for constructing EvidenceItems.

Design constraints:
    - All models are frozen (immutable after construction).
    - All numeric values are normalized floats in [0.0, 1.0].
    - Free-text fields (reason, message) are NOT used as evidence values —
      they are metadata for human debugging only.

Sources mapped to EvidenceItem:
    - ModelGateCheckResult  → source="validator_result"
    - ModelTestRunResult    → source="test_output"
    - ModelStaticAnalysisResult → source="static_analysis"
    - Cost/latency are separate items constructed from scalar telemetry.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ModelGateCheckResult",
    "ModelSessionCheckResults",
    "ModelStaticAnalysisResult",
    "ModelTestRunResult",
]


class ModelGateCheckResult(BaseModel):
    """Result of a single gate check execution (validator_result evidence source).

    Represents one gate execution record from the agent session. The pass_rate
    field is normalized to [0.0, 1.0] (0.0 = fail, 1.0 = pass for a binary gate).

    Attributes:
        gate_id: Identifier for the gate (e.g., "pre_commit", "mypy_strict").
        passed: Whether the gate passed (True) or failed (False).
        pass_rate: Normalized pass rate in [0.0, 1.0].
            For binary gates: 1.0 if passed else 0.0.
            For partial gates (e.g., % of checks passing): fractional value.
        check_count: Total number of checks evaluated.
        pass_count: Number of checks that passed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    gate_id: str = Field(
        description="Unique gate identifier (e.g., 'pre_commit', 'mypy_strict')."
    )
    passed: bool = Field(description="True if the gate passed, False otherwise.")
    pass_rate: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Normalized pass rate in [0.0, 1.0]. "
            "1.0 for full pass, 0.0 for full fail, fractional for partial."
        ),
    )
    check_count: int = Field(
        ge=0,
        default=1,
        description="Total number of checks evaluated by this gate.",
    )
    pass_count: int = Field(
        ge=0,
        default=0,
        description="Number of checks that passed.",
    )


class ModelTestRunResult(BaseModel):
    """Structured pytest / test runner output (test_output evidence source).

    Represents the structured output from a pytest execution. The pass_rate
    is the primary scoring signal.

    Attributes:
        test_suite: Identifier for the test suite (e.g., "unit", "integration").
        total_tests: Total number of tests collected.
        passed_tests: Number of tests that passed.
        failed_tests: Number of tests that failed.
        error_tests: Number of tests with errors (setup/teardown failures).
        pass_rate: Computed pass rate: passed_tests / total_tests.
        duration_seconds: Test suite wall-clock duration.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    test_suite: str = Field(
        description="Test suite identifier (e.g., 'unit', 'integration', 'smoke')."
    )
    total_tests: int = Field(ge=0, description="Total number of tests collected.")
    passed_tests: int = Field(ge=0, description="Number of tests that passed.")
    failed_tests: int = Field(
        ge=0, default=0, description="Number of tests that failed."
    )
    error_tests: int = Field(
        ge=0, default=0, description="Number of tests with errors."
    )
    pass_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized pass rate: passed_tests / total_tests. 1.0 if total_tests=0.",
    )
    duration_seconds: float = Field(
        ge=0.0,
        default=0.0,
        description="Test suite wall-clock execution time in seconds.",
    )


class ModelStaticAnalysisResult(BaseModel):
    """Structured static analysis output (static_analysis evidence source).

    Represents the structured output from mypy, ruff, or similar tools.
    The error_rate is the primary scoring signal (lower is better for raw
    count, but normalized as a pass/fail rate for the evidence item).

    Attributes:
        tool: Tool identifier (e.g., "mypy", "ruff").
        files_checked: Number of files analyzed.
        error_count: Number of errors found.
        warning_count: Number of warnings found.
        clean_rate: Normalized clean rate: 1.0 if error_count=0, else 0.0.
            Binary: either the tool passes or it doesn't (for strict mode).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    tool: str = Field(
        description="Static analysis tool identifier (e.g., 'mypy', 'ruff')."
    )
    files_checked: int = Field(ge=0, default=0, description="Number of files analyzed.")
    error_count: int = Field(ge=0, default=0, description="Number of errors found.")
    warning_count: int = Field(ge=0, default=0, description="Number of warnings found.")
    clean_rate: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Normalized clean rate in [0.0, 1.0]. "
            "1.0 = no errors (strict pass). 0.0 = any errors present. "
            "Use partial rates for non-strict mode."
        ),
    )


class ModelSessionCheckResults(BaseModel):
    """Aggregated check results for a single agent session (ChangeFrame data).

    This is the primary input to the EvidenceCollector. It represents all
    structured, ledger-backed outputs from the agent execution pipeline
    for a single session run.

    Attributes:
        run_id: Unique identifier for the agent session run.
        session_id: Claude Code session identifier (opaque string from upstream).
        gate_results: Gate execution records (validator_result evidence source).
        test_results: Pytest structured outputs (test_output evidence source).
        static_analysis_results: mypy/ruff outputs (static_analysis evidence source).
        cost_usd: Total cost in USD for the session (cost_telemetry source).
            None if cost telemetry is unavailable.
        latency_seconds: End-to-end session duration (latency_telemetry source).
            None if latency telemetry is unavailable.
        collected_at_utc: ISO-8601 UTC timestamp when check results were collected.
        correlation_id: Correlation ID for distributed tracing. Propagated from the STOP event.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    run_id: str = Field(
        description="Unique identifier for the agent session run (e.g., correlation_id as str)."
    )
    session_id: str = Field(
        description="Claude Code session identifier (opaque string from upstream API)."
    )
    correlation_id: str = Field(
        default="",
        description="Correlation ID for distributed tracing. Propagated from the STOP event.",
    )
    gate_results: tuple[ModelGateCheckResult, ...] = Field(
        default=(),
        description="Gate execution records. Empty if no gates were evaluated.",
    )
    test_results: tuple[ModelTestRunResult, ...] = Field(
        default=(),
        description="Pytest structured outputs. Empty if no tests were run.",
    )
    static_analysis_results: tuple[ModelStaticAnalysisResult, ...] = Field(
        default=(),
        description="Static analysis outputs. Empty if no tools were run.",
    )
    cost_usd: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Total cost in USD for the session. "
            "None if cost telemetry is unavailable. "
            "Used as cost_telemetry evidence source."
        ),
    )
    latency_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "End-to-end session duration in seconds. "
            "None if latency telemetry is unavailable. "
            "Used as latency_telemetry evidence source."
        ),
    )
    collected_at_utc: str = Field(
        description="ISO-8601 UTC timestamp when check results were collected."
    )
