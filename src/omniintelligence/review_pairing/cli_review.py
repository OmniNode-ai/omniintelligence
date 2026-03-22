# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI entry point for standalone multi-model adversarial review.

Replaces manual ChatGPT copy-paste workflow with automated multi-model
review using local LLMs and optionally Codex CLI. Supports reviewing
both plan files and PR diffs.

Usage:
    # Review a plan file (default model: deepseek-r1)
    uv run python -m omniintelligence.review_pairing.cli_review --file plan.md

    # Review a PR diff
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --pr 433 --repo OmniNode-ai/omniintelligence

    # Multi-model
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --file plan.md --model codex --model qwen3-coder

    # Output to file
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --file plan.md --output review.json

CLI Stream Policy:
    stdout: canonical ModelMultiReviewResult JSON
    stderr: human-readable summary

Exit Codes:
    0: at least one model succeeded
    1: all models failed

Reference: OMN-5793, OMN-5819
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    MODEL_REGISTRY,
)
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    async_parse_raw as llm_async_parse_raw,
)
from omniintelligence.review_pairing.adapters.adapter_codex_reviewer import (
    async_parse_raw as codex_async_parse_raw,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelExternalReviewResult,
    ModelMultiReviewResult,
)

_DEFAULT_MODEL: str = "deepseek-r1"
_CODEX_MODEL_KEY: str = "codex"


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="cli_review",
        description="Multi-model adversarial review for plans and PRs.",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        type=str,
        help="Path to plan or document file to review.",
    )
    input_group.add_argument(
        "--pr",
        type=int,
        help="PR number to review (requires --repo).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="GitHub repo slug (e.g., OmniNode-ai/omniintelligence). Required with --pr.",
    )
    parser.add_argument(
        "--model",
        type=str,
        action="append",
        default=None,
        help=(
            "Model key to use (repeatable). "
            f"Valid LLM models: {', '.join(sorted(MODEL_REGISTRY.keys()))}. "
            "Use 'codex' for Codex CLI adapter. "
            f"Default: {_DEFAULT_MODEL}"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for JSON results (default: stdout).",
    )
    return parser


async def run_review(
    content: str,
    model_keys: list[str],
    *,
    review_type: str = "plan",
) -> ModelMultiReviewResult:
    """Execute multi-model review.

    Runs each model sequentially and aggregates results.

    Args:
        content: Raw content to review (plan text or PR diff).
        model_keys: List of model keys to use.
        review_type: "plan" for plan review, "pr" for PR diff review.

    Returns:
        Aggregated ModelMultiReviewResult.
    """
    results: list[ModelExternalReviewResult] = []

    for model_key in model_keys:
        if model_key == _CODEX_MODEL_KEY:
            result = await codex_async_parse_raw(
                content,
                review_type=review_type,
            )
        else:
            result = await llm_async_parse_raw(
                content,
                model=model_key,
                review_type=review_type,
            )
        results.append(result)

    models_succeeded = [r.model for r in results if r.success]
    models_failed = [r.model for r in results if not r.success]
    total_findings = sum(r.result_count for r in results if r.success)

    return ModelMultiReviewResult(
        models_attempted=model_keys,
        models_succeeded=models_succeeded,
        models_failed=models_failed,
        results=results,
        total_findings=total_findings,
    )


def _severity_summary(result: ModelMultiReviewResult) -> str:
    """Generate severity bucket summary for stderr.

    Args:
        result: Multi-model review result.

    Returns:
        Human-readable severity summary string.
    """
    buckets: dict[str, int] = {}
    for r in result.results:
        if not r.success:
            continue
        for finding in r.findings:
            sev = finding.severity.value
            buckets[sev] = buckets.get(sev, 0) + 1

    if not buckets:
        return "No findings"

    parts = []
    for sev in ("error", "warning", "info", "hint"):
        count = buckets.get(sev, 0)
        if count > 0:
            parts.append(f"{sev}: {count}")
    return ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code (0=success, 1=all models failed).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve input content.
    if args.pr is not None:
        if not args.repo:
            print("Error: --repo is required with --pr", file=sys.stderr)
            return 1
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(args.pr), "--repo", args.repo],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            review_content = result.stdout
        except FileNotFoundError:
            print("Error: gh CLI not found", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as exc:
            print(f"Error: gh pr diff failed: {exc.stderr.strip()}", file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired:
            print("Error: gh pr diff timed out", file=sys.stderr)
            return 1
        if not review_content.strip():
            print(f"Error: PR #{args.pr} has no diff", file=sys.stderr)
            return 1
        print(f"Reviewing PR #{args.pr} in {args.repo}", file=sys.stderr)
    else:
        plan_path = Path(args.file)
        if not plan_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
        review_content = plan_path.read_text(encoding="utf-8")

    # Resolve model keys.
    model_keys: list[str] = args.model if args.model else [_DEFAULT_MODEL]

    # Determine review type.
    review_type = "pr" if args.pr is not None else "plan"

    # Run review.
    result = asyncio.run(
        run_review(review_content, model_keys, review_type=review_type)
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
    print(
        f"\nModels attempted: {', '.join(result.models_attempted)}",
        file=sys.stderr,
    )
    if result.models_succeeded:
        print(
            f"Models succeeded: {', '.join(result.models_succeeded)}",
            file=sys.stderr,
        )
    if result.models_failed:
        failed_details = []
        for r in result.results:
            if not r.success:
                failed_details.append(f"{r.model} ({r.error})")
        print(
            f"Models failed: {', '.join(failed_details)}",
            file=sys.stderr,
        )
    print(
        f"Total findings: {result.total_findings}",
        file=sys.stderr,
    )
    print(
        f"Severity: {_severity_summary(result)}",
        file=sys.stderr,
    )

    # Exit code: 0 if at least one model succeeded.
    return 0 if result.models_succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
