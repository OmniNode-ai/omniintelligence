# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Executable explicit context-serving CLI proofs."""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from omniintelligence.code_projection._canonical import (
    canonical_json_bytes,
    sha256_hex,
)
from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from omniintelligence.code_projection.context_serving import cli
from omniintelligence.code_projection.context_serving.codec import (
    serialize_authorization_profile,
)
from omniintelligence.code_projection.context_serving.models import (
    ModelCodeContextResponse,
    derive_repository_policy_scope_ref,
)
from tests.unit.code_projection.context_serving.fixtures import (
    OTHER_TENANT_ID,
    QUERY_TEXT,
    ContextScenario,
    build_scenario,
)
from tests.unit.code_projection.context_serving.test_service import FakeSearch

pytestmark = pytest.mark.unit


def _files(
    root: Path,
) -> tuple[ContextScenario, Path, Path]:
    scenario = build_scenario(root / "projection")
    request_path = root / "request.json"
    authorization_path = root / "authorization.json"
    request_path.write_bytes(scenario.request_bytes)
    authorization_path.write_bytes(serialize_authorization_profile(scenario.profile))
    return scenario, request_path, authorization_path


def _bind_authorization(
    monkeypatch: pytest.MonkeyPatch,
    authorization_path: Path,
) -> None:
    monkeypatch.setenv("CODE_CONTEXT_AUTHORIZATION_FILE", str(authorization_path))
    monkeypatch.setenv(
        "CODE_CONTEXT_AUTHORIZATION_SHA256",
        sha256_hex(authorization_path.read_bytes()),
    )


@pytest.mark.asyncio
async def test_cli_run_uses_exact_request_file_with_live_adapter_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scenario, request_path, authorization_path = _files(tmp_path)
    _bind_authorization(monkeypatch, authorization_path)

    @asynccontextmanager
    async def fake_live_qdrant_store(
        artifact_store: CodeProjectionArtifactStore,
    ) -> AsyncIterator[FakeSearch]:
        assert artifact_store.root == scenario.store.root
        yield FakeSearch((scenario.hit,))

    monkeypatch.setattr(cli, "live_code_context_search", fake_live_qdrant_store)
    response_bytes = await cli._run(
        argparse.Namespace(
            request_file=str(request_path),
            artifact_root=str(scenario.store.root),
        )
    )
    response = ModelCodeContextResponse.model_validate_json(
        response_bytes,
        strict=True,
    )

    assert response.pack.request_payload_sha256
    assert response.pack.items[0].document_id == scenario.hit.document_id
    assert QUERY_TEXT.encode() not in response_bytes


def test_cli_rejects_unauthorized_request_before_live_connection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    scenario, request_path, authorization_path = _files(tmp_path)
    _bind_authorization(monkeypatch, authorization_path)
    unauthorized = scenario.request.model_copy(
        update={
            "tenant_id": OTHER_TENANT_ID,
            "policy_scope_ref": derive_repository_policy_scope_ref(
                tenant_id=OTHER_TENANT_ID,
                repository_id=scenario.request.repository_id,
                repository_instance_id=scenario.request.repository_instance_id,
            ),
        }
    )
    request_path.write_bytes(canonical_json_bytes(unauthorized.model_dump(mode="json")))
    entered = False

    @asynccontextmanager
    async def forbidden_live_qdrant_store(
        artifact_store: CodeProjectionArtifactStore,
    ) -> AsyncIterator[FakeSearch]:
        nonlocal entered
        del artifact_store
        entered = True
        yield FakeSearch(())

    monkeypatch.setattr(cli, "live_code_context_search", forbidden_live_qdrant_store)
    unauthorized_artifact_root = tmp_path / "unauthorized-artifact-root"
    result = cli.main(
        [
            "--request-file",
            str(request_path),
            "--artifact-root",
            str(unauthorized_artifact_root),
        ]
    )

    assert result == 1
    assert entered is False
    assert not unauthorized_artifact_root.exists()
    assert QUERY_TEXT not in capsys.readouterr().err


def test_cli_rejects_unpinned_authorization_before_live_connection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    _scenario, request_path, authorization_path = _files(tmp_path)
    monkeypatch.setenv("CODE_CONTEXT_AUTHORIZATION_FILE", str(authorization_path))
    monkeypatch.setenv("CODE_CONTEXT_AUTHORIZATION_SHA256", "0" * 64)
    entered = False

    @asynccontextmanager
    async def forbidden_live_search(
        artifact_store: CodeProjectionArtifactStore,
    ) -> AsyncIterator[FakeSearch]:
        nonlocal entered
        del artifact_store
        entered = True
        yield FakeSearch(())

    monkeypatch.setattr(cli, "live_code_context_search", forbidden_live_search)
    artifact_root = tmp_path / "unpinned-artifact-root"
    result = cli.main(
        [
            "--request-file",
            str(request_path),
            "--artifact-root",
            str(artifact_root),
        ]
    )

    assert result == 1
    assert entered is False
    assert not artifact_root.exists()
    assert QUERY_TEXT not in capsys.readouterr().err


def test_cli_maps_live_setup_failure_without_echoing_query(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    scenario, request_path, authorization_path = _files(tmp_path)
    _bind_authorization(monkeypatch, authorization_path)

    @asynccontextmanager
    async def failed_live_search(
        artifact_store: CodeProjectionArtifactStore,
    ) -> AsyncIterator[FakeSearch]:
        if str(artifact_store.root):
            raise RuntimeError(QUERY_TEXT)
        yield FakeSearch(())  # pragma: no cover - async-generator type anchor

    monkeypatch.setattr(cli, "live_code_context_search", failed_live_search)
    result = cli.main(
        [
            "--request-file",
            str(request_path),
            "--artifact-root",
            str(scenario.store.root),
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "CodeContextSearchError" in captured.err
    assert QUERY_TEXT not in captured.err
