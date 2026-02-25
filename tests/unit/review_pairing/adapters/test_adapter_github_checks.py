# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the GitHub Checks API annotations adapter.

Covers: happy path, annotation level mapping, missing fields, malformed input.

Reference: OMN-2542
"""

from __future__ import annotations

import json

import pytest

from omniintelligence.review_pairing.adapters.adapter_github_checks import (
    get_confidence_tier,
    parse_raw,
)
from omniintelligence.review_pairing.models import FindingSeverity

_REPO = "OmniNode-ai/omniintelligence"
_PR_ID = 194
_SHA = "abc1234def5"


def _annotation(**overrides) -> dict:
    base = {
        "path": "src/foo/bar.py",
        "blob_href": "https://github.com/OmniNode-ai/omniintelligence/blob/abc1234/src/foo/bar.py",
        "start_line": 10,
        "end_line": 10,
        "start_column": None,
        "end_column": None,
        "annotation_level": "failure",
        "title": "Line too long",
        "message": "E501 Line too long (95 > 88 characters)",
        "raw_details": None,
    }
    base.update(overrides)
    return base


class TestGithubChecksAdapterHappyPath:
    @pytest.mark.unit
    def test_parse_failure_annotation_from_list(self) -> None:
        findings = parse_raw([_annotation()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == FindingSeverity.ERROR
        assert f.file_path == "src/foo/bar.py"
        assert f.line_start == 10
        assert f.repo == _REPO
        assert f.pr_id == _PR_ID

    @pytest.mark.unit
    def test_parse_from_json_string(self) -> None:
        raw = json.dumps([_annotation()])
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1

    @pytest.mark.unit
    def test_failure_level_is_error(self) -> None:
        findings = parse_raw(
            [_annotation(annotation_level="failure")],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert findings[0].severity == FindingSeverity.ERROR

    @pytest.mark.unit
    def test_warning_level_is_warning(self) -> None:
        findings = parse_raw(
            [_annotation(annotation_level="warning")],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert findings[0].severity == FindingSeverity.WARNING

    @pytest.mark.unit
    def test_notice_level_is_info(self) -> None:
        findings = parse_raw(
            [_annotation(annotation_level="notice")],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert findings[0].severity == FindingSeverity.INFO

    @pytest.mark.unit
    def test_single_line_finding_has_none_line_end(self) -> None:
        a = _annotation(start_line=10, end_line=10)
        findings = parse_raw([a], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].line_end is None

    @pytest.mark.unit
    def test_multiline_finding_has_line_end(self) -> None:
        a = _annotation(start_line=10, end_line=15)
        findings = parse_raw([a], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].line_end == 15

    @pytest.mark.unit
    def test_check_run_name_in_tool_name(self) -> None:
        findings = parse_raw(
            [_annotation()],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
            check_run_name="Lint",
        )
        assert "Lint" in findings[0].tool_name

    @pytest.mark.unit
    def test_default_tool_name_is_github_checks(self) -> None:
        findings = parse_raw([_annotation()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert "github-checks" in findings[0].tool_name

    @pytest.mark.unit
    def test_multiple_annotations(self) -> None:
        anns = [
            _annotation(path="src/a.py", start_line=1),
            _annotation(path="src/b.py", start_line=2, annotation_level="warning"),
        ]
        findings = parse_raw(anns, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 2

    @pytest.mark.unit
    def test_empty_list_returns_empty(self) -> None:
        assert parse_raw([], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_confidence_tier(self) -> None:
        assert get_confidence_tier() == "semi_deterministic"

    @pytest.mark.unit
    def test_unique_finding_ids(self) -> None:
        anns = [_annotation(path="a.py"), _annotation(path="b.py")]
        findings = parse_raw(anns, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        ids = {f.finding_id for f in findings}
        assert len(ids) == 2


class TestGithubChecksAdapterMissingFields:
    @pytest.mark.unit
    def test_missing_path_skipped(self) -> None:
        a = _annotation()
        del a["path"]
        findings = parse_raw([a], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_empty_path_skipped(self) -> None:
        a = _annotation(path="")
        findings = parse_raw([a], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_missing_start_line_defaults_to_1(self) -> None:
        a = _annotation()
        del a["start_line"]
        findings = parse_raw([a], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].line_start == 1

    @pytest.mark.unit
    def test_unknown_annotation_level_defaults_to_info(self) -> None:
        a = _annotation(annotation_level="unknown-level")
        findings = parse_raw([a], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].severity == FindingSeverity.INFO


class TestGithubChecksAdapterMalformedInput:
    @pytest.mark.unit
    def test_invalid_json_string(self) -> None:
        assert parse_raw("not-json", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_json_object_not_array(self) -> None:
        raw = json.dumps({"path": "src/foo.py"})
        assert parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_non_dict_item_skipped(self) -> None:
        raw_list = ["not-a-dict", _annotation()]
        findings = parse_raw(raw_list, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
