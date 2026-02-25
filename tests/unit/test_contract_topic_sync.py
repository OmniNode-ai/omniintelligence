# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Contract-to-Constants Topic Synchronization Tests.

This module validates that Kafka topic suffixes defined as Python constants in
constants.py stay in sync with the topic definitions in contract.yaml files.

Background:
    Topic suffixes are defined in constants.py as TEMP_BOOTSTRAP constants until
    runtime injection from contract.yaml is wired (OMN-1546). This test ensures
    the constants don't drift from the contract definitions.

Validated Constants:
    - TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1: subscribe topic for claude hook events
    - TOPIC_SUFFIX_INTENT_CLASSIFIED_V1: publish topic for classified intents
    - TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1: publish topic for pattern learning commands
    - TOPIC_SUFFIX_PATTERN_PROMOTED_V1: publish topic for promoted patterns
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from omniintelligence.constants import (
    TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1,
    TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
    TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1,
    TOPIC_SUFFIX_PATTERN_PROMOTED_V1,
    TOPIC_SUFFIX_PATTERN_STORED_V1,
    TOPIC_SUFFIX_TOOL_CONTENT_V1,
)

# =========================================================================
# Constants and Configuration
# =========================================================================

# Base path for node contracts (relative to project root)
NODES_DIR = Path("src/omniintelligence/nodes")

# Mapping of Python constants to their expected contract locations
# Format: (constant_name, constant_value, node_name, topic_type, contract_subpath)
# topic_type is either "subscribe_topics" or "publish_topics"
TOPIC_CONSTANT_MAPPINGS: list[tuple[str, str, str, str, str]] = [
    (
        "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
        TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1,
        "node_claude_hook_event_effect",
        "subscribe_topics",
        "contract.yaml",
    ),
    (
        "TOPIC_SUFFIX_TOOL_CONTENT_V1",
        TOPIC_SUFFIX_TOOL_CONTENT_V1,
        "node_claude_hook_event_effect",
        "subscribe_topics",
        "contract.yaml",
    ),
    (
        "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
        TOPIC_SUFFIX_INTENT_CLASSIFIED_V1,
        "node_claude_hook_event_effect",
        "publish_topics",
        "contract.yaml",
    ),
    (
        "TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1",
        TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1,
        "node_claude_hook_event_effect",
        "publish_topics",
        "contract.yaml",
    ),
    (
        "TOPIC_SUFFIX_PATTERN_STORED_V1",
        TOPIC_SUFFIX_PATTERN_STORED_V1,
        "node_pattern_storage_effect",
        "publish_topics",
        "contract.yaml",
    ),
    (
        "TOPIC_SUFFIX_PATTERN_PROMOTED_V1",
        TOPIC_SUFFIX_PATTERN_PROMOTED_V1,
        "node_pattern_storage_effect",
        "publish_topics",
        "contract.yaml",
    ),
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


def load_contract_yaml(
    nodes_dir: Path, node_name: str, contract_subpath: str
) -> dict[str, Any]:
    """Load a contract.yaml file for a specific node.

    Args:
        nodes_dir: Base nodes directory
        node_name: Name of the node directory
        contract_subpath: Relative path to contract.yaml within node directory

    Returns:
        Parsed YAML content as dictionary

    Raises:
        FileNotFoundError: If contract file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    contract_path = nodes_dir / node_name / contract_subpath
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    with open(contract_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_topics_from_contract(
    contract_data: dict[str, Any], topic_type: str
) -> list[str]:
    """Extract topic suffixes from a contract's event_bus section.

    Args:
        contract_data: Parsed contract YAML
        topic_type: Either "subscribe_topics" or "publish_topics"

    Returns:
        List of topic suffix strings
    """
    event_bus = contract_data.get("event_bus", {})
    if not isinstance(event_bus, dict):
        return []

    topics = event_bus.get(topic_type, [])
    if not isinstance(topics, list):
        return []

    # Contract topics may include an {env}. prefix (e.g., "{env}.onex.cmd...").
    # Strip it so comparisons work against the TOPIC_SUFFIX_* constants which
    # store the canonical suffix without the env prefix.
    env_prefix = "{env}."
    return [str(t).removeprefix(env_prefix) for t in topics if t]


# =========================================================================
# Topic Synchronization Tests
# =========================================================================


@pytest.mark.unit
class TestTopicConstantSync:
    """Test that Python topic constants match contract.yaml definitions."""

    def test_all_topic_constants_have_mappings(self) -> None:
        """Verify all expected topic constants are defined in the mapping.

        This test ensures we don't forget to add new topic constants to the
        validation mapping.
        """
        expected_constants = {
            "TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1",
            "TOPIC_SUFFIX_INTENT_CLASSIFIED_V1",
            "TOPIC_SUFFIX_PATTERN_LEARNING_CMD_V1",
            "TOPIC_SUFFIX_PATTERN_PROMOTED_V1",
            "TOPIC_SUFFIX_PATTERN_STORED_V1",
            "TOPIC_SUFFIX_TOOL_CONTENT_V1",
        }
        mapped_constants = {mapping[0] for mapping in TOPIC_CONSTANT_MAPPINGS}

        missing = expected_constants - mapped_constants
        assert not missing, f"Missing topic constant mappings: {missing}"

    def test_topic_constants_match_contracts(self, nodes_dir: Path) -> None:
        """Verify each topic constant matches its contract.yaml definition.

        This is the core synchronization test. It validates that:
        1. Each constant's contract.yaml file exists
        2. The event_bus section contains the expected topic type
        3. The topic suffix in the constant matches the contract
        """
        if not nodes_dir.exists():
            pytest.skip(f"Nodes directory not found: {nodes_dir}")

        errors = []

        for (
            const_name,
            const_value,
            node_name,
            topic_type,
            contract_subpath,
        ) in TOPIC_CONSTANT_MAPPINGS:
            try:
                contract_data = load_contract_yaml(
                    nodes_dir, node_name, contract_subpath
                )
            except FileNotFoundError as e:
                errors.append(f"{const_name}: Contract file not found - {e}")
                continue
            except yaml.YAMLError as e:
                errors.append(f"{const_name}: Invalid YAML in contract - {e}")
                continue

            # Extract topics from contract
            contract_topics = extract_topics_from_contract(contract_data, topic_type)

            if not contract_topics:
                errors.append(
                    f"{const_name}: No {topic_type} found in "
                    f"{node_name}/{contract_subpath} event_bus section"
                )
                continue

            # Check if the constant value is in the contract topics
            if const_value not in contract_topics:
                errors.append(
                    f"{const_name}: Mismatch detected!\n"
                    f"  Python constant value: {const_value!r}\n"
                    f"  Contract {topic_type}: {contract_topics}\n"
                    f"  Contract path: {node_name}/{contract_subpath}"
                )

        if errors:
            pytest.fail(
                "Topic constant/contract synchronization failures:\n\n"
                + "\n\n".join(errors)
            )

    def test_contract_topics_have_matching_constants(self, nodes_dir: Path) -> None:
        """Verify contract topics have corresponding Python constants.

        This reverse check ensures we don't have topics in contracts that
        are missing from the Python constants (orphaned contract topics).
        """
        if not nodes_dir.exists():
            pytest.skip(f"Nodes directory not found: {nodes_dir}")

        # Build set of all constant values for quick lookup
        constant_values = {mapping[1] for mapping in TOPIC_CONSTANT_MAPPINGS}

        # Group mappings by contract to avoid loading same contract multiple times
        contracts_to_check: dict[tuple[str, str], list[str]] = {}
        for _, _, node_name, topic_type, contract_subpath in TOPIC_CONSTANT_MAPPINGS:
            key = (node_name, contract_subpath)
            if key not in contracts_to_check:
                contracts_to_check[key] = []
            if topic_type not in contracts_to_check[key]:
                contracts_to_check[key].append(topic_type)

        errors = []

        for (node_name, contract_subpath), topic_types in contracts_to_check.items():
            try:
                contract_data = load_contract_yaml(
                    nodes_dir, node_name, contract_subpath
                )
            except (FileNotFoundError, yaml.YAMLError):
                # Already reported in test_topic_constants_match_contracts
                continue

            for topic_type in topic_types:
                contract_topics = extract_topics_from_contract(
                    contract_data, topic_type
                )

                for topic in contract_topics:
                    if topic not in constant_values:
                        errors.append(
                            f"Contract topic {topic!r} in {node_name}/{contract_subpath} "
                            f"({topic_type}) has no matching Python constant"
                        )

        if errors:
            pytest.fail(
                "Contract topics without matching Python constants:\n\n"
                + "\n\n".join(errors)
            )


@pytest.mark.unit
class TestTopicConstantValues:
    """Test that topic constant values follow naming conventions."""

    def test_topic_suffixes_follow_onex_convention(self) -> None:
        """Verify topic suffixes follow ONEX naming convention.

        ONEX convention: onex.{kind}.{producer}.{event-name}.{version}
        - kind: cmd (commands/inputs) or evt (events/outputs)
        - producer: omniintelligence (this service)
        - event-name: kebab-case event identifier
        - version: v1, v2, etc.
        """
        errors = []

        for const_name, const_value, _, topic_type, _ in TOPIC_CONSTANT_MAPPINGS:
            parts = const_value.split(".")
            if len(parts) != 5:
                errors.append(
                    f"{const_name}: Expected 5 parts (onex.kind.producer.event.version), "
                    f"got {len(parts)}: {const_value!r}"
                )
                continue

            prefix, kind, producer, _event_name, version = parts

            # Check prefix
            if prefix != "onex":
                errors.append(f"{const_name}: Expected prefix 'onex', got {prefix!r}")

            # Check kind matches topic type.
            # subscribe_topics must use 'cmd' kind (incoming commands).
            # publish_topics typically use 'evt' kind (outgoing events),
            # but may use 'cmd' kind when issuing commands to other nodes
            # (e.g., pattern-learning commands triggered by Stop events).
            if topic_type == "subscribe_topics":
                if kind != "cmd":
                    errors.append(
                        f"{const_name}: Expected kind 'cmd' for {topic_type}, "
                        f"got {kind!r}"
                    )
            elif topic_type == "publish_topics":
                if kind not in ("evt", "cmd"):
                    errors.append(
                        f"{const_name}: Expected kind 'evt' or 'cmd' for "
                        f"{topic_type}, got {kind!r}"
                    )

            # Check producer
            if producer != "omniintelligence":
                errors.append(
                    f"{const_name}: Expected producer 'omniintelligence', "
                    f"got {producer!r}"
                )

            # Check version format
            if not version.startswith("v") or not version[1:].isdigit():
                errors.append(
                    f"{const_name}: Invalid version format {version!r}, "
                    "expected v1, v2, etc."
                )

        if errors:
            pytest.fail("Topic naming convention violations:\n\n" + "\n".join(errors))

    def test_constant_names_match_topic_names(self) -> None:
        """Verify Python constant names reflect their topic names.

        For example:
        - TOPIC_SUFFIX_CLAUDE_HOOK_EVENT_V1 should contain "claude-hook-event"
        - TOPIC_SUFFIX_INTENT_CLASSIFIED_V1 should contain "intent-classified"
        """
        errors = []

        for const_name, const_value, _, _, _ in TOPIC_CONSTANT_MAPPINGS:
            # Extract event name from topic suffix
            parts = const_value.split(".")
            if len(parts) < 4:
                continue  # Already reported in other test

            event_name = parts[3]  # e.g., "claude-hook-event"
            version = parts[4] if len(parts) > 4 else ""  # e.g., "v1"

            # Convert event name to expected constant suffix
            # "claude-hook-event" -> "CLAUDE_HOOK_EVENT"
            expected_suffix = event_name.upper().replace("-", "_")
            if version:
                expected_suffix += f"_{version.upper()}"

            # Base expected name without kind qualifier
            expected_const_name = f"TOPIC_SUFFIX_{expected_suffix}"

            # Allow optional kind qualifier (CMD/EVT) in the constant name.
            # This is useful when a node publishes a command topic (cmd kind)
            # to trigger downstream processing, making the intent explicit.
            kind = parts[1]  # "cmd" or "evt"
            expected_const_name_with_kind = (
                f"TOPIC_SUFFIX_{expected_suffix.rsplit('_', 1)[0]}"
                f"_{kind.upper()}_{version.upper()}"
                if version
                else f"TOPIC_SUFFIX_{expected_suffix}_{kind.upper()}"
            )

            if const_name not in (expected_const_name, expected_const_name_with_kind):
                errors.append(
                    f"Constant name mismatch:\n"
                    f"  Actual:   {const_name}\n"
                    f"  Expected: {expected_const_name} or "
                    f"{expected_const_name_with_kind}\n"
                    f"  (based on topic: {const_value})"
                )

        if errors:
            pytest.fail(
                "Constant name/topic name mismatches:\n\n" + "\n\n".join(errors)
            )


# =========================================================================
# Summary Test
# =========================================================================


@pytest.mark.unit
def test_topic_sync_summary(nodes_dir: Path) -> None:
    """Generate a summary of topic constant/contract synchronization."""
    if not nodes_dir.exists():
        pytest.skip(f"Nodes directory not found: {nodes_dir}")

    print("\n--- Topic Constant/Contract Sync Summary ---")
    print(f"Total topic constants validated: {len(TOPIC_CONSTANT_MAPPINGS)}")

    for (
        const_name,
        const_value,
        node_name,
        topic_type,
        contract_subpath,
    ) in TOPIC_CONSTANT_MAPPINGS:
        print(f"\n{const_name}:")
        print(f"  Value: {const_value}")
        print(f"  Contract: {node_name}/{contract_subpath}")
        print(f"  Type: {topic_type}")

    print("\n--------------------------------------------\n")

    # Always pass - this is informational
    assert True
