# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for the Prompt Writer.

Reference: OMN-6175 (epic OMN-6164)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from omniintelligence.review_pairing.models_calibration import FewShotExample
from omniintelligence.review_pairing.prompt_writer import (
    PromptWriter,
    _build_fewshot_constant,
    _bump_minor_version,
    _sanitize_for_python_string,
)


def _make_example(
    example_type: str = "true_positive",
    category: str = "architecture",
) -> FewShotExample:
    return FewShotExample(
        example_type=example_type,  # type: ignore[arg-type]
        category=category,
        description="Missing error handling in retry logic",
        evidence="Both models found this issue",
        ground_truth_present=True,
        explanation="Both models identified the missing error handling.",
    )


@pytest.mark.unit
class TestSanitize:
    def test_escapes_quotes(self) -> None:
        result = _sanitize_for_python_string('say "hello"')
        assert '\\"' in result

    def test_escapes_backslashes(self) -> None:
        result = _sanitize_for_python_string("path\\to\\file")
        assert "\\\\" in result

    def test_strips_dangerous_patterns(self) -> None:
        result = _sanitize_for_python_string("import os\nexec(bad)")
        assert "import os" not in result
        assert "exec(" not in result

    def test_truncates_long_text(self) -> None:
        result = _sanitize_for_python_string("x" * 600)
        assert len(result) <= 500

    def test_strips_sentinel_markers(self) -> None:
        result = _sanitize_for_python_string(
            "# --- BEGIN FEW_SHOT_EXAMPLES --- something"
        )
        assert "BEGIN FEW_SHOT_EXAMPLES" not in result


@pytest.mark.unit
class TestBuildFewshotConstant:
    def test_builds_valid_constant(self) -> None:
        examples = [
            _make_example("true_positive"),
            _make_example("false_positive"),
        ]
        result = _build_fewshot_constant(examples)
        assert "FEW_SHOT_EXAMPLES: str" in result
        assert "True Positive" in result
        assert "False Positive" in result


@pytest.mark.unit
class TestBumpMinorVersion:
    def test_bumps_minor(self) -> None:
        assert _bump_minor_version("1.1.0") == "1.2.0"

    def test_bumps_from_zero(self) -> None:
        assert _bump_minor_version("1.0.0") == "1.1.0"

    def test_preserves_major_patch(self) -> None:
        assert _bump_minor_version("2.5.3") == "2.6.3"


@pytest.mark.unit
class TestPromptWriter:
    def test_file_not_found_raises(self) -> None:
        writer = PromptWriter()
        with pytest.raises(FileNotFoundError):
            writer.write_fewshot_examples([], prompt_path=Path("/nonexistent/file.py"))

    def test_dry_run_returns_content(self) -> None:
        writer = PromptWriter()
        examples = [_make_example()]
        result = writer.write_fewshot_examples(
            examples,
            prompt_path=Path("/nonexistent/file.py") if False else None,
            dry_run=True,
        )
        assert "FEW_SHOT_EXAMPLES" in result

    def test_write_to_temp_file(self, tmp_path: Path) -> None:
        prompt = tmp_path / "adversarial_reviewer.py"
        prompt.write_text(
            "# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.\n"
            "# SPDX-License-Identifier: MIT\n"
            "\n"
            'PROMPT_VERSION = "1.1.0"\n'
            "\n"
            'SYSTEM_PROMPT = """\n'
            "You are a code reviewer.\n"
            '"""\n'
        )
        writer = PromptWriter()
        examples = [_make_example("true_positive"), _make_example("false_positive")]
        new_version = writer.write_fewshot_examples(
            examples, prompt_path=prompt, run_id="test-run"
        )
        assert new_version == "1.2.0"
        content = prompt.read_text()
        assert "FEW_SHOT_EXAMPLES" in content
        assert "1.2.0" in content

    def test_idempotent_write(self, tmp_path: Path) -> None:
        prompt = tmp_path / "adversarial_reviewer.py"
        prompt.write_text(
            "# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.\n"
            "# SPDX-License-Identifier: MIT\n"
            "\n"
            'PROMPT_VERSION = "1.1.0"\n'
            "\n"
            'SYSTEM_PROMPT = """\n'
            "You are a code reviewer.\n"
            '"""\n'
        )
        writer = PromptWriter()
        examples = [_make_example()]
        v1 = writer.write_fewshot_examples(examples, prompt_path=prompt)
        v2 = writer.write_fewshot_examples(examples, prompt_path=prompt)
        assert v1 == v2
