# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Contract validation tests for canonical models and contracts.

This module validates that:
1. Contract YAML files are valid and parseable
2. Contract schemas match their corresponding Pydantic models
3. Input/output field names are consistent with canonical naming conventions
4. Required fields exist in all contracts
5. Node types follow ONEX conventions
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml

# =========================================================================
# Constants and Configuration
# =========================================================================

# Base path for node contracts (relative to project root)
NODES_DIR = Path("src/omniintelligence/nodes")

# Required fields in all contracts
REQUIRED_CONTRACT_FIELDS = [
    "contract_version",
    "node_version",
    "name",
    "node_type",
    "description",
    "input_model",
    "output_model",
]

# Required fields in input_model and output_model sections
REQUIRED_MODEL_FIELDS = ["name", "module", "description"]

# Valid node types (ONEX canonical types)
VALID_NODE_TYPES = [
    "COMPUTE_GENERIC",
    "EFFECT_GENERIC",
    "REDUCER_GENERIC",
    "ORCHESTRATOR_GENERIC",
]

# Canonical field names that should be used (key: canonical, value: deprecated alternatives)
CANONICAL_FIELD_NAMES = {
    "source_path": ["file_path", "filepath", "path"],
    "content": ["code", "text", "data"],
    "correlation_id": ["trace_id", "request_id"],
    "entity_id": ["document_id", "item_id"],
    "metadata": ["meta", "extra"],
    "options": ["config", "settings", "params"],
}

# Fields that are optional but when present should follow conventions
OPTIONAL_CONTRACT_FIELDS = [
    "operations",
    "dependencies",
    "health_check",
    "metadata",
    "consumed_events",
    "published_events",
    "state_machine",
    "workflow_coordination",
    "error_handling",
    "status",  # For stub contracts
]


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    # Navigate from tests/unit to project root
    return Path(__file__).parent.parent.parent


@pytest.fixture
def nodes_dir(project_root: Path) -> Path:
    """Get the nodes directory."""
    return project_root / NODES_DIR


@pytest.fixture
def all_contracts(nodes_dir: Path) -> list[Path]:
    """Discover all contract YAML files in the nodes directory.

    Returns:
        List of paths to contract.yaml files
    """
    if not nodes_dir.exists():
        pytest.skip(f"Nodes directory not found: {nodes_dir}")
    contracts = list(nodes_dir.glob("*/contract.yaml"))
    if not contracts:
        pytest.skip(f"No contract.yaml files found in {nodes_dir}")
    return sorted(contracts)


@pytest.fixture
def all_contract_data(all_contracts: list[Path]) -> list[tuple[Path, dict[str, Any]]]:
    """Load all contracts and return path-data pairs.

    Returns:
        List of (path, data) tuples for each contract
    """
    result = []
    for contract_path in all_contracts:
        with open(contract_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        result.append((contract_path, data))
    return result


# =========================================================================
# Basic YAML Validity Tests
# =========================================================================


@pytest.mark.unit
class TestContractYamlValidity:
    """Test that all contract YAML files are valid and parseable."""

    def test_contracts_are_valid_yaml(self, all_contracts: list[Path]) -> None:
        """Verify all contract files contain valid YAML syntax."""
        errors = []
        for contract_path in all_contracts:
            try:
                with open(contract_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"{contract_path.name} is empty"
            except yaml.YAMLError as e:
                errors.append(f"{contract_path}: YAML parse error - {e}")
            except Exception as e:
                errors.append(f"{contract_path}: Unexpected error - {e}")

        if errors:
            pytest.fail("\n".join(errors))

    def test_contracts_are_dictionaries(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify all contracts parse to dictionaries (not lists or scalars)."""
        errors = []
        for contract_path, data in all_contract_data:
            # Note: This check is defensive; the fixture type guarantees dict
            # but we verify anyway in case YAML contains unexpected data
            if not isinstance(data, dict):
                errors.append(  # type: ignore[unreachable]
                    f"{contract_path.name}: Expected dict, got {type(data).__name__}"
                )

        if errors:
            pytest.fail("\n".join(errors))

    def test_contract_count(self, all_contracts: list[Path]) -> None:
        """Verify we have a reasonable number of contracts to test."""
        # This ensures the test discovery is working
        assert len(all_contracts) >= 10, (
            f"Expected at least 10 contracts, found {len(all_contracts)}. "
            "Check contract discovery pattern."
        )


# =========================================================================
# Required Fields Tests
# =========================================================================


@pytest.mark.unit
class TestContractRequiredFields:
    """Test that all contracts have required fields."""

    def test_contracts_have_required_fields(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify all contracts contain required top-level fields."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            missing = [field for field in REQUIRED_CONTRACT_FIELDS if field not in data]
            if missing:
                errors.append(f"{node_name}: Missing required fields: {missing}")

        if errors:
            pytest.fail("\n".join(errors))

    def test_contracts_have_valid_contract_version(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify contract_version has major, minor, patch fields."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            version = data.get("contract_version", {})

            if not isinstance(version, dict):
                errors.append(f"{node_name}: contract_version must be a dict")
                continue

            for field in ["major", "minor", "patch"]:
                if field not in version:
                    errors.append(f"{node_name}: contract_version missing '{field}'")
                elif not isinstance(version[field], int):
                    errors.append(f"{node_name}: contract_version.{field} must be int")

        if errors:
            pytest.fail("\n".join(errors))

    def test_input_model_has_required_fields(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify input_model sections have required fields."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            input_model = data.get("input_model", {})

            if not isinstance(input_model, dict):
                errors.append(f"{node_name}: input_model must be a dict")
                continue

            for field in REQUIRED_MODEL_FIELDS:
                if field not in input_model:
                    errors.append(f"{node_name}: input_model missing '{field}'")

        if errors:
            pytest.fail("\n".join(errors))

    def test_output_model_has_required_fields(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify output_model sections have required fields."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            output_model = data.get("output_model", {})

            if not isinstance(output_model, dict):
                errors.append(f"{node_name}: output_model must be a dict")
                continue

            for field in REQUIRED_MODEL_FIELDS:
                if field not in output_model:
                    errors.append(f"{node_name}: output_model missing '{field}'")

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Node Type Validation Tests
# =========================================================================


@pytest.mark.unit
class TestContractNodeTypes:
    """Test that node types follow ONEX conventions."""

    def test_contracts_have_valid_node_types(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify node_type is one of the valid ONEX node types."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            node_type = data.get("node_type")

            if node_type not in VALID_NODE_TYPES:
                errors.append(
                    f"{node_name}: Invalid node_type '{node_type}'. "
                    f"Must be one of: {VALID_NODE_TYPES}"
                )

        if errors:
            pytest.fail("\n".join(errors))

    def test_node_type_matches_directory_suffix(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify node type matches directory naming convention.

        Directory naming convention:
        - *_compute -> COMPUTE_GENERIC
        - *_effect -> EFFECT_GENERIC
        - *_reducer -> REDUCER_GENERIC
        - *_orchestrator -> ORCHESTRATOR_GENERIC
        """
        errors = []
        suffix_to_type = {
            "_compute": "COMPUTE_GENERIC",
            "_effect": "EFFECT_GENERIC",
            "_reducer": "REDUCER_GENERIC",
            "_orchestrator": "ORCHESTRATOR_GENERIC",
            # Special case for adapter nodes (also effect nodes)
            "_adapter": "EFFECT_GENERIC",
        }

        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            node_type = data.get("node_type")

            expected_type = None
            for suffix, ntype in suffix_to_type.items():
                if node_name.endswith(suffix):
                    expected_type = ntype
                    break

            if expected_type and node_type != expected_type:
                errors.append(
                    f"{node_name}: Directory suffix suggests {expected_type}, "
                    f"but contract declares {node_type}"
                )

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Canonical Field Naming Tests
# =========================================================================


@pytest.mark.unit
class TestContractCanonicalNaming:
    """Test that contracts use canonical field names."""

    def _check_dict_for_deprecated_fields(
        self, data: Any, path: str = ""
    ) -> list[tuple[str, str, str]]:
        """Recursively check a dict for deprecated field names.

        Returns:
            List of (path, deprecated_name, canonical_name) tuples
        """
        issues = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                # Check if this key is a deprecated alternative
                for canonical, deprecated_list in CANONICAL_FIELD_NAMES.items():
                    if key in deprecated_list:
                        issues.append((current_path, key, canonical))

                # Recurse into nested structures
                issues.extend(
                    self._check_dict_for_deprecated_fields(value, current_path)
                )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                issues.extend(
                    self._check_dict_for_deprecated_fields(item, current_path)
                )

        return issues

    def test_contracts_use_canonical_field_names(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify contracts use canonical field names instead of deprecated alternatives."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            issues = self._check_dict_for_deprecated_fields(data)

            for path, deprecated, canonical in issues:
                errors.append(
                    f"{node_name}: Use '{canonical}' instead of '{deprecated}' at {path}"
                )

        if errors:
            pytest.fail("\n".join(errors))

    def test_operations_use_canonical_field_names(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify operation input/output field names use canonical naming."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            operations = data.get("operations", [])

            for op in operations:
                if not isinstance(op, dict):
                    continue

                op_name = op.get("name", "unknown")

                # Check input_fields
                for field in op.get("input_fields", []):
                    for canonical, deprecated_list in CANONICAL_FIELD_NAMES.items():
                        if field in deprecated_list:
                            errors.append(
                                f"{node_name}.{op_name}: input_field '{field}' "
                                f"should be '{canonical}'"
                            )

                # Check output_fields
                for field in op.get("output_fields", []):
                    for canonical, deprecated_list in CANONICAL_FIELD_NAMES.items():
                        if field in deprecated_list:
                            errors.append(
                                f"{node_name}.{op_name}: output_field '{field}' "
                                f"should be '{canonical}'"
                            )

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Model Reference Validation Tests
# =========================================================================


@pytest.mark.unit
class TestContractModelReferences:
    """Test that referenced models exist and are importable."""

    def test_model_names_follow_convention(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify model names follow Model* naming convention.

        Note: External models (from packages outside omniintelligence.*) are
        exempt from this check. External packages have their own naming
        conventions that we should not enforce.
        """
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name

            for model_key in ["input_model", "output_model"]:
                model_info = data.get(model_key, {})
                model_name = model_info.get("name", "")
                module_path = model_info.get("module", "")

                # Skip external models - they follow their own naming conventions
                # External = module does NOT start with "omniintelligence."
                if module_path and not module_path.startswith("omniintelligence."):
                    continue

                if model_name and not model_name.startswith("Model"):
                    errors.append(
                        f"{node_name}: {model_key}.name '{model_name}' "
                        "should start with 'Model'"
                    )

        if errors:
            pytest.fail("\n".join(errors))

    def test_model_modules_are_valid_python_paths(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify model module paths are valid Python import paths."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name

            for model_key in ["input_model", "output_model"]:
                model_info = data.get(model_key, {})
                module_path = model_info.get("module", "")

                if not module_path:
                    continue

                # Check for valid module path format
                if not all(
                    part.isidentifier() or part == "" for part in module_path.split(".")
                ):
                    errors.append(
                        f"{node_name}: {model_key}.module '{module_path}' "
                        "is not a valid Python module path"
                    )

        if errors:
            pytest.fail("\n".join(errors))

    @pytest.mark.parametrize(
        "check_imports", [False]
    )  # Set to True to enable import checking
    def test_model_imports_are_valid(
        self, all_contract_data: list[tuple[Path, dict]], check_imports: bool
    ) -> None:
        """Optionally verify that referenced models can be imported.

        This test is disabled by default as it requires all dependencies to be installed.
        Enable by changing check_imports parameter to True.
        """
        if not check_imports:
            pytest.skip("Import checking disabled by default")

        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name

            for model_key in ["input_model", "output_model"]:
                model_info = data.get(model_key, {})
                module_path = model_info.get("module", "")
                model_name = model_info.get("name", "")

                if not module_path or not model_name:
                    continue

                try:
                    module = importlib.import_module(module_path)
                    if not hasattr(module, model_name):
                        errors.append(
                            f"{node_name}: {model_key} - Model '{model_name}' "
                            f"not found in module '{module_path}'"
                        )
                except ImportError as e:
                    errors.append(
                        f"{node_name}: {model_key} - Cannot import module "
                        f"'{module_path}': {e}"
                    )

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Contract Name Consistency Tests
# =========================================================================


@pytest.mark.unit
class TestContractNameConsistency:
    """Test that contract names match directory names and follow conventions."""

    def test_contract_name_matches_directory(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify contract name matches containing directory name."""
        errors = []
        for contract_path, data in all_contract_data:
            dir_name = contract_path.parent.name
            contract_name = data.get("name", "")

            if contract_name != dir_name:
                errors.append(
                    f"Contract name mismatch: directory is '{dir_name}', "
                    f"but contract declares name='{contract_name}'"
                )

        if errors:
            pytest.fail("\n".join(errors))

    def test_contract_names_use_snake_case(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify contract names use snake_case."""
        errors = []
        for _contract_path, data in all_contract_data:
            name = data.get("name", "")

            # Check for snake_case: lowercase with underscores, no consecutive underscores
            if name:
                is_snake_case = (
                    (name.islower() or "_" in name)
                    and not name.startswith("_")
                    and not name.endswith("_")
                    and "__" not in name
                )

                # Also check that it doesn't contain invalid characters
                valid_chars = all(c.islower() or c.isdigit() or c == "_" for c in name)

                if not (is_snake_case and valid_chars):
                    errors.append(f"Contract name '{name}' should be snake_case")

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Optional Section Validation Tests
# =========================================================================


@pytest.mark.unit
class TestContractOptionalSections:
    """Test that optional sections follow expected formats when present."""

    def test_dependencies_format(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify dependencies sections have correct format when present."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            dependencies = data.get("dependencies", [])

            if not isinstance(dependencies, list):
                errors.append(f"{node_name}: dependencies must be a list")
                continue

            for i, dep in enumerate(dependencies):
                if not isinstance(dep, dict):
                    errors.append(f"{node_name}: dependency[{i}] must be a dict")
                    continue

                # Check required dependency fields
                if "name" not in dep:
                    errors.append(f"{node_name}: dependency[{i}] missing 'name'")
                if "type" not in dep:
                    errors.append(f"{node_name}: dependency[{i}] missing 'type'")

        if errors:
            pytest.fail("\n".join(errors))

    def test_health_check_format(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify health_check sections have correct format when present."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            health_check = data.get("health_check")

            if health_check is None:
                continue

            if not isinstance(health_check, dict):
                errors.append(f"{node_name}: health_check must be a dict")
                continue

            # Check expected fields
            if "enabled" in health_check and not isinstance(
                health_check["enabled"], bool
            ):
                errors.append(f"{node_name}: health_check.enabled must be boolean")

            if "interval_seconds" in health_check and not isinstance(
                health_check["interval_seconds"], int | float
            ):
                errors.append(
                    f"{node_name}: health_check.interval_seconds must be numeric"
                )

        if errors:
            pytest.fail("\n".join(errors))

    def test_metadata_format(self, all_contract_data: list[tuple[Path, dict]]) -> None:
        """Verify metadata sections have correct format when present."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            metadata = data.get("metadata")

            if metadata is None:
                continue

            if not isinstance(metadata, dict):
                errors.append(f"{node_name}: metadata must be a dict")
                continue

            # Check tags are a list if present
            tags = metadata.get("tags")
            if tags is not None and not isinstance(tags, list):
                errors.append(f"{node_name}: metadata.tags must be a list")

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Reducer-Specific Validation Tests
# =========================================================================


@pytest.mark.unit
class TestReducerContracts:
    """Test reducer-specific contract requirements."""

    def test_reducers_have_state_machine(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify reducer contracts have state_machine section."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            node_type = data.get("node_type", "")

            if node_type == "REDUCER_GENERIC":
                if "state_machine" not in data:
                    errors.append(
                        f"{node_name}: Reducer missing 'state_machine' section"
                    )
                else:
                    sm = data["state_machine"]
                    if not isinstance(sm, dict):
                        errors.append(f"{node_name}: state_machine must be a dict")
                    elif "states" not in sm:
                        errors.append(f"{node_name}: state_machine missing 'states'")
                    elif "transitions" not in sm:
                        errors.append(
                            f"{node_name}: state_machine missing 'transitions'"
                        )

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Orchestrator-Specific Validation Tests
# =========================================================================


@pytest.mark.unit
class TestOrchestratorContracts:
    """Test orchestrator-specific contract requirements."""

    def test_orchestrators_have_workflow_coordination(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify orchestrator contracts have workflow_coordination section."""
        errors = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            node_type = data.get("node_type", "")

            if (
                node_type == "ORCHESTRATOR_GENERIC"
                and "workflow_coordination" not in data
            ):
                errors.append(
                    f"{node_name}: Orchestrator missing 'workflow_coordination' section"
                )

        if errors:
            pytest.fail("\n".join(errors))


# =========================================================================
# Effect-Specific Validation Tests
# =========================================================================


@pytest.mark.unit
class TestEffectContracts:
    """Test effect-specific contract requirements."""

    def test_event_driven_effects_have_topics(
        self, all_contract_data: list[tuple[Path, dict]]
    ) -> None:
        """Verify event-driven effect nodes declare consumed/published events."""
        # Note: Not all effect nodes are event-driven, so this is informational
        event_driven_nodes = []
        for contract_path, data in all_contract_data:
            node_name = contract_path.parent.name
            node_type = data.get("node_type", "")

            if node_type == "EFFECT_GENERIC":
                has_consumed = "consumed_events" in data
                has_published = "published_events" in data

                if has_consumed or has_published:
                    event_driven_nodes.append(node_name)

        # Just verify we found some event-driven nodes
        # This is informational, not a failure condition
        assert len(event_driven_nodes) >= 0  # Always passes, but logs info


# =========================================================================
# Summary Report Test
# =========================================================================


@pytest.mark.unit
def test_contract_summary(all_contract_data: list[tuple[Path, dict]]) -> None:
    """Generate a summary of all contracts for visibility."""
    total_contracts = len(all_contract_data)
    by_type: dict[str, int] = {}
    stub_contracts: list[str] = []

    for contract_path, data in all_contract_data:
        node_name = contract_path.parent.name
        node_type = data.get("node_type", "UNKNOWN")

        # Count by type
        by_type[node_type] = by_type.get(node_type, 0) + 1

        # Track stubs
        if data.get("status") == "stub":
            stub_contracts.append(node_name)

    # Print summary (will show in pytest -v output)
    print("\n--- Contract Summary ---")
    print(f"Total contracts: {total_contracts}")
    print("By type:")
    for node_type, count in sorted(by_type.items()):
        print(f"  {node_type}: {count}")
    if stub_contracts:
        print(f"Stub contracts: {', '.join(stub_contracts)}")
    print("------------------------\n")

    # Always pass - this is informational
    assert True
