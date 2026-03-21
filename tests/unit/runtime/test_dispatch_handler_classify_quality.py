# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for classify + quality dispatch handlers (OMN-5678)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from omniintelligence.runtime.dispatch_handler_code_classify import (
    create_code_classify_dispatch_handler,
)
from omniintelligence.runtime.dispatch_handler_code_quality import (
    create_code_quality_dispatch_handler,
)

CLASSIFY_CONFIG = {
    "enabled": True,
    "scoring_weights": {
        "domain": 0.30,
        "operation": 0.30,
        "keyword": 0.25,
        "feature": 0.15,
    },
    "classifications": {
        "effect": {
            "keywords": ["database", "persist", "send", "publish"],
            "domains": ["database"],
            "operations": ["create", "send", "publish"],
            "features": ["connection_pooling"],
        },
        "compute": {
            "keywords": ["transform", "parse", "compute"],
            "domains": ["ml"],
            "operations": ["transform", "compute"],
            "features": ["validation"],
        },
    },
    "min_confidence": 0.4,
}

QUALITY_CONFIG = {
    "enabled": True,
    "weights": {
        "complexity": 0.20,
        "maintainability": 0.20,
        "documentation": 0.15,
        "temporal_relevance": 0.15,
        "pattern_compliance": 0.15,
        "architectural_compliance": 0.15,
    },
    "complexity_thresholds": {
        "cyclomatic_low": 5,
        "cyclomatic_medium": 10,
        "cyclomatic_high": 15,
    },
    "code_smells": [],
    "good_patterns": [],
}


def _make_envelope(payload: dict) -> MagicMock:  # type: ignore[type-arg]
    envelope = MagicMock()
    envelope.payload = payload
    return envelope


def _make_context() -> MagicMock:
    ctx = MagicMock()
    ctx.correlation_id = "test-cid"
    return ctx


def _persisted_event_payload(entity_ids: list[str]) -> dict[str, object]:
    return {
        "event_id": "evt-test",
        "crawl_id": "crawl-1",
        "repo_name": "omniintelligence",
        "file_path": "src/foo/bar.py",
        "file_hash": "hash123",
        "entity_ids": entity_ids,
        "persisted_count": len(entity_ids),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@pytest.mark.unit
class TestClassifyHandler:
    """Tests for classification dispatch handler."""

    @pytest.mark.asyncio
    async def test_classifies_entities(self) -> None:
        """Handler classifies entities and updates Postgres."""
        mock_repo = MagicMock()
        mock_repo.get_entities_by_ids = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "entity_name": "NodeDatabaseEffect",
                    "entity_type": "class",
                    "bases": ["NodeEffect"],
                    "methods": json.dumps([{"name": "persist"}, {"name": "send"}]),
                    "decorators": [],
                    "docstring": "Persists to database.",
                    "file_hash": "hash123",
                }
            ]
        )
        mock_repo.get_entity_enrichment_metadata = AsyncMock(
            return_value={
                "file_hash": "hash123",
                "enrichment_metadata": {},
            }
        )
        mock_repo.update_deterministic_classification = AsyncMock()

        handler = create_code_classify_dispatch_handler(
            repository=mock_repo,
            classify_config=CLASSIFY_CONFIG,
        )

        result = await handler(
            _make_envelope(_persisted_event_payload(["e1"])),
            _make_context(),
        )
        assert result == "ok"
        mock_repo.update_deterministic_classification.assert_called_once()
        call_args = mock_repo.update_deterministic_classification.call_args
        assert call_args.kwargs["entity_id"] == "e1"

    @pytest.mark.asyncio
    async def test_idempotency_skip(self) -> None:
        """Handler skips entity with matching (file_hash, config_hash, stage_version)."""
        import hashlib

        ch = hashlib.sha256(
            json.dumps(CLASSIFY_CONFIG, sort_keys=True).encode()
        ).hexdigest()[:16]
        mock_repo = MagicMock()
        mock_repo.get_entities_by_ids = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "entity_name": "Foo",
                    "entity_type": "class",
                    "bases": [],
                    "methods": [],
                    "decorators": [],
                    "docstring": None,
                    "file_hash": "hash123",
                }
            ]
        )
        mock_repo.get_entity_enrichment_metadata = AsyncMock(
            return_value={
                "file_hash": "hash123",
                "enrichment_metadata": {
                    "classify": {"config_hash": ch, "stage_version": "1.0.0"}
                },
            }
        )
        mock_repo.update_deterministic_classification = AsyncMock()

        handler = create_code_classify_dispatch_handler(
            repository=mock_repo,
            classify_config=CLASSIFY_CONFIG,
        )

        await handler(
            _make_envelope(_persisted_event_payload(["e1"])),
            _make_context(),
        )
        mock_repo.update_deterministic_classification.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_change_triggers_reenrichment(self) -> None:
        """Changed config_hash forces re-classification despite same file_hash."""
        mock_repo = MagicMock()
        mock_repo.get_entities_by_ids = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "entity_name": "Foo",
                    "entity_type": "class",
                    "bases": [],
                    "methods": [],
                    "decorators": [],
                    "docstring": None,
                    "file_hash": "hash123",
                }
            ]
        )
        mock_repo.get_entity_enrichment_metadata = AsyncMock(
            return_value={
                "file_hash": "hash123",
                "enrichment_metadata": {
                    "classify": {"config_hash": "OLD_HASH", "stage_version": "1.0.0"}
                },
            }
        )
        mock_repo.update_deterministic_classification = AsyncMock()

        handler = create_code_classify_dispatch_handler(
            repository=mock_repo,
            classify_config=CLASSIFY_CONFIG,
        )

        await handler(
            _make_envelope(_persisted_event_payload(["e1"])),
            _make_context(),
        )
        # Should re-classify because config_hash differs
        mock_repo.update_deterministic_classification.assert_called_once()


@pytest.mark.unit
class TestQualityHandler:
    """Tests for quality scoring dispatch handler."""

    @pytest.mark.asyncio
    async def test_scores_entities(self) -> None:
        """Handler scores entities and updates Postgres."""
        mock_repo = MagicMock()
        mock_repo.get_entities_by_ids = AsyncMock(
            return_value=[
                {
                    "id": "e1",
                    "entity_name": "my_func",
                    "entity_type": "function",
                    "source_path": "nonexistent.py",
                    "file_hash": "hash123",
                }
            ]
        )
        mock_repo.get_entity_enrichment_metadata = AsyncMock(
            return_value={
                "file_hash": "hash123",
                "enrichment_metadata": {},
            }
        )
        mock_repo.update_quality_score = AsyncMock()

        handler = create_code_quality_dispatch_handler(
            repository=mock_repo,
            quality_config=QUALITY_CONFIG,
        )

        result = await handler(
            _make_envelope(_persisted_event_payload(["e1"])),
            _make_context(),
        )
        assert result == "ok"
        mock_repo.update_quality_score.assert_called_once()
