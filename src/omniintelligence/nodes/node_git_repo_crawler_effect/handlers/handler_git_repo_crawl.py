# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Handler for GitRepoCrawlerEffect — git-based change detection.

Algorithm (from OMN-2387 design doc §5):

  1. Read HEAD SHA for the repo root.
     If unchanged vs stored head_sha: skip entire repo (O(1) fast-path).
  2. If HEAD changed:
     - Run: git diff --name-only <old_sha>..<new_sha>
     - Filter to *.md files only.
  3. Per changed file:
     - git log -1 --format=%H -- <path>  (file-level SHA, not HEAD)
     - Compute SHA-256(content).
     - If hash differs from stored content_fingerprint: emit document.changed.v1.
  4. Files not in walk result but in crawl_state: emit document.removed.v1.
  5. Files in git repo not in crawl_state: emit document.discovered.v1.

``source_version`` tracks the file-level commit SHA (not HEAD), so a file
that hasn't changed in 20 commits will not re-emit after HEAD advances.

Ticket: OMN-2387
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.protocol_crawl_state import (
        ProtocolCrawlStateStore,
    )

from omniintelligence.nodes.node_git_repo_crawler_effect.handlers.protocol_crawl_state import (
    ModelCrawlStateEntry,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.models.model_crawl_input import (
    ModelGitRepoCrawlInput,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.models.model_crawl_output import (
    ModelDocumentChangedEvent,
    ModelDocumentDiscoveredEvent,
    ModelDocumentRemovedEvent,
    ModelGitRepoCrawlOutput,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal git helpers (thin subprocess wrappers)
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout as a stripped string.

    Raises:
        RuntimeError: If the subprocess exits with a non-zero return code.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _get_head_sha(repo_path: str) -> str:
    """Return the current HEAD commit SHA."""
    return _run_git(["rev-parse", "HEAD"], cwd=repo_path)


def _get_changed_md_files(repo_path: str, old_sha: str, new_sha: str) -> list[str]:
    """Return list of .md paths changed between old_sha and new_sha.

    Uses ``git diff --name-only --diff-filter=d`` to list files that were
    added, modified, or renamed (excludes deleted files — those are detected
    separately via crawl_state).
    """
    output = _run_git(
        ["diff", "--name-only", "--diff-filter=d", f"{old_sha}..{new_sha}"],
        cwd=repo_path,
    )
    if not output:
        return []
    return [p for p in output.splitlines() if p.endswith(".md")]


def _get_all_md_files(repo_path: str) -> list[str]:
    """Return all .md files tracked by git in the repository.

    Uses ``git ls-files`` for correctness: this only returns committed files,
    matching what the crawler should track.
    """
    output = _run_git(["ls-files", "*.md", "**/*.md"], cwd=repo_path)
    if not output:
        return []
    return [p for p in output.splitlines() if p]


def _get_file_commit_sha(repo_path: str, file_path: str) -> str:
    """Return the SHA of the most recent commit that modified file_path.

    This is the *file-level* SHA, not HEAD.  A file unchanged in 20 commits
    will return the same SHA regardless of how many times HEAD has advanced.
    """
    return _run_git(["log", "-1", "--format=%H", "--", file_path], cwd=repo_path)


def _sha256_of_file(repo_path: str, file_path: str) -> str:
    """Return the SHA-256 hex digest of the current on-disk content."""
    full_path = Path(repo_path) / file_path
    # io-audit: ignore-next-line file-io
    return hashlib.sha256(full_path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


async def handle_git_repo_crawl(
    input_data: ModelGitRepoCrawlInput,
    *,
    crawl_state: ProtocolCrawlStateStore,
) -> ModelGitRepoCrawlOutput:
    """Perform git-based change detection for a single repository.

    Steps:
        1. Read HEAD SHA. If unchanged (fast-path), return skipped=True.
        2. Determine the set of .md files changed between old and new HEAD.
        3. For each changed .md file:
           - Compute file-level SHA and content fingerprint.
           - If not in crawl_state → emit ``discovered``.
           - If content_fingerprint differs → emit ``changed``.
           - Update crawl_state entry.
        4. Walk all .md files in the repo to find newly committed files
           that were not in the diff (initial crawl / first-time files).
        5. Emit ``removed`` for entries in crawl_state not in the git tree.
        6. Persist updated HEAD SHA to crawl_state.

    Args:
        input_data: Crawl request with repo_path and trigger metadata.
        crawl_state: Persistence interface for omnimemory_crawl_state.

    Returns:
        ModelGitRepoCrawlOutput with discovered/changed/removed lists
        and a ``skipped`` flag when the HEAD was unchanged.
    """
    repo_path = input_data.repo_path
    correlation_id = input_data.correlation_id

    # ------------------------------------------------------------------
    # Step 1 — HEAD SHA fast-path
    # ------------------------------------------------------------------
    try:
        new_head_sha = _get_head_sha(repo_path)
    except RuntimeError as exc:
        logger.error(
            "git rev-parse HEAD failed for %s: %s",
            repo_path,
            exc,
        )
        return ModelGitRepoCrawlOutput(
            repo_path=repo_path,
            head_sha="",
            errors={"": str(exc)},
        )

    stored_head_sha = await crawl_state.get_head_sha(repo_path)

    if stored_head_sha is not None and stored_head_sha == new_head_sha:
        logger.debug(
            "Skipping repo %s — HEAD unchanged (%s)",
            repo_path,
            new_head_sha[:12],
        )
        return ModelGitRepoCrawlOutput(
            repo_path=repo_path,
            head_sha=new_head_sha,
            skipped=True,
        )

    # ------------------------------------------------------------------
    # Step 2 — determine candidate files to inspect
    # ------------------------------------------------------------------
    # When we have a previous HEAD we diff; otherwise we fall through
    # to inspecting all files (first-time crawl).
    candidate_files: set[str] = set()

    if stored_head_sha is not None:
        try:
            diff_files = _get_changed_md_files(repo_path, stored_head_sha, new_head_sha)
            candidate_files.update(diff_files)
        except RuntimeError as exc:
            logger.warning(
                "git diff failed for %s (%s..%s): %s — falling back to full scan",
                repo_path,
                stored_head_sha[:12],
                new_head_sha[:12],
                exc,
            )
            # Fall through to full scan below

    # Always walk the full file set to catch:
    # (a) the first crawl (no stored_head_sha)
    # (b) partial diff fallback
    # (c) newly committed files not appearing in the diff
    try:
        all_git_files = set(_get_all_md_files(repo_path))
    except RuntimeError as exc:
        logger.error("git ls-files failed for %s: %s", repo_path, exc)
        return ModelGitRepoCrawlOutput(
            repo_path=repo_path,
            head_sha=new_head_sha,
            errors={"": str(exc)},
        )

    # The union ensures we process every file that could have changed.
    candidate_files.update(all_git_files)

    # ------------------------------------------------------------------
    # Step 3 — process candidate files
    # ------------------------------------------------------------------
    existing_entries: dict[str, ModelCrawlStateEntry] = {
        entry.file_path: entry for entry in await crawl_state.get_all_entries(repo_path)
    }

    discovered: list[ModelDocumentDiscoveredEvent] = []
    changed: list[ModelDocumentChangedEvent] = []
    errors: dict[str, str] = {}

    for file_path in sorted(candidate_files):
        try:
            file_commit_sha = _get_file_commit_sha(repo_path, file_path)
            content_fingerprint = _sha256_of_file(repo_path, file_path)
        except (RuntimeError, OSError) as exc:
            errors[file_path] = str(exc)
            logger.warning("Error processing %s in %s: %s", file_path, repo_path, exc)
            continue

        existing = existing_entries.get(file_path)

        if existing is None:
            # New file — emit discovered
            discovered.append(
                ModelDocumentDiscoveredEvent(
                    repo_path=repo_path,
                    file_path=file_path,
                    source_version=file_commit_sha,
                    content_fingerprint=content_fingerprint,
                    correlation_id=correlation_id,
                )
            )
            await crawl_state.upsert_entry(
                ModelCrawlStateEntry(
                    repo_path=repo_path,
                    file_path=file_path,
                    source_version=file_commit_sha,
                    content_fingerprint=content_fingerprint,
                    head_sha=new_head_sha,
                )
            )
        elif content_fingerprint != existing.content_fingerprint:
            # Content changed — emit changed
            changed.append(
                ModelDocumentChangedEvent(
                    repo_path=repo_path,
                    file_path=file_path,
                    source_version=file_commit_sha,
                    previous_source_version=existing.source_version,
                    content_fingerprint=content_fingerprint,
                    correlation_id=correlation_id,
                )
            )
            await crawl_state.upsert_entry(
                ModelCrawlStateEntry(
                    repo_path=repo_path,
                    file_path=file_path,
                    source_version=file_commit_sha,
                    content_fingerprint=content_fingerprint,
                    head_sha=new_head_sha,
                )
            )
        # else: file unchanged — no event, no state update needed

    # ------------------------------------------------------------------
    # Step 4 — detect removed files
    # ------------------------------------------------------------------
    removed: list[ModelDocumentRemovedEvent] = []

    for file_path, entry in existing_entries.items():
        if file_path not in all_git_files:
            removed.append(
                ModelDocumentRemovedEvent(
                    repo_path=repo_path,
                    file_path=file_path,
                    last_source_version=entry.source_version,
                    correlation_id=correlation_id,
                )
            )
            await crawl_state.delete_entry(repo_path, file_path)

    # ------------------------------------------------------------------
    # Step 5 — persist new HEAD SHA
    # ------------------------------------------------------------------
    await crawl_state.update_head_sha(repo_path, new_head_sha)

    logger.info(
        "Crawl complete for %s: discovered=%d changed=%d removed=%d errors=%d "
        "(head=%s)",
        repo_path,
        len(discovered),
        len(changed),
        len(removed),
        len(errors),
        new_head_sha[:12],
    )

    return ModelGitRepoCrawlOutput(
        repo_path=repo_path,
        head_sha=new_head_sha,
        discovered=discovered,
        changed=changed,
        removed=removed,
        errors=errors,
    )


__all__ = ["handle_git_repo_crawl"]
