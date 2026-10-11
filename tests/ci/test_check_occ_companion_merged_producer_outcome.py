# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Head-bound producer outcomes for the OCC companion gate.

Writer pin-only exemptions (OMN-20161) and terminal producer failures
(OMN-18069 / OMN-18647) must not trust another head or prose mentions.
"""

from __future__ import annotations

import pytest

from scripts.ci.check_occ_companion_merged import (
    AUTOBIND_OUTCOME_CHECK_NAME,
    AUTOBIND_OUTCOME_MARKER_PREFIX,
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_PENDING,
    GhFetcher,
    Verdict,
    evaluate_once,
)

pytestmark = pytest.mark.unit

PRODUCT_REPO = "OmniNode-ai/omniintelligence"
HEAD = "a" * 40
OTHER_HEAD = "b" * 40
WRITER_LOGINS = (
    "onexbot-occ-writer[bot]",
    "app/onexbot-occ-writer",
    "onexbot-occ-writer",
)
PIN_REASON = "skip:DEPENDENCY_PIN_ONLY"


def _outcome_run(
    outcome: str, reason: str, *, completed_at: str = "2026-09-30T16:00:00Z"
) -> dict[str, object]:
    return {
        "name": AUTOBIND_OUTCOME_CHECK_NAME,
        "status": "completed",
        "head_sha": HEAD,
        "completed_at": completed_at,
        "output": {
            "summary": (
                f"{AUTOBIND_OUTCOME_MARKER_PREFIX} {outcome} "
                f"repo={PRODUCT_REPO} pr=1053 correlation_id=c reason={reason}\n"
                "Producer details follow."
            )
        },
    }


class FakeFetcher(GhFetcher):
    """Serve outcomes by SHA, and reject reads outside the gate's paths."""

    def __init__(
        self,
        author: str,
        runs_by_sha: dict[str, list[dict[str, object]] | None],
        *,
        body: str = "",
        head_sha: str = HEAD,
    ) -> None:
        self.author = author
        self.runs_by_sha = runs_by_sha
        self.body = body
        self.head_sha = head_sha
        self.check_run_reads: list[tuple[str, str]] = []

    def pr_view(self, repo: str, number: str, fields: str) -> dict[str, object]:
        assert (repo, number, fields) == (
            PRODUCT_REPO,
            "1053",
            "body,author,headRefOid",
        )
        return {
            "body": self.body,
            "author": {"login": self.author},
            "headRefOid": self.head_sha,
        }

    def check_runs(self, repo: str, head_sha: str) -> list[dict[str, object]] | None:
        self.check_run_reads.append((repo, head_sha))
        return self.runs_by_sha.get(head_sha, [])

    def _run(self, argv: list[str]) -> str | None:
        raise AssertionError(f"unexpected live GitHub read: {argv}")


def _evaluate(fetcher: FakeFetcher) -> Verdict:
    return evaluate_once(
        fetcher,
        event_name="pull_request",
        repo=PRODUCT_REPO,
        pr_number="1053",
    )


@pytest.mark.parametrize("login", WRITER_LOGINS)
def test_writer_with_pin_only_outcome_on_head_passes(login: str) -> None:
    fetcher = FakeFetcher(login, {HEAD: [_outcome_run("DECLINED", PIN_REASON)]})
    verdict = _evaluate(fetcher)
    assert verdict.code == EXIT_PASS
    assert PIN_REASON in verdict.reason
    assert login in verdict.reason
    assert fetcher.check_run_reads == [(PRODUCT_REPO, HEAD)]


def test_writer_pin_only_exemption_precedes_stamp_validation() -> None:
    fetcher = FakeFetcher(
        WRITER_LOGINS[0],
        {HEAD: [_outcome_run("DECLINED", PIN_REASON)]},
        body="Evidence-Source: not-a-valid-ref",
    )
    assert _evaluate(fetcher).code == EXIT_PASS


def test_writer_pin_only_outcome_on_another_sha_is_not_exempt() -> None:
    run = _outcome_run("DECLINED", PIN_REASON)
    run["head_sha"] = OTHER_HEAD
    fetcher = FakeFetcher(WRITER_LOGINS[0], {OTHER_HEAD: [run]})
    assert _evaluate(fetcher).code == EXIT_PENDING
    assert fetcher.check_run_reads
    assert all(read == (PRODUCT_REPO, HEAD) for read in fetcher.check_run_reads)


@pytest.mark.parametrize(
    "runs",
    [
        [],
        None,
        [_outcome_run("MINTED", PIN_REASON)],
        [_outcome_run("DECLINED", "skip:LEASE_HELD")],
        [_outcome_run("DECLINED", "classifier refused " + PIN_REASON)],
    ],
    ids=["absent", "unreadable", "minted", "lease-held", "prose-mention"],
)
def test_writer_without_pin_only_verdict_stays_pending(
    runs: list[dict[str, object]] | None,
) -> None:
    assert _evaluate(FakeFetcher(WRITER_LOGINS[0], {HEAD: runs})).code == EXIT_PENDING


def test_writer_without_head_sha_is_not_exempt() -> None:
    fetcher = FakeFetcher(
        WRITER_LOGINS[0], {HEAD: [_outcome_run("DECLINED", PIN_REASON)]}, head_sha=""
    )
    assert _evaluate(fetcher).code == EXIT_PENDING
    assert fetcher.check_run_reads == []


@pytest.mark.parametrize("login", ["human-author", "onexbot-occ-writer-evil[bot]"])
def test_human_and_near_miss_author_are_not_pin_only_exempt(login: str) -> None:
    fetcher = FakeFetcher(login, {HEAD: [_outcome_run("DECLINED", PIN_REASON)]})
    verdict = _evaluate(fetcher)
    assert verdict.code == EXIT_PENDING
    assert "body has no 'Evidence-Source:' line yet" in verdict.reason


def test_error_without_stamp_fails_with_producer_reason() -> None:
    reason = "fault:COMPANION_PUBLISH_FAILED"
    fetcher = FakeFetcher("human-author", {HEAD: [_outcome_run("ERROR", reason)]})
    verdict = _evaluate(fetcher)
    assert verdict.code == EXIT_FAIL
    assert "ERROR" in verdict.reason
    assert reason in verdict.reason
    assert "OMN-18069" in verdict.reason


def test_check_run_read_failure_without_stamp_stays_pending() -> None:
    assert _evaluate(FakeFetcher("human-author", {HEAD: None})).code == EXIT_PENDING


@pytest.mark.parametrize(
    "reason",
    [
        "skip:NO_RED_DERIVABLE_CHECK no candidate is RED-derivable",
        "skip:DEFER_HAND_AUTHORED contention path",
    ],
)
def test_permanent_decline_without_stamp_requires_hand_authored_evidence(
    reason: str,
) -> None:
    fetcher = FakeFetcher("human-author", {HEAD: [_outcome_run("DECLINED", reason)]})
    verdict = _evaluate(fetcher)
    assert verdict.code == EXIT_FAIL
    assert reason in verdict.reason
    assert "bus path will not mint for this head" in verdict.reason
    assert "Hand-authored OCC evidence is required" in verdict.reason
    assert "OMN-15247" in verdict.reason


@pytest.mark.parametrize(
    "reason",
    [
        "skip:LEASE_HELD",
        "skip:DRAFT",
        "skip:CLOSED",
        "classifier mentioned skip:NO_RED_DERIVABLE_CHECK",
        "classifier mentioned skip:DEFER_HAND_AUTHORED",
    ],
)
def test_other_declines_without_stamp_stay_pending(reason: str) -> None:
    fetcher = FakeFetcher("human-author", {HEAD: [_outcome_run("DECLINED", reason)]})
    assert _evaluate(fetcher).code == EXIT_PENDING


@pytest.mark.parametrize("outcome", ["ERROR", "DECLINED"])
def test_terminal_outcome_on_another_sha_stays_pending(outcome: str) -> None:
    run = _outcome_run(outcome, "skip:NO_RED_DERIVABLE_CHECK")
    run["head_sha"] = OTHER_HEAD
    fetcher = FakeFetcher("human-author", {OTHER_HEAD: [run]})
    assert _evaluate(fetcher).code == EXIT_PENDING


@pytest.mark.parametrize("outcome", ["ERROR", "DECLINED"])
def test_stamped_human_pr_does_not_read_producer_outcomes(outcome: str) -> None:
    fetcher = FakeFetcher(
        "human-author",
        {HEAD: [_outcome_run(outcome, "skip:NO_RED_DERIVABLE_CHECK")]},
        body="Evidence-Source: not-a-valid-ref",
    )
    verdict = _evaluate(fetcher)
    assert verdict.code == EXIT_FAIL
    assert "fix the PR body" in verdict.reason
    assert fetcher.check_run_reads == []


def test_newest_completed_outcome_controls_writer_exemption() -> None:
    older = _outcome_run("DECLINED", PIN_REASON)
    newer = _outcome_run("MINTED", "", completed_at="2026-09-30T17:00:00Z")
    fetcher = FakeFetcher(WRITER_LOGINS[0], {HEAD: [newer, older]})
    assert _evaluate(fetcher).code == EXIT_PENDING


@pytest.mark.parametrize("shape", ["wrong-name", "in-progress", "no-marker"])
def test_unrecognized_check_run_does_not_exempt_writer(shape: str) -> None:
    run = _outcome_run("DECLINED", PIN_REASON)
    if shape == "wrong-name":
        run["name"] = "another check"
    elif shape == "in-progress":
        run["status"] = "in_progress"
    else:
        run["output"] = {"summary": f"DECLINED reason={PIN_REASON}"}
    assert _evaluate(FakeFetcher(WRITER_LOGINS[0], {HEAD: [run]})).code == EXIT_PENDING
