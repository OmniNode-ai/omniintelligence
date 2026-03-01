# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Main dispatcher handler for NodePlanReviewerMultiCompute.

Orchestrates a multi-LLM plan review run:

1. Fetch per-model accuracy weights (``handler_confidence_scorer``).
2. Dispatch to the correct strategy handler (S1-S4) based on
   ``command.strategy``.
3. Insert an audit row into ``plan_reviewer_strategy_runs`` (best-effort).
4. Return ``ModelPlanReviewerMultiOutput``.

Architecture note:
    Pure business logic.  Network I/O is performed by caller-injected
    ``ModelCaller`` callables and a ``ProtocolDBConnection``.  No ``httpx``
    or ``os.getenv`` usage is allowed here (ARCH-002).

Ticket: OMN-3290
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.handler_confidence_scorer import (
    ProtocolDBConnection,
    fetch_accuracy_weights,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_independent_merge import (
    handle_independent_merge,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_panel_vote import (
    handle_panel_vote,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_sequential_critique import (
    CriticCaller,
    handle_sequential_critique,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.handlers.strategies.handler_specialist_split import (
    handle_specialist_split,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_plan_review_category import (
    EnumPlanReviewCategory,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_strategy import (
    EnumReviewStrategy,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_review_finding import (
    PlanReviewFinding,
    PlanReviewFindingWithConfidence,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_input import (
    ModelPlanReviewerMultiCommand,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.model_plan_reviewer_multi_output import (
    ModelPlanReviewerMultiOutput,
)

logger = logging.getLogger(__name__)

# Type alias: standard per-model caller.
ModelCaller = Callable[
    [str, list[EnumPlanReviewCategory]],
    Awaitable[list[PlanReviewFinding]],
]

# SQL to insert an audit row into plan_reviewer_strategy_runs.
_SQL_INSERT_STRATEGY_RUN = """
INSERT INTO plan_reviewer_strategy_runs (
    id,
    run_id,
    strategy,
    models_used,
    plan_text_hash,
    findings_count,
    categories_with_findings,
    categories_clean,
    avg_confidence,
    duration_ms
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
"""


def _sha256_hex(text: str) -> str:
    """Return the SHA-256 hex digest of *text*."""
    return hashlib.sha256(text.encode()).hexdigest()


def _avg_confidence(findings: list[PlanReviewFindingWithConfidence]) -> float | None:
    """Return mean confidence across *findings*, or ``None`` if empty."""
    if not findings:
        return None
    return sum(f.confidence for f in findings) / len(findings)


async def _write_strategy_run(
    *,
    db_conn: ProtocolDBConnection,
    run_id_str: str,
    strategy: EnumReviewStrategy,
    models_used: list[EnumReviewModel],
    plan_text: str,
    findings: list[PlanReviewFindingWithConfidence],
    duration_ms: int,
) -> UUID:
    """Insert one row into ``plan_reviewer_strategy_runs``.

    Args:
        db_conn: DB connection to use for the INSERT.
        run_id_str: Caller-supplied correlation ID (empty string if None).
        strategy: Strategy that was executed.
        models_used: Models that participated.
        plan_text: Original plan text (hashed before storage).
        findings: Merged findings from the strategy.
        duration_ms: Wall-clock duration of the run.

    Returns:
        UUID of the newly inserted row.

    Raises:
        Exception: Any DB error is propagated to the caller, which catches
            it and sets ``strategy_run_stored=False``.
    """
    row_id = uuid4()
    plan_hash = _sha256_hex(plan_text)
    models_array = [m.value for m in models_used]

    categories_with_findings: list[str] = sorted({f.category.value for f in findings})
    all_category_values = {c.value for c in EnumPlanReviewCategory}
    categories_clean: list[str] = sorted(
        all_category_values - set(categories_with_findings)
    )

    await db_conn.execute(  # type: ignore[attr-defined]
        _SQL_INSERT_STRATEGY_RUN,
        row_id,
        run_id_str,
        strategy.value,
        models_array,
        plan_hash,
        len(findings),
        categories_with_findings,
        categories_clean,
        _avg_confidence(findings),
        duration_ms,
    )
    return row_id


async def handle_plan_reviewer_multi_compute(
    command: ModelPlanReviewerMultiCommand,
    model_callers: dict[EnumReviewModel, ModelCaller],
    *,
    db_conn: ProtocolDBConnection | None = None,
    critic_caller: CriticCaller | None = None,
) -> ModelPlanReviewerMultiOutput:
    """Dispatch a plan review run and persist an audit row.

    This is the main entry point for the multi-LLM plan reviewer.  It:

    1. Resolves which models to use (``command.model_ids`` or all).
    2. Fetches per-model accuracy weights from the DB (or defaults to 0.5).
    3. Routes to the correct strategy handler (S1-S4).
    4. Attempts to insert an audit row into ``plan_reviewer_strategy_runs``.
    5. Returns ``ModelPlanReviewerMultiOutput`` — always, even if the DB
       write fails.

    Args:
        command: Frozen input command (strategy, plan text, categories, etc.).
        model_callers: Mapping of ``EnumReviewModel`` → async callable that
            calls the real LLM client and returns ``list[PlanReviewFinding]``.
            Callers inject these; the handler never calls LLMs directly.
        db_conn: Optional asyncpg-compatible connection.  When ``None``,
            accuracy weights fall back to 0.5 and the audit row is skipped.
        critic_caller: S3-only critic callable.  Required when
            ``command.strategy == EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE``.
            Ignored for all other strategies.

    Returns:
        ``ModelPlanReviewerMultiOutput`` with merged findings and DB-write
        status.

    Example::

        output = await handle_plan_reviewer_multi_compute(
            command=ModelPlanReviewerMultiCommand(
                plan_text="## Plan\\n1. Step one\\n2. Step two",
                strategy=EnumReviewStrategy.S4_INDEPENDENT_MERGE,
                run_id="OMN-1234",
            ),
            model_callers={
                EnumReviewModel.QWEN3_CODER: my_qwen_caller,
                EnumReviewModel.DEEPSEEK_R1: my_deepseek_caller,
                EnumReviewModel.GEMINI_FLASH: my_gemini_caller,
                EnumReviewModel.GLM_4: my_glm_caller,
            },
            db_conn=pool_conn,
        )
        assert isinstance(output.findings, list)
    """
    t_start = time.monotonic()

    # Resolve models to use.
    if command.model_ids is not None:
        active_callers: dict[EnumReviewModel, ModelCaller] = {
            m: model_callers[m] for m in command.model_ids if m in model_callers
        }
    else:
        active_callers = dict(model_callers)

    models_used = list(active_callers.keys())

    # Fetch accuracy weights (falls back to 0.5 on DB error or None conn).
    accuracy_weights = await fetch_accuracy_weights(db_conn)

    # Dispatch to the correct strategy.
    findings: list[PlanReviewFindingWithConfidence]

    strategy = command.strategy

    if strategy == EnumReviewStrategy.S1_PANEL_VOTE:
        findings = await handle_panel_vote(
            plan_text=command.plan_text,
            categories=command.review_categories,
            model_callers=active_callers,
            accuracy_weights=accuracy_weights,
        )

    elif strategy == EnumReviewStrategy.S2_SPECIALIST_SPLIT:
        findings = await handle_specialist_split(
            plan_text=command.plan_text,
            categories=command.review_categories,
            model_callers=active_callers,
            accuracy_weights=accuracy_weights,
        )

    elif strategy == EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE:
        drafter_caller = active_callers.get(EnumReviewModel.QWEN3_CODER)
        if drafter_caller is None or critic_caller is None:
            logger.warning(
                "handle_plan_reviewer_multi_compute: S3 requires qwen3-coder caller "
                "and critic_caller — falling back to S4 independent_merge"
            )
            findings = await handle_independent_merge(
                plan_text=command.plan_text,
                categories=command.review_categories,
                model_callers=active_callers,
                accuracy_weights=accuracy_weights,
            )
        else:
            findings = await handle_sequential_critique(
                plan_text=command.plan_text,
                categories=command.review_categories,
                drafter_caller=drafter_caller,
                critic_caller=critic_caller,
                accuracy_weights=accuracy_weights,
            )

    else:
        # S4_INDEPENDENT_MERGE — widest coverage, all findings included.
        findings = await handle_independent_merge(
            plan_text=command.plan_text,
            categories=command.review_categories,
            model_callers=active_callers,
            accuracy_weights=accuracy_weights,
        )

    duration_ms = int((time.monotonic() - t_start) * 1000)

    # Best-effort DB write.
    strategy_run_id: UUID | None = None
    strategy_run_stored: bool = False

    if db_conn is not None:
        try:
            strategy_run_id = await _write_strategy_run(
                db_conn=db_conn,
                run_id_str=command.run_id or "",
                strategy=strategy,
                models_used=models_used,
                plan_text=command.plan_text,
                findings=findings,
                duration_ms=duration_ms,
            )
            strategy_run_stored = True
            logger.debug(
                "handle_plan_reviewer_multi_compute: strategy_run row inserted id=%s",
                strategy_run_id,
            )
        except Exception:
            logger.exception(
                "handle_plan_reviewer_multi_compute: DB write failed — "
                "strategy_run_stored=False (review result is still valid)"
            )

    logger.info(
        "handle_plan_reviewer_multi_compute: strategy=%s models=%s findings=%d "
        "stored=%s duration_ms=%d",
        strategy.value,
        [m.value for m in models_used],
        len(findings),
        strategy_run_stored,
        duration_ms,
    )

    return ModelPlanReviewerMultiOutput(
        strategy_run_id=strategy_run_id,
        strategy=strategy,
        models_used=models_used,
        findings=findings,
        findings_count=len(findings),
        strategy_run_stored=strategy_run_stored,
        run_id=command.run_id,
    )


__all__ = ["ModelCaller", "handle_plan_reviewer_multi_compute"]
