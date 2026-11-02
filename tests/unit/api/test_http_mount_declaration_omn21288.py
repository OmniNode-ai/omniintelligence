# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The intelligence API is a contract-declared ASGI mount (OMN-21288, T15).

The runtime serves an ``http_mount`` block of any loaded node ``contract.yaml``
on its own HTTP port (omnibase_infra ``handlers/http_mount``): it imports
``factory``, calls it with no arguments, drives the returned ASGI application's
lifespan and hands it every request at or below ``path_prefix``. The
application sees the request path unchanged, so a mount only works when the
prefix covers the application's absolute routes.

These tests hold the declaration to that contract without importing the
runtime's loader, which this repository only gets with the next omnibase_infra
release.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import re
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI

import omniintelligence.nodes as nodes_package

pytestmark = pytest.mark.unit

_NODES_DIR = Path(nodes_package.__file__).parent
# Same grammar as omnibase_infra.models.model_http_mount.ModelHttpMount.
_FACTORY_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$"
)
_PREFIX_PATTERN = re.compile(r"^/[A-Za-z0-9._~\-]+(/[A-Za-z0-9._~\-]+)*$")
# The runtime owns /health on its port; a mount may not shadow it.
_RUNTIME_ROUTES = ("/health",)


def _declarations() -> list[tuple[str, dict[str, str]]]:
    found: list[tuple[str, dict[str, str]]] = []
    for contract in sorted(_NODES_DIR.glob("*/contract.yaml")):
        raw = yaml.safe_load(contract.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("http_mount") is not None:
            found.append((contract.parent.name, raw["http_mount"]))
    return found


def _covers(prefix: str, path: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _declared_mount() -> dict[str, str]:
    declared = _declarations()
    assert len(declared) == 1, f"expected one http_mount declaration, got {declared}"
    return declared[0][1]


def _build(mount: dict[str, str]) -> FastAPI:
    module_name, _, attribute = mount["factory"].partition(":")
    factory: Callable[[], Any] = getattr(
        importlib.import_module(module_name), attribute
    )
    app = factory()
    assert isinstance(app, FastAPI)
    return app


def test_one_node_declares_the_intelligence_api_mount() -> None:
    node, mount = _declarations()[0]
    assert len(_declarations()) == 1
    assert node == "node_pattern_storage_effect"
    assert mount == {
        "factory": "omniintelligence.api.app:create_app",
        "path_prefix": "/api/v1",
    }


def test_declaration_is_well_formed() -> None:
    mount = _declared_mount()
    assert set(mount) == {"factory", "path_prefix"}
    assert _FACTORY_PATTERN.match(mount["factory"])
    assert _PREFIX_PATTERN.match(mount["path_prefix"])


def test_factory_builds_an_app_with_no_arguments_and_no_database() -> None:
    app = _build(_declared_mount())
    assert app.router.lifespan_context is not None


def test_prefix_serves_every_route_except_the_runtime_owned_health() -> None:
    mount = _declared_mount()
    paths = set(_build(mount).openapi()["paths"])
    assert "/api/v1/patterns" in paths
    outside = {p for p in paths if not _covers(mount["path_prefix"], p)}
    assert outside == {"/health"}


def test_prefix_does_not_shadow_a_runtime_route() -> None:
    prefix = _declared_mount()["path_prefix"]
    assert not any(_covers(prefix, route) for route in _RUNTIME_ROUTES)


def _lifespan_startup_reply(app: FastAPI) -> MutableMapping[str, Any]:
    """Drive the ASGI lifespan startup the way the runtime's mount does."""

    async def run() -> MutableMapping[str, Any]:
        inbox: asyncio.Queue[MutableMapping[str, Any]] = asyncio.Queue()
        outbox: asyncio.Queue[MutableMapping[str, Any]] = asyncio.Queue()
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}
        task = asyncio.create_task(app(scope, inbox.get, outbox.put))
        await inbox.put({"type": "lifespan.startup"})
        reply = await asyncio.wait_for(outbox.get(), timeout=30)
        # Starlette re-raises the startup error after reporting it; the mount's
        # driver reads the reply first and surfaces the task error itself.
        with contextlib.suppress(OSError):
            await asyncio.wait_for(task, timeout=30)
        return reply

    return asyncio.run(run())


def test_unreachable_database_fails_lifespan_startup_instead_of_serving_partly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Port 1 refuses: the factory is built exactly as the mount builds it, with
    # no arguments, and the pool the lifespan opens cannot connect.
    monkeypatch.setenv("OMNIINTELLIGENCE_DB_URL", "postgresql://u:p@127.0.0.1:1/none")
    reply = _lifespan_startup_reply(_build(_declared_mount()))
    assert reply["type"] == "lifespan.startup.failed"
