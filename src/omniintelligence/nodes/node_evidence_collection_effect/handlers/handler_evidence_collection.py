# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Evidence collection handler — extracts EvidenceItems and drives evaluation.

This module implements the core logic for OMN-2578: constructing an
EvidenceBundle from ChangeFrame check results at session end and feeding it
into the objective evaluation pipeline.

Architecture:
    EvidenceCollector — pure extractor (no I/O), converts session check results
        into a sequence of ModelEvidenceItem instances.
    collect_and_evaluate — async top-level function (has I/O: Kafka, DB).
        This is the integration point called from handle_stop.

Evidence source mapping (OMN-2537 typed source literals):
    ModelGateCheckResult       → "validator_result"
    ModelTestRunResult         → "test_output"
    ModelStaticAnalysisResult  → "static_analysis"
    cost_usd telemetry         → "cost_telemetry"
    latency_seconds telemetry  → "latency_telemetry"

Free-text sources are structurally disallowed:
    - If a free-text source is passed programmatically → DisallowedEvidenceSourceError
    - If no evidence items are collected (empty results) → silently skip evaluation

Non-blocking constraint (OMN-2578 requirements):
    collect_and_evaluate is called from handle_stop as a fire-and-forget
    asyncio.ensure_future / asyncio.create_task. Session completion is NOT
    delayed by evaluation. Errors are logged and swallowed.

Ticket: OMN-2578
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from omniintelligence.nodes.node_evidence_collection_effect.errors import (
    DisallowedEvidenceSourceError,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_collection_output import (
    ModelCollectionOutput,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_run_evaluated_event import (
    ModelRunEvaluatedEvent,
)
from omniintelligence.nodes.node_evidence_collection_effect.models.model_session_check_results import (
    ModelGateCheckResult,
    ModelSessionCheckResults,
    ModelStaticAnalysisResult,
    ModelTestRunResult,
)

if TYPE_CHECKING:
    from omniintelligence.protocols import ProtocolKafkaPublisher

logger = logging.getLogger(__name__)

# ============================================================================
# Free-text source blocklist — any source in this set must be rejected
# ============================================================================

_DISALLOWED_SOURCES: frozenset[str] = frozenset(
    {
        "chat_log",
        "model_confidence",
        "free_text",
        "llm_summary",
        "unstructured_text",
        "review_text",
        "description",
        "comment",
    }
)

# ============================================================================
# Known valid evidence sources (from OMN-2537 ModelEvidenceItem spec)
# ============================================================================

_ALLOWED_SOURCES: frozenset[str] = frozenset(
    {
        "test_output",
        "validator_result",
        "static_analysis",
        "build_warnings",
        "structured_review_tag",
        "cost_telemetry",
        "latency_telemetry",
    }
)

# ============================================================================
# Cost normalization: $0.50 per session = score 0.0, $0.00 = score 1.0
# ============================================================================
_COST_NORMALIZATION_MAX_USD: float = 0.50
_LATENCY_NORMALIZATION_MAX_SECONDS: float = 300.0  # 5 minutes


class EvidenceCollector:
    """Pure evidence extractor — no I/O, no side effects.

    Converts structured check results from a completed agent session into
    a sequence of ModelEvidenceItem-compatible dicts. Uses only the seven
    allowed evidence source types.

    This class is designed to be used as a pure computation unit: identical
    inputs always produce identical outputs (replay invariant).

    Usage:
        collector = EvidenceCollector()
        items = collector.collect(check_results)
        # items is a list of dicts compatible with ModelEvidenceItem constructor

    Raises:
        DisallowedEvidenceSourceError: If a caller injects a free-text source
            via the public API (programming contract violation).
    """

    def collect(self, check_results: ModelSessionCheckResults) -> list[dict[str, Any]]:
        """Extract EvidenceItem-compatible dicts from session check results.

        Processes gate results, test results, static analysis results, and
        cost/latency telemetry in deterministic order.

        Args:
            check_results: Aggregated structured check results for the session.

        Returns:
            List of dicts suitable for constructing ModelEvidenceItem instances.
            May be empty if no check results are available (caller should skip
            evaluation rather than constructing an empty bundle).

        Raises:
            DisallowedEvidenceSourceError: If free-text source injection is
                detected (programming contract violation — not a runtime error).
        """
        items: list[dict[str, Any]] = []

        # Stage 1: Gate execution records → validator_result
        for gate in check_results.gate_results:
            items.append(self._from_gate(gate))

        # Stage 2: pytest outputs → test_output
        for test_run in check_results.test_results:
            items.append(self._from_test_run(test_run))

        # Stage 3: mypy/ruff outputs → static_analysis
        for analysis in check_results.static_analysis_results:
            items.append(self._from_static_analysis(analysis))

        # Stage 4: Cost telemetry → cost_telemetry (optional)
        if check_results.cost_usd is not None:
            items.append(self._from_cost(check_results.run_id, check_results.cost_usd))

        # Stage 5: Latency telemetry → latency_telemetry (optional)
        if check_results.latency_seconds is not None:
            items.append(
                self._from_latency(check_results.run_id, check_results.latency_seconds)
            )

        return items

    def assert_no_free_text(self, source: str) -> None:
        """Assert that a source string is not a disallowed free-text source.

        Called by the public API when a caller explicitly specifies a source.
        This is a hard error — callers must not inject free-text sources.

        Args:
            source: The source string to check.

        Raises:
            DisallowedEvidenceSourceError: If source is in the disallowed set.
        """
        if source in _DISALLOWED_SOURCES:
            raise DisallowedEvidenceSourceError(
                source=source,
                reason=(
                    "This source type is structurally disallowed. "
                    "Only structured, ledger-backed evidence sources are permitted."
                ),
            )

    def _from_gate(self, gate: ModelGateCheckResult) -> dict[str, Any]:
        """Convert a gate check result to an EvidenceItem dict."""
        return {
            "item_id": f"gate_{gate.gate_id}",
            "source": "validator_result",
            "value": gate.pass_rate,
            "metadata": {
                "gate_id": gate.gate_id,
                "passed": gate.passed,
                "check_count": gate.check_count,
                "pass_count": gate.pass_count,
            },
        }

    def _from_test_run(self, test_run: ModelTestRunResult) -> dict[str, Any]:
        """Convert a test run result to an EvidenceItem dict."""
        return {
            "item_id": f"test_{test_run.test_suite}",
            "source": "test_output",
            "value": test_run.pass_rate,
            "metadata": {
                "test_suite": test_run.test_suite,
                "total_tests": test_run.total_tests,
                "passed_tests": test_run.passed_tests,
                "failed_tests": test_run.failed_tests,
                "error_tests": test_run.error_tests,
                "duration_seconds": test_run.duration_seconds,
            },
        }

    def _from_static_analysis(
        self, analysis: ModelStaticAnalysisResult
    ) -> dict[str, Any]:
        """Convert a static analysis result to an EvidenceItem dict."""
        return {
            "item_id": f"static_{analysis.tool}",
            "source": "static_analysis",
            "value": analysis.clean_rate,
            "metadata": {
                "tool": analysis.tool,
                "files_checked": analysis.files_checked,
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
            },
        }

    def _from_cost(self, run_id: str, cost_usd: float) -> dict[str, Any]:
        """Convert cost telemetry to an EvidenceItem dict.

        Normalizes cost to [0.0, 1.0] where 1.0 = no cost and 0.0 = max cost.
        """
        normalized = max(0.0, 1.0 - (cost_usd / _COST_NORMALIZATION_MAX_USD))
        return {
            "item_id": f"cost_{run_id}",
            "source": "cost_telemetry",
            "value": min(1.0, normalized),
            "metadata": {
                "cost_usd": cost_usd,
                "normalization_max_usd": _COST_NORMALIZATION_MAX_USD,
            },
        }

    def _from_latency(self, run_id: str, latency_seconds: float) -> dict[str, Any]:
        """Convert latency telemetry to an EvidenceItem dict.

        Normalizes latency to [0.0, 1.0] where 1.0 = instant, 0.0 = max latency.
        """
        normalized = max(
            0.0, 1.0 - (latency_seconds / _LATENCY_NORMALIZATION_MAX_SECONDS)
        )
        return {
            "item_id": f"latency_{run_id}",
            "source": "latency_telemetry",
            "value": min(1.0, normalized),
            "metadata": {
                "latency_seconds": latency_seconds,
                "normalization_max_seconds": _LATENCY_NORMALIZATION_MAX_SECONDS,
            },
        }


# ============================================================================
# Protocol for scoring — decouples node_evidence_collection_effect from
# node_scoring_reducer_compute at import time (avoids circular deps)
# ============================================================================


class _ProtocolObjectiveEvaluator:
    """Protocol-like interface for the scoring function.

    The concrete implementation is imported lazily to avoid hard coupling
    to node_scoring_reducer_compute at module load time.
    """

    @staticmethod
    def evaluate(evidence_bundle: Any, objective_spec: Any) -> Any:
        """Evaluate an EvidenceBundle against an ObjectiveSpec.

        Args:
            evidence_bundle: ModelEvidenceBundle instance.
            objective_spec: ModelObjectiveSpec instance.

        Returns:
            ModelEvaluationResult instance.
        """
        raise NotImplementedError


def _get_default_objective_spec() -> Any:
    """Return the default ObjectiveSpec for sessions without explicit task class.

    This spec uses lenient gates (no hard failures for base sessions) and
    provides lightweight shaped scoring across all six dimensions.

    The spec is constructed inline here rather than loaded from YAML to
    avoid the need for external config at runtime.

    Returns:
        ModelObjectiveSpec instance with default settings.
    """
    try:
        from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_gate_type import (
            EnumGateType,
        )
        from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
            ModelGateSpec,
            ModelObjectiveSpec,
            ModelScoreRange,
            ModelShapedTermSpec,
        )
    except ImportError:
        logger.warning(
            "node_scoring_reducer_compute not available — objective evaluation skipped. "
            "This is expected until OMN-2545 (PR #209) is merged."
        )
        return None

    return ModelObjectiveSpec(
        spec_id="default_v1",
        version="1.0.0",
        gates=(
            ModelGateSpec(
                id="gate_static_analysis",
                gate_type=EnumGateType.THRESHOLD,
                threshold=0.0,  # Any clean_rate >= 0.0 passes (permissive for existing pre-errors)
                evidence_source="static_analysis",
            ),
        ),
        shaped_terms=(
            ModelShapedTermSpec(
                id="term_test_quality",
                evidence_source="test_output",
                score_dimension="correctness",
                weight=0.4,
                direction="maximize",
            ),
            ModelShapedTermSpec(
                id="term_static_quality",
                evidence_source="static_analysis",
                score_dimension="maintainability",
                weight=0.3,
                direction="maximize",
            ),
            ModelShapedTermSpec(
                id="term_cost",
                evidence_source="cost_telemetry",
                score_dimension="cost",
                weight=0.15,
                direction="maximize",
            ),
            ModelShapedTermSpec(
                id="term_latency",
                evidence_source="latency_telemetry",
                score_dimension="latency",
                weight=0.15,
                direction="maximize",
            ),
        ),
        score_range=ModelScoreRange(minimum=0.0, maximum=1.0),
    )


def _build_evidence_bundle(
    run_id: str,
    items_dicts: list[dict[str, Any]],
    collected_at_utc: str,
) -> Any | None:
    """Build a ModelEvidenceBundle from item dicts.

    Args:
        run_id: The run identifier.
        items_dicts: List of EvidenceItem-compatible dicts.
        collected_at_utc: ISO-8601 UTC timestamp.

    Returns:
        ModelEvidenceBundle instance, or None if import fails.
    """
    try:
        from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evidence_bundle import (
            ModelEvidenceBundle,
            ModelEvidenceItem,
        )
    except ImportError:
        logger.warning(
            "node_scoring_reducer_compute models not available — "
            "EvidenceBundle construction skipped. Expected until PR #209 merges."
        )
        return None

    items = tuple(
        ModelEvidenceItem(
            item_id=d["item_id"],
            source=d["source"],
            value=d["value"],
            metadata=d.get("metadata", {}),
        )
        for d in items_dicts
    )

    return ModelEvidenceBundle(
        run_id=run_id,
        bundle_fingerprint=ModelEvidenceBundle.fingerprint(items),
        items=items,
        collected_at_utc=collected_at_utc,
    )


def _run_evaluation(evidence_bundle: Any, objective_spec: Any) -> Any | None:
    """Run the scoring evaluation.

    Args:
        evidence_bundle: ModelEvidenceBundle instance.
        objective_spec: ModelObjectiveSpec instance.

    Returns:
        ModelEvaluationResult instance, or None if import fails.
    """
    try:
        from omniintelligence.nodes.node_scoring_reducer_compute.handlers.handler_scoring import (
            evaluate_run,
        )
    except ImportError:
        logger.warning(
            "handler_scoring.evaluate_run not available — "
            "evaluation skipped. Expected until PR #209 merges."
        )
        return None

    return evaluate_run(evidence=evidence_bundle, spec=objective_spec)


async def _emit_to_kafka(
    event: ModelRunEvaluatedEvent,
    kafka_publisher: ProtocolKafkaPublisher,
    topic: str,
) -> bool:
    """Emit a RunEvaluatedEvent to Kafka.

    Args:
        event: The event to emit.
        kafka_publisher: Kafka publisher (from constructor injection).
        topic: Target Kafka topic.

    Returns:
        True if emitted successfully, False on error.
    """
    try:
        await kafka_publisher.publish(
            topic=topic,
            key=event.run_id,
            value=event.model_dump(),
        )
        return True
    except Exception:
        logger.exception(
            "Failed to emit RunEvaluatedEvent to Kafka",
            extra={"run_id": event.run_id, "topic": topic},
        )
        return False


async def _store_to_db(
    evaluation_result: Any,
    bundle_fingerprint: str,
    run_id: str,
    session_id: str,
    task_class: str,
    evaluated_at_utc: str,
    db_conn: Any,
) -> bool:
    """Store EvaluationResult in the objective_evaluations table.

    Args:
        evaluation_result: ModelEvaluationResult from the scorer.
        bundle_fingerprint: SHA-256 fingerprint of the EvidenceBundle.
        run_id: The run identifier.
        session_id: The session identifier.
        task_class: The task class used for spec selection.
        evaluated_at_utc: ISO-8601 UTC timestamp.
        db_conn: Async database connection.

    Returns:
        True if stored successfully, False on error.
    """
    try:
        score = evaluation_result.score_vector
        await db_conn.execute(
            """
            INSERT INTO objective_evaluations (
                run_id,
                session_id,
                task_class,
                bundle_fingerprint,
                passed,
                failures,
                score_correctness,
                score_safety,
                score_cost,
                score_latency,
                score_maintainability,
                score_human_time,
                evaluated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
            )
            ON CONFLICT (run_id, bundle_fingerprint) DO UPDATE
                SET evaluated_at = EXCLUDED.evaluated_at
            """,
            run_id,
            session_id,
            task_class,
            bundle_fingerprint,
            evaluation_result.passed,
            list(evaluation_result.failures),
            score.correctness,
            score.safety,
            score.cost,
            score.latency,
            score.maintainability,
            score.human_time,
            evaluated_at_utc,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to store EvaluationResult to DB",
            extra={"run_id": run_id, "bundle_fingerprint": bundle_fingerprint},
        )
        return False


# Topic constant for RunEvaluatedEvent
TOPIC_RUN_EVALUATED_V1: str = "onex.evt.omniintelligence.run-evaluated.v1"


async def collect_and_evaluate(
    check_results: ModelSessionCheckResults,
    *,
    task_class: str | None = None,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
    db_conn: Any | None = None,
    objective_spec: Any | None = None,
) -> ModelCollectionOutput:
    """Top-level async pipeline: collect evidence → evaluate → emit → store.

    This is the integration point called from handle_stop at session end.
    It is designed to be non-blocking: callers should wrap this in
    asyncio.ensure_future() or asyncio.create_task() to avoid delaying
    session completion.

    Pipeline stages:
        1. EvidenceCollector.collect(check_results) → list[EvidenceItem dicts]
        2. If empty: return skipped output (graceful, not an error).
        3. ModelEvidenceBundle.create(run_id, items, collected_at_utc)
        4. Select ObjectiveSpec (provided or default).
        5. evaluate_run(bundle, spec) → ModelEvaluationResult
        6. Emit RunEvaluatedEvent to Kafka (if publisher available).
        7. Store EvaluationResult to DB (if db_conn available).

    Error handling:
        - All errors are logged and swallowed (non-blocking contract).
        - If collection returns no items: skip silently.
        - If free-text injection is detected: propagate DisallowedEvidenceSourceError
          (this is a programming error, not a runtime failure).

    Args:
        check_results: Structured check results from the agent session.
        task_class: Optional task class for ObjectiveSpec selection.
        kafka_publisher: Optional Kafka publisher for RunEvaluatedEvent emission.
        db_conn: Optional DB connection for EvaluationResult storage.
        objective_spec: Optional pre-constructed ObjectiveSpec. If None, the
            default spec is used.

    Returns:
        ModelCollectionOutput with outcome metadata.

    Raises:
        DisallowedEvidenceSourceError: Only if a free-text source is explicitly
            injected via the public API (programming contract violation).
    """
    run_id = check_results.run_id
    session_id = check_results.session_id
    resolved_task_class = task_class or "default"
    collected_at_utc = check_results.collected_at_utc

    # Stage 1: Collect evidence items
    collector = EvidenceCollector()
    try:
        items_dicts = collector.collect(check_results)
    except DisallowedEvidenceSourceError:
        raise  # Propagate hard errors (programming contract violation)
    except Exception:
        logger.exception(
            "Evidence collection failed — skipping evaluation",
            extra={"run_id": run_id, "session_id": session_id},
        )
        return ModelCollectionOutput(
            run_id=run_id,
            session_id=session_id,
            skipped=True,
            skip_reason="evidence_collection_error",
        )

    # Stage 2: Skip if no evidence items
    if not items_dicts:
        logger.debug(
            "No evidence items collected — skipping evaluation",
            extra={"run_id": run_id, "session_id": session_id},
        )
        return ModelCollectionOutput(
            run_id=run_id,
            session_id=session_id,
            skipped=True,
            skip_reason="no_evidence_items",
        )

    # Stage 3: Build EvidenceBundle
    bundle = _build_evidence_bundle(
        run_id=run_id,
        items_dicts=items_dicts,
        collected_at_utc=collected_at_utc,
    )
    if bundle is None:
        return ModelCollectionOutput(
            run_id=run_id,
            session_id=session_id,
            evidence_item_count=len(items_dicts),
            skipped=True,
            skip_reason="scoring_reducer_unavailable",
        )

    bundle_fingerprint: str = bundle.bundle_fingerprint

    # Stage 4: Select ObjectiveSpec
    spec = objective_spec or _get_default_objective_spec()
    if spec is None:
        return ModelCollectionOutput(
            run_id=run_id,
            session_id=session_id,
            bundle_fingerprint=bundle_fingerprint,
            evidence_item_count=len(items_dicts),
            skipped=True,
            skip_reason="objective_spec_unavailable",
        )

    # Stage 5: Evaluate
    try:
        evaluation_result = _run_evaluation(evidence_bundle=bundle, objective_spec=spec)
    except Exception:
        logger.exception(
            "Objective evaluation failed",
            extra={"run_id": run_id, "bundle_fingerprint": bundle_fingerprint},
        )
        return ModelCollectionOutput(
            run_id=run_id,
            session_id=session_id,
            bundle_fingerprint=bundle_fingerprint,
            evidence_item_count=len(items_dicts),
            skipped=True,
            skip_reason="evaluation_error",
        )

    if evaluation_result is None:
        return ModelCollectionOutput(
            run_id=run_id,
            session_id=session_id,
            bundle_fingerprint=bundle_fingerprint,
            evidence_item_count=len(items_dicts),
            skipped=True,
            skip_reason="evaluation_returned_none",
        )

    evaluated_at_utc = datetime.now(UTC).isoformat()
    score = evaluation_result.score_vector

    # Stage 6: Emit RunEvaluatedEvent to Kafka
    kafka_emitted = False
    if kafka_publisher is not None:
        run_event = ModelRunEvaluatedEvent(
            run_id=run_id,
            session_id=session_id,
            task_class=resolved_task_class,
            bundle_fingerprint=bundle_fingerprint,
            passed=evaluation_result.passed,
            failures=evaluation_result.failures,
            score_correctness=score.correctness,
            score_safety=score.safety,
            score_cost=score.cost,
            score_latency=score.latency,
            score_maintainability=score.maintainability,
            score_human_time=score.human_time,
            evaluated_at_utc=evaluated_at_utc,
        )
        kafka_emitted = await _emit_to_kafka(
            event=run_event,
            kafka_publisher=kafka_publisher,
            topic=TOPIC_RUN_EVALUATED_V1,
        )
        if kafka_emitted:
            logger.info(
                "RunEvaluatedEvent emitted",
                extra={
                    "run_id": run_id,
                    "passed": evaluation_result.passed,
                    "bundle_fingerprint": bundle_fingerprint,
                },
            )

    # Stage 7: Store EvaluationResult to DB
    db_stored = False
    if db_conn is not None:
        db_stored = await _store_to_db(
            evaluation_result=evaluation_result,
            bundle_fingerprint=bundle_fingerprint,
            run_id=run_id,
            session_id=session_id,
            task_class=resolved_task_class,
            evaluated_at_utc=evaluated_at_utc,
            db_conn=db_conn,
        )

    return ModelCollectionOutput(
        run_id=run_id,
        session_id=session_id,
        bundle_fingerprint=bundle_fingerprint,
        passed=evaluation_result.passed,
        evidence_item_count=len(items_dicts),
        kafka_emitted=kafka_emitted,
        db_stored=db_stored,
        skipped=False,
    )


async def fire_and_forget_evaluate(
    check_results: ModelSessionCheckResults,
    *,
    task_class: str | None = None,
    kafka_publisher: ProtocolKafkaPublisher | None = None,
    db_conn: Any | None = None,
    objective_spec: Any | None = None,
) -> None:
    """Fire-and-forget wrapper for collect_and_evaluate.

    This is the integration point called from handle_stop. It wraps
    collect_and_evaluate in a try/except to ensure that ANY error is
    logged and swallowed — session completion must never be delayed.

    Args:
        check_results: Structured check results from the agent session.
        task_class: Optional task class for ObjectiveSpec selection.
        kafka_publisher: Optional Kafka publisher.
        db_conn: Optional DB connection.
        objective_spec: Optional pre-constructed ObjectiveSpec.
    """
    try:
        output = await collect_and_evaluate(
            check_results,
            task_class=task_class,
            kafka_publisher=kafka_publisher,
            db_conn=db_conn,
            objective_spec=objective_spec,
        )
        if output.skipped:
            logger.debug(
                "Objective evaluation skipped",
                extra={
                    "run_id": output.run_id,
                    "skip_reason": output.skip_reason,
                },
            )
        else:
            logger.info(
                "Objective evaluation complete",
                extra={
                    "run_id": output.run_id,
                    "passed": output.passed,
                    "evidence_items": output.evidence_item_count,
                    "kafka_emitted": output.kafka_emitted,
                    "db_stored": output.db_stored,
                },
            )
    except DisallowedEvidenceSourceError:
        logger.error(
            "Disallowed evidence source injection detected — programming contract violation",
            exc_info=True,
        )
    except asyncio.CancelledError:
        raise  # Allow task cancellation to propagate
    except Exception:
        logger.exception(
            "Unexpected error in objective evaluation (non-blocking — session unaffected)"
        )
