# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Parity of HandlerGitRepoCrawl.handle(request) with the pre-class module function.

``EXPECTED`` was recorded by running ``handle_git_repo_crawl`` (omniintelligence@fa990e38),
the module function that ``HandlerGitRepoCrawl.handle`` replaced, through the same scenarios on
real git repositories. Commit SHAs and the repository path vary per run and are masked by name.
The class is resolved inside the test, so the pre-class tree collects the test and fails the
assertion instead of failing at import.

Ticket: OMN-21536
"""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from omniintelligence.nodes.node_git_repo_crawler_effect.models.model_crawl_input import (
    ModelGitRepoCrawlInput,
)
from omniintelligence.nodes.node_git_repo_crawler_effect.node_tests.conftest import (
    GitFixture,
    InMemoryCrawlStateStore,
)

pytestmark = pytest.mark.unit

_HANDLER_MODULE = "omniintelligence.nodes.node_git_repo_crawler_effect.handlers.handler_git_repo_crawl"
_CORRELATION_ID = "11111111-1111-1111-1111-111111111111"

Invoke = Callable[[ModelGitRepoCrawlInput, InMemoryCrawlStateStore], Awaitable[Any]]


def _mask(value: Any, names: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {k: _mask(v, names) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_mask(v, names) for v in value]
    if isinstance(value, str):
        return names.get(value, value)
    return value


async def _crawl(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> Any:
    return await invoke(
        ModelGitRepoCrawlInput(repo_path=repo.path, correlation_id=_CORRELATION_ID),
        state,
    )


async def _outcome(
    output: Any,
    repo: GitFixture,
    state: InMemoryCrawlStateStore,
    names: dict[str, str],
) -> dict[str, Any]:
    names = {**names, repo.path: "<repo>", _CORRELATION_ID: "<cid>"}
    entries = sorted(
        (e.file_path, e.source_version, e.content_fingerprint)
        for e in await state.get_all_entries(repo.path)
    )
    return _mask(
        {
            "head_sha": output.head_sha,
            "skipped": output.skipped,
            "discovered": [e.model_dump() for e in output.discovered],
            "changed": [e.model_dump() for e in output.changed],
            "removed": [e.model_dump() for e in output.removed],
            "error_files": sorted(output.errors),
            "stored_head": await state.get_head_sha(repo.path),
            "stored_entries": [list(e) for e in entries],
        },
        names,
    )


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def scenario_unchanged_head(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    repo.write("docs/page.md", "# Hello")
    head = repo.commit("add page")
    await state.update_head_sha(repo.path, head)
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, {head: "<head>"})


async def scenario_first_crawl(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    repo.write("docs/a.md", "# A")
    repo.write("docs/b.md", "# B")
    repo.write("src/code.py", "x = 1")
    head = repo.commit("initial")
    names = {
        head: "<head>",
        repo.file_commit_sha("docs/a.md"): "<commit>",
        _fingerprint("# A"): "<fp:a>",
        _fingerprint("# B"): "<fp:b>",
    }
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, names)


async def scenario_changed_file(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    repo.write("docs/a.md", "# A")
    repo.write("docs/b.md", "# B")
    first = repo.commit("initial")
    await _crawl(invoke, repo, state)
    repo.write("docs/a.md", "# A v2")
    second = repo.commit("update a")
    names = {
        first: "<head:1>",
        second: "<head:2>",
        repo.file_commit_sha("docs/a.md"): "<commit:a2>",
        repo.file_commit_sha("docs/b.md"): "<commit:b1>",
        _fingerprint("# A v2"): "<fp:a2>",
        _fingerprint("# B"): "<fp:b>",
    }
    # the first commit introduced a.md at <head:1>; the update moved its commit to <head:2>
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, names)


async def scenario_removed_file(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    repo.write("docs/a.md", "# A")
    repo.write("docs/b.md", "# B")
    first = repo.commit("initial")
    await _crawl(invoke, repo, state)
    repo.delete("docs/b.md")
    second = repo.commit("remove b")
    names = {
        first: "<head:1>",
        second: "<head:2>",
        _fingerprint("# A"): "<fp:a>",
        _fingerprint("# B"): "<fp:b>",
    }
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, names)


async def scenario_stale_stored_head(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    repo.write("docs/a.md", "# A")
    head = repo.commit("initial")
    await state.update_head_sha(repo.path, "0" * 40)
    names = {
        head: "<head>",
        "0" * 40: "<stale>",
        repo.file_commit_sha("docs/a.md"): "<commit>",
        _fingerprint("# A"): "<fp:a>",
    }
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, names)


async def scenario_unreadable_tracked_file(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    repo.write("docs/a.md", "# A")
    repo.write("docs/b.md", "# B")
    head = repo.commit("initial")
    repo.delete("docs/b.md")  # still tracked by the index, gone from disk
    names = {
        head: "<head>",
        repo.file_commit_sha("docs/a.md"): "<commit>",
        _fingerprint("# A"): "<fp:a>",
    }
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, names)


async def scenario_not_a_git_repo(
    invoke: Invoke, repo: GitFixture, state: InMemoryCrawlStateStore
) -> dict[str, Any]:
    out = await _crawl(invoke, repo, state)
    return await _outcome(out, repo, state, {})


SCENARIOS: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
    "unchanged_head": scenario_unchanged_head,
    "first_crawl": scenario_first_crawl,
    "changed_file": scenario_changed_file,
    "removed_file": scenario_removed_file,
    "stale_stored_head": scenario_stale_stored_head,
    "unreadable_tracked_file": scenario_unreadable_tracked_file,
    "not_a_git_repo": scenario_not_a_git_repo,
}

EXPECTED: dict[str, dict[str, Any]] = {
    "changed_file": {
        "changed": [
            {
                "content_fingerprint": "<fp:a2>",
                "correlation_id": "<cid>",
                "event_type": "document.changed.v1",
                "file_path": "docs/a.md",
                "previous_source_version": "<commit:b1>",
                "repo_path": "<repo>",
                "source_version": "<commit:a2>",
            }
        ],
        "discovered": [],
        "error_files": [],
        "head_sha": "<commit:a2>",
        "removed": [],
        "skipped": False,
        "stored_entries": [
            ["docs/a.md", "<commit:a2>", "<fp:a2>"],
            ["docs/b.md", "<commit:b1>", "<fp:b>"],
        ],
        "stored_head": "<commit:a2>",
    },
    "first_crawl": {
        "changed": [],
        "discovered": [
            {
                "content_fingerprint": "<fp:a>",
                "correlation_id": "<cid>",
                "event_type": "document.discovered.v1",
                "file_path": "docs/a.md",
                "repo_path": "<repo>",
                "source_version": "<commit>",
            },
            {
                "content_fingerprint": "<fp:b>",
                "correlation_id": "<cid>",
                "event_type": "document.discovered.v1",
                "file_path": "docs/b.md",
                "repo_path": "<repo>",
                "source_version": "<commit>",
            },
        ],
        "error_files": [],
        "head_sha": "<commit>",
        "removed": [],
        "skipped": False,
        "stored_entries": [
            ["docs/a.md", "<commit>", "<fp:a>"],
            ["docs/b.md", "<commit>", "<fp:b>"],
        ],
        "stored_head": "<commit>",
    },
    "not_a_git_repo": {
        "changed": [],
        "discovered": [],
        "error_files": [""],
        "head_sha": "",
        "removed": [],
        "skipped": False,
        "stored_entries": [],
        "stored_head": None,
    },
    "removed_file": {
        "changed": [],
        "discovered": [],
        "error_files": [],
        "head_sha": "<head:2>",
        "removed": [
            {
                "correlation_id": "<cid>",
                "event_type": "document.removed.v1",
                "file_path": "docs/b.md",
                "last_source_version": "<head:1>",
                "repo_path": "<repo>",
            }
        ],
        "skipped": False,
        "stored_entries": [["docs/a.md", "<head:1>", "<fp:a>"]],
        "stored_head": "<head:2>",
    },
    "stale_stored_head": {
        "changed": [],
        "discovered": [
            {
                "content_fingerprint": "<fp:a>",
                "correlation_id": "<cid>",
                "event_type": "document.discovered.v1",
                "file_path": "docs/a.md",
                "repo_path": "<repo>",
                "source_version": "<commit>",
            }
        ],
        "error_files": [],
        "head_sha": "<commit>",
        "removed": [],
        "skipped": False,
        "stored_entries": [["docs/a.md", "<commit>", "<fp:a>"]],
        "stored_head": "<commit>",
    },
    "unchanged_head": {
        "changed": [],
        "discovered": [],
        "error_files": [],
        "head_sha": "<head>",
        "removed": [],
        "skipped": True,
        "stored_entries": [],
        "stored_head": "<head>",
    },
    "unreadable_tracked_file": {
        "changed": [],
        "discovered": [
            {
                "content_fingerprint": "<fp:a>",
                "correlation_id": "<cid>",
                "event_type": "document.discovered.v1",
                "file_path": "docs/a.md",
                "repo_path": "<repo>",
                "source_version": "<commit>",
            }
        ],
        "error_files": ["docs/b.md"],
        "head_sha": "<commit>",
        "removed": [],
        "skipped": False,
        "stored_entries": [["docs/a.md", "<commit>", "<fp:a>"]],
        "stored_head": "<commit>",
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", sorted(SCENARIOS))
async def test_canonical_handle_matches_preserved_function(
    case: str, git_repo: GitFixture, crawl_state: InMemoryCrawlStateStore
) -> None:
    handler_class = getattr(
        importlib.import_module(_HANDLER_MODULE), "HandlerGitRepoCrawl", None
    )
    assert handler_class is not None, "canonical handle(request) class is required"

    async def invoke(
        request: ModelGitRepoCrawlInput, state: InMemoryCrawlStateStore
    ) -> Any:
        return await handler_class(crawl_state=state).handle(request)

    assert await SCENARIOS[case](invoke, git_repo, crawl_state) == EXPECTED[case]
