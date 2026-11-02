# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The declared intelligence API mount against a real Postgres (OMN-21288, T15).

The application is built from the ``http_mount`` declaration exactly as the
runtime builds it (import the factory, call it with no arguments), then driven
through the ASGI lifespan and ASGI HTTP protocol messages the runtime's mount
sends. Needs ``OMNIINTELLIGENCE_DB_URL`` to reach a database that holds the
``learned_patterns`` table.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import pytest
import yaml

import omniintelligence.nodes as nodes_package
from tests.integration.conftest import requires_postgres

pytestmark = [pytest.mark.integration, requires_postgres]

_Message = MutableMapping[str, Any]
_CONTRACT = (
    Path(nodes_package.__file__).parent
    / "node_pattern_storage_effect"
    / "contract.yaml"
)


def _mounted_app() -> Any:
    mount = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))["http_mount"]
    module_name, _, attribute = mount["factory"].partition(":")
    return getattr(importlib.import_module(module_name), attribute)()


async def _get(app: Any, path: str, query: str = "") -> tuple[int, Any]:
    sent: list[_Message] = []
    body_sent = False

    async def receive() -> _Message:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    async def send(message: _Message) -> None:
        sent.append(message)

    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 1),
        "server": None,
        "state": {},
    }
    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(
        m.get("body", b"") for m in sent if m["type"] == "http.response.body"
    )
    return status, json.loads(body)


async def test_pool_opens_and_closes_with_the_mount_lifecycle() -> None:
    app = _mounted_app()
    inbox: asyncio.Queue[_Message] = asyncio.Queue()
    outbox: asyncio.Queue[_Message] = asyncio.Queue()
    scope = {"type": "lifespan", "asgi": {"version": "3.0"}, "state": {}}
    lifespan = asyncio.create_task(app(scope, inbox.get, outbox.put))

    # Before startup there is no pool: the API's own health says so.
    assert await _get(app, "/health") == (503, {"status": "starting"})

    await inbox.put({"type": "lifespan.startup"})
    reply = await asyncio.wait_for(outbox.get(), timeout=30)
    assert reply["type"] == "lifespan.startup.complete", reply

    status, health = await _get(app, "/health")
    assert (status, health) == (200, {"status": "healthy"})

    status, page = await _get(app, "/api/v1/patterns", "limit=1")
    assert status == 200
    assert {"patterns", "total_returned", "limit", "offset"} <= set(page)

    await inbox.put({"type": "lifespan.shutdown"})
    reply = await asyncio.wait_for(outbox.get(), timeout=30)
    assert reply["type"] == "lifespan.shutdown.complete", reply
    await asyncio.wait_for(lifespan, timeout=30)

    # After shutdown the pool is closed and released.
    assert await _get(app, "/health") == (503, {"status": "starting"})
