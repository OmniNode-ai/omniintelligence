# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Contract-driven topic discovery for the Intelligence domain.

Reads ``event_bus.subscribe_topics`` from intelligence effect-node
``contract.yaml`` files and returns the collected list.  This replaces
the formerly-hardcoded ``INTELLIGENCE_SUBSCRIBE_TOPICS`` list that
lived in ``plugin.py``.

Design decisions:
    - Topics are declared in each effect node's contract.yaml (source of truth).
    - This module reads those contracts via ``importlib.resources`` (ONEX I/O
      audit compliant -- package resource reads, not arbitrary filesystem I/O).
    - The module also provides ``canonical_topic_to_dispatch_alias`` to convert
      ONEX canonical topic naming (``.cmd.`` / ``.evt.``) to the dispatch engine
      format (``.commands.`` / ``.events.``).

Related:
    - OMN-2033: Move intelligence topics to contract.yaml declarations
"""

from __future__ import annotations

import importlib.resources
import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ============================================================================
# Node packages that declare subscribe_topics
# ============================================================================
# Only effect nodes that receive events from the event bus are listed here.
# Compute and orchestrator nodes do not subscribe to Kafka topics directly.

_INTELLIGENCE_EFFECT_NODE_PACKAGES: list[str] = [
    "omniintelligence.nodes.node_claude_hook_event_effect",
    "omniintelligence.nodes.node_pattern_feedback_effect",
    "omniintelligence.nodes.node_pattern_lifecycle_effect",
]


# ============================================================================
# Public API
# ============================================================================


def collect_subscribe_topics_from_contracts(
    *,
    node_packages: list[str] | None = None,
) -> list[str]:
    """Collect subscribe topics from intelligence node contracts.

    Scans ``contract.yaml`` files from intelligence effect nodes and extracts
    ``event_bus.subscribe_topics`` from each enabled node.  Returns the union
    of all topics in package-declaration order.

    This is the single replacement for the former hardcoded
    ``INTELLIGENCE_SUBSCRIBE_TOPICS`` list.

    Args:
        node_packages: Override list of node packages to scan.  Defaults to
            the three built-in intelligence effect nodes.

    Returns:
        Ordered list of subscribe topic strings.

    Raises:
        FileNotFoundError: If a ``contract.yaml`` is missing from a package.
        yaml.YAMLError: If a ``contract.yaml`` is malformed YAML.
    """
    packages = node_packages or _INTELLIGENCE_EFFECT_NODE_PACKAGES
    all_topics: list[str] = []

    for package in packages:
        topics = _read_subscribe_topics(package)
        all_topics.extend(topics)

    logger.debug(
        "Collected %d intelligence subscribe topics from %d contracts",
        len(all_topics),
        len(packages),
    )

    return all_topics


def collect_publish_topics_for_dispatch(
    *,
    node_packages: list[str] | None = None,
) -> dict[str, str]:
    """Collect publish topics from contracts and map to dispatch engine keys.

    Reads ``event_bus.publish_topics`` from intelligence effect node contracts
    and returns a dict compatible with
    ``create_intelligence_dispatch_engine(publish_topics=...)``.

    The mapping from package to dispatch key is:
        - ``node_claude_hook_event_effect`` → ``"claude_hook"``
        - ``node_pattern_lifecycle_effect`` → ``"lifecycle"``

    Only the first publish topic per contract is used (each contract declares
    exactly one publish topic).

    Args:
        node_packages: Override list of node packages to scan.  Defaults to
            the built-in intelligence effect nodes that publish events.

    Returns:
        Dict mapping handler key to full publish topic string.
        Empty dict if no publish topics are declared.
    """
    _DISPATCH_KEY_TO_PACKAGE: dict[str, str] = {
        "claude_hook": "omniintelligence.nodes.node_claude_hook_event_effect",
        "lifecycle": "omniintelligence.nodes.node_pattern_lifecycle_effect",
    }

    if node_packages is not None:
        # Override: scan provided packages, use package tail as key
        result: dict[str, str] = {}
        for package in node_packages:
            topics = _read_publish_topics(package)
            if topics:
                key = (
                    package.rsplit(".", 1)[-1]
                    .replace("node_", "")
                    .replace("_effect", "")
                )
                result[key] = topics[0]
        return result

    result = {}
    for key, package in _DISPATCH_KEY_TO_PACKAGE.items():
        topics = _read_publish_topics(package)
        if topics:
            result[key] = topics[0]

    logger.debug(
        "Collected %d publish topics for dispatch engine: %s",
        len(result),
        result,
    )

    return result


def canonical_topic_to_dispatch_alias(topic: str) -> str:
    """Convert ONEX canonical topic naming to dispatch engine format.

    ONEX canonical naming uses ``.cmd.`` for commands and ``.evt.`` for
    events.  ``MessageDispatchEngine`` expects ``.commands.`` and
    ``.events.`` segments.  This function bridges the naming gap.

    Args:
        topic: Canonical topic string (e.g.
            ``onex.cmd.omniintelligence.claude-hook-event.v1``).

    Returns:
        Dispatch-compatible topic string (e.g.
            ``onex.commands.omniintelligence.claude-hook-event.v1``).
    """
    return topic.replace(".cmd.", ".commands.").replace(".evt.", ".events.")


# ============================================================================
# Internal helpers
# ============================================================================


def _read_subscribe_topics(package: str) -> list[str]:
    """Read ``event_bus.subscribe_topics`` from a node package's contract.

    Uses ``importlib.resources`` for ONEX I/O audit compliance.

    Args:
        package: Fully-qualified Python package path containing
            a ``contract.yaml`` file.

    Returns:
        List of subscribe topic strings (empty if event bus is disabled).
    """
    package_files = importlib.resources.files(package)
    contract_file = package_files.joinpath("contract.yaml")
    content = contract_file.read_text()
    contract: Any = yaml.safe_load(content)

    if not isinstance(contract, dict):
        logger.warning(
            "contract.yaml in %s is not a valid mapping (got %s), skipping",
            package,
            type(contract).__name__,
        )
        return []

    event_bus = contract.get("event_bus", {})
    if not isinstance(event_bus, dict):
        logger.warning(
            "event_bus in %s contract.yaml is not a mapping (got %s), skipping",
            package,
            type(event_bus).__name__,
        )
        return []

    if not event_bus.get("event_bus_enabled", False):
        return []

    topics: list[str] = event_bus.get("subscribe_topics", [])
    if topics:
        logger.debug(
            "Discovered subscribe_topics from %s: %s",
            package,
            topics,
        )
    return topics


def _read_publish_topics(package: str) -> list[str]:
    """Read ``event_bus.publish_topics`` from a node package's contract.

    Uses ``importlib.resources`` for ONEX I/O audit compliance.

    Args:
        package: Fully-qualified Python package path containing
            a ``contract.yaml`` file.

    Returns:
        List of publish topic strings (empty if event bus is disabled or
        no publish topics are declared).
    """
    package_files = importlib.resources.files(package)
    contract_file = package_files.joinpath("contract.yaml")
    content = contract_file.read_text()
    contract: Any = yaml.safe_load(content)

    if not isinstance(contract, dict):
        logger.warning(
            "contract.yaml in %s is not a valid mapping (got %s), skipping",
            package,
            type(contract).__name__,
        )
        return []

    event_bus = contract.get("event_bus", {})
    if not isinstance(event_bus, dict):
        logger.warning(
            "event_bus in %s contract.yaml is not a mapping (got %s), skipping",
            package,
            type(event_bus).__name__,
        )
        return []

    if not event_bus.get("event_bus_enabled", False):
        return []

    topics: list[str] = event_bus.get("publish_topics", [])
    if topics:
        logger.debug(
            "Discovered publish_topics from %s: %s",
            package,
            topics,
        )
    return topics


__all__ = [
    "canonical_topic_to_dispatch_alias",
    "collect_publish_topics_for_dispatch",
    "collect_subscribe_topics_from_contracts",
]
