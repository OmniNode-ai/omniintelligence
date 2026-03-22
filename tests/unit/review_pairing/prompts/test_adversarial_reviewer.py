# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for the adversarial reviewer prompt module.

Reference: OMN-5789
"""

from __future__ import annotations

import pytest

from omniintelligence.review_pairing.prompts.adversarial_reviewer import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)


@pytest.mark.unit
class TestSystemPrompt:
    """Verify SYSTEM_PROMPT content and format constraints."""

    def test_contains_journal_style_critique(self) -> None:
        assert (
            "journal-style critique" in SYSTEM_PROMPT.lower()
            or "Journal-style critique" in SYSTEM_PROMPT
        )

    def test_contains_generally_disagrees(self) -> None:
        assert "Generally disagrees" in SYSTEM_PROMPT

    def test_contains_failures_of_critical_evaluation(self) -> None:
        assert "failures of critical evaluation" in SYSTEM_PROMPT

    def test_contains_rigorous_objectivity(self) -> None:
        assert "Rigorous Objectivity" in SYSTEM_PROMPT

    def test_contains_intellectual_honesty(self) -> None:
        assert "intellectual honesty" in SYSTEM_PROMPT

    def test_contains_kind_but_unsentimental(self) -> None:
        assert "Kind but unsentimental" in SYSTEM_PROMPT

    def test_no_em_dashes(self) -> None:
        """SYSTEM_PROMPT must not contain em dashes (U+2014)."""
        assert "\u2014" not in SYSTEM_PROMPT

    def test_no_em_dashes_in_user_template(self) -> None:
        """USER_PROMPT_TEMPLATE must not contain em dashes (U+2014)."""
        assert "\u2014" not in USER_PROMPT_TEMPLATE

    def test_requests_json_output(self) -> None:
        assert "JSON array" in SYSTEM_PROMPT

    def test_specifies_severity_levels(self) -> None:
        for level in ("critical", "major", "minor", "nit"):
            assert level in SYSTEM_PROMPT, f"Missing severity level: {level}"

    def test_specifies_required_fields(self) -> None:
        for field in (
            "category",
            "severity",
            "title",
            "description",
            "evidence",
            "proposed_fix",
            "location",
        ):
            assert field in SYSTEM_PROMPT, f"Missing required field: {field}"

    def test_is_nonempty_string(self) -> None:
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100


@pytest.mark.unit
class TestUserPromptTemplate:
    """Verify USER_PROMPT_TEMPLATE format."""

    def test_has_plan_content_placeholder(self) -> None:
        assert "{plan_content}" in USER_PROMPT_TEMPLATE

    def test_can_format_with_plan_content(self) -> None:
        result = USER_PROMPT_TEMPLATE.format(plan_content="# My Plan\n\nDo stuff.")
        assert "# My Plan" in result
        assert "{plan_content}" not in result

    def test_is_nonempty_string(self) -> None:
        assert isinstance(USER_PROMPT_TEMPLATE, str)
        assert len(USER_PROMPT_TEMPLATE) > 20


@pytest.mark.unit
class TestPromptVersion:
    """Verify PROMPT_VERSION format."""

    def test_is_semver_string(self) -> None:
        assert isinstance(PROMPT_VERSION, str)
        parts = PROMPT_VERSION.split(".")
        assert len(parts) == 3, f"Expected semver, got: {PROMPT_VERSION}"
        for part in parts:
            assert part.isdigit(), f"Non-numeric semver part: {part}"

    def test_current_version(self) -> None:
        assert PROMPT_VERSION == "1.1.0"
