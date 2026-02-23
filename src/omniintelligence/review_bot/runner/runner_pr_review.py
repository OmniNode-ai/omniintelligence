"""Core PR review runner for the Code Intelligence Review Bot.

Runs a full review against a PR diff, produces ReviewFindings, computes a
ReviewScore, and determines the CI check result based on enforcement mode.

OMN-2496: Implement PR Gatekeeper CI integration.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_score import ModelReviewScore
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity
from omniintelligence.review_bot.schemas.model_review_policy import (
    ModelReviewPolicy,
    ModelReviewRule,
)
from omniintelligence.review_bot.validators.validator_policy import ValidatorPolicy


@dataclass
class PrReviewResult:
    """Result of a PR review run.

    Attributes:
        findings: All detected review findings.
        score: Aggregate score derived from findings.
        enforcement_mode: The enforcement mode used for this run.
        ci_passed: True if the CI check should pass.
        summary: Human-readable summary for workflow output.
    """

    findings: list[ModelReviewFinding]
    score: ModelReviewScore
    enforcement_mode: str
    ci_passed: bool
    summary: str


class RunnerPrReview:
    """Core PR review runner.

    Runs a full review against PR diff content, applies policy rules,
    and produces findings + score. Used by both GitHub Actions CI and
    the pre-commit fast-path.

    CI behavior per enforcement mode:
    - ``observe``: Always passes, findings logged to summary only
    - ``warn``: Always passes, findings posted as PR comments
    - ``block``: Fails if any BLOCKER findings present

    Usage::

        runner = RunnerPrReview()
        result = runner.run(
            diff_content=pr_diff,
            policy=policy,
        )
        sys.exit(0 if result.ci_passed else 1)
    """

    def run(
        self,
        diff_content: str,
        policy: ModelReviewPolicy,
        *,
        slow: bool = True,
    ) -> PrReviewResult:
        """Run a full review against a diff.

        Args:
            diff_content: Git diff content to review (unified diff format).
            policy: Loaded and validated policy to apply.
            slow: If True, include slow rules; if False, skip slow rules (pre-commit).

        Returns:
            PrReviewResult with findings, score, and CI pass/fail decision.
        """
        rules = policy.get_active_rules() if slow else policy.get_fast_rules()
        findings = self._scan_diff(diff_content, rules, policy)
        score = ModelReviewScore.from_findings(findings, policy_version=policy.version)
        enforcement_mode = policy.enforcement_mode
        ci_passed = self._compute_ci_passed(findings, enforcement_mode)
        summary = self._build_summary(findings, score, enforcement_mode, ci_passed)

        return PrReviewResult(
            findings=findings,
            score=score,
            enforcement_mode=enforcement_mode,
            ci_passed=ci_passed,
            summary=summary,
        )

    @classmethod
    def load_policy(cls, policy_path: str) -> ModelReviewPolicy | None:
        """Load and validate a policy file.

        Args:
            policy_path: Path to the policy YAML file.

        Returns:
            Validated ModelReviewPolicy, or None if file is missing/invalid.
        """
        validator = ValidatorPolicy()
        result = validator.validate_file(policy_path)

        if not result.is_valid:
            print(
                f"WARNING: Policy file {policy_path!r} is invalid:",
                file=sys.stderr,
            )
            for error in result.errors:
                print(f"  ERROR: {error}", file=sys.stderr)
            return None

        for warning in result.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)

        return result.policy

    def _scan_diff(
        self,
        diff_content: str,
        rules: list[ModelReviewRule],
        policy: ModelReviewPolicy,
    ) -> list[ModelReviewFinding]:
        """Scan diff content against all active rules.

        Parses the unified diff to extract changed lines, then applies
        each rule's pattern to detect violations.

        Args:
            diff_content: Unified diff content.
            rules: List of rules to apply.
            policy: Policy for exemption checking.

        Returns:
            List of detected findings.
        """
        findings: list[ModelReviewFinding] = []
        parsed_files = self._parse_diff(diff_content)

        for file_path, lines in parsed_files.items():
            for rule in rules:
                try:
                    pattern = re.compile(rule.pattern, re.MULTILINE)
                except re.error:
                    # Invalid regex pattern; skip this rule
                    continue

                for line_number, line_content in lines:
                    if pattern.search(line_content):
                        # Check if this path is exempted for this rule
                        if self._is_exempted(rule.id, file_path, policy):
                            continue

                        findings.append(
                            ModelReviewFinding(
                                rule_id=rule.id,
                                severity=ReviewSeverity(rule.severity.value),
                                confidence=0.85,  # Default confidence for pattern matches
                                rationale=rule.message,
                                suggested_fix=f"See rule {rule.id!r} for remediation guidance.",
                                file_path=file_path,
                                line_number=line_number,
                            )
                        )

        return findings

    def _parse_diff(self, diff_content: str) -> dict[str, list[tuple[int, str]]]:
        """Parse unified diff into file -> [(line_number, line_content)] mapping.

        Only includes added/changed lines (prefixed with '+' in the diff),
        not removed lines.

        Args:
            diff_content: Unified diff string.

        Returns:
            Dict mapping file path to list of (line_number, content) tuples.
        """
        result: dict[str, list[tuple[int, str]]] = {}
        current_file: str | None = None
        current_line = 0

        for raw_line in diff_content.splitlines():
            # New file in diff
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                result.setdefault(current_file, [])
                current_line = 0
            elif raw_line.startswith("+++ /dev/null"):
                current_file = None
            # Hunk header: @@ -a,b +c,d @@
            elif raw_line.startswith("@@"):
                match = re.search(r"\+(\d+)", raw_line)
                if match:
                    current_line = int(match.group(1)) - 1
            # Added line
            elif raw_line.startswith("+") and current_file is not None:
                current_line += 1
                line_content = raw_line[1:]  # Strip leading '+'
                result[current_file].append((current_line, line_content))
            # Context or removed line
            elif not raw_line.startswith("-"):
                current_line += 1

        return result

    def _is_exempted(
        self,
        rule_id: str,
        file_path: str,
        policy: ModelReviewPolicy,
    ) -> bool:
        """Check if a rule is exempted for a given file path.

        Args:
            rule_id: The rule to check.
            file_path: The file path to check against.
            policy: The policy containing exemptions.

        Returns:
            True if the file/rule combination is exempted and not expired.
        """
        for exemption in policy.exemptions:
            if exemption.rule != rule_id:
                continue
            if exemption.is_expired:
                continue
            # Check if path is a prefix match
            if file_path.startswith(exemption.path) or file_path == exemption.path:
                return True
        return False

    def _compute_ci_passed(
        self,
        findings: list[ModelReviewFinding],
        enforcement_mode: str,
    ) -> bool:
        """Determine if CI should pass based on enforcement mode.

        Args:
            findings: Review findings from the scan.
            enforcement_mode: "observe", "warn", or "block".

        Returns:
            True if CI should pass.
        """
        if enforcement_mode in ("observe", "warn"):
            return True

        if enforcement_mode == "block":
            has_blockers = any(f.severity == ReviewSeverity.BLOCKER for f in findings)
            return not has_blockers

        # Unknown mode: default to passing
        return True

    def _build_summary(
        self,
        findings: list[ModelReviewFinding],
        score: ModelReviewScore,
        enforcement_mode: str,
        ci_passed: bool,
    ) -> str:
        """Build a human-readable summary for workflow output.

        Args:
            findings: Review findings.
            score: Computed review score.
            enforcement_mode: The enforcement mode.
            ci_passed: Whether CI passed.

        Returns:
            Markdown-formatted summary string.
        """
        status = "PASSED" if ci_passed else "FAILED"
        blocker_count = score.finding_count_by_severity.get(
            ReviewSeverity.BLOCKER.value, 0
        )
        warning_count = score.finding_count_by_severity.get(
            ReviewSeverity.WARNING.value, 0
        )
        info_count = score.finding_count_by_severity.get(ReviewSeverity.INFO.value, 0)

        lines = [
            f"## Code Intelligence Review Bot - {status}",
            "",
            f"**Score**: {score.score}/100 | **Mode**: {enforcement_mode}",
            f"**Findings**: {blocker_count} BLOCKER, {warning_count} WARNING, {info_count} INFO",
            "",
        ]

        if findings:
            lines.append("### Findings")
            for finding in findings[:20]:  # Limit summary to first 20
                loc = f":{finding.line_number}" if finding.line_number else ""
                lines.append(
                    f"- **[{finding.severity.value}]** `{finding.file_path}{loc}` "
                    f"({finding.rule_id}): {finding.rationale}"
                )
            if len(findings) > 20:
                lines.append(f"- *... and {len(findings) - 20} more findings*")
        else:
            lines.append("No findings detected.")

        return "\n".join(lines)


__all__ = ["PrReviewResult", "RunnerPrReview"]
