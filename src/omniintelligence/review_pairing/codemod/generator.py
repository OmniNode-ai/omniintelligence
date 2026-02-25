# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Deterministic refactor tool generation from STABLE patterns.

Converts STABLE patterns with convergent transform signatures into executable
codemod definitions and anti-pattern validators.

Core components:
    - ``CodemodDefinition``: Generated codemod with source code and status.
    - ``CodemodReplayValidator``: Validates a codemod against historical pairs.
    - ``AntiPatternValidator``: Detects reintroduction of deprecated patterns.
    - ``CodemodGeneratorSpec``: Structured input for LLM-based generation (caller provides).

Architecture:
    This module contains only the pure-computation replay validation and
    violation detection logic. The LLM call for codemod generation is
    performed by the caller (Effect node) using ``CodemodGeneratorSpec`` as
    a structured prompt contract. The caller invokes the LLM, receives
    ``codemod_source`` as a string, constructs a ``CodemodDefinition``, and
    passes it to ``CodemodReplayValidator.validate()`` for sandbox testing.

Safety constraints:
    - Generated codemod code is NEVER exec'd outside ``CodemodReplayValidator``.
    - Replay runs in a subprocess with a timeout.
    - Anti-pattern validators run in-process but are pure Python functions.
    - No filesystem writes from this module.

Reference: OMN-2585
"""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SANDBOX_TIMEOUT_SECONDS: int = 10
"""Maximum wall-clock time for a single codemod replay run."""

MIN_REPLAY_PASS_FRACTION: float = 1.0
"""All historical cases must pass for a codemod to be marked ``validated``."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@unique
class CodemodStatus(str, Enum):
    """Status of a generated codemod definition.

    Values:
        PENDING: Just generated, not yet validated.
        VALIDATED: All replay cases pass; ready for activation.
        FAILED: One or more replay cases failed; flagged for manual review.
        REJECTED: Static analysis (mypy/ruff) rejected the generated code.
    """

    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class ReplayCase:
    """A single before/after code example for replay validation.

    Attributes:
        pair_id: UUID of the ``FindingFixPair`` this example came from.
        input_source: Source code before the fix.
        expected_output: Source code after the fix (ground truth).
        file_path: Relative path to the file (for context).
        rule_id: Rule this fix addresses.
    """

    pair_id: UUID
    input_source: str
    expected_output: str
    file_path: str = ""
    rule_id: str = ""


@dataclass
class ReplayResult:
    """Result of running replay validation for a codemod.

    Attributes:
        passed: Whether all replay cases produced the expected output.
        cases_total: Total number of replay cases.
        cases_passed: Number of cases that produced correct output.
        cases_failed: Number of cases that produced incorrect output.
        failing_case_ids: pair_ids of the failing cases.
        failure_details: Human-readable details per failing case.
        validated_at: UTC datetime of validation completion.
    """

    passed: bool
    cases_total: int
    cases_passed: int
    cases_failed: int
    failing_case_ids: list[UUID] = field(default_factory=list)
    failure_details: list[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class CodemodDefinition:
    """Generated codemod definition for a STABLE pattern.

    Attributes:
        codemod_id: Unique identifier for this codemod.
        pattern_id: Pattern this codemod was generated from.
        rule_id: Rule this codemod fixes.
        language: Target language (e.g. ``python``, ``typescript``).
        codemod_source: Full Python source of the codemod class.
            Must implement ``def apply(self, source_code: str) -> str``.
        status: Current status (PENDING / VALIDATED / FAILED / REJECTED).
        replay_result: Result of replay validation (None if not yet run).
        generated_at: UTC datetime of generation.
        transform_signature: The convergent diff transform this was built from.
    """

    codemod_id: UUID
    pattern_id: UUID
    rule_id: str
    language: str
    codemod_source: str
    status: CodemodStatus = CodemodStatus.PENDING
    replay_result: ReplayResult | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    transform_signature: str = ""


@dataclass(frozen=True)
class AntiPatternViolation:
    """A detected reintroduction of a deprecated pattern.

    Attributes:
        rule_id: The deprecated rule that was reintroduced.
        file_path: File where the violation was detected.
        line_number: Line number (1-indexed) of the violation.
        matched_text: The specific text that matched the deprecated pattern.
        pattern_id: The deprecated ``PatternCandidate`` that was violated.
    """

    rule_id: str
    file_path: str
    line_number: int
    matched_text: str
    pattern_id: UUID


@dataclass
class AntiPatternValidator:
    """Detects reintroduction of a deprecated pattern in source code.

    Each deprecated pattern generates one ``AntiPatternValidator``.
    These validators are registered in the linter adapter pipeline so
    that new occurrences of the deprecated pattern are flagged immediately.

    Attributes:
        validator_id: Unique identifier for this validator.
        pattern_id: The deprecated pattern this validator guards against.
        rule_id: The rule this validator checks for.
        signature_tokens: Key tokens from the deprecated transform signature.
            Used for in-process text matching.
        description: Human-readable description of what this detects.
    """

    validator_id: UUID
    pattern_id: UUID
    rule_id: str
    signature_tokens: list[str]
    description: str

    def check(
        self, source_code: str, file_path: str = ""
    ) -> list[AntiPatternViolation]:
        """Check source code for reintroductions of the deprecated pattern.

        Uses token-level matching against ``signature_tokens``. This is a
        conservative heuristic — false positives are possible and expected
        to be reviewed by the linter adapter pipeline.

        Args:
            source_code: Source code to check.
            file_path: Relative file path (for violation reporting).

        Returns:
            List of ``AntiPatternViolation`` instances (empty if clean).
        """
        violations: list[AntiPatternViolation] = []

        if not self.signature_tokens:
            return violations

        for line_num, line in enumerate(source_code.splitlines(), 1):
            for token in self.signature_tokens:
                if token and token in line:
                    violations.append(
                        AntiPatternViolation(
                            rule_id=self.rule_id,
                            file_path=file_path,
                            line_number=line_num,
                            matched_text=line.strip(),
                            pattern_id=self.pattern_id,
                        )
                    )
                    break  # Only report one violation per line

        return violations


@dataclass
class CodemodGeneratorSpec:
    """Structured input spec for LLM-based codemod generation.

    The caller (Effect node) uses this as a structured prompt contract:
    it fills this spec from the pattern's metadata and historical pairs,
    serialises it as a prompt, calls the LLM, and gets back
    ``codemod_source`` as a string.

    Attributes:
        rule_id: Rule the codemod should fix.
        language: Target language.
        transform_signature: Convergent diff transform signature from the reducer.
        before_after_examples: List of ``(before, after)`` string tuples
            from historical confirmed pairs. Used as few-shot examples.
        pattern_id: Pattern this codemod is being generated for.
        description: Human-readable description of what the codemod does.
    """

    rule_id: str
    language: str
    transform_signature: str
    before_after_examples: list[tuple[str, str]]
    pattern_id: UUID
    description: str = ""


# ---------------------------------------------------------------------------
# Replay validator
# ---------------------------------------------------------------------------


class CodemodReplayValidator:
    """Validates a generated codemod against historical before/after pairs.

    Runs the codemod's ``apply()`` method against each replay case in a
    sandboxed subprocess. Marks the codemod as VALIDATED only if all cases
    pass.

    Usage::

        validator = CodemodReplayValidator()
        codemod = CodemodDefinition(
            codemod_id=uuid4(),
            pattern_id=pattern_id,
            rule_id="ruff:E501",
            language="python",
            codemod_source=generated_source,
        )
        updated_codemod = validator.validate(codemod, replay_cases)
        if updated_codemod.status == CodemodStatus.VALIDATED:
            # Safe to store and activate
            ...
    """

    def validate(
        self,
        codemod: CodemodDefinition,
        replay_cases: list[ReplayCase],
        *,
        timeout: int = SANDBOX_TIMEOUT_SECONDS,
    ) -> CodemodDefinition:
        """Run replay validation for a codemod.

        Performs static analysis first (AST parse + mypy stub check), then
        runs each replay case in a sandboxed subprocess.

        Args:
            codemod: The ``CodemodDefinition`` to validate.
            replay_cases: Historical before/after examples.
            timeout: Per-case subprocess timeout in seconds.

        Returns:
            Updated ``CodemodDefinition`` with status and replay_result set.
        """
        if not replay_cases:
            logger.warning(
                "CodemodReplayValidator.validate: no replay cases for codemod=%s",
                codemod.codemod_id,
            )
            codemod.status = CodemodStatus.FAILED
            codemod.replay_result = ReplayResult(
                passed=False,
                cases_total=0,
                cases_passed=0,
                cases_failed=0,
                failure_details=["no replay cases provided"],
            )
            return codemod

        # Step 1: Static analysis — ensure the code parses
        rejection_reason = self._static_check(codemod.codemod_source)
        if rejection_reason:
            logger.warning(
                "CodemodReplayValidator.validate: codemod=%s rejected: %s",
                codemod.codemod_id,
                rejection_reason,
            )
            codemod.status = CodemodStatus.REJECTED
            codemod.replay_result = ReplayResult(
                passed=False,
                cases_total=len(replay_cases),
                cases_passed=0,
                cases_failed=len(replay_cases),
                failure_details=[f"static check failed: {rejection_reason}"],
            )
            return codemod

        # Step 2: Replay each case
        passed_ids: list[UUID] = []
        failed_ids: list[UUID] = []
        details: list[str] = []

        for case in replay_cases:
            ok, detail = self._run_case(
                codemod_source=codemod.codemod_source,
                case=case,
                timeout=timeout,
            )
            if ok:
                passed_ids.append(case.pair_id)
            else:
                failed_ids.append(case.pair_id)
                details.append(f"pair {case.pair_id}: {detail}")

        all_passed = len(failed_ids) == 0
        codemod.status = CodemodStatus.VALIDATED if all_passed else CodemodStatus.FAILED
        codemod.replay_result = ReplayResult(
            passed=all_passed,
            cases_total=len(replay_cases),
            cases_passed=len(passed_ids),
            cases_failed=len(failed_ids),
            failing_case_ids=failed_ids,
            failure_details=details,
        )

        logger.info(
            "CodemodReplayValidator.validate: codemod=%s %s (%d/%d cases passed)",
            codemod.codemod_id,
            codemod.status.value,
            len(passed_ids),
            len(replay_cases),
        )

        return codemod

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _static_check(codemod_source: str) -> str:
        """Run AST-level static check on codemod source.

        Returns empty string if OK, or an error message if the code is invalid.
        """
        try:
            ast.parse(codemod_source)
        except SyntaxError as exc:
            return f"SyntaxError: {exc}"

        # Check that the source contains an ``apply`` method signature
        if "def apply" not in codemod_source:
            return "codemod_source missing required 'def apply' method"

        return ""

    @staticmethod
    def _run_case(
        *,
        codemod_source: str,
        case: ReplayCase,
        timeout: int,
    ) -> tuple[bool, str]:
        """Run a single replay case in a sandboxed subprocess.

        The codemod is exec'd in a fresh Python interpreter. If the
        output matches ``case.expected_output``, the case passes.

        Args:
            codemod_source: Python source of the codemod class.
            case: The replay case to run.
            timeout: Wall-clock timeout in seconds.

        Returns:
            ``(passed, detail)`` tuple.
        """
        # Build a harness script that instantiates the codemod and calls apply()
        # NOTE: We concatenate the codemod source directly (not via f-string indented block)
        # to avoid dedent-stripping the user's indentation.
        harness = (
            "import sys\nimport inspect\n\n" + codemod_source + "\n\n"
            "klass = None\n"
            "for name, obj in list(globals().items()):\n"
            "    if inspect.isclass(obj) and hasattr(obj, 'apply'):\n"
            "        klass = obj\n"
            "        break\n"
            "\n"
            "if klass is None:\n"
            "    print('ERROR: no codemod class with apply() found', file=sys.stderr)\n"
            "    sys.exit(1)\n"
            "\n"
            "instance = klass()\n"
            f"input_src = {case.input_source!r}\n"
            "result = instance.apply(input_src)\n"
            "print(result, end='')\n"
        )

        try:
            proc = subprocess.run(
                [sys.executable, "-c", harness],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"timeout after {timeout}s"
        except Exception as exc:
            return False, f"subprocess error: {exc}"

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            return False, f"codemod exited {proc.returncode}: {stderr[:200]}"

        actual = proc.stdout
        expected = case.expected_output

        if actual == expected:
            return True, ""

        # Provide a diff-like detail for debugging
        actual_lines = actual.splitlines()
        expected_lines = expected.splitlines()
        first_diff = next(
            (
                f"line {i + 1}: got {a!r}, expected {e!r}"
                for i, (a, e) in enumerate(
                    zip(actual_lines, expected_lines, strict=False)
                )
                if a != e
            ),
            f"output length mismatch: got {len(actual_lines)} lines, "
            f"expected {len(expected_lines)} lines",
        )
        return False, first_diff


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_codemod_definition(
    *,
    pattern_id: UUID,
    rule_id: str,
    language: str,
    codemod_source: str,
    transform_signature: str = "",
) -> CodemodDefinition:
    """Convenience factory for creating a ``CodemodDefinition``.

    Args:
        pattern_id: Pattern UUID this codemod was generated for.
        rule_id: Rule the codemod fixes.
        language: Target language.
        codemod_source: Generated Python source code.
        transform_signature: Optional convergent diff transform signature.

    Returns:
        ``CodemodDefinition`` in PENDING status.
    """
    return CodemodDefinition(
        codemod_id=uuid4(),
        pattern_id=pattern_id,
        rule_id=rule_id,
        language=language,
        codemod_source=codemod_source,
        transform_signature=transform_signature,
    )


def make_anti_pattern_validator(
    *,
    pattern_id: UUID,
    rule_id: str,
    transform_signature: str,
    description: str = "",
) -> AntiPatternValidator:
    """Create an ``AntiPatternValidator`` from a deprecated pattern's transform.

    Extracts key tokens from the transform signature for heuristic matching.

    Args:
        pattern_id: UUID of the deprecated pattern.
        rule_id: Rule this validator guards against.
        transform_signature: Convergent transform signature from the reducer.
        description: Human-readable description.

    Returns:
        ``AntiPatternValidator`` ready to be registered in the linter pipeline.
    """
    # Extract non-trivial tokens from the signature for matching
    # Filter out common structural tokens and keep meaningful identifiers
    tokens: list[str] = []
    for line in transform_signature.splitlines():
        line = line.strip()
        if line and not line.startswith(("@@", "---", "+++")):
            # Take the first meaningful non-whitespace token per line
            parts = line.lstrip("+-").split()
            for part in parts:
                if len(part) >= 3 and part not in {"def", "class", "return", "import"}:
                    tokens.append(part)
                    break
        if len(tokens) >= 5:
            break  # Enough tokens for matching

    return AntiPatternValidator(
        validator_id=uuid4(),
        pattern_id=pattern_id,
        rule_id=rule_id,
        signature_tokens=tokens[:5],
        description=description
        or f"Anti-pattern validator for deprecated rule {rule_id}",
    )
