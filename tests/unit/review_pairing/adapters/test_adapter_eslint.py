# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the ESLint JSON output adapter.

Covers: happy path, missing fields, malformed input, severity mapping.

Reference: OMN-2542
"""

from __future__ import annotations

import json

import pytest

from omniintelligence.review_pairing.adapters.adapter_eslint import (
    get_confidence_tier,
    parse_raw,
)
from omniintelligence.review_pairing.models import FindingSeverity

_REPO = "OmniNode-ai/omnidash"
_PR_ID = 7
_SHA = "ghi9012jkl"


def _file_result(file_path: str = "src/app.ts", messages: list | None = None) -> dict:
    return {
        "filePath": file_path,
        "messages": messages or [_message()],
        "errorCount": 1,
        "warningCount": 0,
    }


def _message(**overrides) -> dict:
    base = {
        "ruleId": "no-unused-vars",
        "severity": 2,
        "message": "'foo' is defined but never used.",
        "line": 10,
        "column": 5,
        "endLine": 10,
        "endColumn": 8,
        "fix": None,
    }
    base.update(overrides)
    return base


class TestEslintAdapterHappyPath:
    @pytest.mark.unit
    def test_parse_single_error_from_string(self) -> None:
        raw = json.dumps([_file_result()])
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "eslint:no-unused-vars"
        assert f.severity == FindingSeverity.ERROR
        assert f.file_path == "src/app.ts"
        assert f.line_start == 10

    @pytest.mark.unit
    def test_parse_single_error_from_list(self) -> None:
        findings = parse_raw(
            [_file_result()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert len(findings) == 1

    @pytest.mark.unit
    def test_severity_2_is_error(self) -> None:
        findings = parse_raw(
            [_file_result(messages=[_message(severity=2)])],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert findings[0].severity == FindingSeverity.ERROR

    @pytest.mark.unit
    def test_severity_1_is_warning(self) -> None:
        findings = parse_raw(
            [_file_result(messages=[_message(severity=1)])],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert findings[0].severity == FindingSeverity.WARNING

    @pytest.mark.unit
    def test_severity_0_is_skipped(self) -> None:
        findings = parse_raw(
            [_file_result(messages=[_message(severity=0)])],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
        )
        assert findings == []

    @pytest.mark.unit
    def test_single_line_finding_has_none_line_end(self) -> None:
        msg = _message(line=10, endLine=10)
        findings = parse_raw(
            [_file_result(messages=[msg])], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert findings[0].line_end is None

    @pytest.mark.unit
    def test_multiline_finding_has_line_end(self) -> None:
        msg = _message(line=10, endLine=15)
        findings = parse_raw(
            [_file_result(messages=[msg])], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert findings[0].line_end == 15

    @pytest.mark.unit
    def test_multiple_files(self) -> None:
        raw_list = [
            _file_result("src/a.ts"),
            _file_result("src/b.ts"),
        ]
        findings = parse_raw(raw_list, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 2
        paths = {f.file_path for f in findings}
        assert paths == {"src/a.ts", "src/b.ts"}

    @pytest.mark.unit
    def test_multiple_messages_per_file(self) -> None:
        msgs = [
            _message(ruleId="no-unused-vars", line=1),
            _message(ruleId="eqeqeq", line=2),
        ]
        findings = parse_raw(
            [_file_result(messages=msgs)], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert len(findings) == 2

    @pytest.mark.unit
    def test_tool_name_is_eslint(self) -> None:
        findings = parse_raw(
            [_file_result()], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert findings[0].tool_name == "eslint"

    @pytest.mark.unit
    def test_eslint_version_stored(self) -> None:
        findings = parse_raw(
            [_file_result()],
            repo=_REPO,
            pr_id=_PR_ID,
            commit_sha=_SHA,
            eslint_version="9.0.0",
        )
        assert findings[0].tool_version == "9.0.0"

    @pytest.mark.unit
    def test_repo_root_relativizes_path(self) -> None:
        result = _file_result("/workspace/src/app.ts")
        findings = parse_raw(
            [result], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA, repo_root="/workspace"
        )
        assert findings[0].file_path == "src/app.ts"

    @pytest.mark.unit
    def test_empty_list_returns_empty(self) -> None:
        assert parse_raw([], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_confidence_tier(self) -> None:
        assert get_confidence_tier() == "deterministic"


class TestEslintAdapterMissingFields:
    @pytest.mark.unit
    def test_missing_file_path_skipped(self) -> None:
        result = {"messages": [_message()], "errorCount": 1, "warningCount": 0}
        findings = parse_raw([result], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_empty_file_path_skipped(self) -> None:
        result = {"filePath": "", "messages": [_message()], "errorCount": 1}
        findings = parse_raw([result], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_missing_rule_id_uses_unknown(self) -> None:
        msg = _message()
        del msg["ruleId"]
        findings = parse_raw(
            [_file_result(messages=[msg])], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert len(findings) == 1
        assert "eslint:unknown" in findings[0].rule_id

    @pytest.mark.unit
    def test_missing_line_defaults_to_1(self) -> None:
        msg = _message()
        del msg["line"]
        findings = parse_raw(
            [_file_result(messages=[msg])], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA
        )
        assert findings[0].line_start == 1


class TestEslintAdapterMalformedInput:
    @pytest.mark.unit
    def test_invalid_json_string(self) -> None:
        assert parse_raw("not-json", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_json_object_not_array(self) -> None:
        raw = json.dumps({"filePath": "foo.ts"})
        assert parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_non_dict_file_result_skipped(self) -> None:
        raw_list = ["not-a-dict", _file_result()]
        findings = parse_raw(raw_list, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1

    @pytest.mark.unit
    def test_null_messages_skipped(self) -> None:
        result = {"filePath": "src/a.ts", "messages": None, "errorCount": 0}
        findings = parse_raw([result], repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []
