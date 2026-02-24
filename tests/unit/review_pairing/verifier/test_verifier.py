# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Finding Disappearance Verifier (OMN-2560).

Covers: confirmed, still_present, config_only, disappears_without_mod
outcomes, confidence delta values, resolved event construction, and
edge cases.

Reference: OMN-2560
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from omniintelligence.review_pairing.models import (
    FindingFixPair,
    FindingSeverity,
    PairingType,
    ReviewFindingObserved,
)
from omniintelligence.review_pairing.verifier.verifier import (
    FindingDisappearanceVerifier,
    PostFixCIFindings,
    PostFixFinding,
    VerificationOutcome,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_REPO = "OmniNode-ai/omniintelligence"
_FILE = "src/omniintelligence/nodes/foo.py"
_RULE = "ruff:E501"
_SHA_FINDING = "abc1234def5"
_SHA_FIX = "fedcba98765"
_SHA_POST = "111222333aa"


def _make_finding(
    rule_id: str = _RULE,
    file_path: str = _FILE,
    line_start: int = 10,
) -> ReviewFindingObserved:
    return ReviewFindingObserved(
        finding_id=uuid4(),
        repo=_REPO,
        pr_id=42,
        rule_id=rule_id,
        severity=FindingSeverity.WARNING,
        file_path=file_path,
        line_start=line_start,
        tool_name="ruff",
        tool_version="0.3.0",
        normalized_message="line too long",
        raw_message="E501 line too long",
        commit_sha_observed=_SHA_FINDING,
        observed_at=_NOW,
    )


def _make_pair(finding: ReviewFindingObserved) -> FindingFixPair:
    return FindingFixPair(
        pair_id=uuid4(),
        finding_id=finding.finding_id,
        fix_commit_sha=_SHA_FIX,
        diff_hunks=["@@ -8,5 +8,5 @@ E501\n-long\n+short"],
        confidence_score=0.80,
        disappearance_confirmed=False,
        pairing_type=PairingType.TEMPORAL,
        created_at=_NOW,
    )


def _make_post_fix(
    *,
    findings: list[PostFixFinding] | None = None,
    files_modified_by_fix: set[str] | None = None,
    files_in_pr: set[str] | None = None,
    ci_run_id: str = "run-12345",
) -> PostFixCIFindings:
    return PostFixCIFindings(
        commit_sha=_SHA_POST,
        findings=findings or [],
        ci_run_id=ci_run_id,
        files_modified_by_fix=files_modified_by_fix
        if files_modified_by_fix is not None
        else {_FILE},
        files_in_pr=files_in_pr if files_in_pr is not None else {_FILE},
        verification_source="ci_rerun",
    )


# ---------------------------------------------------------------------------
# Confirmed: finding absent
# ---------------------------------------------------------------------------


class TestVerifierConfirmed:
    @pytest.mark.unit
    def test_confirmed_when_finding_absent_from_post_fix_ci(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(findings=[])  # no findings

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)

        assert result.outcome == VerificationOutcome.CONFIRMED
        assert result.disappearance_confirmed is True
        assert result.confidence_delta == 0.0
        assert result.resolved_event is not None

    @pytest.mark.unit
    def test_resolved_event_has_correct_fields(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(ci_run_id="run-99999")

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)

        assert result.resolved_event is not None
        assert result.resolved_event.finding_id == finding.finding_id
        assert result.resolved_event.fix_commit_sha == pair.fix_commit_sha
        assert result.resolved_event.verified_at_commit_sha == _SHA_POST
        assert result.resolved_event.ci_run_id == "run-99999"

    @pytest.mark.unit
    def test_confirmed_different_file_finding_absent(self) -> None:
        """Finding in file A; post-fix only has finding in file B → confirmed."""
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(file_path="src/a.py")
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[
                PostFixFinding(
                    rule_id=_RULE, file_path="src/b.py", line_start=5, tool_name="ruff"
                )
            ],
            files_modified_by_fix={"src/a.py"},
            files_in_pr={"src/a.py", "src/b.py"},
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.outcome == VerificationOutcome.CONFIRMED

    @pytest.mark.unit
    def test_pair_id_in_result_matches_input(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix()

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.pair_id == pair.pair_id

    @pytest.mark.unit
    def test_finding_id_in_result_matches_input(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix()

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.finding_id == finding.finding_id


# ---------------------------------------------------------------------------
# Still present
# ---------------------------------------------------------------------------


class TestVerifierStillPresent:
    @pytest.mark.unit
    def test_still_present_when_same_rule_and_file_in_post_fix(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(rule_id="ruff:E501", file_path=_FILE)
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[
                PostFixFinding(
                    rule_id="ruff:E501",
                    file_path=_FILE,
                    line_start=15,
                    tool_name="ruff",
                )
            ]
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)

        assert result.outcome == VerificationOutcome.STILL_PRESENT
        assert result.disappearance_confirmed is False
        assert result.confidence_delta == pytest.approx(-0.20)
        assert result.resolved_event is None

    @pytest.mark.unit
    def test_still_present_matches_by_bare_rule_code(self) -> None:
        """Post-fix uses bare rule code (E501) vs qualified rule_id (ruff:E501)."""
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(rule_id="ruff:E501")
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[
                PostFixFinding(
                    rule_id="E501", file_path=_FILE, line_start=10, tool_name="ruff"
                )
            ]
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.outcome == VerificationOutcome.STILL_PRESENT

    @pytest.mark.unit
    def test_different_rule_id_same_file_is_not_still_present(self) -> None:
        """Different rule in the same file should not count as still present."""
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(rule_id="ruff:E501", file_path=_FILE)
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[
                PostFixFinding(
                    rule_id="ruff:E302",
                    file_path=_FILE,
                    line_start=10,
                    tool_name="ruff",
                )
            ]
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        # Different rule → not still present → likely confirmed or other
        assert result.outcome != VerificationOutcome.STILL_PRESENT


# ---------------------------------------------------------------------------
# Config-only fix
# ---------------------------------------------------------------------------


class TestVerifierConfigOnly:
    @pytest.mark.unit
    def test_config_only_when_pyproject_toml_modified(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],  # finding absent
            files_in_pr={_FILE, "pyproject.toml"},
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)

        assert result.outcome == VerificationOutcome.CONFIG_ONLY
        assert result.disappearance_confirmed is False
        assert result.confidence_delta == pytest.approx(-0.10)

    @pytest.mark.unit
    def test_config_only_when_eslintrc_modified(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(rule_id="eslint:no-unused-vars")
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],
            files_in_pr={"src/foo.ts", ".eslintrc.json"},
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.outcome == VerificationOutcome.CONFIG_ONLY

    @pytest.mark.unit
    def test_no_config_change_no_config_only(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],
            files_in_pr={_FILE, "src/bar.py"},  # no config files
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        # No config files → not config_only
        assert result.outcome != VerificationOutcome.CONFIG_ONLY


# ---------------------------------------------------------------------------
# Disappears without modification
# ---------------------------------------------------------------------------


class TestVerifierDisappearsWithoutMod:
    @pytest.mark.unit
    def test_disappears_without_mod_when_fix_didnt_touch_finding_file(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(file_path="src/original.py")
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],  # absent
            files_modified_by_fix={"src/other.py"},  # didn't touch original.py
            files_in_pr={"src/original.py", "src/other.py"},
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)

        assert result.outcome == VerificationOutcome.DISAPPEARS_WITHOUT_MOD
        assert result.disappearance_confirmed is False
        assert result.confidence_delta == pytest.approx(-0.15)

    @pytest.mark.unit
    def test_fix_touched_finding_file_no_disappears_without_mod(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(file_path=_FILE)
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],
            files_modified_by_fix={_FILE},  # fix touched the finding's file
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.outcome != VerificationOutcome.DISAPPEARS_WITHOUT_MOD

    @pytest.mark.unit
    def test_empty_files_modified_no_disappears_without_mod(self) -> None:
        """If files_modified_by_fix is empty, can't infer disappears_without_mod."""
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],
            files_modified_by_fix=set(),  # empty → can't determine
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        # empty files_modified_by_fix → condition len > 0 is False → not disappears_without_mod
        assert result.outcome != VerificationOutcome.DISAPPEARS_WITHOUT_MOD


# ---------------------------------------------------------------------------
# Priority order: still_present > config_only > disappears_without_mod > confirmed
# ---------------------------------------------------------------------------


class TestVerifierPriorityOrder:
    @pytest.mark.unit
    def test_still_present_takes_priority_over_config_change(self) -> None:
        """If finding is still present AND there's a config change, still_present wins."""
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[
                PostFixFinding(
                    rule_id=_RULE, file_path=_FILE, line_start=10, tool_name="ruff"
                )
            ],
            files_in_pr={_FILE, "pyproject.toml"},
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        assert result.outcome == VerificationOutcome.STILL_PRESENT

    @pytest.mark.unit
    def test_config_only_takes_priority_over_disappears_without_mod(self) -> None:
        """Config change is checked before disappears_without_mod."""
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding(file_path="src/target.py")
        pair = _make_pair(finding)
        post_fix = _make_post_fix(
            findings=[],  # absent
            files_modified_by_fix={"src/other.py"},  # didn't touch target.py
            files_in_pr={
                "src/target.py",
                "src/other.py",
                "pyproject.toml",
            },  # config change
        )

        result = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        # Config change detected first → config_only wins over disappears_without_mod
        assert result.outcome == VerificationOutcome.CONFIG_ONLY


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestVerifierIdempotency:
    @pytest.mark.unit
    def test_same_inputs_produce_same_outcome(self) -> None:
        verifier = FindingDisappearanceVerifier()
        finding = _make_finding()
        pair = _make_pair(finding)
        post_fix = _make_post_fix(findings=[])

        result1 = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)
        result2 = verifier.verify(finding=finding, pair=pair, post_fix_ci=post_fix)

        assert result1.outcome == result2.outcome
        assert result1.disappearance_confirmed == result2.disappearance_confirmed
        assert result1.confidence_delta == result2.confidence_delta
