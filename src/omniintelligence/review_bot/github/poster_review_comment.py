"""GitHub PR comment poster for the Code Intelligence Review Bot.

Posts ReviewFinding results as inline review comments on GitHub PRs.
Findings with file_path + line_number get inline comments; findings
without line_number are grouped as top-level PR comments.

Bot comment cleanup: all bot comments include the hidden marker
<!-- omni-review-bot --> and are deleted before posting new ones.

OMN-2497: Implement inline GitHub PR comment posting.
"""

from __future__ import annotations

import sys

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity

from omniintelligence.review_bot.github.client_github import BOT_MARKER, GitHubClient

_SEVERITY_BADGES = {
    ReviewSeverity.BLOCKER: "🔴 **BLOCKER**",
    ReviewSeverity.WARNING: "🟡 **WARNING**",
    ReviewSeverity.INFO: "🔵 **INFO**",
}


class ReviewCommentPoster:
    """Posts ReviewFindings as GitHub PR comments.

    Features:
    - Inline comments at the exact file/line of each finding
    - Top-level grouped comment for findings without a line number
    - Stale bot comment cleanup on re-run
    - Deduplication by finding_id within a single run
    - Graceful degradation: API failures log to stderr and return 0

    Usage::

        poster = ReviewCommentPoster(client=github_client)
        poster.post_findings(
            findings=result.findings,
            pr_number=42,
            commit_id="abc123",
        )
    """

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    def post_findings(
        self,
        findings: list[ModelReviewFinding],
        pr_number: int,
        commit_id: str,
    ) -> None:
        """Post findings as GitHub PR comments.

        Cleans up existing bot comments first, then posts new ones.
        API failures are logged but do not raise.

        Args:
            findings: List of review findings to post.
            pr_number: PR number to comment on.
            commit_id: Commit SHA for inline comment positioning.
        """
        try:
            # Step 1: Clean up stale bot comments
            self._cleanup_bot_comments(pr_number)

            # Step 2: Deduplicate findings by finding_id
            seen_ids: set[str] = set()
            unique_findings: list[ModelReviewFinding] = []
            for finding in findings:
                fid = str(finding.finding_id)
                if fid not in seen_ids:
                    seen_ids.add(fid)
                    unique_findings.append(finding)

            # Step 3: Split into inline and summary findings
            inline = [f for f in unique_findings if f.line_number is not None]
            summary = [f for f in unique_findings if f.line_number is None]

            # Step 4: Post inline comments
            for finding in inline:
                self._post_inline_comment(finding, pr_number, commit_id)

            # Step 5: Post grouped top-level comment for summary findings
            if summary:
                self._post_summary_comment(summary, pr_number)

        except Exception as exc:
            # API failures must not fail CI
            print(f"WARNING: Failed to post review comments: {exc}", file=sys.stderr)

    def _cleanup_bot_comments(self, pr_number: int) -> None:
        """Delete all existing bot comments on the PR.

        Args:
            pr_number: PR number to clean up.
        """
        # Clean inline review comments
        try:
            review_comments = self._client.list_pr_review_comments(pr_number)
            for comment in review_comments:
                body = comment.get("body", "")
                if BOT_MARKER in body:
                    comment_id = comment.get("id")
                    if comment_id:
                        self._client.delete_review_comment(int(comment_id))
        except Exception as exc:
            print(f"WARNING: Could not clean review comments: {exc}", file=sys.stderr)

        # Clean top-level issue comments
        try:
            issue_comments = self._client.list_pr_issue_comments(pr_number)
            for comment in issue_comments:
                body = comment.get("body", "")
                if BOT_MARKER in body:
                    comment_id = comment.get("id")
                    if comment_id:
                        self._client.delete_issue_comment(int(comment_id))
        except Exception as exc:
            print(f"WARNING: Could not clean issue comments: {exc}", file=sys.stderr)

    def _post_inline_comment(
        self,
        finding: ModelReviewFinding,
        pr_number: int,
        commit_id: str,
    ) -> None:
        """Post a single inline review comment for a finding.

        Args:
            finding: The finding to post (must have line_number).
            pr_number: PR number.
            commit_id: Commit SHA for positioning.
        """
        assert finding.line_number is not None
        body = self._format_inline_comment(finding)

        self._client.create_review_comment(
            pr_number=pr_number,
            commit_id=commit_id,
            path=finding.file_path,
            line=finding.line_number,
            body=body,
        )

    def _post_summary_comment(
        self,
        findings: list[ModelReviewFinding],
        pr_number: int,
    ) -> None:
        """Post a grouped top-level comment for findings without line numbers.

        Args:
            findings: Findings without line_number.
            pr_number: PR number.
        """
        body = self._format_summary_comment(findings)
        self._client.create_issue_comment(pr_number=pr_number, body=body)

    def _format_inline_comment(self, finding: ModelReviewFinding) -> str:
        """Format a single finding as an inline comment body.

        Args:
            finding: The finding to format.

        Returns:
            Markdown comment body with bot marker.
        """
        badge = _SEVERITY_BADGES.get(finding.severity, f"**{finding.severity.value}**")
        return (
            f"{BOT_MARKER}\n"
            f"{badge} `{finding.rule_id}`\n\n"
            f"**{finding.rationale}**\n\n"
            f"**Suggested fix**: {finding.suggested_fix}\n\n"
            f"<sub>finding_id: `{finding.finding_id}` | "
            f"confidence: {finding.confidence:.0%}</sub>"
        )

    def _format_summary_comment(self, findings: list[ModelReviewFinding]) -> str:
        """Format multiple findings without line numbers as a top-level comment.

        Grouped by file_path for readability.

        Args:
            findings: Findings to format.

        Returns:
            Markdown comment body with bot marker.
        """
        by_file: dict[str, list[ModelReviewFinding]] = {}
        for finding in findings:
            by_file.setdefault(finding.file_path, []).append(finding)

        lines = [
            f"{BOT_MARKER}",
            "## Code Intelligence Review Bot - Summary Findings",
            "",
        ]

        for file_path, file_findings in sorted(by_file.items()):
            lines.append(f"### `{file_path}`")
            lines.append("")
            for finding in file_findings:
                badge = _SEVERITY_BADGES.get(
                    finding.severity, f"**{finding.severity.value}**"
                )
                lines.append(f"- {badge} **{finding.rule_id}**: {finding.rationale}")
                lines.append(f"  - Fix: {finding.suggested_fix}")
            lines.append("")

        return "\n".join(lines)


__all__ = ["ReviewCommentPoster"]
