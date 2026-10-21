# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI entry point for standalone multi-model adversarial review.

Replaces manual ChatGPT copy-paste workflow with automated multi-model
review using local LLMs and optionally Codex CLI. Supports reviewing
both plan files and PR diffs.

Usage:
    # Review a plan file (default model: qwen3-review)
    uv run python -m omniintelligence.review_pairing.cli_review --file plan.md

    # Review a PR diff
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --pr 433 --repo OmniNode-ai/omniintelligence

    # Multi-model
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --file plan.md --model codex --model qwen3-coder

    # With persona injection
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --file plan.md --persona analytical-strict

    # With custom system prompt file
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --file plan.md --system-prompt /path/to/my-prompt.md

    # Voters from the contract overlay (OMN-20910) -- the Hostile Reviewer gate
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --pr 433 --repo OmniNode-ai/omniintelligence \\
        --voters-overlay docker/lane-overlays/hostile-review-voters.yaml

    # Output to file
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --file plan.md --output review.json

    # Gated review against the reviewed repository's standing rules, read from
    # the protected base branch (never the pull request's own branch)
    uv run python -m omniintelligence.review_pairing.cli_review \\
        --pr 433 --repo OmniNode-ai/omniintelligence --gated \\
        --rules-file .review/standing-rules.yaml --rules-base-ref origin/dev

    # Validate a rules file (and, with a base ref, check it weakens nothing)
    uv run python -m omniintelligence.review_pairing.cli_review \\
        validate-rules --rules-file .review/standing-rules.yaml

    # The review bot judges rejected findings (OMN-17427): a judge from the CI
    # overlay that is none of the voters accepts or refuses each rejection
    uv run python -m omniintelligence.review_pairing.cli_review \\
        judge-rejections --pending pending.json --output judgements.json \\
        --voters-overlay overlay.yaml --judge-overlay rejection_judge.yaml

CLI Stream Policy:
    stdout: canonical ModelMultiReviewResult JSON, including the quorum
        verdict a caller reads instead of summing severities itself
    stderr: human-readable summary

Standing rules (OMN-20784):
    ``--rules-file`` supplies the reviewed repository's standing rules, rendered
    into every model's prompt by id, and the digest lands in the verdict.
    ``--gated`` makes them mandatory: no rules file, or an invalid one, exits 1
    before any model call. ``--rules-base-ref`` reads the file from that git ref
    instead of the working tree, so a pull request cannot supply its own rules;
    the pull request's copy (``--rules-head-ref``, default HEAD) is only checked
    against the base, and a mandatory base rule it removes, demotes or rewords
    makes the verdict BLOCKED without a model call.

Exit Codes:
    0: a verdict was produced. Whether it PASSED or BLOCKED is in
       ``quorum.verdict`` -- the exit code says a verdict exists, not that
       the review was clean, because every caller already reads the
       document and several would misread a blocking exit as an outage.
    1: no review happened (every model failed, or the invocation was
       rejected before any model ran)
    2: DEGRADED QUORUM -- fewer models succeeded than
       ``review_quorum.min_agreeing_models`` requires, so agreement could
       not be established and there is NO valid verdict. Distinct from 1
       (something ran) and from 0 (a verdict exists). Callers fail closed
       on it; treating it as a pass makes the quorum vacuous. With
       ``--voters-overlay`` it also means a REQUIRED voter did not vote
       (unreachable or failed); the voter is named on stderr (OMN-20910).
       A required voter that TIMED OUT, or whose endpoint was UNAVAILABLE
       (HTTP 502/503/504, a refused or failed connection, a failed
       reachability probe), counts as voted only when the overlay declares
       ``substitute_votes`` and the pull request carries enough valid, clean,
       signed review receipts for ``--head-sha`` (OMN-20947).

Review records (OMN-20981):
    ``--record-out FILE`` writes one ``ModelReviewRecorded`` per voter and per
    substitute vote, as JSON lines, findings included.

Reference: OMN-5793, OMN-5819, OMN-6228, OMN-18479, OMN-20910, OMN-20947, OMN-20981
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import secrets
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NamedTuple
from uuid import uuid4

from omniintelligence.handlers.handler_review_standing_rules import (
    handle as handle_standing_rules,
)
from omniintelligence.models.review.model_review_standing_rules import (
    ModelReviewStandingRules,
)
from omniintelligence.models.review.model_standing_rules_record import (
    ModelStandingRulesRecord,
)
from omniintelligence.models.review.model_standing_rules_request import (
    ModelStandingRulesRequest,
)
from omniintelligence.models.review.model_standing_rules_result import (
    ModelStandingRulesResult,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    apply_substitutes,
    substitutable_failure,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.handlers.handler_review_receipt_substitute import (
    handle as decide_substitute_votes,
)
from omniintelligence.nodes.node_review_receipt_substitute_compute.models import (
    ModelPullRequestReviewView,
    ModelSubstituteVoteRequest,
)
from omniintelligence.nodes.node_review_record_compute.handlers.handler_review_record import (
    handle as record_handle,
)
from omniintelligence.nodes.node_review_record_compute.models import (
    ModelReviewRecordRequest,
)
from omniintelligence.nodes.node_review_rejection_judge_compute.handlers.handler_review_rejection_judge import (
    JSON_ONLY_RETRY as _JUDGE_JSON_ONLY_RETRY,
)
from omniintelligence.nodes.node_review_rejection_judge_compute.handlers.handler_review_rejection_judge import (
    handle as plan_rejection_judgement,
)
from omniintelligence.nodes.node_review_rejection_judge_compute.handlers.handler_review_rejection_judge import (
    read_judgement,
)
from omniintelligence.nodes.node_review_rejection_judge_compute.models import (
    ModelRejectionJudgeBatch,
    ModelRejectionJudgeBatchResult,
    ModelRejectionJudgementRecord,
    ModelRejectionJudgeRequest,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter_roster import (
    ModelReviewVoterRoster,
)
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    _DEFAULT_MODEL_KEY as _DEFAULT_MODEL,
)
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    MODEL_REGISTRY,
    SERVED_BASE_URLS,
    call_model,
    probe_local_reachability,
    register_review_voters,
    select_models_with_fallback,
)
from omniintelligence.review_pairing.adapters.adapter_ai_reviewer import (
    async_parse_raw as llm_async_parse_raw,
)
from omniintelligence.review_pairing.adapters.adapter_codex_reviewer import (
    async_parse_raw as codex_async_parse_raw,
)
from omniintelligence.review_pairing.cli_review_models import ModelPersonaConfig
from omniintelligence.review_pairing.model_registry_loader import (
    load_registry,
    load_review_voters,
    resolve_endpoint_url,
)
from omniintelligence.review_pairing.models import EnumFindingSeverity
from omniintelligence.review_pairing.models_external_review import (
    EnumQuorumVerdict,
    ModelExternalReviewResult,
    ModelMultiReviewResult,
    ModelQuorumFinding,
    ModelReviewQuorumPolicy,
    ModelReviewQuorumSummary,
)
from omniintelligence.review_pairing.persona_loader import load_persona
from omniintelligence.review_pairing.prompts.adversarial_reviewer import PROMPT_VERSION
from omniintelligence.review_pairing.quorum import (
    evaluate_quorum,
    format_quorum_summary,
)
from omniintelligence.review_pairing.reviewer_identity import reviewer_identity
from omniintelligence.review_pairing.served_model_resolver import (
    ServedModelResolutionError,
    resolve_served_model_id,
)

_CODEX_MODEL_KEY: str = "codex"
_LARGE_PR_DIFF_MARKERS: tuple[str, ...] = (
    "PullRequest.diff too_large",
    "diff exceeded the maximum number of files",
    "HTTP 406",
)
_MAX_FALLBACK_REVIEW_CHARS = 120_000
_MAX_FALLBACK_PATCH_CHARS = 6_000
_VOTER_MODEL_PROBE_TIMEOUT_SECONDS = 15.0


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
        "--voters-overlay",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "Review voters overlay (review_voters_overlay.v1 or .v2, OMN-20910). The "
            "overlay IS the roster: each voter's endpoint, model, sampling, "
            "focus, timeout and required flag come from it. Excludes --model. "
            "No API fallback is substituted for a voter, and a required voter "
            "that is unreachable or fails makes the run exit 2, naming it."
        ),
    )
    parser.add_argument(
        "--head-sha",
        type=str,
        default=None,
        metavar="SHA",
        help=(
            "The pull request head commit this run reviews (with --pr). Needed "
            "only when the voters overlay declares substitute_votes: a voter "
            "that times out or is unavailable may then be replaced by clean "
            "off-CI review receipts bound to exactly this commit (OMN-20947)."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for JSON results (default: stdout).",
    )
    parser.add_argument(
        "--record-out",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "Write one typed review record (ModelReviewRecorded, one JSON "
            "object per line) per voter and per substitute vote, findings "
            "included (OMN-20981). A run that reviews nothing writes an empty "
            "file."
        ),
    )
    parser.add_argument(
        "--persona",
        type=str,
        default=None,
        metavar="NAME",
        help=(
            "Persona name from review_pairing/personas/ "
            "(e.g., analytical-strict). Fails hard if name not found. "
            "Prepends persona content to the system prompt for each LLM call."
        ),
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        metavar="FILE",
        help=(
            "Path to a custom system prompt .md file. Ignored if --persona is also set."
        ),
    )
    parser.add_argument(
        "--quorum-threshold",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Raise the number of distinct models that must agree before a "
            "finding blocks. Defaults to review_quorum.min_agreeing_models "
            "in model_registry.yaml. A value BELOW the contract minimum is "
            "refused -- the threshold can be raised, never lowered."
        ),
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        default=False,
        help=(
            "Disable automatic API fallback when local models are unreachable. "
            "Unreachable local models will cause the run to exit 1."
        ),
    )
    _add_rules_arguments(parser)
    parser.add_argument(
        "--gated",
        action="store_true",
        default=False,
        help=(
            "Run only with the reviewed repository's standing rules: requires "
            "--rules-file (and, with --pr, --rules-base-ref). A missing or "
            "invalid rules file exits 1 before any model call."
        ),
    )
    return parser


def _add_rules_arguments(parser: argparse.ArgumentParser) -> None:
    """Arguments shared by the review and ``validate-rules`` commands."""
    parser.add_argument(
        "--rules-file",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Standing rules file of the reviewed repository (YAML, "
            "ModelReviewStandingRules). Repo-relative when --rules-base-ref is set."
        ),
    )
    parser.add_argument(
        "--rules-base-ref",
        type=str,
        default=None,
        metavar="REF",
        help=(
            "Git ref of the protected base branch to read --rules-file from, "
            "instead of the working tree. The pull request's own copy is only "
            "compared against it."
        ),
    )
    parser.add_argument(
        "--rules-head-ref",
        type=str,
        default="HEAD",
        metavar="REF",
        help="Git ref of the pull request's head, compared with the base rules.",
    )
    parser.add_argument(
        "--rules-repo-dir",
        type=str,
        default=".",
        metavar="DIR",
        help="Directory of the git repository the refs are read from.",
    )


class _RulesLoad(NamedTuple):
    """Outcome of loading the standing rules for a review."""

    result: ModelStandingRulesResult | None
    source: str
    error: str | None


class _GitReadError(Exception):
    """A rules file could not be read from git for a reason other than absence."""


def _git_show(repo_dir: str, ref: str, path: str) -> str | None:
    """Text of ``path`` at ``ref``; None when the ref has no such file."""
    try:
        completed = subprocess.run(
            ["git", "-C", repo_dir, "show", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise _GitReadError(f"git show {ref}:{path} failed: {exc}") from exc
    if completed.returncode == 0:
        return completed.stdout
    stderr = completed.stderr.strip()
    if "does not exist in" in stderr or "exists on disk, but not in" in stderr:
        return None
    raise _GitReadError(f"git show {ref}:{path} failed: {stderr}")


def _read_rules_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError):
        return None
    except (OSError, UnicodeDecodeError) as exc:
        raise _GitReadError(f"cannot read rules file {path}: {exc}") from exc


def _load_standing_rules(
    *,
    rules_file: str,
    base_ref: str | None,
    head_ref: str,
    repo_dir: str,
) -> _RulesLoad:
    """Read and check the rules; from the base ref when one is given.

    With a base ref the working tree is never read: the authoritative text is
    the base branch's, and the head ref's copy is only compared with it.
    """
    try:
        if base_ref is None:
            result = handle_standing_rules(
                ModelStandingRulesRequest(rules_text=_read_rules_text(rules_file))
            )
            return _RulesLoad(result, rules_file, None)
        if Path(rules_file).is_absolute():
            return _RulesLoad(
                None,
                rules_file,
                "--rules-file must be repo-relative when --rules-base-ref is set",
            )
        result = handle_standing_rules(
            ModelStandingRulesRequest(
                rules_text=_git_show(repo_dir, base_ref, rules_file),
                compare_candidate=True,
                candidate_text=_git_show(repo_dir, head_ref, rules_file),
            )
        )
        return _RulesLoad(result, f"{base_ref}:{rules_file}", None)
    except _GitReadError as exc:
        return _RulesLoad(None, rules_file, str(exc))


def _rules_record(
    result: ModelStandingRulesResult, *, source: str, gated: bool
) -> ModelStandingRulesRecord | None:
    """The verdict's record of the rules in force; None without valid rules."""
    rules: ModelReviewStandingRules | None = result.rules
    if rules is None:
        return None
    return ModelStandingRulesRecord(
        version=rules.version,
        digest=rules.digest,
        rule_ids=tuple(r.id for r in rules.rules),
        mandatory_rule_ids=tuple(r.id for r in rules.rules if r.mandatory),
        source=source,
        gated=gated,
        violations=result.weakened,
        candidate_errors=result.candidate_errors,
    )


def _rules_refusal(args: argparse.Namespace) -> str | None:
    """Why the invocation is refused before any rules are read, or None."""
    if args.rules_file is None:
        if args.gated:
            return "--gated requires --rules-file"
        if args.rules_base_ref is not None:
            return "--rules-base-ref requires --rules-file"
    elif args.gated and args.pr is not None and args.rules_base_ref is None:
        return (
            "--gated with --pr requires --rules-base-ref: the rules of a pull "
            "request come from its protected base branch, never from its own branch"
        )
    return None


def _blocked_by_weakened_rules(
    record: ModelStandingRulesRecord,
    rules_path: str,
    policy: ModelReviewQuorumPolicy,
) -> ModelMultiReviewResult:
    """Verdict for a pull request whose rules file weakens the base rules.

    No model ran: the verdict is BLOCKED because the change under review drops
    or weakens a mandatory rule, which needs no opinion to establish.
    """
    blocking = [
        ModelQuorumFinding(
            file_path=rules_path,
            line_start=1,
            severity=EnumFindingSeverity.ERROR,
            rule=f"standing:{v.rule_id}",
            message=(
                f"mandatory standing rule {v.rule_id!r} is {v.reason} by the "
                "pull request's rules file"
            ),
            agreeing_models=(),
            agreement_count=0,
            blocking=True,
            standing_rule_id=v.rule_id,
        )
        for v in record.violations
    ]
    if record.candidate_errors:
        blocking.append(
            ModelQuorumFinding(
                file_path=rules_path,
                line_start=1,
                severity=EnumFindingSeverity.ERROR,
                rule="rules-file:invalid",
                message=(
                    "the pull request's rules file is invalid: "
                    + "; ".join(record.candidate_errors)
                ),
                agreeing_models=(),
                agreement_count=0,
                blocking=True,
            )
        )
    return ModelMultiReviewResult(
        quorum=ModelReviewQuorumSummary(
            verdict=EnumQuorumVerdict.BLOCKED,
            quorum_threshold=policy.min_agreeing_models,
            quorum_met=False,
            blocking_count=len(blocking),
            blocking_findings=tuple(blocking),
        ),
        skipped_reason="standing_rules_weakened",
        standing_rules=record,
    )


def _validate_rules_main(argv: list[str]) -> int:
    """``validate-rules``: check a rules file, and optionally a pull request's copy."""
    parser = argparse.ArgumentParser(
        prog="cli_review validate-rules",
        description="Validate a standing rules file against ModelReviewStandingRules.",
    )
    _add_rules_arguments(parser)
    args = parser.parse_args(argv)
    if args.rules_file is None:
        print("Error: validate-rules requires --rules-file", file=sys.stderr)
        return 1
    load = _load_standing_rules(
        rules_file=args.rules_file,
        base_ref=args.rules_base_ref,
        head_ref=args.rules_head_ref,
        repo_dir=args.rules_repo_dir,
    )
    if load.result is None:
        report: dict[str, object] = {"ok": False, "errors": [load.error]}
    else:
        rules = load.result.rules
        report = {
            "ok": load.result.ok,
            "source": load.source,
            "version": rules.version if rules else None,
            "digest": rules.digest if rules else None,
            "rule_ids": [r.id for r in rules.rules] if rules else [],
            "mandatory_rule_ids": (
                [r.id for r in rules.rules if r.mandatory] if rules else []
            ),
            "errors": list(load.result.errors),
            "violations": [v.model_dump() for v in load.result.weakened],
            "candidate_errors": list(load.result.candidate_errors),
        }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


async def run_review(
    content: str,
    model_keys: list[str],
    *,
    review_type: str = "plan",
    persona: ModelPersonaConfig | None = None,
    standing_rules: ModelReviewStandingRules | None = None,
    repository: str | None = None,
) -> ModelMultiReviewResult:
    """Execute multi-model review.

    Runs each model sequentially and aggregates results.

    Args:
        content: Raw content to review (plan text or PR diff).
        model_keys: List of model keys to use.
        review_type: "plan" for plan review, "pr" for PR diff review.
        persona: Optional persona config. When provided, persona content is
            prepended to the system prompt for each LLM call.
        standing_rules: The reviewed repository's standing rules (OMN-20784).
            Handed to every model; when None the call is exactly as before.
        repository: Repository sent to each LLM voter as metadata.repository
            (OMN-20106). None sends no metadata.

    Returns:
        Aggregated ModelMultiReviewResult.
    """
    results: list[ModelExternalReviewResult] = []

    # OMN-15066: print a visible progress marker around each sequential model
    # call. This does NOT depend on Python logging configuration (unlike the
    # omnibase_infra transport's retry-loop logger, fixed separately) --
    # cli_review.py never calls logging.basicConfig, so a caller that only
    # captures stderr (e.g. the hostile-reviewer GitHub Actions step) would
    # otherwise see nothing at all between "Reviewing PR #N" and the final
    # JSON output, indistinguishable from a hang for the full duration of a
    # slow or stalled model call.
    for model_key in model_keys:
        config = MODEL_REGISTRY.get(model_key)
        timeout_note = (
            f"timeout={config.timeout_seconds:g}s"
            if config is not None
            else "timeout=?"
        )
        print(
            f"Calling model '{model_key}' ({timeout_note})...",
            file=sys.stderr,
            flush=True,
        )
        call_started_at = time.monotonic()
        SERVED_BASE_URLS.pop(model_key, None)
        if model_key == _CODEX_MODEL_KEY:
            if standing_rules is None:
                result = await codex_async_parse_raw(content, review_type=review_type)
            else:
                result = await codex_async_parse_raw(
                    content, review_type=review_type, standing_rules=standing_rules
                )
        else:
            prefix = persona.content if persona is not None else None
            if standing_rules is None:
                result = await llm_async_parse_raw(
                    content,
                    model=model_key,
                    review_type=review_type,
                    system_prompt_prefix=prefix,
                    repository=repository,
                )
            else:
                result = await llm_async_parse_raw(
                    content,
                    model=model_key,
                    review_type=review_type,
                    system_prompt_prefix=prefix,
                    standing_rules=standing_rules,
                    repository=repository,
                )
        elapsed = time.monotonic() - call_started_at
        # OMN-17492: record WHICH reviewer this key is (endpoint + model), so
        # the quorum counts two names for one model once.
        result = result.model_copy(
            update={
                "reviewer_identity": reviewer_identity(
                    model_key,
                    config,
                    os.environ,
                    served_base_url=SERVED_BASE_URLS.get(model_key),
                )
            }
        )
        status = "succeeded" if result.success else "FAILED"
        dropped_note = (
            f", {len(result.dropped_findings)} dropped as self-negating"
            if result.dropped_findings
            else ""
        )
        print(
            f"Model '{model_key}' {status} in {elapsed:.1f}s "
            f"({result.result_count} finding(s){dropped_note}).",
            file=sys.stderr,
            flush=True,
        )
        results.append(result)

    models_succeeded = [r.model for r in results if r.success]
    models_failed = [r.model for r in results if not r.success]
    total_findings = sum(r.result_count for r in results if r.success)
    total_dropped = sum(len(r.dropped_findings) for r in results if r.success)

    return ModelMultiReviewResult(
        models_attempted=model_keys,
        models_succeeded=models_succeeded,
        models_failed=models_failed,
        results=results,
        total_findings=total_findings,
        total_dropped=total_dropped,
    )


def _select_overlay_voters(
    roster: ModelReviewVoterRoster,
) -> tuple[list[str], list[str]]:
    """Probe every overlay voter; return (voters to call, unreachable voters).

    No fallback is substituted for an unreachable voter (OMN-20910): the
    overlay names the roster and a silent stand-in would be a different
    review. When a REQUIRED voter is unreachable and the overlay declares no
    ``substitute_votes`` policy, no voter is called at all -- the run cannot
    produce a verdict, so the remaining calls would only spend shared lab
    capacity. With a policy, the reachable voters are still called: signed
    off-CI receipts may stand in for the unreachable voter, but never without
    a real vote beside them (OMN-20947). Each reachable voter's served model is read and
    printed, so the job log names the model every vote came from.
    """
    reachability = probe_local_reachability(roster.voter_ids)
    for resolved_voter in roster.voters:
        if resolved_voter.voter.provider in {"anthropic", "claude_code"}:
            # Missing credentials are a named failed vote from the adapter,
            # never an unreachable lab endpoint eligible for substitution.
            reachability[resolved_voter.voter_id] = True
    skipped = [vid for vid in roster.voter_ids if not reachability.get(vid, False)]
    for voter_id in skipped:
        level = "ERROR" if voter_id in roster.required_ids else "WARNING"
        role = "required" if voter_id in roster.required_ids else "optional"
        print(
            f"{level}: {role} review voter {voter_id!r} is unreachable "
            f"({_endpoint_label(voter_id)}).",
            file=sys.stderr,
        )
    if any(voter_id in roster.required_ids for voter_id in skipped):
        if roster.substitute_votes is None:
            print(
                "ERROR: a required review voter is unreachable; no voter is called.",
                file=sys.stderr,
            )
            return [], skipped
        print(
            "WARNING: a required review voter is unreachable; the reachable "
            "voters are called because the overlay allows signed review "
            "receipts to stand in for it.",
            file=sys.stderr,
        )

    selected = [vid for vid in roster.voter_ids if vid not in skipped]
    for voter_id in selected:
        voter = roster.get(voter_id)
        if (
            voter is None
            or voter.voter.provider in {"anthropic", "claude_code"}
            or voter.voter.model_id_source != "served"
        ):
            continue
        try:
            served = resolve_served_model_id(
                voter.base_url, timeout_seconds=_VOTER_MODEL_PROBE_TIMEOUT_SECONDS
            )
        except ServedModelResolutionError as exc:
            print(
                f"WARNING: review voter {voter_id!r} served model unresolved: {exc}",
                file=sys.stderr,
            )
            continue
        print(
            f"Review voter {voter_id!r} -> {voter.base_url} serves model {served}",
            file=sys.stderr,
        )
    return selected, skipped


def _record_unreachable(
    result: ModelMultiReviewResult, skipped: list[str]
) -> ModelMultiReviewResult:
    """Name every reviewer the reachability probe dropped (OMN-17492).

    A dropped key used to vanish from the emitted JSON, so a run that lost a
    reviewer read like a run that never asked for it. Each one is recorded as
    an attempted, failed model. It never succeeds, so the quorum is unchanged.
    """
    if not skipped:
        return result
    failed = [
        ModelExternalReviewResult(
            model=key,
            prompt_version=PROMPT_VERSION,
            success=False,
            error=(
                "unreachable: the TCP reachability probe of "
                f"{_endpoint_label(key)} failed, so this reviewer was not called"
            ),
        )
        for key in skipped
        if key not in result.models_attempted
    ]
    if not failed:
        return result
    return result.model_copy(
        update={
            "models_attempted": [*result.models_attempted, *(r.model for r in failed)],
            "models_failed": [*result.models_failed, *(r.model for r in failed)],
            "results": [*result.results, *failed],
        }
    )


def _fetch_pr_reviews(repo: str, pr: int) -> list[ModelPullRequestReviewView]:
    """Every review on the pull request, as the gate reads them (OMN-20947)."""
    completed = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/pulls/{pr}/reviews?per_page=100",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    reviews: list[ModelPullRequestReviewView] = []
    for item in _parse_paginated_gh_json(completed.stdout):
        if not isinstance(item, dict):
            continue
        user = item.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        reviews.append(
            ModelPullRequestReviewView(
                author_login=str(login or ""),
                commit_id=str(item.get("commit_id") or ""),
                state=str(item.get("state") or ""),
                body=str(item.get("body") or ""),
            )
        )
    return reviews


def _substitute_lost_voters(
    result: ModelMultiReviewResult,
    roster: ModelReviewVoterRoster,
    *,
    repo: str | None,
    pr: int | None,
    head_sha: str | None,
) -> ModelMultiReviewResult:
    """Let clean off-CI receipts stand in for voters lost to the lab (OMN-20947).

    Does nothing unless a voter timed out or was unavailable. Every reason a
    receipt is not accepted is printed, so a run that stays red says why.
    """
    if not any(substitutable_failure(r) for r in result.results):
        return result
    policy = roster.substitute_votes
    if policy is None:
        return result
    if pr is None or not repo or not head_sha:
        print(
            "WARNING: a review voter timed out or was unavailable; substitute "
            "receipts need --pr, "
            "--repo and --head-sha, so none were read.",
            file=sys.stderr,
        )
        return result
    try:
        reviews = _fetch_pr_reviews(repo, pr)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        print(
            f"WARNING: could not read pull request reviews for substitute "
            f"receipts: {exc}",
            file=sys.stderr,
        )
        return result
    key = os.environ.get(policy.signing_key_env, "")
    decision = decide_substitute_votes(
        ModelSubstituteVoteRequest(
            result=result,
            policy=policy,
            reviews=tuple(reviews),
            repo=repo,
            pr=pr,
            head_sha=head_sha,
            key=key.encode() if key else None,
            now=datetime.now(tz=UTC),
        )
    )
    for reason in decision.refusals:
        print(f"Substitute receipt not accepted: {reason}", file=sys.stderr)
    for record in decision.records:
        print(
            f"Substitute vote: voter {record.voter_id!r} {record.failure}; clean receipts "
            f"from {', '.join(record.reviewer_ids)} (posted by "
            f"{', '.join(record.review_authors)}) at {record.head_sha} stand in.",
            file=sys.stderr,
        )
    return apply_substitutes(result, decision)


def _write_records(
    path: str | None,
    *,
    voted: ModelMultiReviewResult,
    final: ModelMultiReviewResult,
    review_type: Literal["pr", "plan"],
    repo: str | None,
    pr: int | None,
    head_sha: str | None,
) -> None:
    """Write the run's review records to ``path`` as JSON lines (OMN-20981).

    ``voted`` is the run before any substitute replaced a lost voter, so a lost
    voter is recorded as the failed run it was; ``final`` supplies the
    substitute votes that stood in for it.
    """
    if path is None:
        return
    batch = record_handle(
        ModelReviewRecordRequest(
            invocation_id=uuid4(),
            recorded_at=datetime.now(tz=UTC),
            review_type=review_type,
            repo=repo,
            pr=pr,
            head_sha=head_sha,
            results=tuple(voted.results),
            substitute_votes=tuple(final.substitute_votes),
        )
    )
    lines = "".join(r.model_dump_json() + "\n" for r in batch.records)
    Path(path).write_text(lines, encoding="utf-8")
    print(f"{len(batch.records)} review record(s) written to {path}", file=sys.stderr)


def _endpoint_label(model_key: str) -> str:
    """host:port of a registry key's resolved endpoint, for messages only."""
    config = MODEL_REGISTRY.get(model_key)
    if config is None:
        return model_key
    url = resolve_endpoint_url(model_key, config)
    if not url:
        return f"{model_key} (endpoint not configured; set {config.env_var})"
    parsed = urllib.parse.urlparse(url)
    return f"{model_key} at {parsed.hostname}:{parsed.port or 80}"


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


def _is_large_pr_diff_error(stderr: str) -> bool:
    return any(marker in stderr for marker in _LARGE_PR_DIFF_MARKERS)


def _parse_paginated_gh_json(stdout: str) -> list[object]:
    decoder = json.JSONDecoder()
    values: list[object] = []
    index = 0
    while index < len(stdout):
        while index < len(stdout) and stdout[index].isspace():
            index += 1
        if index >= len(stdout):
            break
        value, index = decoder.raw_decode(stdout, index)
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)
    return values


def _append_bounded_chunk(chunks: list[str], chunk: str, max_chars: int) -> bool:
    """Append chunk if it fits, or append a clipped tail marker.

    Returns True when the full chunk was appended.
    """
    current_size = sum(len(existing) + 1 for existing in chunks)
    remaining = max_chars - current_size
    if remaining <= 0:
        return False
    if len(chunk) <= remaining:
        chunks.append(chunk)
        return True

    marker = "\n[truncated to stay within hostile-reviewer input budget]"
    if remaining > len(marker):
        chunks.append(chunk[: remaining - len(marker)] + marker)
    return False


def _fetch_pr_files_fallback(pr_number: int, repo: str, reason: str) -> str:
    """Build a size-bounded review target from the pull request files API.

    Args:
        pr_number: Pull request number.
        repo: ``owner/name`` slug.
        reason: Why the unified diff was not usable directly. Rendered into the
            review target's preamble, so it must describe the ACTUAL trigger --
            either GitHub refusing the diff endpoint, or the diff exceeding the
            reviewer's own input budget (OMN-17293). Stating the wrong one
            misleads the reviewer model about what it is looking at.
    """
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"/repos/{repo}/pulls/{pr_number}/files?per_page=100",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    files = _parse_paginated_gh_json(result.stdout)
    file_dicts = [file_info for file_info in files if isinstance(file_info, dict)]
    total_additions = sum(
        int(file_info.get("additions") or 0) for file_info in file_dicts
    )
    total_deletions = sum(
        int(file_info.get("deletions") or 0) for file_info in file_dicts
    )
    chunks: list[str] = [
        f"PR #{pr_number} in {repo}: {reason}",
        "Fallback review target built from the pull request files API with an explicit input budget.",
        f"Budget: max_review_chars={_MAX_FALLBACK_REVIEW_CHARS}, max_patch_chars_per_file={_MAX_FALLBACK_PATCH_CHARS}.",
        f"Files changed: {len(file_dicts)}. Totals: +{total_additions}/-{total_deletions}.",
        "Only file metadata and patch excerpts present in this target are reviewable evidence.",
        "Do not invent line-level findings for omitted files or truncated hunks.",
        "",
        "Changed files:",
    ]

    for index, file_info in enumerate(file_dicts, start=1):
        filename = str(file_info.get("filename", "<unknown>"))
        status = str(file_info.get("status", "modified"))
        additions = file_info.get("additions", 0)
        deletions = file_info.get("deletions", 0)
        summary = f"{index}. {filename} ({status}, +{additions}/-{deletions})"
        if not _append_bounded_chunk(chunks, summary, _MAX_FALLBACK_REVIEW_CHARS):
            return "\n".join(chunks)

    chunks.append("")
    chunks.append("Patch excerpts:")
    omitted_patch_files = 0
    for file_info in file_dicts:
        filename = str(file_info.get("filename", "<unknown>"))
        status = str(file_info.get("status", "modified"))
        additions = file_info.get("additions", 0)
        deletions = file_info.get("deletions", 0)
        patch = file_info.get("patch")
        if isinstance(patch, str) and patch.strip():
            patch_text = patch.strip()
            truncated = len(patch_text) > _MAX_FALLBACK_PATCH_CHARS
            excerpt = patch_text[:_MAX_FALLBACK_PATCH_CHARS]
            if truncated:
                excerpt += "\n[patch excerpt truncated for this file]"
            block = (
                f"\n--- {filename} ({status}, +{additions}/-{deletions}) ---\n{excerpt}"
            )
        else:
            block = (
                f"\n--- {filename} ({status}, +{additions}/-{deletions}) ---\n"
                "[patch unavailable from pull request files API]"
            )

        if not _append_bounded_chunk(chunks, block, _MAX_FALLBACK_REVIEW_CHARS):
            omitted_patch_files += 1
            break

    if omitted_patch_files:
        _append_bounded_chunk(
            chunks,
            "[additional patch excerpts omitted due to input budget]",
            _MAX_FALLBACK_REVIEW_CHARS,
        )
    return "\n".join(chunks)


# OMN-17427: the review bot's judgement of rejected findings.
_MAX_JUDGEMENTS_PER_RUN = 10
_JUDGE_ANSWER_TOKENS = 400


async def judge_rejections(
    batch: ModelRejectionJudgeBatch,
    voters_overlay: Path,
    judge_overlay: Path,
    *,
    ask: Callable[[str, str, str, str], Awaitable[str]] | None = None,
) -> ModelRejectionJudgeBatchResult:
    """Judge every pending rejection with an independent judge (OMN-17427).

    The judges come from ``judge_overlay``, a review_voters_overlay document
    loaded, validated and registered exactly as the voters are, and every call
    goes through the reviewer's own ``call_model``. A judge is never a voter of
    ``voters_overlay`` (``node_review_rejection_judge_compute``). Anything that
    stops a judgement is returned as data, never raised: ``unavailable`` for
    the whole batch, ``notes`` per rejection, so the caller fails closed.

    ``ask(system_prompt, user_prompt, judge_id, repo)`` replaces the model call
    in tests.
    """
    if not batch.items:
        return ModelRejectionJudgeBatchResult()
    voters = load_review_voters(voters_overlay)
    if not voters.ok:
        return ModelRejectionJudgeBatchResult(
            unavailable=(
                f"the review voters overlay is refused ({voters.error_message}), so "
                "no judge can be shown to differ from the voters"
            )
        )
    judges = load_review_voters(judge_overlay)
    if not judges.ok:
        return ModelRejectionJudgeBatchResult(
            unavailable=(
                f"no rejection judge is configured ({judges.error_message}); declare "
                f"one in the CI overlay as {judge_overlay.name} beside the voters "
                "overlay, a review_voters_overlay document"
            )
        )
    try:
        register_review_voters(judges.endpoint_configs())
    except ValueError as exc:
        return ModelRejectionJudgeBatchResult(
            unavailable=f"the rejection judge cannot be registered: {exc}"
        )

    async def _call_model(system: str, user: str, judge_id: str, repo: str) -> str:
        return await call_model(
            system, user, judge_id, repository=repo, max_tokens=_JUDGE_ANSWER_TOKENS
        )

    call = ask or _call_model
    judge_identities = judges.identities()
    voter_identities = tuple(sorted(set(voters.identities().values())))
    print(
        "rejection judges: "
        + ", ".join(f"{j} ({judge_identities.get(j)})" for j in judges.voter_ids)
        + "; review voters: "
        + ", ".join(voter_identities),
        file=sys.stderr,
    )
    records: list[ModelRejectionJudgementRecord] = []
    notes: dict[str, str] = {}
    for index, item in enumerate(batch.items):
        if index >= _MAX_JUDGEMENTS_PER_RUN:
            notes[item.key] = (
                f"more than {_MAX_JUDGEMENTS_PER_RUN} rejections await the review "
                "bot in one run; the rest are judged on the next reply"
            )
            continue
        plan = plan_rejection_judgement(
            ModelRejectionJudgeRequest(
                repo=batch.repo,
                pr=batch.pr,
                head_sha=batch.head_sha,
                rejection=item,
                judge_ids=tuple(judges.voter_ids),
                judge_identities=judge_identities,
                voter_ids=tuple(voters.voter_ids),
                voter_identities=voter_identities,
                nonce=secrets.token_hex(8),
            )
        )
        if plan.refusal:
            notes[item.key] = plan.refusal
            continue
        try:
            judgement = read_judgement(
                await call(
                    plan.system_prompt, plan.user_prompt, plan.judge_id, batch.repo
                )
            )
            if judgement is None:
                judgement = read_judgement(
                    await call(
                        plan.system_prompt,
                        plan.user_prompt + _JUDGE_JSON_ONLY_RETRY,
                        plan.judge_id,
                        batch.repo,
                    )
                )
        except Exception as exc:
            # Boundary: call_model raises transport, configuration and provider
            # errors of many types. Degrade to a named note for this rejection
            # (the gate keeps the finding blocked) and keep judging the rest.
            logging.getLogger(__name__).exception(
                "rejection judge %s failed on rejection %s", plan.judge_id, item.key
            )
            first = (str(exc).splitlines() or [type(exc).__name__])[0][:300]
            notes[item.key] = (
                f"the judge {plan.judge_id} ({plan.identity}) did not answer: {first}"
            )
            continue
        if judgement is None:
            notes[item.key] = (
                f"the judge {plan.judge_id} ({plan.identity}) answered twice without "
                "a verdict"
            )
            continue
        records.append(
            ModelRejectionJudgementRecord(
                key=item.key,
                verdict=judgement.verdict,
                sentence=judgement.sentence,
                judge_id=plan.judge_id,
                identity=plan.identity,
            )
        )
        print(
            f"rejection {item.key} ({item.raised_by}): {judgement.verdict} by "
            f"{plan.judge_id} ({plan.identity}): {judgement.sentence}",
            file=sys.stderr,
        )
    return ModelRejectionJudgeBatchResult(judgements=tuple(records), notes=notes)


def _judge_rejections_main(argv: list[str]) -> int:
    """``judge-rejections``: the review bot's verdicts on rejected findings (OMN-17427)."""
    parser = argparse.ArgumentParser(
        prog="cli_review judge-rejections",
        description=(
            "Judge rejected Hostile Reviewer findings with a model that is none of "
            "the voters; write the verdicts as JSON. Exit 1 when any rejection "
            "could not be judged (fail closed)."
        ),
    )
    parser.add_argument("--pending", type=Path, required=True)
    parser.add_argument("--voters-overlay", type=Path, required=True)
    parser.add_argument("--judge-overlay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        batch = ModelRejectionJudgeBatch.model_validate_json(
            args.pending.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        result = ModelRejectionJudgeBatchResult(
            unavailable=f"the pending rejections file is unreadable: {exc}"
        )
    else:
        result = asyncio.run(
            judge_rejections(batch, args.voters_overlay, args.judge_overlay)
        )
    args.output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if result.unavailable:
        print(
            f"ERROR: the review bot cannot judge: {result.unavailable}", file=sys.stderr
        )
    for key, why in result.notes.items():
        print(f"ERROR: rejection {key} is not judged: {why}", file=sys.stderr)
    return 1 if result.unavailable or result.notes else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code (0=success, 1=all models failed).
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    if raw_argv and raw_argv[0] == "validate-rules":
        return _validate_rules_main(raw_argv[1:])
    if raw_argv and raw_argv[0] == "judge-rejections":
        return _judge_rejections_main(raw_argv[1:])

    parser = build_parser()
    args = parser.parse_args(raw_argv)

    # Resolve the quorum policy BEFORE any model runs: a refused threshold
    # must fail in milliseconds, not after a full multi-model review.
    contract_policy = load_registry().review_quorum
    policy = contract_policy
    if args.quorum_threshold is not None:
        if args.quorum_threshold < contract_policy.min_agreeing_models:
            print(
                f"Error: --quorum-threshold {args.quorum_threshold} is below the "
                f"contract minimum {contract_policy.min_agreeing_models} declared in "
                "model_registry.yaml (review_quorum.min_agreeing_models). The "
                "threshold may be raised, never lowered.",
                file=sys.stderr,
            )
            return 1
        policy = contract_policy.model_copy(
            update={"min_agreeing_models": args.quorum_threshold}
        )

    # Standing rules (OMN-20784), also BEFORE any model or diff fetch: a gated
    # review with no usable rules fails here, and a pull request that weakens
    # the base branch's mandatory rules is blocked here without a model call.
    standing_rules: ModelReviewStandingRules | None = None
    rules_record: ModelStandingRulesRecord | None = None
    refusal = _rules_refusal(args)
    if refusal is not None:
        print(f"Error: {refusal}", file=sys.stderr)
        return 1
    if args.rules_file is not None:
        load = _load_standing_rules(
            rules_file=args.rules_file,
            base_ref=args.rules_base_ref,
            head_ref=args.rules_head_ref,
            repo_dir=args.rules_repo_dir,
        )
        if load.result is None or load.result.rules is None:
            reasons = (
                [load.error]
                if load.error
                else list(load.result.errors)
                if load.result is not None
                else []
            )
            print(
                f"Error: standing rules unusable ({load.source}): "
                f"{'; '.join(str(r) for r in reasons)}",
                file=sys.stderr,
            )
            return 1
        standing_rules = load.result.rules
        rules_record = _rules_record(load.result, source=load.source, gated=args.gated)
        if not load.result.ok and rules_record is not None:
            blocked = _blocked_by_weakened_rules(rules_record, args.rules_file, policy)
            json_output = blocked.model_dump_json(indent=2)
            if args.output:
                Path(args.output).write_text(json_output + "\n", encoding="utf-8")
                print(f"Results written to {args.output}", file=sys.stderr)
            else:
                print(json_output)
            _write_records(
                args.record_out,
                voted=blocked,
                final=blocked,
                review_type="pr" if args.pr is not None else "plan",
                repo=args.repo,
                pr=args.pr,
                head_sha=args.head_sha,
            )
            if blocked.quorum is not None:
                for line in format_quorum_summary(blocked.quorum):
                    print(line, file=sys.stderr)
            return 0

    # OMN-20910: the voters overlay is loaded before anything else runs, so a
    # malformed overlay or an unknown backend fails in milliseconds, naming the
    # voter, instead of after the diff is fetched.
    roster: ModelReviewVoterRoster | None = None
    if args.voters_overlay is not None:
        if args.model:
            print(
                "Error: --voters-overlay and --model are mutually exclusive; "
                "the overlay is the roster.",
                file=sys.stderr,
            )
            return 1
        roster = load_review_voters(Path(args.voters_overlay))
        if not roster.ok:
            print(
                f"ERROR: review voters overlay: {roster.error_message}",
                file=sys.stderr,
            )
            return 1
        try:
            register_review_voters(roster.endpoint_configs())
        except ValueError as exc:
            print(f"ERROR: review voters overlay: {exc}", file=sys.stderr)
            return 1
        print(f"Review voters from {roster.overlay_source}:", file=sys.stderr)
        for voter in roster.voters:
            print(f"  {voter.describe()}", file=sys.stderr)

    # Resolve input content.
    if args.pr is not None:
        if not args.repo:
            print("Error: --repo is required with --pr", file=sys.stderr)
            return 1
        try:
            gh_result = subprocess.run(
                ["gh", "pr", "diff", str(args.pr), "--repo", args.repo],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            review_content = gh_result.stdout
            # OMN-17293: GitHub served the diff, but "GitHub will serve it" and
            # "the reviewer model will accept it" are different limits, and only
            # the former was ever checked. An oversized diff is rejected by the
            # endpoint at request-validation time with HTTP 400
            # (ONEX_CORE_007_INVALID_INPUT) in ~1-3s, every model fails
            # identically, and the verdict resolves to `degraded` -- which reads
            # as transient GPU contention but is fully deterministic, so the
            # re-run the gate advertises can never clear it. Observed on
            # omnimarket#2240: a 793,705-char diff (99.6% of it one generated
            # uv.lock) against a live `max_model_len` of 122,880 tokens.
            # Bound it here through the same budgeted builder the
            # GitHub-refused path already uses.
            if len(review_content) > _MAX_FALLBACK_REVIEW_CHARS:
                oversize_reason = (
                    f"unified diff is {len(review_content)} chars, over the "
                    f"{_MAX_FALLBACK_REVIEW_CHARS}-char hostile-reviewer input budget."
                )
                try:
                    review_content = _fetch_pr_files_fallback(
                        args.pr, args.repo, oversize_reason
                    )
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ) as exc:
                    print(
                        f"Error: {oversize_reason} Files API fallback failed: {exc}",
                        file=sys.stderr,
                    )
                    return 1
                print(
                    f"WARNING: {oversize_reason} Using bounded pull request "
                    "files API review target.",
                    file=sys.stderr,
                )
        except FileNotFoundError:
            print("Error: gh CLI not found", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()
            if not _is_large_pr_diff_error(stderr):
                print(f"Error: gh pr diff failed: {stderr}", file=sys.stderr)
                return 1
            try:
                review_content = _fetch_pr_files_fallback(
                    args.pr,
                    args.repo,
                    "exceeded GitHub's unified diff size limit.",
                )
            except subprocess.CalledProcessError as fallback_exc:
                print(
                    "Error: gh pr diff exceeded GitHub's size limit and "
                    f"files API fallback failed: {fallback_exc.stderr.strip()}",
                    file=sys.stderr,
                )
                return 1
            except subprocess.TimeoutExpired:
                print(
                    "Error: gh pr diff exceeded GitHub's size limit and "
                    "files API fallback timed out",
                    file=sys.stderr,
                )
                return 1
            print(
                "WARNING: gh pr diff exceeded GitHub's size limit; "
                "using pull request files API fallback",
                file=sys.stderr,
            )
        except subprocess.TimeoutExpired:
            print("Error: gh pr diff timed out", file=sys.stderr)
            return 1
        if not review_content.strip():
            # OMN-18409: an empty diff (e.g. a merge/ancestry commit whose
            # tree is identical to the base branch) is a legitimate
            # "nothing to review" outcome, not an infra failure -- emit a
            # real, valid verdict document instead of erroring with empty
            # stdout. Previously this returned 1 with no stdout at all,
            # which crashed the hostile-reviewer CI caller's JSON parse
            # (json.decoder.JSONDecodeError on the empty string) instead of
            # ever producing a verdict.
            print(
                f"PR #{args.pr} has no diff — nothing to review.",
                file=sys.stderr,
            )
            result = ModelMultiReviewResult(
                models_attempted=[],
                models_succeeded=[],
                models_failed=[],
                results=[],
                total_findings=0,
                skipped_reason="empty_diff",
                standing_rules=rules_record,
            )
            json_output = result.model_dump_json(indent=2)
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(json_output + "\n", encoding="utf-8")
                print(f"Results written to {args.output}", file=sys.stderr)
            else:
                print(json_output)
            _write_records(
                args.record_out,
                voted=result,
                final=result,
                review_type="pr",
                repo=args.repo,
                pr=args.pr,
                head_sha=args.head_sha,
            )
            return 0
        print(f"Reviewing PR #{args.pr} in {args.repo}", file=sys.stderr)
    else:
        plan_path = Path(args.file)
        if not plan_path.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
        review_content = plan_path.read_text(encoding="utf-8")

    # Resolve model keys, applying reachability probe + API fallback unless suppressed.
    requested_keys: list[str] = args.model if args.model else [_DEFAULT_MODEL]

    skipped: list[str]
    if roster is not None:
        model_keys, skipped = _select_overlay_voters(roster)
    elif args.no_fallback:
        model_keys = requested_keys
        skipped = []
    else:
        model_keys, skipped = select_models_with_fallback(requested_keys)
        if skipped:
            print(
                f"WARNING: local model(s) unreachable, skipped: {', '.join(skipped)}",
                file=sys.stderr,
            )
        if set(model_keys) != set(requested_keys):
            activated = [k for k in model_keys if k not in requested_keys]
            if activated:
                print(
                    f"INFO: API fallback activated — using: {', '.join(activated)}",
                    file=sys.stderr,
                )

    # Determine review type.
    review_type: Literal["pr", "plan"] = "pr" if args.pr is not None else "plan"

    # Load persona if specified (--persona takes precedence over --system-prompt).
    persona: ModelPersonaConfig | None = None
    if args.persona is not None:
        try:
            persona = load_persona(args.persona)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Persona loaded: {args.persona}", file=sys.stderr)
    elif args.system_prompt is not None:
        sp_path = Path(args.system_prompt).expanduser().resolve()
        if not sp_path.exists():
            print(
                f"Error: --system-prompt file not found: {sp_path}",
                file=sys.stderr,
            )
            return 1
        sp_content = sp_path.read_text(encoding="utf-8")
        # Wrap the custom system prompt as a persona with a synthetic name.
        persona = ModelPersonaConfig(name="custom", content=sp_content)
        print(f"Custom system prompt loaded: {sp_path}", file=sys.stderr)

    # Run review.
    result = asyncio.run(
        run_review(
            review_content,
            model_keys,
            review_type=review_type,
            persona=persona,
            standing_rules=standing_rules,
            repository=args.repo,
        )
    )
    result = _record_unreachable(result, skipped)
    voted = result
    if roster is not None:
        result = _substitute_lost_voters(
            result, roster, repo=args.repo, pr=args.pr, head_sha=args.head_sha
        )

    # Resolve cross-model agreement (OMN-18479). The verdict travels in the
    # emitted document so no caller has to re-derive one by summing
    # severities across models -- the rule that let a single model's
    # rotating hallucination block a merge.
    quorum_summary = evaluate_quorum(result, policy)
    result = result.model_copy(
        update={"quorum": quorum_summary, "standing_rules": rules_record}
    )

    # Output JSON to stdout (or file).
    json_output = result.model_dump_json(indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output + "\n", encoding="utf-8")
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(json_output)
    _write_records(
        args.record_out,
        voted=voted,
        final=result,
        review_type=review_type,
        repo=args.repo,
        pr=args.pr,
        head_sha=args.head_sha,
    )

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
    # OMN-20422: a finding dropped because its own text says there is no
    # defect is named here, so the drop is never silent.
    print(
        f"Dropped (own text states no defect): {result.total_dropped}",
        file=sys.stderr,
    )
    for r in result.results:
        if not r.success:
            continue
        for dropped in r.dropped_findings:
            print(
                f"  [dropped] {r.model} {dropped.severity} {dropped.title}: "
                f"{dropped.reason}",
                file=sys.stderr,
            )
    for line in format_quorum_summary(quorum_summary):
        print(line, file=sys.stderr)

    if roster is not None:
        failed_required = [
            r
            for r in result.results
            if not r.success and r.model in roster.required_ids
        ]
        not_attempted = sorted(roster.required_ids - set(result.models_attempted))
        for r in failed_required:
            print(
                f"ERROR: required review voter {r.model!r} did not vote: {r.error}",
                file=sys.stderr,
            )
        for voter_id in not_attempted:
            print(
                f"ERROR: required review voter {voter_id!r} was not called.",
                file=sys.stderr,
            )
        if failed_required or not_attempted:
            print(
                "ERROR: NO VERDICT -- a required voter declared in "
                f"{roster.overlay_source} did not vote. Fix or replace that voter "
                "in the overlay; nothing is substituted for it.",
                file=sys.stderr,
            )
            return 2

    if quorum_summary.verdict is EnumQuorumVerdict.NO_MODELS:
        print(
            "ERROR: All models failed. Review could not be performed.",
            file=sys.stderr,
        )
        return 1

    if quorum_summary.verdict is EnumQuorumVerdict.DEGRADED_QUORUM:
        print(
            "ERROR: DEGRADED QUORUM — "
            f"{len(quorum_summary.models_succeeded)} model(s) succeeded as "
            f"{len(quorum_summary.distinct_reviewers_succeeded)} distinct "
            "reviewer(s) (endpoint + model), "
            f"{quorum_summary.quorum_threshold} required for agreement. "
            "No verdict was established; this is not a pass.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
