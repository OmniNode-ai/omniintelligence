# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Contract handler import validation tests.

This module validates that all handler paths declared in contract.yaml files
are importable at runtime. This prevents silent failures when HandlerPluginLoader
or ContractLoader attempts to resolve handler functions via importlib.

Validates:
1. handler_routing module paths resolve via importlib.import_module()
2. handler_routing function/class names exist as attributes on the resolved module
3. input_model and output_model paths resolve and contain the declared class

Ticket: OMN-1975
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml

# =========================================================================
# Constants
# =========================================================================

NODES_DIR = Path("src/omniintelligence/nodes")

# Node types that are NOT expected to have handler_routing.
# Declarative orchestrators use workflow_coordination instead.
# Reducers use inline handler delegation.
HANDLER_ROUTING_EXEMPT_TYPES = {"ORCHESTRATOR_GENERIC", "REDUCER_GENERIC"}


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def nodes_dir(project_root: Path) -> Path:
    """Get the nodes directory."""
    return project_root / NODES_DIR


@pytest.fixture
def all_contracts(nodes_dir: Path) -> list[Path]:
    """Discover all contract YAML files in the nodes directory."""
    if not nodes_dir.exists():
        pytest.skip(f"Nodes directory not found: {nodes_dir}")
    contracts = list(nodes_dir.glob("*/contract.yaml"))
    if not contracts:
        pytest.skip(f"No contract.yaml files found in {nodes_dir}")
    return sorted(contracts)


@pytest.fixture
def all_contract_data(all_contracts: list[Path]) -> list[tuple[Path, dict[str, Any]]]:
    """Load all contracts and return path-data pairs."""
    result = []
    for contract_path in all_contracts:
        with open(contract_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        result.append((contract_path, data))
    return result


# =========================================================================
# Handler Import Validation Tests
# =========================================================================


@pytest.mark.unit
class TestContractHandlerImports:
    """Validate that all handler paths declared in contracts are importable.

    These tests run unconditionally (not behind a flag) because handler
    path validity is a runtime correctness requirement. A broken handler
    path means the node silently fails to load at deploy time.
    """

    def test_handler_routing_modules_are_importable(
        self, all_contract_data: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify every handler_routing module path resolves via importlib."""
        errors: list[str] = []

        for contract_path, data in all_contract_data:
            node_name = data.get("name", contract_path.parent.name)
            handler_routing = data.get("handler_routing")

            if handler_routing is None:
                continue

            handlers = handler_routing.get("handlers", [])
            for handler_entry in handlers:
                handler_config = handler_entry.get("handler", {})
                module_path = handler_config.get(
                    "module", handler_entry.get("handler_module", "")
                )

                if not module_path:
                    errors.append(
                        f"{node_name}: handler_routing entry for operation "
                        f"'{handler_entry.get('operation', '?')}' has no module path"
                    )
                    continue

                try:
                    importlib.import_module(module_path)
                except ImportError as e:
                    errors.append(
                        f"{node_name}: Cannot import handler module "
                        f"'{module_path}': {e}"
                    )

        if errors:
            pytest.fail(
                f"Handler module import failures ({len(errors)}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_handler_routing_functions_exist(
        self, all_contract_data: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify every handler function/class declared in contracts exists."""
        errors: list[str] = []

        for contract_path, data in all_contract_data:
            node_name = data.get("name", contract_path.parent.name)
            handler_routing = data.get("handler_routing")

            if handler_routing is None:
                continue

            handlers = handler_routing.get("handlers", [])
            for handler_entry in handlers:
                handler_config = handler_entry.get("handler", {})
                module_path = handler_config.get(
                    "module", handler_entry.get("handler_module", "")
                )
                function_name = handler_config.get(
                    "function", handler_entry.get("handler_class", "")
                )

                if not module_path or not function_name:
                    continue

                try:
                    module = importlib.import_module(module_path)
                except ImportError:
                    # Already caught by test_handler_routing_modules_are_importable
                    continue

                if not hasattr(module, function_name):
                    errors.append(
                        f"{node_name}: Handler '{function_name}' not found in "
                        f"module '{module_path}' (operation: "
                        f"'{handler_entry.get('operation', '?')}')"
                    )

        if errors:
            pytest.fail(
                f"Handler function/class not found ({len(errors)}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_model_imports_resolve(
        self, all_contract_data: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify input_model and output_model paths resolve via importlib."""
        errors: list[str] = []

        for contract_path, data in all_contract_data:
            node_name = data.get("name", contract_path.parent.name)

            for model_key in ["input_model", "output_model"]:
                model_info = data.get(model_key, {})
                module_path = model_info.get("module", "")
                model_name = model_info.get("name", "")

                if not module_path or not model_name:
                    continue

                try:
                    module = importlib.import_module(module_path)
                except ImportError as e:
                    errors.append(
                        f"{node_name}: Cannot import {model_key} module "
                        f"'{module_path}': {e}"
                    )
                    continue

                if not hasattr(module, model_name):
                    errors.append(
                        f"{node_name}: {model_key} class '{model_name}' not found "
                        f"in module '{module_path}'"
                    )

        if errors:
            pytest.fail(
                f"Model import failures ({len(errors)}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_all_nodes_have_handler_routing_or_exemption(
        self, all_contract_data: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify every node has handler_routing unless it's an exempt type.

        Orchestrators may use workflow_coordination instead.
        Reducers may use inline handler delegation.
        All other node types must declare handler_routing.
        """
        missing: list[str] = []

        for contract_path, data in all_contract_data:
            node_name = data.get("name", contract_path.parent.name)
            node_type = data.get("node_type", "")
            has_handler_routing = "handler_routing" in data

            if (
                not has_handler_routing
                and node_type not in HANDLER_ROUTING_EXEMPT_TYPES
            ):
                missing.append(
                    f"{node_name} ({node_type}): missing handler_routing section"
                )

        if missing:
            pytest.fail(
                f"Nodes missing handler_routing ({len(missing)}):\n"
                + "\n".join(f"  - {m}" for m in missing)
            )

    def test_entry_point_imports_resolve(
        self, all_contract_data: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify every handler_routing entry_point module and function resolve."""
        errors: list[str] = []

        for contract_path, data in all_contract_data:
            node_name = data.get("name", contract_path.parent.name)
            handler_routing = data.get("handler_routing")

            if handler_routing is None:
                continue

            entry_point = handler_routing.get("entry_point")
            if entry_point is None:
                continue

            module_path = entry_point.get("module", "")
            function_name = entry_point.get("function", "")

            if not module_path:
                errors.append(f"{node_name}: entry_point has no module path")
                continue

            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                errors.append(
                    f"{node_name}: Cannot import entry_point module "
                    f"'{module_path}': {e}"
                )
                continue

            if function_name and not hasattr(module, function_name):
                errors.append(
                    f"{node_name}: entry_point function '{function_name}' "
                    f"not found in module '{module_path}'"
                )

        if errors:
            pytest.fail(
                f"Entry point import failures ({len(errors)}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_default_handler_imports_resolve(
        self, all_contract_data: list[tuple[Path, dict[str, Any]]]
    ) -> None:
        """Verify every handler_routing default_handler module and function resolve."""
        errors: list[str] = []

        for contract_path, data in all_contract_data:
            node_name = data.get("name", contract_path.parent.name)
            handler_routing = data.get("handler_routing")

            if handler_routing is None:
                continue

            default_handler = handler_routing.get("default_handler")
            if default_handler is None:
                continue

            module_path = default_handler.get("module", "")
            function_name = default_handler.get("function", "")

            if not module_path:
                errors.append(f"{node_name}: default_handler has no module path")
                continue

            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                errors.append(
                    f"{node_name}: Cannot import default_handler module "
                    f"'{module_path}': {e}"
                )
                continue

            if function_name and not hasattr(module, function_name):
                errors.append(
                    f"{node_name}: default_handler function "
                    f"'{function_name}' not found in module '{module_path}'"
                )

        if errors:
            pytest.fail(
                f"Default handler import failures ({len(errors)}):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def test_no_duplicate_contract_files(self, nodes_dir: Path) -> None:
        """Verify no node directory has multiple contract.yaml files.

        Catches stale contract files in subdirectories (e.g., contracts/contract.yaml)
        that can cause confusion during discovery.
        """
        duplicates: list[str] = []

        for node_dir in sorted(nodes_dir.iterdir()):
            if not node_dir.is_dir() or not node_dir.name.startswith("node_"):
                continue

            contracts = list(node_dir.rglob("contract.yaml"))
            if len(contracts) > 1:
                paths = [str(c.relative_to(nodes_dir)) for c in contracts]
                duplicates.append(f"{node_dir.name}: {paths}")

        if duplicates:
            pytest.fail(
                f"Duplicate contract.yaml files found ({len(duplicates)}):\n"
                + "\n".join(f"  - {d}" for d in duplicates)
            )
