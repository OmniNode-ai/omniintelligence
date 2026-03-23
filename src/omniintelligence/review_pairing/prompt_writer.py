# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Prompt writer for injecting few-shot examples into adversarial reviewer prompts.

Reads the adversarial_reviewer.py prompt file, inserts or replaces few-shot
examples between sentinel comments, bumps the PROMPT_VERSION, and optionally
appends the examples reference to USER_PROMPT_TEMPLATE.

Supply-chain controls: file locking, input sanitization, audit log, dry-run.

Reference: OMN-6175
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from omniintelligence.review_pairing.models_calibration import FewShotExample

_BEGIN_SENTINEL = "# --- BEGIN FEW_SHOT_EXAMPLES ---"
_END_SENTINEL = "# --- END FEW_SHOT_EXAMPLES ---"

_SENTINEL_PATTERN = re.compile(
    rf"^{re.escape(_BEGIN_SENTINEL)}\n.*?^{re.escape(_END_SENTINEL)}\n",
    re.MULTILINE | re.DOTALL,
)

_VERSION_PATTERN = re.compile(r'PROMPT_VERSION:\s*str\s*=\s*"(\d+)\.(\d+)\.(\d+)"')

_DANGEROUS_PATTERNS = re.compile(r'"""|\'\'\'|\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\0')

_FEWSHOT_REF_MARKER = "{few_shot_examples}"


class PromptWriter:
    """Injects few-shot examples into adversarial_reviewer.py.

    Args:
        dry_run: If True, compute the result but do not write to disk.
        audit_log_path: If provided, append a JSONL entry for each write.
    """

    def __init__(
        self,
        *,
        dry_run: bool = False,
        audit_log_path: Path | None = None,
    ) -> None:
        self._dry_run = dry_run
        self._audit_log_path = audit_log_path

    def write_fewshot_examples(
        self,
        examples: list[FewShotExample],
        prompt_path: Path | None = None,
    ) -> str:
        """Write few-shot examples into the adversarial reviewer prompt file.

        Args:
            examples: Non-empty list of few-shot examples to inject.
            prompt_path: Path to adversarial_reviewer.py. If None, uses the
                default location relative to this package.

        Returns:
            The new PROMPT_VERSION string.

        Raises:
            FileNotFoundError: If prompt_path does not exist.
            ValueError: If examples is empty or contains unsanitized content.
        """
        if not examples:
            raise ValueError("examples must be a non-empty list")

        if prompt_path is None:
            prompt_path = Path(__file__).parent / "prompts" / "adversarial_reviewer.py"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        self._sanitize_examples(examples)

        content = prompt_path.read_text()
        old_version = self._extract_version(content)

        # Build the few-shot block
        fewshot_block = self._format_fewshot_block(examples)

        # Insert or replace sentinel section
        new_content = self._inject_sentinels(content, fewshot_block)

        # Add reference to USER_PROMPT_TEMPLATE if needed
        new_content = self._inject_user_prompt_ref(new_content)

        # Compute hash of the fewshot block to detect actual changes
        new_block_hash = hashlib.sha256(fewshot_block.strip().encode()).hexdigest()
        old_block_hash = self._extract_existing_block_hash(content)

        if new_block_hash == old_block_hash:
            # No actual change — return current version without bumping
            return old_version

        # Bump version
        new_version = self._bump_minor(old_version)
        new_content = _VERSION_PATTERN.sub(
            f'PROMPT_VERSION: str = "{new_version}"', new_content
        )

        if not self._dry_run:
            self._write_locked(prompt_path, new_content)

        if self._audit_log_path is not None:
            self._write_audit_entry(
                old_version=old_version,
                new_version=new_version,
                num_examples=len(examples),
                prompt_path=prompt_path,
            )

        return new_version

    @staticmethod
    def _sanitize_examples(examples: list[FewShotExample]) -> None:
        """Validate that example fields contain no dangerous Python constructs."""
        for ex in examples:
            for field_name in ("description", "evidence", "explanation", "category"):
                value = getattr(ex, field_name)
                if _DANGEROUS_PATTERNS.search(value):
                    raise ValueError(
                        f"Unsanitized content in {field_name}: "
                        f"dangerous pattern found in {value!r}"
                    )

    @staticmethod
    def _extract_version(content: str) -> str:
        m = _VERSION_PATTERN.search(content)
        if not m:
            return "0.0.0"
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

    @staticmethod
    def _bump_minor(version: str) -> str:
        parts = version.split(".")
        return f"{parts[0]}.{int(parts[1]) + 1}.0"

    @staticmethod
    def _format_fewshot_block(examples: list[FewShotExample]) -> str:
        """Format examples as a valid Python list-of-dicts constant."""
        items: list[str] = []
        for ex in examples:
            item = textwrap.indent(
                "{\n"
                f'    "example_type": {ex.example_type!r},\n'
                f'    "category": {ex.category!r},\n'
                f'    "description": {ex.description!r},\n'
                f'    "evidence": {ex.evidence!r},\n'
                f'    "ground_truth_present": {ex.ground_truth_present!r},\n'
                f'    "explanation": {ex.explanation!r},\n'
                "}",
                "    ",
            )
            items.append(item)
        joined = ",\n".join(items)
        return f"FEW_SHOT_EXAMPLES: list[dict[str, str]] = [\n{joined},\n]"

    def _inject_sentinels(self, content: str, fewshot_block: str) -> str:
        """Insert or replace the sentinel-wrapped block."""
        sentinel_section = f"{_BEGIN_SENTINEL}\n{fewshot_block}\n{_END_SENTINEL}\n"

        if _SENTINEL_PATTERN.search(content):
            return _SENTINEL_PATTERN.sub(sentinel_section, content)

        # Insert after SYSTEM_PROMPT definition ends.
        # Find the end of the SYSTEM_PROMPT assignment (closing paren or end of string literal).
        # Strategy: find "SYSTEM_PROMPT" then the next blank line after it.
        lines = content.split("\n")
        insert_idx = None
        in_system_prompt = False
        paren_depth = 0
        for i, line in enumerate(lines):
            if "SYSTEM_PROMPT" in line and "=" in line and not in_system_prompt:
                in_system_prompt = True
                paren_depth += line.count("(") - line.count(")")
                if paren_depth <= 0:
                    insert_idx = i + 1
                    break
                continue
            if in_system_prompt:
                paren_depth += line.count("(") - line.count(")")
                if paren_depth <= 0:
                    insert_idx = i + 1
                    break

        if insert_idx is None:
            # Fallback: append before USER_PROMPT_TEMPLATE
            for i, line in enumerate(lines):
                if "USER_PROMPT_TEMPLATE" in line:
                    insert_idx = i
                    break

        if insert_idx is None:
            insert_idx = len(lines)

        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, sentinel_section.rstrip("\n"))
        return "\n".join(lines)

    @staticmethod
    def _inject_user_prompt_ref(content: str) -> str:
        """Add {few_shot_examples} ref to USER_PROMPT_TEMPLATE if absent."""
        if _FEWSHOT_REF_MARKER in content:
            return content

        lines = content.split("\n")
        new_lines: list[str] = []
        in_user_prompt = False
        paren_depth = 0
        injected = False

        for line in lines:
            if (
                "USER_PROMPT_TEMPLATE" in line
                and "=" in line
                and not in_user_prompt
                and "USER_PROMPT_TEMPLATE_PR" not in line
            ):
                in_user_prompt = True
                paren_depth += line.count("(") - line.count(")")
                if paren_depth <= 0:
                    # Single-line template — rewrite to multi-line with ref
                    # e.g. USER_PROMPT_TEMPLATE: str = "Review: {plan_content}"
                    m = re.match(
                        r'(USER_PROMPT_TEMPLATE:\s*str\s*=\s*)"(.+)"$',
                        line,
                    )
                    if m:
                        prefix = m.group(1)
                        body = m.group(2)
                        new_lines.append(f"{prefix}(")
                        new_lines.append(f'    "{body}\\n"')
                        new_lines.append('    "\\n"')
                        new_lines.append('    "## Reference Examples\\n"')
                        new_lines.append(f'    "{_FEWSHOT_REF_MARKER}"')
                        new_lines.append(")")
                    else:
                        new_lines.append(line)
                    in_user_prompt = False
                    injected = True
                    continue
                new_lines.append(line)
                continue
            if in_user_prompt and not injected:
                paren_depth += line.count("(") - line.count(")")
                if paren_depth <= 0:
                    # This is the closing line — inject before it
                    new_lines.append('    "\\n"')
                    new_lines.append('    "## Reference Examples\\n"')
                    new_lines.append(f'    "{_FEWSHOT_REF_MARKER}"')
                    in_user_prompt = False
                    injected = True
                new_lines.append(line)
                continue
            new_lines.append(line)

        if not injected:
            return content

        return "\n".join(new_lines)

    @staticmethod
    def _write_locked(path: Path, content: str) -> None:
        """Write content with exclusive file locking."""
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _extract_existing_block_hash(self, content: str) -> str | None:
        """Extract hash of the existing fewshot block between sentinels."""
        m = _SENTINEL_PATTERN.search(content)
        if not m:
            return None
        block = m.group(0)
        # Extract just the content between sentinels, strip to normalize
        inner = (
            block.replace(_BEGIN_SENTINEL + "\n", "")
            .replace(_END_SENTINEL + "\n", "")
            .strip()
        )
        return hashlib.sha256(inner.encode()).hexdigest()

    def _write_audit_entry(
        self,
        *,
        old_version: str,
        new_version: str,
        num_examples: int,
        prompt_path: Path,
    ) -> None:
        """Append a JSONL audit entry."""
        if self._audit_log_path is None:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "write_fewshot_examples",
            "prompt_path": str(prompt_path),
            "old_version": old_version,
            "new_version": new_version,
            "num_examples": num_examples,
            "dry_run": self._dry_run,
        }
        with open(self._audit_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
