"""OBS-001: Pattern pipeline health smoke test — pytest variant.

Validates the pattern extraction compute pipeline end-to-end by injecting
synthetic sessions with unique markers, running extraction, and verifying
output structure and performance within a time budget.

These tests use the ``smoke`` pytest marker so they can be scheduled by CI
at a 5-minute interval:

    pytest -m smoke --tb=short tests/integration/nodes/test_pattern_pipeline_smoke.py

Scheduling in CI (GitHub Actions):
    on:
      schedule:
        - cron: "*/5 * * * *"

Key invariants tested:
    1. Extraction completes within 30 seconds
    2. At least one insight is extracted from a well-formed synthetic session
    3. Result structure matches ModelPatternExtractionOutput contract
    4. Metrics can be collected and are non-negative
    5. Pipeline handles edge cases gracefully (empty sessions, minimal data)
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    extract_all_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelExtractionConfig,
    ModelPatternExtractionInput,
    ModelPatternExtractionOutput,
    ModelSessionSnapshot,
    ModelToolExecution,
)

pytestmark = [pytest.mark.integration, pytest.mark.smoke]

# ---------------------------------------------------------------------------
# Smoke test constants
# ---------------------------------------------------------------------------

SMOKE_LATENCY_BUDGET_MS = 30_000  # 30 seconds
SMOKE_SESSION_PREFIX = "smoke_test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_marker() -> str:
    """Return a short unique marker for tracing a specific smoke run."""
    return str(uuid.uuid4()).replace("-", "")[:16]


def _build_synthetic_sessions(
    marker: str,
    base_time: datetime,
    count: int = 3,
) -> tuple[ModelSessionSnapshot, ...]:
    """Build ``count`` synthetic sessions with a unique marker.

    Sessions are varied in tool usage, file access, and outcome so that
    all extraction paths (file, error, architecture, tool patterns) can
    produce at least one insight.

    Args:
        marker: Unique string embedded in session IDs for traceability.
        base_time: Reference timestamp (most recent session starts here).
        count: Number of sessions to generate (minimum 2 for pattern detection).

    Returns:
        Tuple of frozen ModelSessionSnapshot objects.
    """
    sessions: list[ModelSessionSnapshot] = []

    for i in range(count):
        session_base = base_time - timedelta(hours=i)
        sessions.append(
            ModelSessionSnapshot(
                session_id=f"{SMOKE_SESSION_PREFIX}_{marker}_{i}",
                working_directory="/smoke/project",
                started_at=session_base,
                ended_at=session_base + timedelta(seconds=30 + i * 5),
                files_accessed=(
                    "src/core/module_a.py",
                    "src/core/module_b.py",
                    "tests/unit/test_module_a.py",
                ),
                files_modified=(
                    "src/core/module_a.py",
                    "src/core/module_b.py",
                ),
                tools_used=("Read", "Edit", "Bash", "Read"),
                tool_executions=(
                    ModelToolExecution(
                        tool_name="Read",
                        success=True,
                        timestamp=session_base,
                    ),
                    ModelToolExecution(
                        tool_name="Edit",
                        success=True,
                        timestamp=session_base + timedelta(seconds=5),
                    ),
                    ModelToolExecution(
                        tool_name="Bash",
                        success=(i % 2 == 0),  # Alternate success/failure
                        error_type="CalledProcessError" if i % 2 != 0 else None,
                        timestamp=session_base + timedelta(seconds=15),
                    ),
                    ModelToolExecution(
                        tool_name="Read",
                        success=True,
                        timestamp=session_base + timedelta(seconds=20),
                    ),
                ),
                errors_encountered=(
                    ("CalledProcessError: exit code 1",) if i % 2 != 0 else ()
                ),
                outcome="success" if i % 2 == 0 else "partial",
                metadata={"smoke_marker": marker, "session_index": i},
            )
        )

    return tuple(sessions)


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


class TestPatternPipelineSmokeLatency:
    """Latency gate: extraction must complete within the budget."""

    def test_extraction_completes_within_30_seconds(self) -> None:
        """End-to-end extraction must complete within 30 s for 3 synthetic sessions."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        sessions = _build_synthetic_sessions(marker, base_time, count=3)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=sessions,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_confidence=0.1,
                extract_file_patterns=True,
                extract_error_patterns=True,
                extract_architecture_patterns=True,
                extract_tool_patterns=True,
            ),
            existing_insights=(),
        )

        start = time.monotonic()
        output = extract_all_patterns(extraction_input)
        latency_ms = (time.monotonic() - start) * 1000

        assert latency_ms < SMOKE_LATENCY_BUDGET_MS, (
            f"Pattern extraction exceeded {SMOKE_LATENCY_BUDGET_MS}ms budget: "
            f"{latency_ms:.1f}ms. Pipeline may be degraded."
        )
        # Sanity check: output is a valid result object
        assert isinstance(output, ModelPatternExtractionOutput)


class TestPatternPipelineSmokeOutputIntegrity:
    """Output integrity: result must match contract structure."""

    def test_output_has_expected_structure(self) -> None:
        """Extraction output must have all required fields."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        sessions = _build_synthetic_sessions(marker, base_time, count=3)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=sessions,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_confidence=0.0,
                extract_file_patterns=True,
                extract_error_patterns=True,
                extract_architecture_patterns=True,
                extract_tool_patterns=True,
            ),
            existing_insights=(),
        )

        output = extract_all_patterns(extraction_input)

        assert hasattr(output, "new_insights"), "Output must have 'new_insights' field"
        assert hasattr(output, "updated_insights"), (
            "Output must have 'updated_insights' field"
        )
        assert hasattr(output, "metrics"), "Output must have 'metrics' field"
        assert hasattr(output, "metadata"), "Output must have 'metadata' field"
        assert isinstance(output.new_insights, tuple), "new_insights must be a tuple"
        assert isinstance(output.updated_insights, tuple), (
            "updated_insights must be a tuple"
        )

    def test_at_least_one_insight_extracted(self) -> None:
        """Well-formed sessions with repeated patterns must produce at least one insight."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        sessions = _build_synthetic_sessions(marker, base_time, count=3)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=sessions,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_confidence=0.0,
                extract_file_patterns=True,
                extract_error_patterns=True,
                extract_architecture_patterns=True,
                extract_tool_patterns=True,
            ),
            existing_insights=(),
        )

        output = extract_all_patterns(extraction_input)

        assert len(output.new_insights) >= 1, (
            f"Expected at least 1 insight from synthetic sessions "
            f"(marker={marker}), got {len(output.new_insights)}. "
            "Pattern extraction pipeline may be degraded."
        )

    def test_insights_have_required_fields(self) -> None:
        """Every extracted insight must have identity_key, description, and confidence."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        sessions = _build_synthetic_sessions(marker, base_time, count=3)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=sessions,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_confidence=0.0,
                extract_file_patterns=True,
                extract_error_patterns=True,
                extract_architecture_patterns=True,
                extract_tool_patterns=True,
            ),
            existing_insights=(),
        )

        output = extract_all_patterns(extraction_input)

        for i, insight in enumerate(output.new_insights):
            assert hasattr(insight, "insight_id") and insight.insight_id, (
                f"Insight {i} missing insight_id (marker={marker})"
            )
            assert hasattr(insight, "description") and insight.description, (
                f"Insight {i} missing description (marker={marker})"
            )
            assert hasattr(insight, "confidence"), (
                f"Insight {i} missing confidence field (marker={marker})"
            )
            assert 0.0 <= insight.confidence <= 1.0, (
                f"Insight {i} confidence {insight.confidence} out of [0, 1] "
                f"(marker={marker})"
            )

    def test_metrics_are_non_negative(self) -> None:
        """All extraction metrics must be >= 0."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        sessions = _build_synthetic_sessions(marker, base_time, count=3)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=sessions,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_confidence=0.0,
                extract_file_patterns=True,
                extract_error_patterns=True,
                extract_architecture_patterns=True,
                extract_tool_patterns=True,
            ),
            existing_insights=(),
        )

        output = extract_all_patterns(extraction_input)
        metrics = output.metrics

        for field_name in type(metrics).model_fields:
            value = getattr(metrics, field_name)
            if isinstance(value, int | float):
                assert value >= 0, (
                    f"Metric '{field_name}' is negative: {value} (marker={marker})"
                )


class TestPatternPipelineSmokeEdgeCases:
    """Edge case handling: pipeline must not crash on unusual inputs."""

    def test_empty_sessions_rejected_by_input_model(self) -> None:
        """Empty session_snapshots must be rejected at input validation (min_length=1)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ModelPatternExtractionInput(
                session_snapshots=(),
                options=ModelExtractionConfig(
                    min_pattern_occurrences=1,
                    min_confidence=0.5,
                ),
                existing_insights=(),
            )

    def test_single_session_does_not_crash(self) -> None:
        """A single session (cannot produce co-access patterns) must not crash."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        session = _build_synthetic_sessions(marker, base_time, count=1)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=session,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1,
                min_confidence=0.0,
            ),
            existing_insights=(),
        )

        # Must complete without raising
        output = extract_all_patterns(extraction_input)
        assert isinstance(output.new_insights, tuple)

    def test_high_threshold_filters_all_insights(self) -> None:
        """With a very high min_confidence, all insights may be filtered — must not error."""
        marker = _make_marker()
        base_time = datetime.now(tz=UTC) - timedelta(minutes=10)
        sessions = _build_synthetic_sessions(marker, base_time, count=3)

        extraction_input = ModelPatternExtractionInput(
            session_snapshots=sessions,
            options=ModelExtractionConfig(
                min_pattern_occurrences=1000,  # impossibly high — filters everything
                min_confidence=1.0,  # maximum threshold
            ),
            existing_insights=(),
        )

        output = extract_all_patterns(extraction_input)
        assert isinstance(output.new_insights, tuple), (
            "High threshold must return empty tuple, not raise"
        )


class TestPatternPipelineSmokeMetricsCollection:
    """Verify metrics can be collected and logged — mirrors the CLI script behaviour."""

    def test_smoke_script_run_smoke_test_returns_true(self) -> None:
        """run_smoke_test() from the CLI script must return True in this environment."""
        import sys
        from pathlib import Path

        # Add scripts/ to sys.path if not already importable
        scripts_dir = str(Path(__file__).parents[3] / "scripts")
        original_path = sys.path[:]
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        try:
            from smoke_test_pattern_pipeline import (
                run_smoke_test,  # type: ignore[import-not-found]
            )

            result = run_smoke_test(timeout_ms=30_000, as_json=False)
            assert result is True, (
                "smoke_test_pattern_pipeline.run_smoke_test() returned False. "
                "Pattern extraction pipeline may be degraded."
            )
        finally:
            sys.path = original_path

    def test_smoke_script_emits_valid_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """run_smoke_test(as_json=True) must emit valid JSON to stdout."""
        import sys
        from pathlib import Path

        scripts_dir = str(Path(__file__).parents[3] / "scripts")
        original_path = sys.path[:]
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "smoke_test_pattern_pipeline",
                Path(scripts_dir) / "smoke_test_pattern_pipeline.py",
            )
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]

            result = mod.run_smoke_test(timeout_ms=30_000, as_json=True)
            captured = capsys.readouterr()

            assert result is True
            # Each line should be valid JSON
            for line in captured.out.strip().split("\n"):
                if line.strip():
                    import json

                    parsed = json.loads(line)
                    assert "metrics" in parsed
                    assert parsed["status"] == "ok"
        finally:
            sys.path = original_path
