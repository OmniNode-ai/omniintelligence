# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Wrapper parity for the document fetch handler (OMN-2389 / OMN-23422).

``HandlerDocumentFetch.handle`` must return exactly what the preserved
``handle_document_fetch`` function returns for the same request and the same
blob store, and must call the blob store identically.

Disk paths in the requests are relative; the test runs inside a temporary
working directory that holds the fixture files and a small real git repository.
"""

import importlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from omniintelligence.nodes.node_document_fetch_effect.handlers.handler_document_fetch import (
    handle_document_fetch,
)
from omniintelligence.nodes.node_document_fetch_effect.models.model_document_fetch_input import (
    ModelDocumentFetchInput,
)

MODULE = (
    "omniintelligence.nodes.node_document_fetch_effect.handlers.handler_document_fetch"
)
CLASS_NAME = "HandlerDocumentFetch"
SCOPE = "omninode/test"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@test.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@test.com",
    "HOME": "/tmp",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


class _RecordingBlobStore:
    """In-memory blob store that records lookups and can raise on demand."""

    def __init__(
        self,
        content: dict[str, str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._content = content or {}
        self._error = error
        self.calls: list[str] = []

    async def get(self, source_ref: str) -> str:
        self.calls.append(source_ref)
        if self._error is not None:
            raise self._error
        return self._content[source_ref]


def _populate(root: Path) -> None:
    """Create the fixture files and the git repositories under ``root``."""
    (root / "docs").mkdir()
    (root / "docs" / "note.md").write_text("# Hello World", encoding="utf-8")

    def git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, env=_GIT_ENV, check=True
        )

    repo = root / "repo"
    (repo / "docs").mkdir(parents=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@test.com")
    git(repo, "config", "user.name", "Test")
    (repo / "docs" / "tracked.md").write_text("# Tracked", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "test")
    (repo / "docs" / "untracked.md").write_text("# Untracked", encoding="utf-8")

    (root / "norepo" / "docs").mkdir(parents=True)
    (root / "norepo" / "docs" / "plain.md").write_text("# Plain", encoding="utf-8")


def _request(**fields: Any) -> Callable[[], ModelDocumentFetchInput]:
    def build() -> ModelDocumentFetchInput:
        return ModelDocumentFetchInput(crawl_scope=SCOPE, **fields)

    return build


def _unknown_crawler_request() -> ModelDocumentFetchInput:
    return ModelDocumentFetchInput.model_construct(
        source_ref="docs/note.md",
        crawler_type="rss",
        repo_path=None,
        crawl_scope=SCOPE,
        event_type="document.discovered.v1",
        correlation_id="corr-unknown",
    )


def _no_deps() -> dict[str, Any]:
    return {}


def _blob_deps(
    content: dict[str, str] | None = None, error: Exception | None = None
) -> Callable[[], dict[str, Any]]:
    return lambda: {"blob_store": _RecordingBlobStore(content, error)}


PARITY_CASES: list[
    tuple[
        str,
        str,
        Callable[[], ModelDocumentFetchInput],
        Callable[[], dict[str, Any]],
    ]
] = [
    (
        "filesystem-success",
        CLASS_NAME,
        _request(source_ref="docs/note.md", crawler_type="filesystem"),
        _no_deps,
    ),
    (
        "filesystem-not-found-removed-event",
        CLASS_NAME,
        _request(
            source_ref="docs/missing.md",
            crawler_type="filesystem",
            correlation_id="corr-1",
        ),
        _no_deps,
    ),
    (
        "watchdog-success-changed-event",
        CLASS_NAME,
        _request(
            source_ref="docs/note.md",
            crawler_type="watchdog",
            event_type="document.changed.v1",
            correlation_id="corr-2",
        ),
        _no_deps,
    ),
    (
        "filesystem-directory-raises",
        CLASS_NAME,
        _request(source_ref="docs", crawler_type="filesystem"),
        _no_deps,
    ),
    (
        "git-success-with-sha",
        CLASS_NAME,
        _request(
            source_ref="docs/tracked.md", crawler_type="git_repo", repo_path="repo"
        ),
        _no_deps,
    ),
    (
        "git-untracked-sha-unavailable",
        CLASS_NAME,
        _request(
            source_ref="docs/untracked.md", crawler_type="git_repo", repo_path="repo"
        ),
        _no_deps,
    ),
    (
        "git-not-a-repository-sha-unavailable",
        CLASS_NAME,
        _request(
            source_ref="docs/plain.md", crawler_type="git_repo", repo_path="norepo"
        ),
        _no_deps,
    ),
    (
        "git-file-not-found-removed-event",
        CLASS_NAME,
        _request(
            source_ref="docs/gone.md",
            crawler_type="git_repo",
            repo_path="repo",
            correlation_id="corr-3",
        ),
        _no_deps,
    ),
    (
        "git-missing-repo-path",
        CLASS_NAME,
        _request(source_ref="docs/tracked.md", crawler_type="git_repo"),
        _no_deps,
    ),
    (
        "linear-success",
        CLASS_NAME,
        _request(source_ref="OMN-1234", crawler_type="linear"),
        _blob_deps({"OMN-1234": "# Linear issue"}),
    ),
    (
        "linear-key-error",
        CLASS_NAME,
        _request(source_ref="OMN-9999", crawler_type="linear"),
        _blob_deps({"OMN-1234": "# Linear issue"}),
    ),
    (
        "linear-runtime-error",
        CLASS_NAME,
        _request(source_ref="OMN-1234", crawler_type="linear", correlation_id="corr-4"),
        _blob_deps(error=RuntimeError("blob store unavailable")),
    ),
    (
        "linear-unexpected-error-propagates",
        CLASS_NAME,
        _request(source_ref="OMN-1234", crawler_type="linear"),
        _blob_deps(error=ValueError("corrupt blob")),
    ),
    (
        "linear-without-blob-store",
        CLASS_NAME,
        _request(source_ref="OMN-1234", crawler_type="linear"),
        _no_deps,
    ),
    (
        "unknown-crawler-type",
        CLASS_NAME,
        _unknown_crawler_request,
        _no_deps,
    ),
]


def corpus_inputs() -> list[dict[str, Any]]:
    """Return the JSON-describable request of every parity case, in order."""
    return [
        {
            "case": case_id,
            "wrapper": class_name,
            "request": json.loads(
                json.dumps(request_builder().model_dump(mode="json"), default=str)
            ),
        }
        for case_id, class_name, request_builder, _ in PARITY_CASES
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("case_id", "class_name", "request_builder", "deps_builder"),
    PARITY_CASES,
    ids=[case[0] for case in PARITY_CASES],
)
async def test_wrapper_matches_preserved_function(
    case_id: str,
    class_name: str,
    request_builder: Callable[[], ModelDocumentFetchInput],
    deps_builder: Callable[[], dict[str, Any]],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapper and preserved function return/raise alike with the same blob calls."""
    wrapper_cls = getattr(importlib.import_module(MODULE), class_name, None)
    assert wrapper_cls is not None, "contract-bound handler class is required"

    _populate(tmp_path)
    monkeypatch.chdir(tmp_path)

    request_a, request_b = request_builder(), request_builder()
    deps_a, deps_b = deps_builder(), deps_builder()

    wrapper_error: Exception | None = None
    function_error: Exception | None = None
    wrapper_result = None
    function_result = None
    try:
        wrapper_result = await wrapper_cls(**deps_a).handle(request_a)
    except Exception as exc:
        wrapper_error = exc
    try:
        function_result = await handle_document_fetch(request_b, **deps_b)
    except Exception as exc:
        function_error = exc

    if function_error is not None:
        assert wrapper_error is not None
        assert type(wrapper_error) is type(function_error)
        assert str(wrapper_error) == str(function_error)
    else:
        assert wrapper_error is None
        assert wrapper_result == function_result
    blob_a, blob_b = deps_a.get("blob_store"), deps_b.get("blob_store")
    assert (blob_a.calls if blob_a else None) == (blob_b.calls if blob_b else None)
