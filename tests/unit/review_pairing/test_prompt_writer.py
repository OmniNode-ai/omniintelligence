# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for PromptWriter few-shot injection."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from omniintelligence.review_pairing.models_calibration import ModelFewShotExample
from omniintelligence.review_pairing.prompt_writer import PromptWriter

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_PROMPT = textwrap.dedent("""\
    from __future__ import annotations

    PROMPT_VERSION: str = "1.1.0"

    SYSTEM_PROMPT: str = "You are a reviewer."

    USER_PROMPT_TEMPLATE: str = "Review this: {plan_content}"
""")

PROMPT_WITH_SENTINELS = textwrap.dedent("""\
    from __future__ import annotations

    PROMPT_VERSION: str = "1.1.0"

    SYSTEM_PROMPT: str = "You are a reviewer."

    # --- BEGIN FEW_SHOT_EXAMPLES ---
    FEW_SHOT_EXAMPLES: list[dict[str, str]] = []
    # --- END FEW_SHOT_EXAMPLES ---

    USER_PROMPT_TEMPLATE: str = (
        "Review this: {plan_content}\\n"
        "\\n"
        "## Reference Examples\\n"
        "{few_shot_examples}"
    )
""")


def _make_example(
    example_type: str = "true_positive",
    category: str = "security",
    description: str = "SQL injection in query builder",
    evidence: str = "User input concatenated into raw SQL",
    ground_truth_present: bool = True,
    explanation: str = "Clear TP: unescaped input reaches DB layer",
) -> ModelFewShotExample:
    return ModelFewShotExample(
        example_type=example_type,  # type: ignore[arg-type]
        category=category,
        description=description,
        evidence=evidence,
        ground_truth_present=ground_truth_present,
        explanation=explanation,
    )


def _write_prompt(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "adversarial_reviewer.py"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPromptWriterSentinelInsertion:
    """Sentinel comments are inserted when not present."""

    def test_inserts_sentinels_when_missing(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        writer.write_fewshot_examples([_make_example()], prompt_path=path)

        content = path.read_text()
        assert "# --- BEGIN FEW_SHOT_EXAMPLES ---" in content
        assert "# --- END FEW_SHOT_EXAMPLES ---" in content

    def test_sentinels_placed_after_system_prompt(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        writer.write_fewshot_examples([_make_example()], prompt_path=path)

        content = path.read_text()
        sys_idx = content.index("SYSTEM_PROMPT")
        begin_idx = content.index("# --- BEGIN FEW_SHOT_EXAMPLES ---")
        assert begin_idx > sys_idx


class TestPromptWriterReplacement:
    """Content between sentinels is replaced correctly."""

    def test_replaces_existing_sentinel_content(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, PROMPT_WITH_SENTINELS)
        writer = PromptWriter()
        examples = [_make_example()]
        writer.write_fewshot_examples(examples, prompt_path=path)

        content = path.read_text()
        assert "SQL injection in query builder" in content
        assert "FEW_SHOT_EXAMPLES: list[dict[str, str]] = [" in content

    def test_multiple_examples(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, PROMPT_WITH_SENTINELS)
        writer = PromptWriter()
        examples = [
            _make_example(description="Issue A"),
            _make_example(
                example_type="false_positive",
                description="Issue B",
                explanation="FP: not actually exploitable",
            ),
        ]
        writer.write_fewshot_examples(examples, prompt_path=path)

        content = path.read_text()
        assert "Issue A" in content
        assert "Issue B" in content


class TestPromptWriterVersionBump:
    """PROMPT_VERSION is bumped on actual changes."""

    def test_bumps_minor_version(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        new_version = writer.write_fewshot_examples([_make_example()], prompt_path=path)

        assert new_version == "1.2.0"
        content = path.read_text()
        assert 'PROMPT_VERSION: str = "1.2.0"' in content

    def test_no_bump_when_examples_unchanged(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, PROMPT_WITH_SENTINELS)
        writer = PromptWriter()
        examples = [_make_example()]

        # First write
        v1 = writer.write_fewshot_examples(examples, prompt_path=path)
        content_after_first = path.read_text()

        # Second write with same examples
        v2 = writer.write_fewshot_examples(examples, prompt_path=path)
        content_after_second = path.read_text()

        assert v1 == v2
        assert content_after_first == content_after_second


class TestPromptWriterIdempotency:
    """Re-running with the same examples produces no file changes."""

    def test_idempotent_writes(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        examples = [_make_example()]

        writer.write_fewshot_examples(examples, prompt_path=path)
        content_first = path.read_text()

        writer.write_fewshot_examples(examples, prompt_path=path)
        content_second = path.read_text()

        assert content_first == content_second


class TestPromptWriterUserPromptInjection:
    """FEW_SHOT_EXAMPLES reference added to USER_PROMPT_TEMPLATE."""

    def test_adds_fewshot_ref_to_user_prompt(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        writer.write_fewshot_examples([_make_example()], prompt_path=path)

        content = path.read_text()
        assert "few_shot_examples" in content

    def test_does_not_duplicate_fewshot_ref(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, PROMPT_WITH_SENTINELS)
        writer = PromptWriter()
        writer.write_fewshot_examples([_make_example()], prompt_path=path)

        content = path.read_text()
        assert content.count("{few_shot_examples}") == 1


class TestPromptWriterErrorHandling:
    """Error cases are handled correctly."""

    def test_raises_file_not_found(self) -> None:
        writer = PromptWriter()
        with pytest.raises(FileNotFoundError):
            writer.write_fewshot_examples(
                [_make_example()],
                prompt_path=Path("/nonexistent/adversarial_reviewer.py"),
            )

    def test_raises_on_empty_examples(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        with pytest.raises(ValueError, match="examples"):
            writer.write_fewshot_examples([], prompt_path=path)


class TestPromptWriterDryRun:
    """Dry-run mode does not modify the file."""

    def test_dry_run_returns_version_without_writing(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter(dry_run=True)
        original = path.read_text()

        new_version = writer.write_fewshot_examples([_make_example()], prompt_path=path)

        assert new_version == "1.2.0"
        assert path.read_text() == original


class TestPromptWriterSanitization:
    """Input content is sanitized."""

    def test_rejects_triple_quotes_in_description(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        bad_example = _make_example(description='injection """attack')
        with pytest.raises(ValueError, match="sanitiz"):
            writer.write_fewshot_examples([bad_example], prompt_path=path)

    def test_rejects_backslash_escapes_in_evidence(self, tmp_path: Path) -> None:
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter()
        bad_example = _make_example(evidence="escape \\x00 attempt")
        with pytest.raises(ValueError, match="sanitiz"):
            writer.write_fewshot_examples([bad_example], prompt_path=path)


class TestPromptWriterAuditLog:
    """Changes are recorded in an audit log."""

    def test_audit_log_written(self, tmp_path: Path) -> None:
        audit_path = tmp_path / "audit.jsonl"
        path = _write_prompt(tmp_path, MINIMAL_PROMPT)
        writer = PromptWriter(audit_log_path=audit_path)
        writer.write_fewshot_examples([_make_example()], prompt_path=path)

        assert audit_path.exists()
        import json

        entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
        assert len(entries) == 1
        assert entries[0]["old_version"] == "1.1.0"
        assert entries[0]["new_version"] == "1.2.0"
        assert entries[0]["num_examples"] == 1
