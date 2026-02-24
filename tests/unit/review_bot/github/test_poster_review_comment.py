"""Unit tests for ReviewCommentPoster with mocked GitHub API.

Tests cover OMN-2497 acceptance criteria:
- R1: Inline comments posted at correct file/line
- R2: Stale bot comments cleaned up
- R3: Graceful degradation on API failure
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from omniintelligence.review_bot.github.client_github import BOT_MARKER, GitHubClient
from omniintelligence.review_bot.github.poster_review_comment import ReviewCommentPoster
from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_finding(
    rule_id: str = "no-bare-except",
    severity: ReviewSeverity = ReviewSeverity.BLOCKER,
    file_path: str = "src/handler.py",
    line_number: int | None = 42,
    finding_id: uuid.UUID | None = None,
) -> ModelReviewFinding:
    return ModelReviewFinding(
        finding_id=finding_id or uuid.uuid4(),
        rule_id=rule_id,
        severity=severity,
        confidence=0.9,
        rationale="Test rationale",
        suggested_fix="Test suggested fix",
        file_path=file_path,
        line_number=line_number,
    )


def make_mock_client() -> MagicMock:
    client = MagicMock(spec=GitHubClient)
    client.list_pr_review_comments.return_value = []
    client.list_pr_issue_comments.return_value = []
    client.create_review_comment.return_value = {"id": 1}
    client.create_issue_comment.return_value = {"id": 2}
    client.delete_review_comment.return_value = True
    client.delete_issue_comment.return_value = True
    return client


# ---------------------------------------------------------------------------
# R1: Inline comments posted at correct file/line
# ---------------------------------------------------------------------------


class TestInlineCommentPosting:
    def test_inline_comment_at_correct_file_and_line(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding(file_path="src/handler.py", line_number=42)
        poster.post_findings([finding], pr_number=1, commit_id="abc123")

        client.create_review_comment.assert_called_once_with(
            pr_number=1,
            commit_id="abc123",
            path="src/handler.py",
            line=42,
            body=poster._format_inline_comment(finding),
        )

    def test_inline_comment_body_includes_severity_badge(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding(severity=ReviewSeverity.BLOCKER)
        body = poster._format_inline_comment(finding)
        assert "BLOCKER" in body

    def test_inline_comment_body_includes_rule_id(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding(rule_id="no-bare-except")
        body = poster._format_inline_comment(finding)
        assert "no-bare-except" in body

    def test_inline_comment_body_includes_rationale(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding()
        body = poster._format_inline_comment(finding)
        assert "Test rationale" in body

    def test_inline_comment_body_includes_suggested_fix(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding()
        body = poster._format_inline_comment(finding)
        assert "Test suggested fix" in body

    def test_inline_comment_contains_bot_marker(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding()
        body = poster._format_inline_comment(finding)
        assert BOT_MARKER in body

    def test_multiple_inline_findings_posted(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        findings = [
            make_finding(file_path="src/a.py", line_number=1),
            make_finding(file_path="src/b.py", line_number=5),
            make_finding(file_path="src/c.py", line_number=10),
        ]
        poster.post_findings(findings, pr_number=1, commit_id="abc123")

        assert client.create_review_comment.call_count == 3

    def test_warning_severity_badge(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding(severity=ReviewSeverity.WARNING)
        body = poster._format_inline_comment(finding)
        assert "WARNING" in body

    def test_info_severity_badge(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding(severity=ReviewSeverity.INFO)
        body = poster._format_inline_comment(finding)
        assert "INFO" in body


# ---------------------------------------------------------------------------
# Findings without line_number -> top-level PR comment
# ---------------------------------------------------------------------------


class TestSummaryCommentPosting:
    def test_finding_without_line_posted_as_issue_comment(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        finding = make_finding(line_number=None)
        poster.post_findings([finding], pr_number=1, commit_id="abc123")

        client.create_issue_comment.assert_called_once()
        client.create_review_comment.assert_not_called()

    def test_summary_comment_contains_bot_marker(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        findings = [make_finding(line_number=None)]
        body = poster._format_summary_comment(findings)
        assert BOT_MARKER in body

    def test_summary_comment_grouped_by_file(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        findings = [
            make_finding(file_path="src/a.py", line_number=None),
            make_finding(file_path="src/b.py", line_number=None),
            make_finding(file_path="src/a.py", line_number=None),  # duplicate file
        ]
        body = poster._format_summary_comment(findings)
        # Both files should appear, src/a.py once (grouped)
        assert "src/a.py" in body
        assert "src/b.py" in body

    def test_mixed_findings_split_correctly(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        findings = [
            make_finding(line_number=10),  # inline
            make_finding(line_number=None),  # summary
            make_finding(line_number=20),  # inline
        ]
        poster.post_findings(findings, pr_number=1, commit_id="abc123")

        assert client.create_review_comment.call_count == 2
        assert client.create_issue_comment.call_count == 1

    def test_no_summary_comment_if_all_have_line_numbers(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        findings = [
            make_finding(line_number=1),
            make_finding(line_number=2),
        ]
        poster.post_findings(findings, pr_number=1, commit_id="abc123")

        client.create_issue_comment.assert_not_called()


# ---------------------------------------------------------------------------
# R2: Stale bot comments cleaned up
# ---------------------------------------------------------------------------


class TestBotCommentCleanup:
    def test_existing_bot_review_comments_deleted(self) -> None:
        client = make_mock_client()
        client.list_pr_review_comments.return_value = [
            {"id": 101, "body": f"some content\n{BOT_MARKER}\nmore content"},
            {"id": 102, "body": "not a bot comment"},  # should NOT be deleted
        ]
        poster = ReviewCommentPoster(client=client)

        poster.post_findings([], pr_number=1, commit_id="abc123")

        client.delete_review_comment.assert_called_once_with(101)

    def test_existing_bot_issue_comments_deleted(self) -> None:
        client = make_mock_client()
        client.list_pr_issue_comments.return_value = [
            {"id": 201, "body": f"{BOT_MARKER} old summary"},
            {"id": 202, "body": "human comment"},  # should NOT be deleted
        ]
        poster = ReviewCommentPoster(client=client)

        poster.post_findings([], pr_number=1, commit_id="abc123")

        client.delete_issue_comment.assert_called_once_with(201)

    def test_non_bot_comments_not_deleted(self) -> None:
        client = make_mock_client()
        client.list_pr_review_comments.return_value = [
            {"id": 100, "body": "Human wrote this"},
            {"id": 101, "body": "Another human comment"},
        ]
        poster = ReviewCommentPoster(client=client)

        poster.post_findings([], pr_number=1, commit_id="abc123")

        client.delete_review_comment.assert_not_called()

    def test_cleanup_runs_before_posting(self) -> None:
        """Verify cleanup happens before new comments are posted."""
        call_order: list[str] = []
        client = make_mock_client()

        client.list_pr_review_comments.return_value = [
            {"id": 99, "body": f"{BOT_MARKER}old"}
        ]

        def track_delete(*_args: object, **_kwargs: object) -> bool:
            call_order.append("delete")
            return True

        def track_create(*_args: object, **_kwargs: object) -> dict[str, int]:
            call_order.append("create")
            return {"id": 1}

        client.delete_review_comment.side_effect = track_delete
        client.create_review_comment.side_effect = track_create

        poster = ReviewCommentPoster(client=client)
        finding = make_finding(line_number=1)
        poster.post_findings([finding], pr_number=1, commit_id="abc123")

        assert call_order[0] == "delete"
        assert "create" in call_order


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_finding_ids_deduped(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        shared_id = uuid.uuid4()
        findings = [
            make_finding(finding_id=shared_id, line_number=1),
            make_finding(finding_id=shared_id, line_number=1),  # duplicate
        ]
        poster.post_findings(findings, pr_number=1, commit_id="abc123")

        # Only one comment should be posted
        assert client.create_review_comment.call_count == 1

    def test_different_finding_ids_all_posted(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        findings = [
            make_finding(finding_id=uuid.uuid4(), line_number=1),
            make_finding(finding_id=uuid.uuid4(), line_number=2),
            make_finding(finding_id=uuid.uuid4(), line_number=3),
        ]
        poster.post_findings(findings, pr_number=1, commit_id="abc123")

        assert client.create_review_comment.call_count == 3


# ---------------------------------------------------------------------------
# R3: Graceful degradation on API error
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_api_failure_does_not_raise(self) -> None:
        client = make_mock_client()
        client.list_pr_review_comments.side_effect = RuntimeError("API is down")

        poster = ReviewCommentPoster(client=client)
        finding = make_finding()

        # Should not raise
        poster.post_findings([finding], pr_number=1, commit_id="abc123")

    def test_create_failure_does_not_raise(self) -> None:
        client = make_mock_client()
        client.create_review_comment.side_effect = RuntimeError("API is down")

        poster = ReviewCommentPoster(client=client)
        finding = make_finding()

        # Should not raise
        poster.post_findings([finding], pr_number=1, commit_id="abc123")

    def test_empty_findings_posts_nothing(self) -> None:
        client = make_mock_client()
        poster = ReviewCommentPoster(client=client)

        poster.post_findings([], pr_number=1, commit_id="abc123")

        client.create_review_comment.assert_not_called()
        client.create_issue_comment.assert_not_called()
