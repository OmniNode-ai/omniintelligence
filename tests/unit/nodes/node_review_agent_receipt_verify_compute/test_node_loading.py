# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The verifier node registers and loads through dependency injection in both profiles (OMN-22175).

The profile fixture is the only thing that differs between the two runs: it writes a
deployment overlay whose ``transport`` is ``in_memory`` (profile ``inmemory``) or
``redpanda`` (profile ``redpanda_overlay``). Everything else is loaded from that
overlay and the contract: the handler is resolved from ``handler_routing``, the policy,
the quorum size and the topics come from the overlay and the contract, and the request
travels onto the command topic and the verdict comes off the decided topic.

Scope of the Redpanda profile in the unit tier: it proves the overlay selects the
``redpanda`` binding and that the node answers over a bus bound by that selection. The
bus behind the port is the in-process one here, because a unit run holds no broker; the
node answering over a live Redpanda lane is the lab step after the release tag.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from omniintelligence.handlers.handler_review_agent_receipt_overlay import (
    OVERLAY_ID,
    load_contract,
    load_topics,
    load_verifier_settings,
)
from omniintelligence.nodes.node_review_agent_receipt_verify_compute.models import (
    EnumAgentReceiptDecision,
    EnumAgentReceiptRefusal,
    EnumAgentReceiptVerifyTransport,
    ModelAgentReceiptContext,
    ModelAgentReceiptVerdict,
    ModelAgentReceiptVerifyRequest,
)

from .helpers import HEAD, KEY, PR, REPO, receipt, voter

pytestmark = pytest.mark.unit

_TRANSPORT_OF_PROFILE = {
    "inmemory": EnumAgentReceiptVerifyTransport.IN_MEMORY,
    "redpanda_overlay": EnumAgentReceiptVerifyTransport.REDPANDA,
}

#: What the deployment overlay supplies in both profiles; only the transport differs.
_DEPLOYMENT_OVERLAY: dict[str, Any] = {
    "quorum_size": 2,
    "policy": {
        "approved_identities": ["voter-a", "voter-b"],
        "forbidden_providers": ["provider-forbidden"],
        "forbidden_endpoint_classes": ["class-forbidden"],
        "forbidden_endpoints": ["192.0.2.50:9000"],
        "forbidden_hosts": ["forbidden-host.test"],
    },
}

BusCallback = Callable[[bytes], Awaitable[None]]


class InProcessBus:
    """The bus port: a topic is a list of subscribers and a publish calls them in order."""

    def __init__(self) -> None:
        self.subscribers: dict[str, list[BusCallback]] = {}

    async def publish(self, topic: str, value: bytes) -> None:
        for callback in list(self.subscribers.get(topic, [])):
            await callback(value)

    def subscribe(self, topic: str, callback: BusCallback) -> None:
        self.subscribers.setdefault(topic, []).append(callback)


def bus_for(transport: EnumAgentReceiptVerifyTransport) -> InProcessBus:
    """The binding the overlay's transport selects."""
    assert transport in set(EnumAgentReceiptVerifyTransport)
    return InProcessBus()


@pytest.fixture(params=["inmemory", "redpanda_overlay"])
def profile(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> EnumAgentReceiptVerifyTransport:
    """Write the deployment overlay of the profile and make it the only overlay root."""
    transport = _TRANSPORT_OF_PROFILE[request.param]
    path = tmp_path / OVERLAY_ID / "overlay.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump({**_DEPLOYMENT_OVERLAY, "transport": transport.value}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONEX_SKILL_OVERLAY_ROOTS", str(tmp_path))
    return transport


def test_contract_binds_the_handler_through_routing(
    profile: EnumAgentReceiptVerifyTransport,
) -> None:
    contract = load_contract()
    assert contract["name"] == "node_review_agent_receipt_verify_compute"
    assert contract["node_type"] == "COMPUTE_GENERIC"
    routes = {
        h["operation"]: h["handler"] for h in contract["handler_routing"]["handlers"]
    }
    assert set(routes) == {"verify_agent_receipt", "resolve_verifier_settings"}
    for handler in routes.values():
        resolved = getattr(
            importlib.import_module(handler["module"]), handler["function"]
        )
        assert callable(resolved)
    assert contract["input_model"]["name"] == ModelAgentReceiptVerifyRequest.__name__
    assert contract["output_model"]["name"] == ModelAgentReceiptVerdict.__name__
    assert contract["dependencies"] == []


def test_overlay_supplies_transport_quorum_and_policy(
    profile: EnumAgentReceiptVerifyTransport,
) -> None:
    settings = load_verifier_settings()
    assert settings.transport is profile
    assert settings.quorum_size == 2
    assert settings.policy.approved_identities == ("voter-a", "voter-b")
    assert settings.policy.forbidden_hosts == ("forbidden-host.test",)


def test_node_answers_accepted_and_refused_over_the_bound_bus(
    profile: EnumAgentReceiptVerifyTransport,
) -> None:
    settings = load_verifier_settings()
    topics = load_topics()
    handler_ref = next(
        h["handler"]
        for h in load_contract()["handler_routing"]["handlers"]
        if h["operation"] == "verify_agent_receipt"
    )
    handler = cast(
        "Callable[[ModelAgentReceiptVerifyRequest], ModelAgentReceiptVerdict]",
        getattr(
            importlib.import_module(handler_ref["module"]), handler_ref["function"]
        ),
    )
    context = ModelAgentReceiptContext(repo=REPO, pr=PR, head_sha=HEAD)
    signed = receipt((voter("voter-a"), voter("voter-b")))
    altered = signed.model_copy(update={"reviewer_id": "someone-else"})

    async def run() -> list[ModelAgentReceiptVerdict]:
        bus = bus_for(settings.transport)
        decided: asyncio.Queue[ModelAgentReceiptVerdict] = asyncio.Queue()

        async def on_command(value: bytes) -> None:
            verdict = handler(ModelAgentReceiptVerifyRequest.model_validate_json(value))
            await bus.publish(topics.decided, verdict.model_dump_json().encode())

        async def on_decided(value: bytes) -> None:
            await decided.put(ModelAgentReceiptVerdict.model_validate_json(value))

        bus.subscribe(topics.command, on_command)
        bus.subscribe(topics.decided, on_decided)
        answers = []
        for sent in (signed, altered):
            command = ModelAgentReceiptVerifyRequest(
                receipt=sent,
                key=KEY,
                policy=settings.policy,
                quorum_size=settings.quorum_size,
                context=context,
            )
            await bus.publish(topics.command, command.model_dump_json().encode())
            answers.append(await asyncio.wait_for(decided.get(), timeout=10))
        return answers

    accepted, refused = asyncio.run(run())
    assert accepted.decision is EnumAgentReceiptDecision.ACCEPTED
    assert accepted.voter_identities == ("voter-a", "voter-b")
    assert refused.decision is EnumAgentReceiptDecision.REFUSED
    assert refused.reason is EnumAgentReceiptRefusal.FORGED_SIGNATURE
