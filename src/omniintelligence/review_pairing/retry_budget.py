# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Retry-budget invariant for the sequential multi-model adversarial review.

``cli_review.run_review`` calls each requested model **sequentially** (a plain
``for`` loop, not concurrent). Each call goes through
``omnibase_infra.mixins.mixin_llm_http_transport.MixinLlmHttpTransport
._execute_llm_http_call``, which retries up to ``max_retries`` times (default
3, i.e. 4 total attempts) with exponential backoff, each attempt bounded by
the model's registered ``timeout_seconds``. A caller that sizes a CI job's
``timeout-minutes`` against the *nominal* per-call timeout, without accounting
for retries and the sequential sum across models, will silently stall past
its own ceiling with no error -- the job just runs until GitHub Actions
cancels it.

This module computes that worst-case budget from the **live** registry and
the **live** installed transport's retry defaults (via reflection, not a
hand-copied constant) so it stays correct as either drifts, and exposes an
assertion a CI step (or a test) can call to fail fast and loudly instead of
stalling silently.

Reference: OMN-15066 -- the hostile-reviewer CI gate (omnimarket) stalled
35m21s and was cancelled at its 35-minute job ceiling because
qwen3-review-b's worst-case retry budget (4 attempts x 600s + 14s backoff =
2414s) alone exceeded it, with zero visible log output because
``cli_review.py`` never configured Python logging (see the companion
omnibase_infra PR for the logging fix).
"""

from __future__ import annotations

import argparse
import inspect
import sys
from dataclasses import dataclass

from omniintelligence.review_pairing.model_registry_loader import load_registry


@dataclass(frozen=True)
class ModelRetryBudgetResult:
    """Worst-case retry budget for a single model key.

    Attributes:
        model_key: Registry key (e.g. "qwen3-review-b").
        per_attempt_timeout_seconds: The model's registered per-attempt timeout.
        total_attempts: 1 + max_retries.
        backoff_seconds: Total exponential-backoff sleep across all retries.
        worst_case_seconds: total_attempts * per_attempt_timeout_seconds
            + backoff_seconds -- the full wall-clock ceiling for this model
            alone if every attempt times out.
    """

    model_key: str
    per_attempt_timeout_seconds: float
    total_attempts: int
    backoff_seconds: float
    worst_case_seconds: float


def resolve_live_max_retries_default() -> int:
    """Introspect the installed omnibase_infra transport's ``max_retries``
    default via reflection.

    This deliberately does NOT hardcode ``3`` -- if a future change to
    ``MixinLlmHttpTransport._execute_llm_http_call``'s signature changes the
    default, this picks it up automatically instead of silently computing a
    stale budget.

    Raises:
        TypeError: If the live default is not an int (defensive -- the
            signature is expected to declare ``max_retries: int = 3``).
    """
    from omnibase_infra.mixins.mixin_llm_http_transport import (
        MixinLlmHttpTransport,
    )

    sig = inspect.signature(MixinLlmHttpTransport._execute_llm_http_call)
    default = sig.parameters["max_retries"].default
    if not isinstance(default, int):
        raise TypeError(
            "MixinLlmHttpTransport._execute_llm_http_call.max_retries default "
            f"is not an int (got {default!r}); the retry-budget invariant "
            "cannot be computed without a known integer default."
        )
    return default


def _simulate_worst_case_seconds(
    per_attempt_timeout_seconds: float, max_retries: int
) -> tuple[int, float]:
    """Mirror the real retry loop's timing for a permanently-timing-out
    endpoint: every attempt consumes its full per-attempt timeout, and
    ``ModelRetryState``'s default exponential backoff (delay=1.0,
    multiplier=2.0) is added between attempts -- never after the terminal
    attempt, which raises instead of retrying.

    Returns:
        (total_attempts, worst_case_seconds).
    """
    from omnibase_infra.handlers.models.model_retry_state import ModelRetryState

    total_attempts = 1 + max_retries
    state = ModelRetryState(max_attempts=total_attempts)
    elapsed = 0.0
    while state.is_retriable():
        elapsed += per_attempt_timeout_seconds
        next_state = state.next_attempt()
        if next_state.is_retriable():
            elapsed += next_state.delay_seconds
        state = next_state
    return total_attempts, elapsed


def compute_sequential_worst_case(
    model_keys: list[str],
    *,
    max_retries: int | None = None,
) -> list[ModelRetryBudgetResult]:
    """Compute the worst-case retry budget for each model key, in the exact
    order ``cli_review.run_review`` calls them (sequential -- see module
    docstring).

    Args:
        model_keys: Model keys as passed to ``cli_review`` (e.g. via
            repeated ``--model`` flags).
        max_retries: Global override for the retry count, applied to every
            model that does NOT declare its own ``max_retries`` in
            ``model_registry.yaml`` (test/CLI convenience). Per-model
            precedence (OMN-15115): ``config.max_retries`` (registry
            override) > this ``max_retries`` argument >
            ``resolve_live_max_retries_default()`` -- this must mirror
            ``call_model()``'s real resolution order exactly, or the
            invariant simulates a budget the real call path doesn't use.

    Returns:
        One ``ModelRetryBudgetResult`` per model key that resolves to a
        registry entry going through the HTTP retry transport (the
        ``cli_fallback`` codex entry is excluded -- it is a subprocess call,
        not an HTTP retry loop, and has its own timeout mechanism).
    """
    registry = load_registry()
    fallback_max_retries = (
        max_retries if max_retries is not None else resolve_live_max_retries_default()
    )

    results: list[ModelRetryBudgetResult] = []
    for model_key in model_keys:
        config = registry.models.get(model_key)
        if config is None or config.kind == "cli_fallback":
            continue
        resolved_max_retries = (
            config.max_retries
            if config.max_retries is not None
            else fallback_max_retries
        )
        total_attempts, worst_case = _simulate_worst_case_seconds(
            config.timeout_seconds, resolved_max_retries
        )
        backoff_seconds = worst_case - (total_attempts * config.timeout_seconds)
        results.append(
            ModelRetryBudgetResult(
                model_key=model_key,
                per_attempt_timeout_seconds=config.timeout_seconds,
                total_attempts=total_attempts,
                backoff_seconds=backoff_seconds,
                worst_case_seconds=worst_case,
            )
        )
    return results


def format_budget_breakdown(results: list[ModelRetryBudgetResult]) -> str:
    """Human-readable per-model breakdown, used in assertion failures and CI
    step output."""
    lines = [
        f"  {r.model_key}: {r.total_attempts} attempts x "
        f"{r.per_attempt_timeout_seconds:g}s + {r.backoff_seconds:g}s backoff "
        f"= {r.worst_case_seconds:g}s"
        for r in results
    ]
    return "\n".join(lines)


def assert_budget_within_ceiling(
    model_keys: list[str],
    *,
    job_timeout_seconds: float,
    setup_overhead_seconds: float = 0.0,
    max_retries: int | None = None,
) -> list[ModelRetryBudgetResult]:
    """Raise ``AssertionError`` if the sequential sum of worst-case per-model
    retry budgets (plus ``setup_overhead_seconds``) meets or exceeds
    ``job_timeout_seconds``.

    This is the invariant OMN-15066 asks to be asserted, not just satisfied:
    ``sum(attempts * per_attempt_timeout + backoff for each model) +
    setup_overhead < job_timeout``. Call this from a CI step (cheap, no GPU
    calls -- it only reads the registry file and reflects on the installed
    package) before the real review runs, so a future registry/retry/job-
    timeout edit that reintroduces the mismatch fails fast and loudly instead
    of stalling silently to cancellation.

    Returns:
        The per-model breakdown on success, so a caller can log/print it.
    """
    results = compute_sequential_worst_case(model_keys, max_retries=max_retries)
    total_worst_case = (
        sum(r.worst_case_seconds for r in results) + setup_overhead_seconds
    )
    if total_worst_case >= job_timeout_seconds:
        raise AssertionError(
            "Retry-budget invariant violated (OMN-15066): sequential "
            f"worst-case {total_worst_case:g}s (setup_overhead="
            f"{setup_overhead_seconds:g}s) >= job_timeout "
            f"{job_timeout_seconds:g}s for models {model_keys}.\n"
            f"{format_budget_breakdown(results)}\n"
            "Either raise the CI job's timeout-minutes or reduce a model's "
            "timeout_seconds in model_registry.yaml -- do not silence this "
            "check."
        )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Assert the sequential multi-model retry-budget invariant "
            "(OMN-15066): attempts * per_attempt_timeout + backoff, summed "
            "across models in call order, plus setup overhead, must stay "
            "below the CI job's timeout-minutes ceiling. Reads the live "
            "model_registry.yaml and reflects on the installed "
            "omnibase_infra transport -- no live network/GPU calls."
        )
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        required=True,
        help="Model key to include (repeatable, in call order).",
    )
    parser.add_argument(
        "--job-timeout-seconds",
        type=float,
        required=True,
        help="The CI job's configured timeout, in seconds.",
    )
    parser.add_argument(
        "--setup-overhead-seconds",
        type=float,
        default=0.0,
        help="Non-review setup time to add to the budget (checkout, clones, "
        "dependency install, preflight probe). Default: 0.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: exit 0 and print the breakdown if the invariant
    holds, exit 1 and print the violation if it does not.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        results = assert_budget_within_ceiling(
            args.models,
            job_timeout_seconds=args.job_timeout_seconds,
            setup_overhead_seconds=args.setup_overhead_seconds,
        )
    except AssertionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    total = sum(r.worst_case_seconds for r in results) + args.setup_overhead_seconds
    print(
        "Retry-budget invariant holds: sequential worst-case "
        f"{total:g}s (setup_overhead={args.setup_overhead_seconds:g}s) < "
        f"job_timeout {args.job_timeout_seconds:g}s for models {args.models}.",
        file=sys.stderr,
    )
    print(format_budget_breakdown(results), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ModelRetryBudgetResult",
    "assert_budget_within_ceiling",
    "compute_sequential_worst_case",
    "format_budget_breakdown",
    "resolve_live_max_retries_default",
]
