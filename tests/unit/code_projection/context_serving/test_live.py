# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Qdrant-only local and cloud configuration proofs."""

from __future__ import annotations

import httpx
import pytest

from omniintelligence.code_projection.context_serving import live

pytestmark = pytest.mark.unit


def test_local_search_configuration_requires_no_postgres_memgraph_or_api_key() -> None:
    configuration = live.load_live_code_context_search_configuration(
        {
            "QDRANT_HOST": "omnimemory-qdrant",
            "QDRANT_PORT": "6333",
            "LLM_EMBEDDING_URL": "http://embedding:8000/v1",
        }
    )

    assert configuration.qdrant_url == "http://omnimemory-qdrant:6333"
    assert configuration.qdrant_api_key is None
    assert configuration.qdrant_collection == "code_semantic_v2"


def test_cloud_search_configuration_accepts_https_database_key() -> None:
    configuration = live.load_live_code_context_search_configuration(
        {
            "QDRANT_URL": "https://cluster.example.qdrant.io:6333",
            "QDRANT_API_KEY": "test-only-database-key",
            "LLM_EMBEDDING_URL": "https://embedding.example.test/v1",
        }
    )

    assert configuration.qdrant_url.startswith("https://")
    assert configuration.qdrant_api_key == "test-only-database-key"


def test_search_configuration_rejects_key_over_plaintext() -> None:
    with pytest.raises(ValueError, match="requires an https QDRANT_URL"):
        live.load_live_code_context_search_configuration(
            {
                "QDRANT_URL": "http://cluster.example.test:6333",
                "QDRANT_API_KEY": "test-only-database-key",
                "LLM_EMBEDDING_URL": "http://embedding:8000/v1",
            }
        )


def test_qdrant_transport_is_bounded_and_does_not_reuse_idle_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = live.load_live_code_context_search_configuration(
        {
            "QDRANT_HOST": "omnimemory-qdrant",
            "QDRANT_PORT": "6333",
            "LLM_EMBEDDING_URL": "http://embedding:8000/v1",
        }
    )
    captured: dict[str, object] = {}

    def fake_qdrant_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(live, "AsyncQdrantClient", fake_qdrant_client)
    live._build_qdrant_client(configuration)

    limits = captured["limits"]
    assert captured["check_compatibility"] is False
    assert isinstance(limits, httpx.Limits)
    assert limits.max_connections == 8
    assert limits.max_keepalive_connections == 0
