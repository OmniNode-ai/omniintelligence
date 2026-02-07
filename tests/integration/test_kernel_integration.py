# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Integration test: kernel boots with intelligence plugin.

Validates the complete wiring path from contract discovery to handler
resolution for all 17 omniintelligence nodes. Uses EventBusInmemory
for topic subscription verification — no Docker or external services.

Test Phases:
    1. Contract Discovery — find all 17 node contracts
    2. Handler Import Resolution — verify all handler modules/functions import
    3. I/O Model Import Resolution — verify input/output models import
    4. EventBusInmemory Topic Wiring — subscribe to all intelligence topics
    5. Message Round-Trip — verify EventBus can deliver messages

Exit Criteria (OMN-1978):
    - Test passes in CI without Docker or external services
    - Validates the complete wiring path from kernel -> plugin -> handlers

Ticket: OMN-1978
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from omnibase_infra.event_bus.event_bus_inmemory import EventBusInmemory
from omnibase_infra.models import ModelNodeIdentity

# =============================================================================
# Constants
# =============================================================================

# Path to the nodes directory containing all 17 ONEX node contracts.
# Resolved relative to this test file to work in both local and CI environments.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
NODES_DIR = _PROJECT_ROOT / "src" / "omniintelligence" / "nodes"

# Total number of node contracts expected in this repository.
EXPECTED_CONTRACT_COUNT = 17

# Node types exempt from handler_routing (use workflow_coordination / inline FSM).
HANDLER_ROUTING_EXEMPT_TYPES = frozenset({"ORCHESTRATOR_GENERIC", "REDUCER_GENERIC"})

# node_pattern_assembler_orchestrator IS an orchestrator but declares handler_routing,
# so it is NOT exempt. Only the two generic types above are exempt.
NODES_WITH_HANDLER_ROUTING_OVERRIDE = frozenset({"node_pattern_assembler_orchestrator"})


# =============================================================================
# Helpers
# =============================================================================


def _discover_contracts() -> list[tuple[Path, dict[str, Any]]]:
    """Discover and parse all contract.yaml files in the nodes directory.

    Returns:
        Sorted list of (path, parsed_yaml) tuples.
    """
    contracts: list[tuple[Path, dict[str, Any]]] = []
    for contract_path in sorted(NODES_DIR.glob("*/contract.yaml")):
        with open(contract_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            continue
        contracts.append((contract_path, data))
    return contracts


def _extract_handler_entry_points(
    data: dict[str, Any],
) -> list[tuple[str, str]]:
    """Extract (module, function_or_class) pairs from handler_routing.

    Handles both contract formats:
        - Standard: handlers[].handler.{module, function}
        - Legacy:   handlers[].{handler_module, handler_class}

    Also extracts entry_point and default_handler when present.

    Returns:
        List of (module_path, attribute_name) tuples.
    """
    handler_routing = data.get("handler_routing")
    if not handler_routing:
        return []

    entry_points: list[tuple[str, str]] = []

    # entry_point (if present)
    ep = handler_routing.get("entry_point")
    if ep and isinstance(ep, dict):
        module = ep.get("module", "")
        function = ep.get("function", "")
        if module and function:
            entry_points.append((module, function))

    # handlers list
    for handler_def in handler_routing.get("handlers", []):
        # Standard format: handler: {module, function}
        handler_inner = handler_def.get("handler")
        if isinstance(handler_inner, dict):
            module = handler_inner.get("module", "")
            function = handler_inner.get("function", "")
            if module and function:
                entry_points.append((module, function))
        else:
            # Legacy format: handler_module + handler_class
            module = handler_def.get("handler_module", "")
            cls = handler_def.get("handler_class", "")
            if module and cls:
                entry_points.append((module, cls))

    # default_handler (if present)
    dh = handler_routing.get("default_handler")
    if dh and isinstance(dh, dict):
        module = dh.get("module", "")
        function = dh.get("function", "")
        if module and function:
            entry_points.append((module, function))

    return entry_points


def _extract_io_models(
    data: dict[str, Any],
) -> list[tuple[str, str]]:
    """Extract (module, class_name) pairs for input/output models.

    Returns:
        List of (module_path, class_name) tuples.
    """
    models: list[tuple[str, str]] = []

    for model_key in ("input_model", "output_model"):
        model_def = data.get(model_key)
        if isinstance(model_def, dict):
            module = model_def.get("module", "")
            name = model_def.get("name", "")
            if module and name:
                models.append((module, name))

    return models


def _extract_subscribe_topics(data: dict[str, Any]) -> list[str]:
    """Extract subscribe_topics from event_bus configuration.

    Returns:
        List of topic strings, empty if event_bus is disabled.
    """
    event_bus = data.get("event_bus") or {}
    if not event_bus.get("event_bus_enabled"):
        return []
    return event_bus.get("subscribe_topics") or []


def _extract_publish_topics(data: dict[str, Any]) -> list[str]:
    """Extract publish_topics from event_bus configuration.

    Returns:
        List of topic strings, empty if event_bus is disabled.
    """
    event_bus = data.get("event_bus") or {}
    if not event_bus.get("event_bus_enabled"):
        return []
    return event_bus.get("publish_topics") or []


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.integration
class TestKernelBootsWithIntelligencePlugin:
    """Validate the complete wiring path: kernel -> plugin -> handlers.

    These tests simulate the kernel boot sequence by exercising each
    phase of the plugin lifecycle:
        1. Discovery (find contracts)
        2. Import resolution (handlers + models)
        3. Topic wiring (EventBusInmemory subscriptions)
        4. Message delivery (round-trip verification)
    """

    @pytest.fixture(scope="class")
    def contracts(self) -> list[tuple[Path, dict[str, Any]]]:
        """Discover all 17 node contracts."""
        return _discover_contracts()

    # -----------------------------------------------------------------
    # Phase 1: Contract Discovery
    # -----------------------------------------------------------------

    def test_discovers_all_17_contracts(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """All 17 intelligence node contracts must be discoverable."""
        assert len(contracts) == EXPECTED_CONTRACT_COUNT, (
            f"Expected {EXPECTED_CONTRACT_COUNT} contracts, "
            f"found {len(contracts)}: "
            f"{[p.parent.name for p, _ in contracts]}"
        )

    def test_every_contract_has_name_and_node_type(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Every contract must declare name and node_type fields."""
        errors: list[str] = []
        for path, data in contracts:
            node_dir = path.parent.name
            if "name" not in data:
                errors.append(f"{node_dir}: missing 'name'")
            if "node_type" not in data:
                errors.append(f"{node_dir}: missing 'node_type'")
        assert not errors, "Contract field errors:\n" + "\n".join(errors)

    def test_handler_routing_present_where_required(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Compute and effect nodes must have handler_routing.

        Orchestrators and reducers are exempt unless they opt in
        (e.g., node_pattern_assembler_orchestrator).
        """
        errors: list[str] = []
        for path, data in contracts:
            node_name = data.get("name", path.parent.name)
            node_type = data.get("node_type", "")
            has_routing = bool(data.get("handler_routing"))

            if node_type in HANDLER_ROUTING_EXEMPT_TYPES:
                # Exempt — but still fine if they have it
                if node_name in NODES_WITH_HANDLER_ROUTING_OVERRIDE and not has_routing:
                    errors.append(
                        f"{node_name}: expected handler_routing override for orchestrator"
                    )
            elif not has_routing:
                errors.append(f"{node_name} ({node_type}): missing handler_routing")

        assert not errors, "handler_routing errors:\n" + "\n".join(errors)

    # -----------------------------------------------------------------
    # Phase 2: Handler Import Resolution
    # -----------------------------------------------------------------

    def test_all_handler_modules_are_importable(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Every handler module declared in handler_routing must be importable."""
        errors: list[str] = []
        seen_modules: set[str] = set()

        for path, data in contracts:
            node_name = data.get("name", path.parent.name)
            entry_points = _extract_handler_entry_points(data)

            for module_path, attr_name in entry_points:
                if module_path in seen_modules:
                    continue
                seen_modules.add(module_path)

                try:
                    importlib.import_module(module_path)
                except ImportError as e:
                    errors.append(f"{node_name}: cannot import {module_path} ({e})")

        assert not errors, "Handler import errors:\n" + "\n".join(errors)

    def test_all_handler_functions_exist(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Every handler function/class declared in contracts must exist in its module."""
        errors: list[str] = []

        for path, data in contracts:
            node_name = data.get("name", path.parent.name)
            entry_points = _extract_handler_entry_points(data)

            for module_path, attr_name in entry_points:
                try:
                    mod = importlib.import_module(module_path)
                except ImportError:
                    continue  # Import errors caught in separate test

                if not hasattr(mod, attr_name):
                    errors.append(
                        f"{node_name}: {attr_name} not found in {module_path}"
                    )

        assert not errors, "Handler attribute errors:\n" + "\n".join(errors)

    def test_handler_count_matches_expected(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """At least 15 nodes must resolve at least one handler entry point.

        17 total - 2 exempt (orchestrator, reducer) = 15 minimum with handlers.
        """
        nodes_with_handlers = 0
        for _path, data in contracts:
            entry_points = _extract_handler_entry_points(data)
            if entry_points:
                nodes_with_handlers += 1

        # 15 = 17 total - 1 orchestrator (no routing) - 1 reducer (no routing)
        assert nodes_with_handlers >= 15, (
            f"Expected at least 15 nodes with handler entry points, "
            f"found {nodes_with_handlers}"
        )

    # -----------------------------------------------------------------
    # Phase 3: I/O Model Import Resolution
    # -----------------------------------------------------------------

    def test_all_io_models_are_importable(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Every input_model and output_model must be importable."""
        errors: list[str] = []

        for path, data in contracts:
            node_name = data.get("name", path.parent.name)
            models = _extract_io_models(data)

            for module_path, class_name in models:
                try:
                    mod = importlib.import_module(module_path)
                except ImportError as e:
                    errors.append(
                        f"{node_name}: cannot import model module {module_path} ({e})"
                    )
                    continue

                if not hasattr(mod, class_name):
                    errors.append(
                        f"{node_name}: {class_name} not found in {module_path}"
                    )

        assert not errors, "I/O model import errors:\n" + "\n".join(errors)

    # -----------------------------------------------------------------
    # Phase 4: EventBusInmemory Topic Wiring
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_intelligence_topics_are_subscribable(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """All subscribe_topics from effect node contracts must wire to EventBusInmemory."""
        # Collect all subscribe topics across all contracts
        all_subscribe_topics: list[str] = []
        for _path, data in contracts:
            all_subscribe_topics.extend(_extract_subscribe_topics(data))

        assert len(all_subscribe_topics) > 0, (
            "No subscribe_topics found in any contract — "
            "expected at least 1 effect node with event_bus_enabled"
        )

        # Boot EventBusInmemory and subscribe to all topics
        bus = EventBusInmemory(environment="test", group="kernel-integration")
        await bus.start()

        try:
            identity = ModelNodeIdentity(
                env="test",
                service="omniintelligence",
                node_name="kernel-integration-test",
                version="v1",
            )

            unsubscribes = []
            for topic in all_subscribe_topics:

                async def _noop_handler(msg: Any) -> None:
                    pass

                unsub = await bus.subscribe(topic, identity, _noop_handler)
                unsubscribes.append(unsub)

            # Verify all subscriptions succeeded (no exceptions raised)
            assert len(unsubscribes) == len(all_subscribe_topics)

            for unsub in unsubscribes:
                await unsub()
        finally:
            await bus.close()

    @pytest.mark.asyncio
    async def test_intelligence_topics_publish_subscribe_roundtrip(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify publish/subscribe round-trip on intelligence topics."""
        # Collect all publish topics (outbound events from effect nodes)
        all_publish_topics: list[str] = []
        for _path, data in contracts:
            all_publish_topics.extend(_extract_publish_topics(data))

        if not all_publish_topics:
            pytest.skip("No publish_topics found")

        bus = EventBusInmemory(environment="test", group="kernel-roundtrip")
        await bus.start()

        try:
            identity = ModelNodeIdentity(
                env="test",
                service="omniintelligence",
                node_name="roundtrip-test",
                version="v1",
            )

            # Subscribe to first publish topic and verify message delivery
            received: list[Any] = []
            test_topic = all_publish_topics[0]

            async def _capture_handler(msg: Any) -> None:
                received.append(msg)

            unsub = await bus.subscribe(test_topic, identity, _capture_handler)

            # Publish a test message
            await bus.publish(
                test_topic,
                b"test-correlation-id",
                b'{"event_type": "test", "correlation_id": "00000000-0000-0000-0000-000000000000"}',
            )

            # Wait for message delivery with condition polling instead of fixed sleep
            for _ in range(50):
                if received:
                    break
                await asyncio.sleep(0.01)

            assert len(received) == 1, (
                f"Expected 1 message on {test_topic}, received {len(received)}"
            )

            await unsub()
        finally:
            await bus.close()

    # -----------------------------------------------------------------
    # Phase 5: Wiring Inventory Assertions
    # -----------------------------------------------------------------

    def test_effect_nodes_have_event_bus_enabled(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """All EFFECT_GENERIC nodes must have event_bus.event_bus_enabled: true."""
        errors: list[str] = []
        effect_count = 0

        for _path, data in contracts:
            node_name = data.get("name", "unknown")
            node_type = data.get("node_type", "")

            if node_type != "EFFECT_GENERIC":
                continue

            effect_count += 1
            event_bus = data.get("event_bus") or {}
            if not event_bus.get("event_bus_enabled"):
                errors.append(f"{node_name}: EFFECT_GENERIC without event_bus_enabled")

        assert effect_count > 0, "No EFFECT_GENERIC nodes found"
        assert not errors, "Effect node event_bus errors:\n" + "\n".join(errors)

    def test_no_duplicate_contract_names(
        self, contracts: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Contract names must be unique across all nodes."""
        names: dict[str, str] = {}
        duplicates: list[str] = []

        for path, data in contracts:
            name = data.get("name", "")
            node_dir = path.parent.name
            if name in names:
                duplicates.append(f"'{name}' in both {names[name]} and {node_dir}")
            else:
                names[name] = node_dir

        assert not duplicates, "Duplicate contract names:\n" + "\n".join(duplicates)
