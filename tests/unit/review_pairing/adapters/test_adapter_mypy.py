# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the mypy text output adapter.

Covers: happy path, missing fields, malformed input, severity filtering.

Reference: OMN-2542
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.adapters.adapter_mypy import (
    get_confidence_tier,
    parse_raw,
)
from omniintelligence.review_pairing.models import FindingSeverity

_REPO = "OmniNode-ai/omniintelligence"
_PR_ID = 10
_SHA = "def5678abc"


class TestMypyAdapterHappyPath:
    @pytest.mark.unit
    def test_parse_error_line(self) -> None:
        raw = (
            "src/foo/bar.py:10: error: Incompatible return value type  [return-value]\n"
        )
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "mypy:return-value"
        assert f.severity == FindingSeverity.ERROR
        assert f.file_path == "src/foo/bar.py"
        assert f.line_start == 10
        assert f.line_end is None

    @pytest.mark.unit
    def test_parse_warning_line(self) -> None:
        raw = "src/bar.py:5: warning: Statement is unreachable  [unreachable]\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.WARNING

    @pytest.mark.unit
    def test_note_lines_are_skipped(self) -> None:
        raw = "src/foo.py:10: note: Revealed type is 'builtins.int'\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_summary_line_is_skipped(self) -> None:
        raw = "Found 1 error in 1 file (checked 3 source files)\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings == []

    @pytest.mark.unit
    def test_multiple_diagnostics(self) -> None:
        raw = (
            "src/a.py:1: error: Module has no attribute 'foo'  [attr-defined]\n"
            "src/b.py:2: error: Missing return statement  [return]\n"
            "src/c.py:3: note: See https://mypy.readthedocs.io\n"
            "Found 2 errors in 2 files (checked 3 source files)\n"
        )
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 2

    @pytest.mark.unit
    def test_rule_id_with_error_code(self) -> None:
        raw = "src/foo.py:10: error: Argument has incompatible type  [arg-type]\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].rule_id == "mypy:arg-type"

    @pytest.mark.unit
    def test_rule_id_without_error_code(self) -> None:
        raw = "src/foo.py:10: error: Something went wrong\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].rule_id == "mypy:misc"

    @pytest.mark.unit
    def test_mypy_version_stored(self) -> None:
        raw = "src/foo.py:1: error: Test error  [misc]\n"
        findings = parse_raw(
            raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA, mypy_version="1.17.0"
        )
        assert findings[0].tool_version == "1.17.0"

    @pytest.mark.unit
    def test_tool_name_is_mypy(self) -> None:
        raw = "src/foo.py:1: error: Test error  [misc]\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert findings[0].tool_name == "mypy"

    @pytest.mark.unit
    def test_line_with_column(self) -> None:
        """mypy sometimes includes :COL, which should be ignored."""
        raw = "src/foo.py:10:5: error: Type is missing  [type-arg]\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert findings[0].line_start == 10

    @pytest.mark.unit
    def test_empty_input(self) -> None:
        assert parse_raw("", repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_confidence_tier(self) -> None:
        assert get_confidence_tier() == "deterministic"

    @pytest.mark.unit
    def test_unique_finding_ids(self) -> None:
        raw = "src/a.py:1: error: Error A  [misc]\nsrc/b.py:2: error: Error B  [misc]\n"
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        ids = {f.finding_id for f in findings}
        assert len(ids) == 2


class TestMypyAdapterMalformedInput:
    @pytest.mark.unit
    def test_non_string_input(self) -> None:
        assert parse_raw(42, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_blank_lines_skipped(self) -> None:
        raw = "\n\n\n"
        assert parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_garbage_lines_skipped(self) -> None:
        raw = "this is not a mypy line\nnor is this\n"
        assert parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA) == []

    @pytest.mark.unit
    def test_mixed_valid_and_garbage(self) -> None:
        raw = (
            "not a diagnostic\n"
            "src/good.py:5: error: Valid error  [misc]\n"
            "also not a diagnostic\n"
        )
        findings = parse_raw(raw, repo=_REPO, pr_id=_PR_ID, commit_sha=_SHA)
        assert len(findings) == 1
        assert findings[0].file_path == "src/good.py"
