"""Thin GitHub REST API wrapper for the Code Intelligence Review Bot.

Provides a minimal interface for PR review comment operations.
All API failures are caught and logged — they never raise to callers.

OMN-2497: Implement inline GitHub PR comment posting.
"""

from __future__ import annotations

import sys
from typing import Any

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_BOT_MARKER = "<!-- omni-review-bot -->"
_DEFAULT_GITHUB_API = "https://api.github.com"


class GitHubClient:
    """Thin GitHub REST API client for PR review comments.

    All methods are fail-open: API errors are logged to stderr and
    the method returns an empty result rather than raising.

    Args:
        token: GitHub personal access token or GITHUB_TOKEN.
        repo: Repository in "owner/repo" format.
        base_url: GitHub API base URL (override for GitHub Enterprise).
    """

    def __init__(
        self,
        token: str,
        repo: str,
        base_url: str = _DEFAULT_GITHUB_API,
    ) -> None:
        self._token = token
        self._repo = repo
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Make a paginated GET request, returning all results.

        Args:
            path: API path (e.g., "/repos/owner/repo/pulls/1/reviews").
            params: Optional query parameters.

        Returns:
            List of response items, empty list on error.
        """
        if not _HTTPX_AVAILABLE:
            print(
                "WARNING: httpx not available; GitHub API calls skipped.",
                file=sys.stderr,
            )
            return []

        results: list[dict[str, Any]] = []
        url = f"{self._base_url}{path}"
        page_params = dict(params or {})
        page_params.setdefault("per_page", 100)

        try:
            with httpx.Client(timeout=10.0) as client:
                while url:
                    resp = client.get(url, headers=self._headers(), params=page_params)
                    if resp.status_code != 200:
                        print(
                            f"WARNING: GitHub API GET {url} returned {resp.status_code}",
                            file=sys.stderr,
                        )
                        break
                    data = resp.json()
                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict):
                        results.append(data)
                    # Handle pagination
                    url = resp.links.get("next", {}).get("url", "")
                    page_params = {}  # Next URL already has params
        except Exception as exc:
            print(f"WARNING: GitHub API error: {exc}", file=sys.stderr)

        return results

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
        """Make a POST request.

        Args:
            path: API path.
            body: JSON request body.

        Returns:
            Response dict, or None on error.
        """
        if not _HTTPX_AVAILABLE:
            print(
                "WARNING: httpx not available; GitHub API calls skipped.",
                file=sys.stderr,
            )
            return None

        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, headers=self._headers(), json=body)
                if resp.status_code not in (200, 201):
                    print(
                        f"WARNING: GitHub API POST {url} returned {resp.status_code}: "
                        f"{resp.text[:200]}",
                        file=sys.stderr,
                    )
                    return None
                return resp.json()  # type: ignore[no-any-return]
        except Exception as exc:
            print(f"WARNING: GitHub API error: {exc}", file=sys.stderr)
            return None

    def _delete(self, path: str) -> bool:
        """Make a DELETE request.

        Args:
            path: API path.

        Returns:
            True if successful.
        """
        if not _HTTPX_AVAILABLE:
            return False

        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.delete(url, headers=self._headers())
                return resp.status_code in (200, 204)
        except Exception as exc:
            print(f"WARNING: GitHub API error: {exc}", file=sys.stderr)
            return False

    def list_pr_review_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """List all review comments on a PR.

        Args:
            pr_number: PR number.

        Returns:
            List of review comment objects.
        """
        return self._get(f"/repos/{self._repo}/pulls/{pr_number}/comments")

    def list_pr_issue_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """List all issue (top-level) comments on a PR.

        Args:
            pr_number: PR number.

        Returns:
            List of issue comment objects.
        """
        return self._get(f"/repos/{self._repo}/issues/{pr_number}/comments")

    def delete_review_comment(self, comment_id: int) -> bool:
        """Delete a PR review comment.

        Args:
            comment_id: Comment ID to delete.

        Returns:
            True if deleted successfully.
        """
        return self._delete(f"/repos/{self._repo}/pulls/comments/{comment_id}")

    def delete_issue_comment(self, comment_id: int) -> bool:
        """Delete an issue (top-level) comment.

        Args:
            comment_id: Comment ID to delete.

        Returns:
            True if deleted successfully.
        """
        return self._delete(f"/repos/{self._repo}/issues/comments/{comment_id}")

    def create_review_comment(
        self,
        pr_number: int,
        commit_id: str,
        path: str,
        line: int,
        body: str,
    ) -> dict[str, Any] | None:
        """Create an inline review comment on a specific file/line.

        Args:
            pr_number: PR number.
            commit_id: The SHA of the commit to comment on.
            path: The relative path to the file.
            line: The line number in the file to comment on.
            body: Comment body text (markdown).

        Returns:
            Created comment object, or None on error.
        """
        return self._post(
            f"/repos/{self._repo}/pulls/{pr_number}/comments",
            {
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "body": body,
                "side": "RIGHT",
            },
        )

    def create_issue_comment(self, pr_number: int, body: str) -> dict[str, Any] | None:
        """Create a top-level PR/issue comment.

        Args:
            pr_number: PR number.
            body: Comment body text (markdown).

        Returns:
            Created comment object, or None on error.
        """
        return self._post(
            f"/repos/{self._repo}/issues/{pr_number}/comments",
            {"body": body},
        )


__all__ = ["BOT_MARKER", "GitHubClient"]
BOT_MARKER = _BOT_MARKER
