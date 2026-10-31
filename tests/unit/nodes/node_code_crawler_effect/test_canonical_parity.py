# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Parity of the canonical HandlerCrawlFiles.handle(request) with the pre-class walk.

``EXPECTED`` was recorded by running the module function ``crawl_files`` that
``HandlerCrawlFiles.handle`` replaced (omniintelligence@fa990e38) over the same file
trees. Only the random per-event id and the event timestamp are masked, and a generated crawl id is masked to
its pattern. The class is resolved inside the test, so the pre-class tree collects the
test and fails the assertion instead of failing at import.
"""

from __future__ import annotations

import hashlib
import importlib
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_HANDLER_MODULE = (
    "omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files"
)
_REQUEST_MODULE = (
    "omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_files_request"
)
_ROOT_ENV = "ONEX_PARITY_ROOT"
_GENERATED_CRAWL_ID = re.compile(r"^crawl_[0-9a-f]{12}$")

TREE: dict[str, bytes] = {
    "alpha/src/main.py": b"print('hello')\n",
    "alpha/src/utils.py": b"def helper():\n    return 1\n",
    "alpha/src/nested/deep.py": b"x = 1\n",
    "alpha/src/readme.txt": b"not python\n",
    "alpha/src/__pycache__/main.cpython-312.pyc": b"bytecode",
    "alpha/src/skipme/hidden.py": b"y = 2\n",
    "alpha/src/binary.py": b"\xff\xfe\x00bad utf-8",
    "beta/lib/tool.ts": b"export const t = 1;\n",
}

REPO_ALPHA: dict[str, Any] = {
    "name": "alpha",
    "path": f"${{{_ROOT_ENV}}}/alpha",
    "include": ["src/**/*.py"],
    "exclude": ["**/__pycache__/**", "src/skipme/*"],
}
REPO_BETA: dict[str, Any] = {
    "name": "beta",
    "path": f"${{{_ROOT_ENV}}}/beta",
    "include": ["lib/**/*.ts"],
    "exclude": [],
}

CASES: dict[str, dict[str, Any]] = {
    "include_exclude": {"repos": [REPO_ALPHA], "crawl_id": "crawl-fixed"},
    "two_repos": {"repos": [REPO_ALPHA, REPO_BETA], "crawl_id": "crawl-fixed"},
    "repo_filter": {
        "repos": [REPO_ALPHA, REPO_BETA],
        "crawl_id": "crawl-fixed",
        "repo_filter": "beta",
    },
    "disabled_repo": {
        "repos": [{**REPO_ALPHA, "enabled": False}, REPO_BETA],
        "crawl_id": "crawl-fixed",
    },
    "missing_path": {
        "repos": [
            {
                "name": "gone",
                "path": f"${{{_ROOT_ENV}}}/does-not-exist",
                "include": ["src/**/*.py"],
                "exclude": [],
            }
        ],
        "crawl_id": "crawl-fixed",
    },
    "generated_crawl_id": {"repos": [REPO_BETA]},
}


def write_tree(root: Path) -> None:
    for relative, content in TREE.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def normalise(events: Iterable[Any]) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        row = event.model_dump(mode="json")
        row.pop("event_id")
        row.pop("timestamp")
        assert (
            row["file_hash"]
            == hashlib.sha256(row["source_content"].encode()).hexdigest()
        )
        row["file_hash"] = "<sha256(source_content)>"
        if _GENERATED_CRAWL_ID.match(row["crawl_id"]):
            row["crawl_id"] = "<generated>"
        rows.append(row)
    return sorted(rows, key=lambda r: (r["repo_name"], r["file_path"]))


def run_case(
    case: str, root: Path, invoke: Callable[[dict[str, Any]], Iterable[Any]]
) -> list[dict[str, Any]]:
    write_tree(root)
    return normalise(invoke(CASES[case]))


EXPECTED: dict[str, list[dict[str, Any]]] = {
    "disabled_repo": [
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".ts",
            "file_hash": "<sha256(source_content)>",
            "file_path": "lib/tool.ts",
            "repo_name": "beta",
            "source_content": "export const t = 1;\n",
        }
    ],
    "generated_crawl_id": [
        {
            "crawl_id": "<generated>",
            "file_extension": ".ts",
            "file_hash": "<sha256(source_content)>",
            "file_path": "lib/tool.ts",
            "repo_name": "beta",
            "source_content": "export const t = 1;\n",
        }
    ],
    "include_exclude": [
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".py",
            "file_hash": "<sha256(source_content)>",
            "file_path": "src/main.py",
            "repo_name": "alpha",
            "source_content": "print('hello')\n",
        },
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".py",
            "file_hash": "<sha256(source_content)>",
            "file_path": "src/nested/deep.py",
            "repo_name": "alpha",
            "source_content": "x = 1\n",
        },
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".py",
            "file_hash": "<sha256(source_content)>",
            "file_path": "src/utils.py",
            "repo_name": "alpha",
            "source_content": "def helper():\n    return 1\n",
        },
    ],
    "missing_path": [],
    "repo_filter": [
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".ts",
            "file_hash": "<sha256(source_content)>",
            "file_path": "lib/tool.ts",
            "repo_name": "beta",
            "source_content": "export const t = 1;\n",
        }
    ],
    "two_repos": [
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".py",
            "file_hash": "<sha256(source_content)>",
            "file_path": "src/main.py",
            "repo_name": "alpha",
            "source_content": "print('hello')\n",
        },
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".py",
            "file_hash": "<sha256(source_content)>",
            "file_path": "src/nested/deep.py",
            "repo_name": "alpha",
            "source_content": "x = 1\n",
        },
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".py",
            "file_hash": "<sha256(source_content)>",
            "file_path": "src/utils.py",
            "repo_name": "alpha",
            "source_content": "def helper():\n    return 1\n",
        },
        {
            "crawl_id": "crawl-fixed",
            "file_extension": ".ts",
            "file_hash": "<sha256(source_content)>",
            "file_path": "lib/tool.ts",
            "repo_name": "beta",
            "source_content": "export const t = 1;\n",
        },
    ],
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_canonical_handle_matches_preserved_walk(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler_class = getattr(
        importlib.import_module(_HANDLER_MODULE), "HandlerCrawlFiles", None
    )
    assert handler_class is not None, "canonical handle(request) class is required"
    request_class = importlib.import_module(_REQUEST_MODULE).ModelCrawlFilesRequest
    monkeypatch.setenv(_ROOT_ENV, str(tmp_path))

    def invoke(spec: dict[str, Any]) -> Iterable[Any]:
        from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
            ModelCrawlConfig,
        )

        request = request_class(
            config=ModelCrawlConfig(repos=spec["repos"]),
            crawl_id=spec.get("crawl_id"),
            repo_filter=spec.get("repo_filter"),
        )
        return handler_class().handle(request)

    assert run_case(case, tmp_path, invoke) == EXPECTED[case]
