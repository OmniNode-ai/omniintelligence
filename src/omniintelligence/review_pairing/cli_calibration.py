# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI entry point for review calibration.

Runs multi-challenger calibration against a ground-truth model,
computing precision/recall/F1/noise metrics per challenger.

Usage:
    uv run python -m omniintelligence.review_pairing.cli_calibration \\
        --file plan.md \\
        --ground-truth codex \\
        --challenger deepseek-r1 \\
        --challenger qwen3-coder

CLI Stream Policy:
    stdout: canonical CalibrationOrchestrationResult JSON
    stderr: human-readable summary with metrics table

Exit Codes:
    0: at least one challenger succeeded
    1: all challengers failed or fatal error

Reference: OMN-6172
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from omniintelligence.review_pairing.alignment_engine import (
    FindingAlignmentEngine,
)
from omniintelligence.review_pairing.calibration_scorer import CalibrationScorer
from omniintelligence.review_pairing.models_calibration import (
    CalibrationConfig,
    CalibrationMetrics,
    CalibrationOrchestrationResult,
    CalibrationRunResult,
)
from omniintelligence.review_pairing.serializer_r1r6 import (
    serialize_external_finding,
)

_DEFAULT_GROUND_TRUTH: str = "codex"


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for calibration CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="cli_calibration",
        description="Multi-challenger calibration against a ground-truth model.",
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="Path to plan or document file to review.",
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        default=_DEFAULT_GROUND_TRUTH,
        help=f"Model key for ground truth (default: {_DEFAULT_GROUND_TRUTH}).",
    )
    parser.add_argument(
        "--challenger",
        type=str,
        action="append",
        required=True,
        help="Model key for challenger (repeatable, required).",
    )
    parser.add_argument(
        "--r1r6-findings",
        type=str,
        default=None,
        help="Optional JSON file with R1-R6 findings.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write JSON output to file (default: stdout).",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        default=False,
        help="Save results to PostgreSQL.",
    )
    parser.add_argument(
        "--no-embedding",
        action="store_true",
        default=False,
        help="Force string-based alignment (disable embedding client).",
    )
    parser.add_argument(
        "--dry-run-fewshot",
        action="store_true",
        default=False,
        help="Preview few-shot examples without writing.",
    )
    return parser


def format_metrics_table(metrics: list[CalibrationMetrics]) -> str:
    """Format metrics as a human-readable table for stderr.

    Args:
        metrics: List of per-model CalibrationMetrics.

    Returns:
        Formatted table string.
    """
    if not metrics:
        return "No metrics to display."

    header = f"{'Model':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Noise':>10}"
    sep = "-" * len(header)
    rows = []
    for m in metrics:
        rows.append(
            f"{m.model:<25} {m.precision:>10.3f} {m.recall:>10.3f} "
            f"{m.f1_score:>10.3f} {m.noise_ratio:>10.3f}"
        )
    return "\n".join([sep, header, sep, *rows, sep])


async def _run_calibration(
    content: str,
    config: CalibrationConfig,
    *,
    no_embedding: bool = False,
    r1r6_findings_path: str | None = None,
) -> CalibrationOrchestrationResult:
    """Run calibration orchestration.

    Dispatches ground-truth and challenger reviews, aligns findings,
    and computes metrics.

    Args:
        content: File content to review.
        config: Calibration configuration.
        no_embedding: If True, use string-based alignment only.
        r1r6_findings_path: Optional path to R1-R6 findings JSON.

    Returns:
        CalibrationOrchestrationResult with per-challenger metrics.
    """
    from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
        async_parse_raw as llm_async_parse_raw,
    )
    from omniintelligence.review_pairing.adapters.adapter_codex_reviewer import (
        async_parse_raw as codex_async_parse_raw,
    )
    from omniintelligence.review_pairing.models_calibration import (
        CalibrationFindingTuple,
    )

    # Get ground-truth findings.
    gt_model = config.ground_truth_model
    print(f"Running ground-truth model: {gt_model}", file=sys.stderr)

    if gt_model == "codex":
        gt_result = await codex_async_parse_raw(content, review_type="plan")
    else:
        gt_result = await llm_async_parse_raw(
            content, model=gt_model, review_type="plan"
        )

    if not gt_result.success:
        return CalibrationOrchestrationResult(
            success=False,
            error=f"Ground-truth model {gt_model} failed: {gt_result.error}",
            ground_truth_findings=[],
            challenger_results=[],
        )

    # Serialize ground-truth findings.
    gt_findings: list[CalibrationFindingTuple] = [
        serialize_external_finding(f) for f in gt_result.findings
    ]

    # Load R1-R6 findings if provided.
    if r1r6_findings_path:
        r1r6_path = Path(r1r6_findings_path)
        if r1r6_path.exists():
            r1r6_data = json.loads(r1r6_path.read_text(encoding="utf-8"))
            for item in r1r6_data:
                from omniintelligence.review_pairing.models import (
                    ReviewFindingObserved,
                )

                finding = ReviewFindingObserved(**item)
                gt_findings.append(serialize_external_finding(finding))

    # Build alignment engine.
    embedding_client = None
    if not no_embedding:
        embedding_url = os.environ.get("LLM_EMBEDDING_URL")
        if embedding_url:
            print(
                f"Embedding URL available ({embedding_url}) but client "
                "not yet wired; falling back to string-based alignment.",
                file=sys.stderr,
            )

    alignment_engine = FindingAlignmentEngine(
        similarity_threshold=config.similarity_threshold,
        embedding_client=embedding_client,
        category_families=config.category_families,
    )
    scorer = CalibrationScorer()

    # Run each challenger.
    challenger_results: list[CalibrationRunResult] = []
    import uuid
    from datetime import datetime, timezone

    for challenger_model in config.challenger_models:
        print(f"Running challenger: {challenger_model}", file=sys.stderr)

        try:
            if challenger_model == "codex":
                ch_result = await codex_async_parse_raw(content, review_type="plan")
            else:
                ch_result = await llm_async_parse_raw(
                    content, model=challenger_model, review_type="plan"
                )

            if not ch_result.success:
                challenger_results.append(
                    CalibrationRunResult(
                        run_id=str(uuid.uuid4()),
                        ground_truth_model=gt_model,
                        challenger_model=challenger_model,
                        alignments=[],
                        metrics=None,
                        prompt_version=ch_result.prompt_version,
                        error=ch_result.error or "Unknown error",
                        created_at=datetime.now(tz=timezone.utc),
                    )
                )
                continue

            ch_findings = [serialize_external_finding(f) for f in ch_result.findings]

            alignments = await alignment_engine.align(gt_findings, ch_findings)
            metrics = scorer.score(alignments, challenger_model)

            challenger_results.append(
                CalibrationRunResult(
                    run_id=str(uuid.uuid4()),
                    ground_truth_model=gt_model,
                    challenger_model=challenger_model,
                    alignments=alignments,
                    metrics=metrics,
                    prompt_version=ch_result.prompt_version,
                    embedding_model_version=alignment_engine._get_model_version(),
                    created_at=datetime.now(tz=timezone.utc),
                )
            )
        except Exception as exc:
            challenger_results.append(
                CalibrationRunResult(
                    run_id=str(uuid.uuid4()),
                    ground_truth_model=gt_model,
                    challenger_model=challenger_model,
                    alignments=[],
                    metrics=None,
                    prompt_version="unknown",
                    error=str(exc),
                    created_at=datetime.now(tz=timezone.utc),
                )
            )

    any_succeeded = any(r.metrics is not None for r in challenger_results)
    return CalibrationOrchestrationResult(
        success=any_succeeded,
        ground_truth_findings=gt_findings,
        challenger_results=challenger_results,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code (0=success, 1=all challengers failed).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate file exists.
    plan_path = Path(args.file)
    if not plan_path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    # Validate --persist requires DB URL.
    if args.persist and not os.environ.get("OMNIBASE_INFRA_DB_URL"):
        print(
            "Error: --persist requires OMNIBASE_INFRA_DB_URL in environment",
            file=sys.stderr,
        )
        return 1

    content = plan_path.read_text(encoding="utf-8")

    config = CalibrationConfig(
        ground_truth_model=args.ground_truth,
        challenger_models=args.challenger,
    )

    # Run calibration.
    result = asyncio.run(
        _run_calibration(
            content,
            config,
            no_embedding=args.no_embedding,
            r1r6_findings_path=args.r1r6_findings,
        )
    )

    # Output JSON to stdout (or file).
    json_output = result.model_dump_json(indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output + "\n", encoding="utf-8")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json_output)

    # Human-readable summary to stderr.
    succeeded = [r for r in result.challenger_results if r.metrics is not None]
    failed = [r for r in result.challenger_results if r.metrics is None]

    print(
        f"\nGround truth: {config.ground_truth_model}",
        file=sys.stderr,
    )
    print(
        f"Challengers attempted: {', '.join(config.challenger_models)}",
        file=sys.stderr,
    )
    if succeeded:
        print(
            f"Succeeded: {', '.join(r.challenger_model for r in succeeded)}",
            file=sys.stderr,
        )
    if failed:
        failed_details = [f"{r.challenger_model} ({r.error})" for r in failed]
        print(
            f"Failed: {', '.join(failed_details)}",
            file=sys.stderr,
        )

    # Metrics table.
    metrics_list = [r.metrics for r in succeeded if r.metrics is not None]
    print(format_metrics_table(metrics_list), file=sys.stderr)

    # Persist if requested.
    if args.persist and succeeded:
        _persist_results(result, config)

    return 0 if result.success else 1


def _persist_results(
    result: CalibrationOrchestrationResult,
    config: CalibrationConfig,
) -> None:
    """Persist calibration results to PostgreSQL.

    Args:
        result: Orchestration result.
        config: Calibration config.
    """
    print("Persisting results to PostgreSQL...", file=sys.stderr)
    # Persistence requires asyncpg and a running database.
    # The actual persistence call would be:
    #   async with asyncpg.connect(db_url) as conn:
    #       persistence = CalibrationPersistence(conn)
    #       for run in result.challenger_results:
    #           await persistence.save_run(run, content_hash)
    #           if run.metrics:
    #               await persistence.update_model_score(
    #                   run.challenger_model,
    #                   config.ground_truth_model,
    #                   run.metrics.f1_score,
    #               )
    print("Persistence not yet wired (requires asyncpg).", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
