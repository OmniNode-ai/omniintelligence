# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Binds a handler through the node contract that declares it (OMN-21679).

A caller names the operation and the type it expects, never the class it builds.
The node's ``contract.yaml`` ``handler_routing`` section names the handler module
and class for that operation, and this binding resolves the class from the
contract and hands back the instance, so the contract stays the one place a
handler is bound. The node is the one whose package holds the expected handler
type, unless the caller names it.
The contract is read as a package resource and the node package is not imported
until the handler itself is resolved.
"""

from __future__ import annotations

import importlib
import importlib.resources
from functools import cache
from typing import TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field

THandler = TypeVar("THandler")


def _load_contract(content: str) -> object:
    """Parse a contract with LibYAML's safe loader when it is available."""
    if yaml.__with_libyaml__:
        return yaml.load(content, Loader=yaml.CSafeLoader)
    return yaml.safe_load(content)


@cache
def _routed_handlers(contracts_package: str, node: str) -> dict[str, tuple[str, str]]:
    """Map each operation of the node's ``handler_routing`` to its (module, class)."""
    contract_file = importlib.resources.files(contracts_package).joinpath(
        node, "contract.yaml"
    )
    contract = _load_contract(contract_file.read_text())
    routing = contract.get("handler_routing") if isinstance(contract, dict) else None
    entries = routing.get("handlers") if isinstance(routing, dict) else None
    routed: dict[str, tuple[str, str]] = {}
    for entry in entries if isinstance(entries, list) else []:
        handler = entry.get("handler") if isinstance(entry, dict) else None
        if (
            isinstance(handler, dict)
            and isinstance(entry.get("operation"), str)
            and isinstance(handler.get("module"), str)
            and isinstance(handler.get("class"), str)
        ):
            routed[entry["operation"]] = (handler["module"], handler["class"])
    return routed


class ModelContractHandlerBinding(BaseModel):
    """Resolves the handler a node contract binds to an operation.

    Attributes:
        nodes_package: Package holding one directory per node.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    nodes_package: str = Field(default="omniintelligence.nodes", min_length=1)

    def bind(
        self,
        operation: str,
        handler_type: type[THandler],
        *,
        node: str | None = None,
        **dependencies: object,
    ) -> THandler:
        """Return the handler the node contract declares for ``operation``.

        Args:
            operation: Operation name in the contract's ``handler_routing``.
            handler_type: Type the bound handler must be an instance of.
            node: Node directory name, e.g. ``"node_ci_fingerprint_compute"``;
                defaults to the node package that holds ``handler_type``.
            **dependencies: Constructor dependencies injected into the handler.

        Raises:
            LookupError: The contract declares no handler for the operation, or
                ``handler_type`` sits in no node package and no node was named.
            TypeError: The declared class is not a ``handler_type``.
        """
        node = node or self._node_of(handler_type)
        routed = _routed_handlers(self.nodes_package, node).get(operation)
        if routed is None:
            raise LookupError(
                f"{node} contract.yaml handler_routing declares no handler for "
                f"operation={operation!r}"
            )
        module_name, class_name = routed
        bound = getattr(importlib.import_module(module_name), class_name)
        if not (isinstance(bound, type) and issubclass(bound, handler_type)):
            raise TypeError(
                f"{node} contract.yaml binds {module_name}.{class_name} to "
                f"operation={operation!r}, which is not a {handler_type.__name__}"
            )
        return bound(**dependencies)

    def _node_of(self, handler_type: type) -> str:
        """The node directory whose package holds ``handler_type``."""
        prefix = f"{self.nodes_package}."
        module = handler_type.__module__
        if not module.startswith(prefix):
            raise LookupError(
                f"{handler_type.__qualname__} sits outside {self.nodes_package}; "
                "name its node"
            )
        return module.removeprefix(prefix).split(".", 1)[0]
