# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Thin GitHub REST API wrapper for the Code Intelligence Review Bot.

Provides a minimal interface for PR review comment operations.
All API failures are caught and logged — they never raise to callers.

Uses stdlib urllib.request for HTTP to comply with ARCH-002 (no transport
library imports in src/omniintelligence/).

OMN-2497: Implement inline GitHub PR comment posting.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_BOT_MARKER = "<!-- omni-review-bot -->"
_DEFAULT_GITHUB_API = "https://api.github.com"


class GitHubClient:
    """Thin GitHub REST API client for PR review comments.

    All methods are fail-open: API errors are logged to stderr and
    the method returns an empty result rather than raising.

    Uses stdlib urllib.request for HTTP (ARCH-002 compliant — no httpx).

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
        results: list[dict[str, Any]] = []
        base_params: dict[str, Any] = dict(params or {})
        base_params.setdefault("per_page", 100)

        url: str | None = (
            f"{self._base_url}{path}?{urllib.parse.urlencode(base_params)}"
        )

        try:
            while url:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status != 200:
                        print(
                            f"WARNING: GitHub API GET {url} returned {resp.status}",
                            file=sys.stderr,
                        )
                        break
                    body = resp.read().decode("utf-8")
                    data = json.loads(body)
                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict):
                        results.append(data)

                    # Handle Link header for pagination
                    link_header = resp.headers.get("Link", "")
                    url = _parse_next_link(link_header)
        except urllib.error.HTTPError as exc:
            print(f"WARNING: GitHub API HTTP error: {exc}", file=sys.stderr)
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
        url = f"{self._base_url}{path}"
        try:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={**self._headers(), "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status not in (200, 201):
                    body_text = resp.read().decode("utf-8")[:200]
                    print(
                        f"WARNING: GitHub API POST {url} returned {resp.status}: "
                        f"{body_text}",
                        file=sys.stderr,
                    )
                    return None
                return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]
        except urllib.error.HTTPError as exc:
            print(f"WARNING: GitHub API HTTP error: {exc}", file=sys.stderr)
            return None
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
        url = f"{self._base_url}{path}"
        try:
            req = urllib.request.Request(
                url,
                headers=self._headers(),
                method="DELETE",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except urllib.error.HTTPError as exc:
            print(f"WARNING: GitHub API HTTP error: {exc}", file=sys.stderr)
            return False
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


def _parse_next_link(link_header: str) -> str | None:
    """Parse the 'next' URL from a GitHub Link header.

    Args:
        link_header: Value of the Link response header.

    Returns:
        The next page URL, or None if not present.
    """
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            url_part = part.split(";")[0].strip()
            return url_part.strip("<>")
    return None


__all__ = ["BOT_MARKER", "GitHubClient"]
BOT_MARKER = _BOT_MARKER
