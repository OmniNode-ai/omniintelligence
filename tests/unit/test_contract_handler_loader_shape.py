# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Every omniintelligence node contract loads through the infra handler loader.

The one runtime auto-wires a package's contracts through
``omnibase_infra.runtime.auto_wiring``. That loader reads each
``handler_routing.handlers[].handler`` as ``{name, module}`` and imports ``name`` as a
handler CLASS. A contract that declares ``function:`` or ``class:`` instead gives the
loader an empty name, and the runtime fails to boot with
``CLASS_NOT_FOUND (HANDLER_LOADER_011)``.

This test runs the loader's own discovery and class import over every node contract
shipped in this package, so a contract that the runtime would reject fails here first.

Ticket: OMN-23422, OMN-23486
"""

from __future__ import annotations

from pathlib import Path

import pytest
from omnibase_core.models.resolver.model_handler_resolver_context import (
    ModelHandlerResolverContext,
)
from omnibase_core.services.service_handler_resolver import ServiceHandlerResolver
from omnibase_infra.runtime.auto_wiring.discovery import discover_contracts_from_paths
from omnibase_infra.runtime.auto_wiring.handler_wiring import _import_handler_class

NODES_DIR = Path(__file__).parent.parent.parent / "src" / "omniintelligence" / "nodes"

CONTRACT_PATHS = sorted(NODES_DIR.glob("*/contract.yaml"))


def _handler_entries() -> list[tuple[str, str, str]]:
    """Return (node, module, name) for every routed handler the loader parses."""
    manifest = discover_contracts_from_paths(CONTRACT_PATHS)
    entries: list[tuple[str, str, str]] = []
    for contract in manifest.contracts:
        if contract.handler_routing is None:
            continue
        entries.extend(
            (contract.name, e.handler.module, e.handler.name)
            for e in contract.handler_routing.handlers
        )
    return entries


@pytest.mark.unit
def test_all_node_contracts_are_discovered() -> None:
    """The contract set under test is the whole package, not a subset."""
    assert len(CONTRACT_PATHS) >= 75


@pytest.mark.unit
def test_every_node_contract_parses_in_the_loader() -> None:
    """No contract is dropped by the loader's parser (fail-closed OMN-14141)."""
    manifest = discover_contracts_from_paths(CONTRACT_PATHS)
    assert [e.error for e in manifest.errors] == []
    assert len(manifest.contracts) == len(CONTRACT_PATHS)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("node", "module", "name"),
    _handler_entries(),
    ids=lambda v: str(v).rsplit(".", 1)[-1],
)
def test_every_declared_handler_is_a_loadable_class(
    node: str, module: str, name: str
) -> None:
    """Each handler entry names a class the runtime can import and dispatch to."""
    assert name, f"{node}: handler entry has no name (HANDLER_LOADER_011)"
    handler_cls = _import_handler_class(module, name)
    assert isinstance(handler_cls, type), f"{node}: {module}.{name} is not a class"
    assert callable(getattr(handler_cls, "handle", None)) or callable(
        getattr(handler_cls, "handle_async", None)
    ), f"{node}: {module}.{name} has neither handle nor handle_async"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("node", "module", "name"),
    _handler_entries(),
    ids=lambda v: str(v).rsplit(".", 1)[-1],
)
def test_every_declared_handler_is_built_by_the_runtime_resolver(
    node: str, module: str, name: str
) -> None:
    """The runtime's handler resolver builds each handler from what it supplies.

    The resolver hands a handler only the event bus, the container and the
    ownership query (and any explicit dependency map a node registry builds). A
    handler class with another required constructor parameter makes the resolver
    raise ``TypeError`` and the runtime stops booting (dev roll of 2026-11-10T07:30Z,
    ``HandlerStreak`` requires ``store``). The context here supplies all three
    runtime objects and no explicit dependency map, which is the most the
    runtime offers these nodes.
    """
    handler_cls = _import_handler_class(module, name)
    context = ModelHandlerResolverContext(
        handler_cls=handler_cls,
        handler_module=module,
        handler_name=name,
        contract_name=node,
        node_name=node,
        event_bus=object(),
        container=object(),
        ownership_query=object(),
    )
    resolution = ServiceHandlerResolver().resolve(context)
    assert resolution.handler_instance is not None, f"{node}: {module}.{name}"
