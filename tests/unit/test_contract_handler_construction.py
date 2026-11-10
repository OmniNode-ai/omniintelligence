# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Every announced handler constructs the way the one runtime constructs it.

The dev runtime boots by running ``wire_from_manifest`` over every contract this
package announces, with ``ONEX_WIRING_STRICT_MODE`` on. A handler class with a
required constructor parameter the resolver has no provider for raises
``TypeError: Handler ... requires constructor parameters [...]`` and the runtime
never becomes healthy (deploy agent job c4b55b6a, ``HandlerStreak`` requires
``['store']``). The loader-shape test checks that each class imports; this one
constructs them, through the production wiring path, over the whole package.

Shape follows omnibase_infra ``test_savings_correlation_pool_di_omn17510.py``: a
real ``MessageDispatchEngine`` (no mock container) and a real
``ModelONEXContainer``, ``event_bus=None`` and ``subscribe_immediately=False`` to
stay offline. No skip: a handler with a required parameter that the plugin does
not register fails here.

Two nodes have no live supplier for a required parameter anywhere in the package
(see ``NODES_WITHOUT_A_LIVE_SUPPLIER``). The kernel filters the manifest through
``filter_manifest_for_runtime_profile`` before wiring, and a deployment excludes
nodes with ``ONEX_RUNTIME_NODE_EXCLUSION``; the dev-lane manifest here is built by
that same filter with those two dropped by name, and a companion test fails the moment the
named set and the unregistered set differ, so the list can only shrink.

Ticket: OMN-23431
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_infra.runtime.auto_wiring.discovery import discover_contracts_from_paths
from omnibase_infra.runtime.auto_wiring.handler_wiring import (
    _import_handler_class,
    _required_handler_init_params,
    wire_from_manifest,
)
from omnibase_infra.runtime.auto_wiring.models import ModelAutoWiringManifest
from omnibase_infra.runtime.auto_wiring.profile_ownership import (
    filter_manifest_for_runtime_profile,
)
from omnibase_infra.runtime.message_dispatch_engine import MessageDispatchEngine

from omniintelligence.handlers.runtime_dependencies import (
    register_contract_handler_dependencies,
)
from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_streak import (
    HandlerStreak,
)
from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_trigger_record import (
    HandlerTriggerRecord,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification import (
    HandlerIntentClassification,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_classification_config import (
    ModelClassificationConfig,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.handler_compute import (
    HandlerEvaluateCompliance,
)
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    HandlerPromotion,
)

NODES_DIR = Path(__file__).parent.parent.parent / "src" / "omniintelligence" / "nodes"
CONTRACT_PATHS = sorted(NODES_DIR.glob("*/contract.yaml"))


# Nodes whose handler needs a constructor argument that nothing in this package can
# build for the runtime today. Each is excluded from the dev-lane manifest exactly as
# the deployment control ONEX_RUNTIME_NODE_EXCLUSION excludes it. Remove an entry in
# the change that registers a live supplier for it.
NODES_WITHOUT_A_LIVE_SUPPLIER: dict[str, str] = {
    "node_git_repo_crawler_effect": (
        "HandlerGitRepoCrawl needs a ProtocolCrawlStateStore; the only store is the "
        "in-memory test one and the omnimemory_crawl_state table is in omnimemory's "
        "database"
    ),
    "node_plan_reviewer_multi_compute": (
        "HandlerPlanReviewerMultiCompute needs per-model LLM callers; no runtime "
        "wiring builds them and the node subscribes to no topic"
    ),
}

_DEV_LANE_ENV = {
    "ONEX_RUNTIME_FOLDED_PROFILES": "effects,workers",
}


class _Store:
    """Stands in for a database-backed store: handlers keep it and do no I/O in __init__."""


class _Repository:
    """Stands in for the pattern repository."""


class _LlmClient:
    """Stands in for the compliance LLM client."""


def _manifest() -> ModelAutoWiringManifest:
    discovered = discover_contracts_from_paths(CONTRACT_PATHS)
    assert [e.error for e in discovered.errors] == []
    return ModelAutoWiringManifest(contracts=list(discovered.contracts))


def _dev_lane_manifest() -> ModelAutoWiringManifest:
    """The manifest the dev lane's main runtime wires.

    The kernel's own ownership filter (profile, folded profiles, lane) runs first;
    then the two named nodes are dropped, as the deployment's
    ``ONEX_RUNTIME_NODE_EXCLUSION`` drops them in omnibase_infra releases that read
    it. The omnibase_infra pinned here predates that variable, so it is applied by
    name here rather than left to the filter.
    """
    owned = filter_manifest_for_runtime_profile(
        _manifest(), "main", environ=_DEV_LANE_ENV
    ).manifest
    return ModelAutoWiringManifest(
        contracts=[
            c for c in owned.contracts if c.name not in NODES_WITHOUT_A_LIVE_SUPPLIER
        ]
    )


async def _wire(container: ModelONEXContainer) -> Any:
    return await wire_from_manifest(
        manifest=_dev_lane_manifest(),
        dispatch_engine=MessageDispatchEngine(),
        event_bus=None,
        container=container,
        subscribe_immediately=False,
    )


async def _registered(
    container: ModelONEXContainer,
    *,
    debug_store: Any,
    repository: Any,
    llm_client: Any,
) -> list[str]:
    return await register_contract_handler_dependencies(
        container,
        debug_store=debug_store,
        pattern_repository=repository,
        kafka_publisher=None,
        classification_config=ModelClassificationConfig(),
        llm_client=llm_client,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unregistered_dependencies_fail_the_loader_with_the_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failing control: with no registration the loader raises the dev boot error."""
    monkeypatch.setenv("ONEX_WIRING_STRICT_MODE", "1")
    with pytest.raises(TypeError, match="requires constructor parameters"):
        await _wire(ModelONEXContainer())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_registered_dependencies_let_every_announced_handler_construct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict wiring over the whole package reports no failure and wires handlers."""
    monkeypatch.setenv("ONEX_WIRING_STRICT_MODE", "1")
    container = ModelONEXContainer()
    await _registered(
        container, debug_store=_Store(), repository=_Repository(), llm_client=None
    )
    report = await _wire(container)
    assert report.total_failed == 0
    assert report.total_wired > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_registered_handlers_receive_the_given_dependencies() -> None:
    """Each registered instance holds the dependency the plugin handed in."""
    container = ModelONEXContainer()
    store, repository, llm_client = _Store(), _Repository(), _LlmClient()
    await _registered(
        container, debug_store=store, repository=repository, llm_client=llm_client
    )
    assert container.get_service(HandlerStreak)._store is store
    assert container.get_service(HandlerTriggerRecord)._store is store
    assert container.get_service(HandlerPromotion)._repository is repository
    assert isinstance(
        container.get_service(HandlerIntentClassification)._config,
        ModelClassificationConfig,
    )
    assert container.get_service(HandlerEvaluateCompliance)._llm_client is llm_client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unregistered_handlers_are_exactly_the_nodes_without_a_live_supplier() -> (
    None
):
    """Discovered, not listed: what needs arguments and is not registered is named."""
    registered = set(
        await _registered(
            ModelONEXContainer(),
            debug_store=_Store(),
            repository=_Repository(),
            llm_client=None,
        )
    )
    unregistered_nodes: set[str] = set()
    needing: set[str] = set()
    for contract in _manifest().contracts:
        if contract.handler_routing is None:
            continue
        for entry in contract.handler_routing.handlers:
            handler_cls = _import_handler_class(
                entry.handler.module, entry.handler.name
            )
            if not _required_handler_init_params(handler_cls):
                continue
            needing.add(entry.handler.name)
            if entry.handler.name not in registered:
                unregistered_nodes.add(contract.name)
    assert needing, "no handler with required parameters found: discovery is broken"
    assert registered <= needing, (
        f"registered but not needed: {sorted(registered - needing)}"
    )
    assert unregistered_nodes == set(NODES_WITHOUT_A_LIVE_SUPPLIER), (
        "handlers the loader cannot construct and the plugin does not register: "
        f"{sorted(unregistered_nodes)}; named without a supplier: "
        f"{sorted(NODES_WITHOUT_A_LIVE_SUPPLIER)}"
    )


@pytest.mark.unit
def test_the_dev_lane_filter_drops_only_the_named_nodes() -> None:
    """The mirrored deployment exclusion removes the named nodes and nothing else."""
    full = {c.name for c in _manifest().contracts}
    kept = {c.name for c in _dev_lane_manifest().contracts}
    assert full - kept == set(NODES_WITHOUT_A_LIVE_SUPPLIER)
