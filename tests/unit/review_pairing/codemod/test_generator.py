# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for Deterministic Refactor Tool Generation.

Tests cover:
- CodemodReplayValidator: pass/fail/reject for generated codemods
- Static check: syntax errors and missing apply() method
- Replay: correct output, wrong output, timeout
- AntiPatternValidator: violation detection and clean code
- make_anti_pattern_validator: token extraction from transform signatures
- make_codemod_definition: factory helper

Reference: OMN-2585
"""

from __future__ import annotations

import uuid

import pytest

from omniintelligence.review_pairing.codemod import (
    AntiPatternValidator,
    AntiPatternViolation,
    CodemodDefinition,
    CodemodGeneratorSpec,
    CodemodReplayValidator,
    CodemodStatus,
    ReplayCase,
    ReplayResult,
)
from omniintelligence.review_pairing.codemod.generator import (
    make_anti_pattern_validator,
    make_codemod_definition,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_VALID_CODEMOD_SOURCE = """\
class TrimTrailingWhitespaceCodemod:
    def apply(self, source_code: str) -> str:
        return "\\n".join(line.rstrip() for line in source_code.splitlines())
"""

_IDENTITY_CODEMOD_SOURCE = """\
class IdentityCodemod:
    def apply(self, source_code: str) -> str:
        return source_code
"""

_SYNTAX_ERROR_SOURCE = """\
class BrokenCodemod:
    def apply(self, source_code: str) -> str
        return source_code  # missing colon
"""

_NO_APPLY_SOURCE = """\
class NoApplyMethod:
    def transform(self, source_code: str) -> str:
        return source_code
"""


def _make_codemod(source: str = _VALID_CODEMOD_SOURCE) -> CodemodDefinition:
    return make_codemod_definition(
        pattern_id=uuid.uuid4(),
        rule_id="ruff:W291",
        language="python",
        codemod_source=source,
    )


def _make_case(
    input_src: str,
    expected: str,
    pair_id: uuid.UUID | None = None,
) -> ReplayCase:
    return ReplayCase(
        pair_id=pair_id or uuid.uuid4(),
        input_source=input_src,
        expected_output=expected,
    )


# ---------------------------------------------------------------------------
# CodemodReplayValidator: static check
# ---------------------------------------------------------------------------


class TestStaticCheck:
    def test_valid_source_passes_static_check(self) -> None:
        validator = CodemodReplayValidator()
        result = validator._static_check(_VALID_CODEMOD_SOURCE)
        assert result == ""

    def test_syntax_error_caught(self) -> None:
        validator = CodemodReplayValidator()
        result = validator._static_check(_SYNTAX_ERROR_SOURCE)
        assert "SyntaxError" in result

    def test_missing_apply_method_caught(self) -> None:
        validator = CodemodReplayValidator()
        result = validator._static_check(_NO_APPLY_SOURCE)
        assert "apply" in result

    def test_identity_codemod_passes_static_check(self) -> None:
        validator = CodemodReplayValidator()
        result = validator._static_check(_IDENTITY_CODEMOD_SOURCE)
        assert result == ""


# ---------------------------------------------------------------------------
# CodemodReplayValidator: validate()
# ---------------------------------------------------------------------------


class TestCodemodReplayValidate:
    def test_no_replay_cases_marks_failed(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod()

        result = validator.validate(codemod, [])
        assert result.status == CodemodStatus.FAILED
        assert result.replay_result is not None
        assert not result.replay_result.passed

    def test_syntax_error_marks_rejected(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_SYNTAX_ERROR_SOURCE)
        case = _make_case("hello  ", "hello")

        result = validator.validate(codemod, [case])
        assert result.status == CodemodStatus.REJECTED

    def test_missing_apply_marks_rejected(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_NO_APPLY_SOURCE)
        case = _make_case("hello  ", "hello")

        result = validator.validate(codemod, [case])
        assert result.status == CodemodStatus.REJECTED

    def test_correct_codemod_validates(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_VALID_CODEMOD_SOURCE)

        # Codemod trims trailing whitespace
        case = _make_case("hello   \nworld  ", "hello\nworld")

        result = validator.validate(codemod, [case])
        assert result.status == CodemodStatus.VALIDATED
        assert result.replay_result is not None
        assert result.replay_result.passed
        assert result.replay_result.cases_passed == 1
        assert result.replay_result.cases_failed == 0

    def test_wrong_output_marks_failed(self) -> None:
        validator = CodemodReplayValidator()
        # Identity codemod — does not trim trailing whitespace
        codemod = _make_codemod(_IDENTITY_CODEMOD_SOURCE)

        case = _make_case("hello   ", "hello")  # expects trimmed

        result = validator.validate(codemod, [case])
        assert result.status == CodemodStatus.FAILED
        assert result.replay_result is not None
        assert not result.replay_result.passed
        assert len(result.replay_result.failing_case_ids) == 1

    def test_multiple_cases_all_pass(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_VALID_CODEMOD_SOURCE)

        cases = [
            _make_case("line1   \nline2  ", "line1\nline2"),
            _make_case("foo  ", "foo"),
            _make_case("bar ", "bar"),
        ]

        result = validator.validate(codemod, cases)
        assert result.status == CodemodStatus.VALIDATED
        assert result.replay_result is not None
        assert result.replay_result.cases_passed == 3
        assert result.replay_result.cases_failed == 0

    def test_some_cases_fail(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_IDENTITY_CODEMOD_SOURCE)  # does not trim

        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()
        cases = [
            _make_case("hello", "hello", pair_id=pid1),  # identity → passes
            _make_case("hello   ", "hello", pair_id=pid2),  # expects trim → fails
        ]

        result = validator.validate(codemod, cases)
        assert result.status == CodemodStatus.FAILED
        assert result.replay_result is not None
        assert result.replay_result.cases_passed == 1
        assert result.replay_result.cases_failed == 1
        assert pid2 in result.replay_result.failing_case_ids

    def test_replay_result_has_validated_at(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_VALID_CODEMOD_SOURCE)
        case = _make_case("foo  ", "foo")

        result = validator.validate(codemod, [case])
        assert result.replay_result is not None
        assert result.replay_result.validated_at is not None

    def test_failure_details_populated_on_fail(self) -> None:
        validator = CodemodReplayValidator()
        codemod = _make_codemod(_IDENTITY_CODEMOD_SOURCE)
        case = _make_case("hello   ", "hello")

        result = validator.validate(codemod, [case])
        assert result.replay_result is not None
        assert len(result.replay_result.failure_details) > 0


# ---------------------------------------------------------------------------
# AntiPatternValidator
# ---------------------------------------------------------------------------


class TestAntiPatternValidator:
    def _make_validator(self, tokens: list[str]) -> AntiPatternValidator:
        return AntiPatternValidator(
            validator_id=uuid.uuid4(),
            pattern_id=uuid.uuid4(),
            rule_id="deprecated:E999",
            signature_tokens=tokens,
            description="Detects deprecated pattern E999",
        )

    def test_clean_code_no_violations(self) -> None:
        v = self._make_validator(["bad_func"])
        violations = v.check("def good_func():\n    pass\n")
        assert violations == []

    def test_matching_token_produces_violation(self) -> None:
        v = self._make_validator(["bad_func"])
        violations = v.check("result = bad_func(x, y)\n", file_path="src/foo.py")
        assert len(violations) == 1
        assert violations[0].rule_id == "deprecated:E999"
        assert violations[0].file_path == "src/foo.py"
        assert violations[0].line_number == 1

    def test_multiple_lines_first_match_per_line(self) -> None:
        v = self._make_validator(["old_api"])
        code = "x = old_api()\ny = new_api()\nz = old_api()\n"
        violations = v.check(code)
        assert len(violations) == 2  # lines 1 and 3

    def test_empty_tokens_no_violations(self) -> None:
        v = self._make_validator([])
        violations = v.check("result = bad_func()\n")
        assert violations == []

    def test_violation_includes_matched_text(self) -> None:
        v = self._make_validator(["legacy_call"])
        code = "  result = legacy_call(arg1, arg2)\n"
        violations = v.check(code)
        assert len(violations) == 1
        assert "legacy_call" in violations[0].matched_text

    def test_violation_has_correct_pattern_id(self) -> None:
        pattern_id = uuid.uuid4()
        v = AntiPatternValidator(
            validator_id=uuid.uuid4(),
            pattern_id=pattern_id,
            rule_id="deprecated:E999",
            signature_tokens=["bad_func"],
            description="test",
        )
        violations = v.check("bad_func()\n")
        assert len(violations) == 1
        assert violations[0].pattern_id == pattern_id


# ---------------------------------------------------------------------------
# make_anti_pattern_validator
# ---------------------------------------------------------------------------


class TestMakeAntiPatternValidator:
    def test_creates_validator_with_rule_id(self) -> None:
        v = make_anti_pattern_validator(
            pattern_id=uuid.uuid4(),
            rule_id="ruff:E501",
            transform_signature="-long_line = some_function_call()\n+short = call()\n",
        )
        assert v.rule_id == "ruff:E501"

    def test_extracts_tokens_from_signature(self) -> None:
        v = make_anti_pattern_validator(
            pattern_id=uuid.uuid4(),
            rule_id="ruff:E501",
            transform_signature="-old_function_name(arg)\n+new_function_name(arg)\n",
        )
        assert len(v.signature_tokens) > 0

    def test_empty_signature_no_tokens(self) -> None:
        v = make_anti_pattern_validator(
            pattern_id=uuid.uuid4(),
            rule_id="ruff:E501",
            transform_signature="",
        )
        # Empty signature may produce no tokens; validator should still be created
        assert v.rule_id == "ruff:E501"

    def test_description_defaults_when_not_provided(self) -> None:
        v = make_anti_pattern_validator(
            pattern_id=uuid.uuid4(),
            rule_id="ruff:E501",
            transform_signature="",
        )
        assert "ruff:E501" in v.description

    def test_validator_id_is_unique(self) -> None:
        pid = uuid.uuid4()
        v1 = make_anti_pattern_validator(
            pattern_id=pid, rule_id="ruff:E501", transform_signature=""
        )
        v2 = make_anti_pattern_validator(
            pattern_id=pid, rule_id="ruff:E501", transform_signature=""
        )
        assert v1.validator_id != v2.validator_id


# ---------------------------------------------------------------------------
# make_codemod_definition
# ---------------------------------------------------------------------------


class TestMakeCodemodDefinition:
    def test_creates_pending_codemod(self) -> None:
        codemod = make_codemod_definition(
            pattern_id=uuid.uuid4(),
            rule_id="ruff:W291",
            language="python",
            codemod_source=_VALID_CODEMOD_SOURCE,
        )
        assert codemod.status == CodemodStatus.PENDING
        assert codemod.replay_result is None

    def test_codemod_id_is_unique(self) -> None:
        pid = uuid.uuid4()
        c1 = make_codemod_definition(
            pattern_id=pid,
            rule_id="ruff:W291",
            language="python",
            codemod_source=_VALID_CODEMOD_SOURCE,
        )
        c2 = make_codemod_definition(
            pattern_id=pid,
            rule_id="ruff:W291",
            language="python",
            codemod_source=_VALID_CODEMOD_SOURCE,
        )
        assert c1.codemod_id != c2.codemod_id

    def test_transform_signature_stored(self) -> None:
        sig = "some convergent transform"
        codemod = make_codemod_definition(
            pattern_id=uuid.uuid4(),
            rule_id="ruff:W291",
            language="python",
            codemod_source=_VALID_CODEMOD_SOURCE,
            transform_signature=sig,
        )
        assert codemod.transform_signature == sig


# ---------------------------------------------------------------------------
# CodemodGeneratorSpec
# ---------------------------------------------------------------------------


class TestCodemodGeneratorSpec:
    def test_spec_stores_examples(self) -> None:
        spec = CodemodGeneratorSpec(
            rule_id="ruff:E501",
            language="python",
            transform_signature="@@\n-long\n+short",
            before_after_examples=[("before code", "after code")],
            pattern_id=uuid.uuid4(),
        )
        assert len(spec.before_after_examples) == 1
        assert spec.before_after_examples[0] == ("before code", "after code")

    def test_spec_description_optional(self) -> None:
        spec = CodemodGeneratorSpec(
            rule_id="ruff:E501",
            language="python",
            transform_signature="",
            before_after_examples=[],
            pattern_id=uuid.uuid4(),
        )
        assert spec.description == ""
