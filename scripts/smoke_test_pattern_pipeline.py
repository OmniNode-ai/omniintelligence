#!/usr/bin/env python3
"""OBS-001: Pattern pipeline health smoke test.

Validates the pattern extraction compute pipeline end-to-end by injecting
a synthetic session with a unique marker, running extraction, and verifying
output within a time budget.

Usage:
    python scripts/smoke_test_pattern_pipeline.py [--timeout-ms 30000] [--json]

Exit codes:
    0  Pipeline healthy (extraction completed within budget)
    1  Pipeline unhealthy (extraction failed or timed out)
    2  Usage error

Metrics emitted (JSON to stdout when --json flag or JSON_METRICS env var is set):
    pattern_pipeline.smoke_test.success     (counter, 1 on pass / 0 on fail)
    pattern_pipeline.smoke_test.failure     (counter, 0 on pass / 1 on fail)
    pattern_pipeline.smoke_test.latency_ms  (histogram, wall-clock ms for extraction)
    pattern_pipeline.smoke_test.insights_extracted (gauge, number of insights found)

Scheduling:
    # Cron (every 5 minutes):
    */5 * * * * /opt/omninode/scripts/smoke_test_pattern_pipeline.py --json

    # Kubernetes CronJob:
    schedule: "*/5 * * * *"
    containers:
      - name: smoke-test
        command: ["python", "scripts/smoke_test_pattern_pipeline.py", "--json"]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# Inline import - keep this script self-contained so it can run as a cron job
# without needing to be installed.  PYTHONPATH must include the project src/.
# ---------------------------------------------------------------------------

try:
    from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
        extract_all_patterns,
    )
    from omniintelligence.nodes.node_pattern_extraction_compute.models import (
        ModelExtractionConfig,
        ModelPatternExtractionInput,
        ModelSessionSnapshot,
        ModelToolExecution,
    )
except ImportError as exc:  # pragma: no cover
    print(
        f"[smoke_test] FATAL: Cannot import omniintelligence: {exc}\n"
        "  Ensure PYTHONPATH includes the project's src/ directory.\n"
        "  Example: PYTHONPATH=src python scripts/smoke_test_pattern_pipeline.py",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_MS = 30_000  # 30 seconds
SMOKE_SESSION_PREFIX = "smoke_test"
# Minimum number of insights we expect from the synthetic session
MIN_EXPECTED_INSIGHTS = 1


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def _emit_metrics(
    *,
    success: bool,
    latency_ms: float,
    insights_extracted: int,
    marker: str,
    error: str | None = None,
    as_json: bool = False,
) -> None:
    """Emit smoke test metrics to stdout.

    When as_json is True (or JSON_METRICS env var is non-empty), emits a
    single-line JSON object suitable for ingestion by log aggregators.
    Otherwise emits a human-readable summary.
    """
    ts = datetime.now(tz=UTC).isoformat()
    payload: dict[str, Any] = {
        "timestamp": ts,
        "event": "pattern_pipeline.smoke_test",
        "marker": marker,
        "metrics": {
            "pattern_pipeline.smoke_test.success": 1 if success else 0,
            "pattern_pipeline.smoke_test.failure": 0 if success else 1,
            "pattern_pipeline.smoke_test.latency_ms": round(latency_ms, 2),
            "pattern_pipeline.smoke_test.insights_extracted": insights_extracted,
        },
        "status": "ok" if success else "fail",
    }
    if error:
        payload["error"] = error

    if as_json or os.environ.get("JSON_METRICS"):
        print(json.dumps(payload), flush=True)
    else:
        status_symbol = "PASS" if success else "FAIL"
        print(
            f"[{ts}] [{status_symbol}] "
            f"marker={marker} "
            f"latency={latency_ms:.1f}ms "
            f"insights={insights_extracted}"
            + (f" error={error!r}" if error else ""),
            flush=True,
        )


# ---------------------------------------------------------------------------
# Synthetic session builder
# ---------------------------------------------------------------------------


def _build_smoke_session(marker: str, base_time: datetime) -> ModelSessionSnapshot:
    """Build a synthetic session snapshot for pipeline validation.

    The session contains a mix of file accesses, tool executions, and a
    recoverable error to exercise all extraction paths.

    Args:
        marker: Unique string embedded in the session ID so results can be
            traced back to this smoke run.
        base_time: Reference timestamp for the session.

    Returns:
        A frozen ModelSessionSnapshot ready for extraction.
    """
    return ModelSessionSnapshot(
        session_id=f"{SMOKE_SESSION_PREFIX}_{marker}",
        working_directory="/smoke/test/project",
        started_at=base_time,
        ended_at=base_time + timedelta(seconds=42),
        files_accessed=(
            "src/smoke/module_a.py",
            "src/smoke/module_b.py",
            "tests/unit/test_module_a.py",
            "tests/unit/test_module_b.py",
            "README.md",
        ),
        files_modified=(
            "src/smoke/module_a.py",
            "src/smoke/module_b.py",
        ),
        tools_used=("Read", "Edit", "Read", "Edit", "Bash", "Read"),
        tool_executions=(
            ModelToolExecution(
                tool_name="Read",
                success=True,
                timestamp=base_time,
            ),
            ModelToolExecution(
                tool_name="Edit",
                success=True,
                timestamp=base_time + timedelta(seconds=5),
            ),
            ModelToolExecution(
                tool_name="Read",
                success=True,
                timestamp=base_time + timedelta(seconds=10),
            ),
            ModelToolExecution(
                tool_name="Edit",
                success=False,
                error_type="FileNotFoundError",
                timestamp=base_time + timedelta(seconds=15),
            ),
            ModelToolExecution(
                tool_name="Edit",
                success=True,
                timestamp=base_time + timedelta(seconds=20),
            ),
            ModelToolExecution(
                tool_name="Bash",
                success=True,
                timestamp=base_time + timedelta(seconds=35),
            ),
        ),
        errors_encountered=("FileNotFoundError: src/smoke/module_a.py not found",),
        outcome="success",
        metadata={"smoke_marker": marker},
    )


# ---------------------------------------------------------------------------
# Main smoke-test logic
# ---------------------------------------------------------------------------


def run_smoke_test(
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    as_json: bool = False,
) -> bool:
    """Run the pattern pipeline smoke test.

    Injects a synthetic session, runs extraction, and validates output.

    Args:
        timeout_ms: Maximum allowed wall-clock time for extraction (ms).
        as_json: Emit metrics as JSON (useful for log aggregators).

    Returns:
        True if the pipeline is healthy, False otherwise.
    """
    marker = str(uuid.uuid4()).replace("-", "")[:16]
    base_time = datetime.now(tz=UTC) - timedelta(minutes=5)

    # Build input with two sessions so extractors detect repeated patterns
    session_a = _build_smoke_session(marker, base_time)
    session_b = _build_smoke_session(f"{marker}_b", base_time - timedelta(hours=1))

    extraction_input = ModelPatternExtractionInput(
        session_snapshots=(session_a, session_b),
        options=ModelExtractionConfig(
            min_pattern_occurrences=1,  # Low threshold: accept any pattern
            min_confidence=0.1,
            extract_file_patterns=True,
            extract_error_patterns=True,
            extract_architecture_patterns=True,
            extract_tool_patterns=True,
        ),
        existing_insights=(),
    )

    start = time.monotonic()
    error: str | None = None
    insights_count = 0

    try:
        # Run synchronous extraction (NodePatternExtractionCompute.compute() is async,
        # but extract_all_patterns is the pure sync handler — no event loop needed)
        output = extract_all_patterns(extraction_input)
        latency_ms = (time.monotonic() - start) * 1000

        insights_count = len(output.new_insights) + len(output.updated_insights)

        # Validate latency budget
        if latency_ms > timeout_ms:
            error = (
                f"Extraction exceeded timeout: {latency_ms:.1f}ms > {timeout_ms}ms"
            )
            _emit_metrics(
                success=False,
                latency_ms=latency_ms,
                insights_extracted=insights_count,
                marker=marker,
                error=error,
                as_json=as_json,
            )
            return False

        # Validate minimum insight count
        if insights_count < MIN_EXPECTED_INSIGHTS:
            error = (
                f"Too few insights: {insights_count} < {MIN_EXPECTED_INSIGHTS} expected. "
                f"Pattern extraction pipeline may be degraded."
            )
            _emit_metrics(
                success=False,
                latency_ms=latency_ms,
                insights_extracted=insights_count,
                marker=marker,
                error=error,
                as_json=as_json,
            )
            return False

        _emit_metrics(
            success=True,
            latency_ms=latency_ms,
            insights_extracted=insights_count,
            marker=marker,
            as_json=as_json,
        )
        return True

    except Exception as exc:  # noqa: BLE001 — smoke test must catch all errors
        latency_ms = (time.monotonic() - start) * 1000
        error = f"{type(exc).__name__}: {exc}"
        _emit_metrics(
            success=False,
            latency_ms=latency_ms,
            insights_extracted=0,
            marker=marker,
            error=error,
            as_json=as_json,
        )
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OBS-001: Pattern pipeline health smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help=f"Max ms for pipeline extraction (default: {DEFAULT_TIMEOUT_MS})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit metrics as JSON (useful for log aggregators)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 on success, 1 on failure, 2 on usage error.
    """
    args = _parse_args(argv)
    healthy = run_smoke_test(timeout_ms=args.timeout_ms, as_json=args.json)
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
