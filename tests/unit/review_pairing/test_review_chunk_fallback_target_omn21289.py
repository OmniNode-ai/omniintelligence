# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Files-API fallback targets fit small review contexts (OMN-21289)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from omniintelligence.review_pairing import cli_review
from omniintelligence.review_pairing.adapters import adapter_ai_reviewer as adapter

pytestmark = [pytest.mark.unit]

_FILE_COUNT = 275
_CHUNK_BYTES = 9078
_PATCH = "@@ -1,40 +0,0 @@\n" + "".join(f"-line_{j} = value\n" for j in range(40))


def _block_header(index: int) -> str:
    return f"--- src/pkg/module_{index:03d}.py (removed, +0/-40) ---"


@pytest.fixture
def fallback_target(monkeypatch: pytest.MonkeyPatch) -> str:
    files = [
        {
            "filename": f"src/pkg/module_{i:03d}.py",
            "status": "removed",
            "additions": 0,
            "deletions": 40,
            "patch": _PATCH,
        }
        for i in range(_FILE_COUNT)
    ]

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert command[0] == "gh"
        return SimpleNamespace(stdout=json.dumps(files), stderr="", returncode=0)

    monkeypatch.setattr(cli_review.subprocess, "run", run)
    # Retain all 275 patch blocks; input truncation is outside this regression.
    monkeypatch.setattr(cli_review, "_MAX_FALLBACK_REVIEW_CHARS", 300_000)
    return cli_review._fetch_pr_files_fallback(1, "owner/repo", "test")


def test_a_275_file_fallback_target_chunks_for_a_32768_token_voter(
    fallback_target: str,
) -> None:
    chunks = adapter._review_chunks(fallback_target, _CHUNK_BYTES)

    assert chunks
    assert all(len(chunk.encode()) <= _CHUNK_BYTES for chunk in chunks)
    assert "".join(chunks) == fallback_target
    for i in range(_FILE_COUNT):
        assert sum(chunk.count(_block_header(i)) for chunk in chunks) == 1


def test_chunks_keep_each_file_block_whole(fallback_target: str) -> None:
    chunks = adapter._review_chunks(fallback_target, _CHUNK_BYTES)

    for i in range(_FILE_COUNT):
        [chunk] = [chunk for chunk in chunks if _block_header(i) in chunk]
        assert f"{_block_header(i)}\n{_PATCH.rstrip()}" in chunk


def _file_diff(name: str) -> str:
    return (
        f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
        "@@ -1 +1,12 @@\n-old\n" + "".join(f"+row_{i} = value\n" for i in range(12))
    )


def test_a_unified_diff_is_chunked_as_before() -> None:
    files = [_file_diff("first.py"), _file_diff("second.py")]
    content = "".join(files)
    budget = max(len(file.encode()) for file in files)

    assert len(content.encode()) > budget
    assert adapter._review_chunks(content, budget) == files
