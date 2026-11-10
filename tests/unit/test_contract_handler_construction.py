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
stay offline. No skip: an announced handler with a required parameter that the
runtime does not supply fails here.

The runtime image removes this package's ``onex.domain_plugins`` entry points
(``omnibase_infra.runtime.strip_runtime_entry_points``), so ``PluginIntelligence``
never runs there and ``register_contract_handler_dependencies`` registers nothing
(deploy agent job d9d269d6: the boot failed on ``HandlerStreak`` ``['store']`` with
the plugin's registration merged). The wiring tests therefore use a plain
container, as the runtime does. Four nodes have no supplier the runtime image can
reach (see ``NODES_WITHOUT_A_LIVE_SUPPLIER``). They are left out of the package's
``onex.nodes`` entry points — the set the dev boot announcer reads to discover
contracts — so the runtime never loads them (OMN-23509); the dev-lane manifest
here is the kernel's profile filter run over exactly that announced set, and a
companion test fails the moment a node the loader refuses is not named.

Ticket: OMN-23431, OMN-23510, OMN-23516
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
from omnibase_core.models.container.model_onex_container import ModelONEXContainer
from omnibase_infra.runtime import strip_runtime_entry_points as runtime_strip_policy
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
from omnibase_infra.runtime.auto_wiring.report import EnumWiringOutcome
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
PYPROJECT = Path(__file__).parent.parent.parent / "pyproject.toml"
CONTRACT_PATHS = sorted(NODES_DIR.glob("*/contract.yaml"))


# Nodes whose handler needs a constructor argument that nothing the runtime image
# carries can build today. Each is left out of the onex.nodes entry points
# (OMN-23509), so the runtime never loads it; an entry is removed in the change that
# registers a live supplier for it and restores the entry point.
NODES_WITHOUT_A_LIVE_SUPPLIER: dict[str, str] = {
    "node_ci_failure_tracker_effect": (
        "HandlerStreak and HandlerTriggerRecord need the debug store; only the "
        "intelligence plugin builds it and the runtime image strips that plugin"
    ),
    "node_pattern_promotion_effect": (
        "HandlerPromotion needs the pattern repository; only the intelligence "
        "plugin builds it and the runtime image strips that plugin"
    ),
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


def _announced_node_dirs() -> set[str]:
    """The node directories the package's ``onex.nodes`` entry points announce.

    This is the table the dev boot announcer reads to discover contracts. One key
    (``node_audit``) maps to a value whose last segment is not the key, so the
    directory name is taken from each value's last dotted segment, not each key.
    """
    data = tomllib.loads(PYPROJECT.read_text())
    values = data["project"]["entry-points"]["onex.nodes"].values()
    return {value.rsplit(".", 1)[-1] for value in values}


def _announced_manifest() -> ModelAutoWiringManifest:
    """The contracts the runtime would discover from the announced entry points."""
    announced = [p for p in CONTRACT_PATHS if p.parent.name in _announced_node_dirs()]
    discovered = discover_contracts_from_paths(announced)
    assert [e.error for e in discovered.errors] == []
    return ModelAutoWiringManifest(contracts=list(discovered.contracts))


def _dev_lane_manifest() -> ModelAutoWiringManifest:
    """The manifest the dev lane's main runtime wires.

    The kernel's own ownership filter (profile, folded profiles, lane) runs over
    the announced manifest — the announced set comes from the package's
    ``onex.nodes`` entry points, exactly what the boot announcer reads — and no
    node is dropped by name here.
    """
    return filter_manifest_for_runtime_profile(
        _announced_manifest(), "main", environ=_DEV_LANE_ENV
    ).manifest


async def _wire_manifest(
    manifest: ModelAutoWiringManifest, container: ModelONEXContainer
) -> Any:
    return await wire_from_manifest(
        manifest=manifest,
        dispatch_engine=MessageDispatchEngine(),
        event_bus=None,
        container=container,
        subscribe_immediately=False,
    )


async def _wire(container: ModelONEXContainer) -> Any:
    return await _wire_manifest(_dev_lane_manifest(), container)


def _full_dev_lane_manifest() -> ModelAutoWiringManifest:
    """Every contract on disk through the profile filter: announced or not."""
    return filter_manifest_for_runtime_profile(
        _manifest(), "main", environ=_DEV_LANE_ENV
    ).manifest


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
    """Failing control: announce every contract and the loader raises the dev boot error."""
    monkeypatch.setenv("ONEX_WIRING_STRICT_MODE", "1")
    with pytest.raises(TypeError, match="requires constructor parameters"):
        await _wire_manifest(_full_dev_lane_manifest(), ModelONEXContainer())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_announced_handlers_construct_with_only_what_the_runtime_supplies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strict wiring of the announced set over a plain container reports no failure."""
    monkeypatch.setenv("ONEX_WIRING_STRICT_MODE", "1")
    report = await _wire(ModelONEXContainer())
    assert report.total_failed == 0
    assert report.total_wired > 0
    assert len(report.results) == len(_dev_lane_manifest().contracts)
    assert [
        (r.contract_name, str(r.outcome))
        for r in report.results
        if r.outcome not in {EnumWiringOutcome.WIRED, EnumWiringOutcome.SKIPPED}
    ] == []


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
async def test_nodes_the_loader_refuses_are_exactly_named_as_without_a_supplier() -> (
    None
):
    """Discovered, not listed: what a plain container cannot build is named.

    The full manifest is wired without strict mode, so the loader quarantines each
    handler it cannot build instead of raising on the first. Every refused node is
    named in ``NODES_WITHOUT_A_LIVE_SUPPLIER``, and every named node really has a
    handler with a required constructor parameter, so a stale entry fails too.
    """
    report = await _wire_manifest(_full_dev_lane_manifest(), ModelONEXContainer())
    refused = {q.contract_name for q in report.quarantined_handlers}
    assert refused, "the loader refused nothing: discovery or the control is broken"
    assert refused <= set(NODES_WITHOUT_A_LIVE_SUPPLIER), (
        "nodes the runtime loader cannot build and the package still announces or "
        f"does not name: {sorted(refused - set(NODES_WITHOUT_A_LIVE_SUPPLIER))}"
    )
    needing: set[str] = set()
    for contract in _manifest().contracts:
        if contract.handler_routing is None:
            continue
        for entry in contract.handler_routing.handlers:
            handler_cls = _import_handler_class(
                entry.handler.module, entry.handler.name
            )
            if _required_handler_init_params(handler_cls):
                needing.add(contract.name)
    assert set(NODES_WITHOUT_A_LIVE_SUPPLIER) <= needing, (
        "named without a supplier but no handler needs one: "
        f"{sorted(set(NODES_WITHOUT_A_LIVE_SUPPLIER) - needing)}"
    )


@pytest.mark.unit
def test_runtime_image_strips_the_intelligence_plugin() -> None:
    """The plugin is not a supplier in the runtime image: read from the image's own policy."""
    kept = getattr(runtime_strip_policy, "DEFAULT_KEPT_GROUPS", {})
    assert "onex.domain_plugins" in runtime_strip_policy.DEFAULT_STRIPPED_GROUPS
    assert "onex.domain_plugins" not in kept.get(
        "omninode-intelligence", frozenset()
    ), (
        "the runtime image keeps the intelligence plugin: it can supply the "
        "handlers' stores there, and NODES_WITHOUT_A_LIVE_SUPPLIER may be revisited"
    )


@pytest.mark.unit
def test_excluded_nodes_are_excluded_by_declaration() -> None:
    """Left out by the package's declared entry points, not by deletion, profile or accident."""
    assert set(NODES_WITHOUT_A_LIVE_SUPPLIER).isdisjoint(_announced_node_dirs())
    for name in NODES_WITHOUT_A_LIVE_SUPPLIER:
        assert (NODES_DIR / name / "contract.yaml").is_file(), (
            f"{name} was deleted instead of being left unannounced"
        )
        declaration = next(
            (
                line
                for line in PYPROJECT.read_text().splitlines()
                if f"# not announced: {name} (" in line
            ),
            "",
        )
        assert declaration, f"pyproject.toml has no '# not announced: {name}' line"
        assert "OMN-23509" in declaration, (
            f"the exclusion declaration for {name} does not cite OMN-23509"
        )
    profile_keeps = {
        c.name
        for c in filter_manifest_for_runtime_profile(
            _manifest(), "main", environ=_DEV_LANE_ENV
        ).manifest.contracts
    }
    assert set(NODES_WITHOUT_A_LIVE_SUPPLIER) <= profile_keeps, (
        "the profile filter alone already removes an excluded node: the entry-point "
        f"declaration is not what keeps it out (profile keeps {sorted(profile_keeps)})"
    )
    assert {c.name for c in _dev_lane_manifest().contracts}.isdisjoint(
        NODES_WITHOUT_A_LIVE_SUPPLIER
    )
