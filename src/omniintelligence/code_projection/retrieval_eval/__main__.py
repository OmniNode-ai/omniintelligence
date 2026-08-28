# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Run the retrieval eval and print or refresh the baseline scorecard.

    uv run python -m omniintelligence.code_projection.retrieval_eval
    uv run python -m omniintelligence.code_projection.retrieval_eval --write

``--write`` refreshes the committed baseline.  Do that only when a change to the
corpus, the golden set, or the embedding-compatibility key makes the old
baseline stale -- a re-baseline is a deliberate act, not a way to make a
regression go away.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from omniintelligence.code_projection.retrieval_eval.baselines import (
    BASELINE_SCORECARD_PATH,
)
from omniintelligence.code_projection.retrieval_eval.runner import run_eval


async def _main(*, write: bool) -> int:
    result = await run_eval()
    payload = result.scorecard.to_canonical_bytes()

    for scenario in result.scorecard.scenarios:
        verdict = "PASS" if scenario.passed else "FAIL"
        sys.stdout.write(f"{scenario.scenario_id} {verdict} {scenario.detail}\n")

    metrics = result.scorecard.metrics
    sys.stdout.write(
        f"metric_status={metrics.metric_status} "
        f"N={metrics.observed_distinct_chunk_keys} "
        f"Q={metrics.observed_labeled_queries}\n"
    )
    sys.stdout.write(
        f"latency: {result.latency.sample_count} samples, "
        f"embed {result.latency.embed_ms_total:.1f}ms of "
        f"{result.latency.total_ms_total:.1f}ms total "
        "(excluded from the scorecard digest)\n"
    )

    passed = all(s.passed for s in result.scorecard.scenarios)

    if not write:
        sys.stdout.write(payload.decode("utf-8"))
        return 0 if passed else 1

    # Refuse to re-baseline off a failing run. Writing here would replace the
    # reference with a scorecard recording failed scenarios, which silently
    # destroys the very thing future runs are compared against.
    if not passed:
        sys.stderr.write(
            "refusing to write the baseline: one or more scenarios failed\n"
        )
        return 1

    BASELINE_SCORECARD_PATH.write_bytes(payload)
    sys.stdout.write(f"wrote {BASELINE_SCORECARD_PATH}\n")
    return 0


def main() -> int:
    """Parse arguments and run the harness."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="refresh the committed baseline scorecard",
    )
    arguments = parser.parse_args()
    return asyncio.run(_main(write=arguments.write))


if __name__ == "__main__":
    raise SystemExit(main())
