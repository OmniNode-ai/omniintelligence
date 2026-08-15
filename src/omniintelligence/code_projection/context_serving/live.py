# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Qdrant-only live composition for explicit code-context serving."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit

import httpx
from qdrant_client import AsyncQdrantClient

from omniintelligence.adapters.embedding_client_local_openai import (
    EmbeddingClientLocalOpenAI,
)
from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from omniintelligence.code_projection.qdrant import (
    CodeProjectionQdrantStore,
    ModelCodeProjectionCurrentGeneration,
    ModelCodeProjectionQdrantConfig,
    ProtocolCodeProjectionContentResolver,
    ProtocolCodeProjectionCurrentGenerationResolver,
)
from omniintelligence.nodes.node_embedding_generation_effect.models.model_embedding_client_config import (
    ModelEmbeddingClientConfig,
)

_DEFAULT_QDRANT_COLLECTION = "code_semantic_v2"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-qwen3"
_DEFAULT_EMBEDDING_MODEL_VERSION = "qwen3-embedding-0.6b-lab-2026-08-14"
_QDRANT_HTTP_MAX_CONNECTIONS = 8


@dataclass(frozen=True, slots=True)
class LiveCodeContextSearchConfiguration:
    """Validated environment bindings required only by code-context search."""

    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    embedding_url: str
    embedding_model: str
    embedding_model_version: str


def _absolute_http_url(value: str, *, name: str) -> str:
    endpoint = urlsplit(value)
    if (
        endpoint.scheme not in {"http", "https"}
        or not endpoint.netloc
        or endpoint.username is not None
        or endpoint.password is not None
    ):
        raise ValueError(f"{name} must be an absolute credential-free http(s) URL")
    return value


def load_live_code_context_search_configuration(
    environment: Mapping[str, str] | None = None,
) -> LiveCodeContextSearchConfiguration:
    """Load the exact Qdrant and embedding bindings without unrelated stores."""

    values = os.environ if environment is None else environment
    qdrant_url = values.get("QDRANT_URL", "").strip()
    if not qdrant_url:
        qdrant_host = values.get("QDRANT_HOST", "").strip()
        qdrant_port = values.get("QDRANT_PORT", "6333").strip()
        if not qdrant_host:
            raise ValueError(
                "QDRANT_URL or QDRANT_HOST must be bound by the active runtime"
            )
        if not qdrant_port.isdigit() or not 1 <= int(qdrant_port) <= 65_535:
            raise ValueError("QDRANT_PORT must be a valid decimal TCP port")
        qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
    qdrant_url = _absolute_http_url(qdrant_url, name="QDRANT_URL")

    raw_qdrant_api_key = values.get("QDRANT_API_KEY")
    if raw_qdrant_api_key is not None and (
        raw_qdrant_api_key != raw_qdrant_api_key.strip()
    ):
        raise ValueError("QDRANT_API_KEY must have no surrounding whitespace")
    qdrant_api_key = raw_qdrant_api_key or None
    if qdrant_api_key is not None and urlsplit(qdrant_url).scheme != "https":
        raise ValueError("QDRANT_API_KEY requires an https QDRANT_URL")

    embedding_url = _absolute_http_url(
        values.get("LLM_EMBEDDING_URL", "").strip(),
        name="LLM_EMBEDDING_URL",
    )
    qdrant_collection = values.get(
        "CODE_PROJECTION_QDRANT_COLLECTION",
        _DEFAULT_QDRANT_COLLECTION,
    )
    embedding_model = values.get(
        "CODE_PROJECTION_EMBEDDING_MODEL",
        _DEFAULT_EMBEDDING_MODEL,
    )
    embedding_model_version = values.get(
        "CODE_PROJECTION_EMBEDDING_MODEL_VERSION",
        _DEFAULT_EMBEDDING_MODEL_VERSION,
    )
    for name, value in (
        ("CODE_PROJECTION_QDRANT_COLLECTION", qdrant_collection),
        ("CODE_PROJECTION_EMBEDDING_MODEL", embedding_model),
        ("CODE_PROJECTION_EMBEDDING_MODEL_VERSION", embedding_model_version),
    ):
        if not value or value != value.strip():
            raise ValueError(f"{name} must be non-empty with no surrounding whitespace")

    return LiveCodeContextSearchConfiguration(
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        qdrant_collection=qdrant_collection,
        embedding_url=embedding_url,
        embedding_model=embedding_model,
        embedding_model_version=embedding_model_version,
    )


def _content_resolver(
    store: CodeProjectionArtifactStore,
) -> Callable[[str], bytes]:
    def resolve(content_ref: str) -> bytes:
        prefix = "artifact://sha256/"
        if not content_ref.startswith(prefix):
            raise ValueError("semantic content_ref is not a SHA-256 artifact URI")
        return store.read_content_artifact(content_ref.removeprefix(prefix))

    return resolve


def _current_generation_resolver(
    store: CodeProjectionArtifactStore,
) -> Callable[[str, str], ModelCodeProjectionCurrentGeneration | None]:
    def resolve(
        tenant_id: str,
        source_id: str,
    ) -> ModelCodeProjectionCurrentGeneration | None:
        current = store.load_current(source_id)
        if current is None:
            return None
        batch = current.batch
        if batch.source.tenant_id != tenant_id:
            raise RuntimeError(
                "current projection tenant does not match source identity"
            )
        return ModelCodeProjectionCurrentGeneration(
            tenant_id=batch.source.tenant_id,
            source_id=batch.source.source_id,
            batch_id=batch.batch_id,
            operation=batch.operation,
            batch_content_hash_sha256=current.batch_content_hash_sha256,
            document_ids=tuple(
                document.document_id for document in batch.semantic_documents
            ),
        )

    return resolve


def _build_qdrant_client(
    configuration: LiveCodeContextSearchConfiguration,
) -> AsyncQdrantClient:
    """Build the same bounded lab/cloud REST transport used by projection."""

    return AsyncQdrantClient(
        url=configuration.qdrant_url,
        api_key=configuration.qdrant_api_key,
        timeout=30,
        prefer_grpc=False,
        cloud_inference=False,
        check_compatibility=False,
        limits=httpx.Limits(
            max_connections=_QDRANT_HTTP_MAX_CONNECTIONS,
            max_keepalive_connections=0,
        ),
    )


@asynccontextmanager
async def live_code_context_search(
    artifact_store: CodeProjectionArtifactStore,
) -> AsyncIterator[CodeProjectionQdrantStore]:
    """Yield the real semantic-search adapter with no Postgres/Memgraph dependency."""

    configuration = load_live_code_context_search_configuration()
    qdrant_client = _build_qdrant_client(configuration)
    embedding_client = EmbeddingClientLocalOpenAI(
        ModelEmbeddingClientConfig(
            base_url=configuration.embedding_url,
            embedding_dimension=1024,
            timeout_seconds=60.0,
            max_retries=2,
            retry_base_delay=0.5,
            max_concurrency=4,
        ),
        model_name=configuration.embedding_model,
    )
    try:
        await embedding_client.connect()
        yield CodeProjectionQdrantStore(
            client=qdrant_client,
            embedding_client=embedding_client,
            content_resolver=cast(
                ProtocolCodeProjectionContentResolver,
                _content_resolver(artifact_store),
            ),
            current_generation_resolver=cast(
                ProtocolCodeProjectionCurrentGenerationResolver,
                _current_generation_resolver(artifact_store),
            ),
            config=ModelCodeProjectionQdrantConfig(
                collection_name=configuration.qdrant_collection,
                vector_name="code_semantic_v2",
                embedding_model=configuration.embedding_model,
                embedding_model_version=configuration.embedding_model_version,
                embedding_dimension=1024,
                read_consistency="majority",
                write_ordering="medium",
            ),
        )
    finally:
        try:
            await embedding_client.close()
        finally:
            await qdrant_client.close()


__all__ = [
    "LiveCodeContextSearchConfiguration",
    "live_code_context_search",
    "load_live_code_context_search_configuration",
]
