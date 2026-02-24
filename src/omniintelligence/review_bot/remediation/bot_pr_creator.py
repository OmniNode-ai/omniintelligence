"""Bot PR creator for the Code Intelligence Review Bot auto-remediation.

Creates isolated bot PRs targeting the same base branch as the source PR.
The source PR is never modified. Bot PRs are for human review before merge.

OMN-2498: Implement auto-remediation pipeline.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from omniintelligence.review_bot.github.client_github import GitHubClient
from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding


@dataclass
class BotPrSpec:
    """Specification for creating a bot PR.

    Attributes:
        source_pr_number: The PR this bot PR is remediating.
        source_pr_title: Title of the source PR (for bot PR title).
        base_branch: Branch to target with the bot PR.
        head_branch: Branch containing the remediation changes.
        applied_findings: Findings whose patches were applied.
    """

    source_pr_number: int
    source_pr_title: str
    base_branch: str
    head_branch: str
    applied_findings: list[ModelReviewFinding]


class BotPrCreator:
    """Creates isolated bot PRs via the GitHub API.

    Bot PR rules:
    - Targets same base branch as source PR (NOT the source PR branch)
    - Source PR is NEVER modified
    - Title format: [omni-review-bot] Auto-remediation for {source_pr_title}
    - Body links back to source PR and lists applied findings

    Usage::

        creator = BotPrCreator(client=github_client)
        pr_url = creator.create_bot_pr(spec)
    """

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    def create_bot_pr(self, spec: BotPrSpec) -> str | None:
        """Create a bot PR via the GitHub API.

        Args:
            spec: Bot PR specification.

        Returns:
            URL of the created PR, or None on failure.
        """
        try:
            title = f"[omni-review-bot] Auto-remediation for {spec.source_pr_title}"
            body = self._build_pr_body(spec)

            result = self._client._post(
                f"/repos/{self._client._repo}/pulls",
                {
                    "title": title,
                    "head": spec.head_branch,
                    "base": spec.base_branch,
                    "body": body,
                    "draft": False,
                },
            )

            if result is None:
                return None

            return result.get("html_url")

        except Exception as exc:
            print(f"WARNING: Failed to create bot PR: {exc}", file=sys.stderr)
            return None

    def _build_pr_body(self, spec: BotPrSpec) -> str:
        """Build the bot PR body with finding details.

        Args:
            spec: Bot PR specification.

        Returns:
            Markdown PR body.
        """
        lines = [
            "## Auto-Remediation PR",
            "",
            "This PR was automatically created by the Code Intelligence Review Bot.",
            f"It contains safe refactors for #{spec.source_pr_number}.",
            "",
            f"**Source PR**: #{spec.source_pr_number} - {spec.source_pr_title}",
            "",
            "## Applied Remediations",
            "",
        ]

        for finding in spec.applied_findings:
            lines.append(
                f"- **[{finding.severity.value}]** `{finding.rule_id}` in "
                f"`{finding.file_path}`: {finding.rationale}"
            )

        lines.extend(
            [
                "",
                "## Review Instructions",
                "",
                "1. Review each change in this PR carefully",
                "2. Merge if the changes look correct",
                "3. Close without merging to reject the auto-remediation",
                "",
                "_These changes are safe refactors only (type completers, formatters, "
                "import sorting, trivial renames). They have no semantic changes._",
            ]
        )

        return "\n".join(lines)


__all__ = ["BotPrCreator", "BotPrSpec"]
