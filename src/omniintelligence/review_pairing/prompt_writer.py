# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Prompt Writer for few-shot injection into the adversarial reviewer prompt.

Manages sentinel-delimited few-shot example sections in the prompt file,
with sanitization, AST validation, and file-lock concurrency control.

Reference: OMN-6175 (epic OMN-6164)
"""

from __future__ import annotations

import ast
import fcntl
import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from omniintelligence.review_pairing.models_calibration import FewShotExample

logger = logging.getLogger(__name__)

_SENTINEL_BEGIN = "# --- BEGIN FEW_SHOT_EXAMPLES ---"
_SENTINEL_END = "# --- END FEW_SHOT_EXAMPLES ---"

_DANGEROUS_PATTERNS = re.compile(
    r"^(import |from .+ import |def |class |exec\(|eval\()",
    re.MULTILINE,
)

_AUDIT_LOG_DIR = Path.home() / ".onex_state"
_AUDIT_LOG_PATH = _AUDIT_LOG_DIR / "prompt-write-audit.jsonl"

_DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompts" / "adversarial_reviewer.py"


class PromptWriter:
    """Writes few-shot examples into the adversarial reviewer prompt file."""

    def write_fewshot_examples(
        self,
        examples: list[FewShotExample],
        prompt_path: Path | None = None,
        run_id: str = "",
        dry_run: bool = False,
    ) -> str:
        """Write few-shot examples to the prompt file.

        Args:
            examples: Few-shot examples to inject.
            prompt_path: Path to the prompt file. Defaults to adversarial_reviewer.py.
            run_id: Triggering calibration run ID for audit trail.
            dry_run: If True, return generated content without writing to file.

        Returns:
            New PROMPT_VERSION string.

        Raises:
            FileNotFoundError: If prompt_path does not exist.
        """
        path = prompt_path or _DEFAULT_PROMPT_PATH
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        fewshot_constant = _build_fewshot_constant(examples)

        if dry_run:
            return fewshot_constant

        content = path.read_text()
        old_hash = sha256(content.encode()).hexdigest()

        old_version = _extract_prompt_version(content)
        existing_fewshot = _extract_existing_fewshot(content)
        if existing_fewshot == fewshot_constant:
            return old_version

        if _SENTINEL_BEGIN not in content:
            content = _insert_sentinels(content)

        content = _replace_between_sentinels(content, fewshot_constant)

        new_version = _bump_minor_version(old_version)
        content = _update_prompt_version(content, old_version, new_version)

        try:
            _validate_fewshot_string(fewshot_constant)
        except ValueError:
            logger.warning(
                "Generated FEW_SHOT_EXAMPLES failed AST validation, skipping write"
            )
            return old_version

        try:
            fd = path.open("r+")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                logger.warning("Could not acquire file lock, skipping write")
                fd.close()
                return old_version

            fd.seek(0)
            fd.write(content)
            fd.truncate()
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()
        except Exception:
            logger.exception("Failed to write prompt file")
            return old_version

        try:
            subprocess.run(
                ["ruff", "format", str(path)],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ruff format failed on prompt file")

        new_hash = sha256(path.read_text().encode()).hexdigest()
        _write_audit_record(
            run_id=run_id,
            old_version=old_version,
            new_version=new_version,
            old_hash=old_hash,
            new_hash=new_hash,
            example_count=len(examples),
        )

        return new_version


def _sanitize_for_python_string(text: str) -> str:
    """Sanitize model-generated text for embedding in Python source."""
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace(_SENTINEL_BEGIN, "").replace(_SENTINEL_END, "")
    text = _DANGEROUS_PATTERNS.sub("", text)
    return text[:500]


def _build_fewshot_constant(examples: list[FewShotExample]) -> str:
    """Build the FEW_SHOT_EXAMPLES Python string constant."""
    parts: list[str] = [
        "## Calibration Examples (auto-generated, do not edit manually)\\n\\n"
    ]
    for ex in examples:
        header = ex.example_type.replace("_", " ").title()
        cat = _sanitize_for_python_string(ex.category)
        desc = _sanitize_for_python_string(ex.description)
        explanation = _sanitize_for_python_string(ex.explanation)
        parts.append(f"### {header}: {cat}\\n")
        parts.append(f"{desc}\\n")
        label = {
            "true_positive": "Why this is valid",
            "false_positive": "Why this is noise",
            "false_negative": "Why this was missed",
        }.get(ex.example_type, "Note")
        parts.append(f"{label}: {explanation}\\n\\n")

    joined = "".join(parts)
    return f'FEW_SHOT_EXAMPLES: str = (\n    "{joined}"\n)'


def _extract_prompt_version(content: str) -> str:
    """Extract current PROMPT_VERSION from file content."""
    match = re.search(r'PROMPT_VERSION\s*[=:]\s*"([^"]+)"', content)
    return match.group(1) if match else "1.0.0"


def _extract_existing_fewshot(content: str) -> str:
    """Extract existing FEW_SHOT_EXAMPLES content between sentinels."""
    begin = content.find(_SENTINEL_BEGIN)
    end = content.find(_SENTINEL_END)
    if begin == -1 or end == -1:
        return ""
    return content[begin + len(_SENTINEL_BEGIN) : end].strip()


def _insert_sentinels(content: str) -> str:
    """Insert sentinel comments after SYSTEM_PROMPT definition."""
    system_prompt_end = content.find('"""', content.find("SYSTEM_PROMPT"))
    if system_prompt_end == -1:
        return content + f"\n\n{_SENTINEL_BEGIN}\n{_SENTINEL_END}\n"

    insert_pos = content.find("\n", system_prompt_end + 3) + 1
    return (
        content[:insert_pos]
        + f"\n{_SENTINEL_BEGIN}\n{_SENTINEL_END}\n"
        + content[insert_pos:]
    )


def _replace_between_sentinels(content: str, fewshot: str) -> str:
    """Replace content between sentinel markers."""
    begin = content.find(_SENTINEL_BEGIN)
    end = content.find(_SENTINEL_END)
    if begin == -1 or end == -1:
        return content
    return (
        content[: begin + len(_SENTINEL_BEGIN)] + "\n" + fewshot + "\n" + content[end:]
    )


def _bump_minor_version(version: str) -> str:
    """Bump the minor component of a semver string."""
    parts = version.split(".")
    if len(parts) >= 2:
        parts[1] = str(int(parts[1]) + 1)
        return ".".join(parts)
    return version


def _update_prompt_version(content: str, old: str, new: str) -> str:
    """Replace PROMPT_VERSION value in content."""
    return content.replace(f'PROMPT_VERSION = "{old}"', f'PROMPT_VERSION = "{new}"')


def _validate_fewshot_string(constant: str) -> None:
    """Validate that the generated Python constant is valid."""
    try:
        match = re.search(r'"([^"]*(?:\\.[^"]*)*)"', constant)
        if match:
            ast.literal_eval(f'"{match.group(1)}"')
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Invalid Python string constant: {e}") from e


def _write_audit_record(
    run_id: str,
    old_version: str,
    new_version: str,
    old_hash: str,
    new_hash: str,
    example_count: int,
) -> None:
    """Write a provenance audit record to the local JSONL log."""
    try:
        _AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "old_version": old_version,
            "new_version": new_version,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "example_count": example_count,
        }
        with _AUDIT_LOG_PATH.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        logger.warning("Failed to write prompt audit record")
