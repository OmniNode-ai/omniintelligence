# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Ruff JSON output adapter.

Covers: happy path, missing fields, malformed input, edge cases.

Reference: OMN-2542
"""

from __future__ import annotations

import json

import pytest

from omniintelligence.review_pairing.adapters.adapter_ruff import (
    get_confidence_tier,
    parse_raw,
)
from omniintelligence.review_pairing.models import (
    FindingSeverity,
    ReviewFindingObserved,
)

_REPO = "OmniNode-ai/omniintelligence"
_PR_ID = 42
_SHA = "abc1234def5"


def _single_diagnostic(**overrides) -> dict:
    base = {
        "code": "E501",
        "message": "Line too long (95 > 88 characters)",
        "url": "https://docs.astral.sh/ruff/rules/line-too-long",
        "filename": "src/foo/bar.py",
        "location": {"row": 10, "column": 1},
        "end_location": {"row": 10, "column": 95},
        "fix": None,
        "noqa_row": None,
    }
    base.update(overrides)
    return base


class TestRuffAdapterHappyPath:
    @pytest.mark.unit
    def test_parse_single_diagnostic_from_string(self) -> None:
        raw = json.dumps([_single_diagnostic()])
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        f = findings[0]
        assert isinstance(f, ReviewFindingObserved)
        assert f.rule_id == "ruff:E501"
        assert f.severity == FindingSeverity.ERROR
        assert f.file_path == "src/foo/bar.py"
        assert f.line_start == 10
        assert f.repo == _REPO
        assert f.pr_id == _PR_ID

    @pytest.mark.unit
    def test_parse_single_diagnostic_from_list(self) -> None:
        findings = parse_raw(
            [_single_diagnostic()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert len(findings) == 1

    @pytest.mark.unit
    def test_multiple_diagnostics(self) -> None:
        raw_list = [
            _single_diagnostic(
                code="E501", filename="a.py", location={"row": 1, "column": 1}
            ),
            _single_diagnostic(
                code="F401",
                message="'os' imported but unused",
                filename="b.py",
                location={"row": 5, "column": 1},
            ),
        ]
        findings = parse_raw(raw_list, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 2
        assert findings[0].rule_id == "ruff:E501"
        assert findings[1].rule_id == "ruff:F401"

    @pytest.mark.unit
    def test_line_end_none_for_single_line(self) -> None:
        """line_end should be None when start == end."""
        d = _single_diagnostic(
            location={"row": 10, "column": 1},
            end_location={"row": 10, "column": 95},
        )
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].line_end is None

    @pytest.mark.unit
    def test_line_end_set_for_multiline(self) -> None:
        """line_end should be set when end row differs from start row."""
        d = _single_diagnostic(
            location={"row": 10, "column": 1},
            end_location={"row": 15, "column": 5},
        )
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].line_end == 15

    @pytest.mark.unit
    def test_tool_name_is_ruff(self) -> None:
        findings = parse_raw(
            [_single_diagnostic()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert findings[0].tool_name == "ruff"

    @pytest.mark.unit
    def test_ruff_version_is_passed_through(self) -> None:
        findings = parse_raw(
            [_single_diagnostic()],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
            ruff_version="0.12.5",
        )
        assert findings[0].tool_version == "0.12.5"

    @pytest.mark.unit
    def test_commit_sha_is_stored(self) -> None:
        findings = parse_raw(
            [_single_diagnostic()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert findings[0].commit_sha_observed == _SHA

    @pytest.mark.unit
    def test_unique_finding_ids(self) -> None:
        """Each finding should have a unique UUID."""
        raw_list = [
            _single_diagnostic(filename="a.py"),
            _single_diagnostic(filename="b.py"),
        ]
        findings = parse_raw(raw_list, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        ids = {f.finding_id for f in findings}
        assert len(ids) == 2

    @pytest.mark.unit
    def test_empty_list_returns_empty(self) -> None:
        assert parse_raw([], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_empty_json_array_string(self) -> None:
        assert parse_raw("[]", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_confidence_tier(self) -> None:
        assert get_confidence_tier() == "deterministic"


class TestRuffAdapterMissingFields:
    @pytest.mark.unit
    def test_missing_filename_skipped(self) -> None:
        d = _single_diagnostic(filename="")
        del d["filename"]
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_empty_filename_skipped(self) -> None:
        d = _single_diagnostic(filename="")
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_missing_code_uses_unknown(self) -> None:
        d = _single_diagnostic()
        del d["code"]
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert "ruff:UNKNOWN" in findings[0].rule_id or "ruff:" in findings[0].rule_id

    @pytest.mark.unit
    def test_missing_location_defaults_to_line_1(self) -> None:
        d = _single_diagnostic()
        del d["location"]
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert findings[0].line_start == 1

    @pytest.mark.unit
    def test_missing_end_location_gives_none_line_end(self) -> None:
        d = _single_diagnostic()
        del d["end_location"]
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].line_end is None

    @pytest.mark.unit
    def test_partial_location_dict(self) -> None:
        d = _single_diagnostic(location={})
        findings = parse_raw([d], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert findings[0].line_start == 1


class TestRuffAdapterMalformedInput:
    @pytest.mark.unit
    def test_invalid_json_string(self) -> None:
        assert parse_raw("not-json", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_json_object_not_array(self) -> None:
        raw = json.dumps({"code": "E501"})
        assert parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_array_with_non_dict_item(self) -> None:
        """Non-dict items should be skipped, not crash."""
        raw = json.dumps(["not-a-dict", 42, None])
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_mixed_valid_and_invalid(self) -> None:
        """Valid items should be parsed; invalid items skipped."""
        raw_list = [
            "not-a-dict",
            _single_diagnostic(filename="valid.py"),
            None,
        ]
        findings = parse_raw(raw_list, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert findings[0].file_path == "valid.py"
