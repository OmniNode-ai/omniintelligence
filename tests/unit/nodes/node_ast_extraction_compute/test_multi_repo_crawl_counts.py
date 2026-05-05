# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""AST crawl acceptance test for OMN-7203: remaining repos.

Validates that the AST crawl pipeline yields at least 500 total
code_entities across omniintelligence, omnibase_core, omnibase_infra,
and omniclaude, with at least 50 entities per repo.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from omniintelligence.nodes.node_ast_extraction_compute.handlers import (
    extract_entities_from_source,
)
from omniintelligence.nodes.node_code_crawler_effect.handlers.handler_crawl_files import (
    crawl_files,
)
from omniintelligence.nodes.node_code_crawler_effect.models.model_crawl_config import (
    ModelCrawlConfig,
    ModelRepoCrawlConfig,
)

_TARGET_REPOS = [
    "omniintelligence",
    "omnibase_core",
    "omnibase_infra",
    "omniclaude",
]

_MIN_TOTAL_ENTITIES = 500
_MIN_PER_REPO_ENTITIES = 50


class ModelOmniHomeSettings(BaseSettings):
    """Settings surface for workspace-level acceptance test paths."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    omni_home: Path | None = Field(default=None, validation_alias="OMNI_HOME")


def _omni_home() -> Path:
    settings = ModelOmniHomeSettings()
    if settings.omni_home is not None and settings.omni_home.is_dir():
        return settings.omni_home
    current = Path(__file__).resolve()
    for ancestor in current.parents:
        if all((ancestor / repo).is_dir() for repo in _TARGET_REPOS):
            return ancestor
    msg = (
        "Cannot locate omni_home. Set the OMNI_HOME environment variable "
        "or run tests from within the omni_home tree."
    )
    raise RuntimeError(msg)


@pytest.mark.unit
class TestMultiRepoCrawlCounts:
    """Acceptance test: AST crawl on 4 repos meets entity count thresholds.

    Requirement (OMN-7203): code_entities > 500 total across all 4 repos;
    each repo > 50 entities.
    """

    @pytest.fixture(scope="class")
    def entity_counts_by_repo(self) -> dict[str, int]:
        """Run crawl + extraction on all 4 repos; return entity counts per repo."""
        omni_home = _omni_home()
        repos = [
            ModelRepoCrawlConfig(
                name=repo,
                enabled=True,
                path=str(omni_home / repo),
                include=["src/**/*.py"],
                exclude=["**/__pycache__/**", "**/node_tests/**"],
            )
            for repo in _TARGET_REPOS
        ]
        config = ModelCrawlConfig(repos=repos)
        counts: dict[str, int] = defaultdict(int)

        for event in crawl_files(config, crawl_id="omn-7203-acceptance"):
            repo_config = next(
                (r for r in config.repos if r.name == event.repo_name), None
            )
            if repo_config is None:
                continue
            full_path = Path(repo_config.path) / event.file_path
            if not full_path.exists():
                continue
            source = full_path.read_text(encoding="utf-8", errors="replace")
            result = extract_entities_from_source(
                source,
                file_path=event.file_path,
                source_repo=event.repo_name,
                file_hash=event.file_hash,
            )
            counts[event.repo_name] += len(result.entities)

        return dict(counts)

    def test_each_repo_exceeds_minimum(
        self, entity_counts_by_repo: dict[str, int]
    ) -> None:
        """Each of the 4 repos must yield at least 50 entities."""
        for repo in _TARGET_REPOS:
            count = entity_counts_by_repo.get(repo, 0)
            assert count > _MIN_PER_REPO_ENTITIES, (
                f"Repo '{repo}' yielded only {count} entities "
                f"(minimum: {_MIN_PER_REPO_ENTITIES})"
            )

    def test_total_entities_exceeds_minimum(
        self, entity_counts_by_repo: dict[str, int]
    ) -> None:
        """Total entities across all 4 repos must exceed 500."""
        total = sum(entity_counts_by_repo.get(repo, 0) for repo in _TARGET_REPOS)
        assert total > _MIN_TOTAL_ENTITIES, (
            f"Total entities {total} does not exceed {_MIN_TOTAL_ENTITIES}. "
            f"Per-repo: {entity_counts_by_repo}"
        )

    def test_all_target_repos_present(
        self, entity_counts_by_repo: dict[str, int]
    ) -> None:
        """All 4 target repos must appear in crawl output with non-zero counts."""
        missing = [r for r in _TARGET_REPOS if entity_counts_by_repo.get(r, 0) == 0]
        assert not missing, (
            f"These repos produced zero entities (missing or unreachable): {missing}"
        )
