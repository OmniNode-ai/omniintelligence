# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Dispatch parity contract test [OMN-6979].

Verifies that every command topic (``onex.cmd.*``) declared in contract YAML
``subscribe_topics`` has a matching dispatch route registered in the
intelligence dispatch engine, and vice-versa.

Without this invariant, a published command can land on the bus with no
handler to consume it — the request goes into the void.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NODES_DIR = Path(__file__).parent.parent.parent / "src" / "omniintelligence" / "nodes"
_REVIEW_PAIRING_DIR = (
    Path(__file__).parent.parent.parent / "src" / "omniintelligence" / "review_pairing"
)


def _to_canonical(topic: str) -> str:
    """Normalize a dispatch alias back to ONEX canonical form.

    Dispatch engine uses ``.commands.`` / ``.events.``; canonical uses
    ``.cmd.`` / ``.evt.``.  This normalizes to canonical so both sides
    can be compared in one namespace.
    """
    return topic.replace(".commands.", ".cmd.").replace(".events.", ".evt.")


def _to_dispatch(topic: str) -> str:
    """Convert canonical topic to dispatch alias form."""
    return topic.replace(".cmd.", ".commands.").replace(".evt.", ".events.")


def _collect_contract_subscribe_topics() -> dict[str, list[str]]:
    """Collect all subscribe_topics from contract.yaml files.

    Returns a dict mapping node name to its subscribe topics (canonical form).
    """
    result: dict[str, list[str]] = {}

    # Scan nodes/
    for child in sorted(_NODES_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue
        contract_path = child / "contract.yaml"
        if not contract_path.exists():
            continue
        topics = _extract_subscribe_topics(contract_path)
        if topics:
            result[child.name] = topics

    # Scan review_pairing/
    review_contract = _REVIEW_PAIRING_DIR / "contract.yaml"
    if review_contract.exists():
        topics = _extract_subscribe_topics(review_contract)
        if topics:
            result["review_pairing"] = topics

    return result


def _extract_subscribe_topics(contract_path: Path) -> list[str]:
    """Extract subscribe_topics from a contract.yaml event_bus section."""
    with open(contract_path) as f:
        contract: Any = yaml.safe_load(f)
    if not isinstance(contract, dict):
        return []
    event_bus = contract.get("event_bus", {})
    if not isinstance(event_bus, dict):
        return []
    if not event_bus.get("event_bus_enabled", False):
        return []
    topics = event_bus.get("subscribe_topics", [])
    if not isinstance(topics, list):
        return []
    # Strip legacy {env}. prefix
    return [str(t).removeprefix("{env}.") for t in topics if t]


def _collect_dispatch_route_topics() -> set[str]:
    """Collect all topic patterns registered as dispatch routes.

    Parses the dispatch_handlers.py and related files to extract
    DISPATCH_ALIAS constants and topic patterns used in register_route calls.

    Returns topics in canonical form (onex.cmd.* / onex.evt.*).
    """
    topics: set[str] = set()

    # Collect DISPATCH_ALIAS_* constants from dispatch_handlers.py
    runtime_dir = (
        Path(__file__).parent.parent.parent / "src" / "omniintelligence" / "runtime"
    )

    # Parse DISPATCH_ALIAS constants from dispatch_handlers.py
    dispatch_file = runtime_dir / "dispatch_handlers.py"
    topics.update(_extract_dispatch_aliases(dispatch_file))

    # Parse from auxiliary dispatch handler files
    for handler_file in sorted(runtime_dir.glob("dispatch_handler_*.py")):
        topics.update(_extract_dispatch_aliases(handler_file))

    # Also collect topics used via canonical_topic_to_dispatch_alias()
    # in create_intelligence_dispatch_engine — these use TOPIC_* constants
    # from omniintelligence.constants
    topics.update(_extract_topic_constants_used_in_engine(dispatch_file))

    return topics


def _extract_dispatch_aliases(filepath: Path) -> set[str]:
    """Extract DISPATCH_ALIAS_* string values from a Python file.

    Returns topics in canonical form.
    """
    content = filepath.read_text()
    # Match string literals assigned to DISPATCH_ALIAS_* or topic_pattern=
    # Handle both single-line and multi-line string assignments
    aliases: set[str] = set()

    # Find all string literals that look like topic patterns
    for match in re.finditer(r'"(onex\.[a-z]+\.[a-z0-9._-]+\.v\d+)"', content):
        topic = match.group(1)
        # Only include topics that are used as dispatch route patterns
        # (DISPATCH_ALIAS_* constants or topic_pattern= args)
        aliases.add(_to_canonical(topic))

    return aliases


def _extract_topic_constants_used_in_engine(dispatch_file: Path) -> set[str]:
    """Extract TOPIC_* constant references used in register_route calls.

    Some routes use constants from omniintelligence.constants rather than
    inline DISPATCH_ALIAS strings. This reads those constants' values.
    """
    topics: set[str] = set()
    content = dispatch_file.read_text()

    # Find references like TOPIC_UTILIZATION_SCORING_CMD_V1
    # These are imported and used in register_route topic_pattern=
    for match in re.finditer(r"topic_pattern=(TOPIC_\w+)", content):
        const_name = match.group(1)
        # Resolve the constant value by importing it
        try:
            from omniintelligence import constants as C

            value = getattr(C, const_name, None)
            if value and isinstance(value, str):
                topics.add(_to_canonical(value))
        except ImportError:
            pass

    return topics


def _collect_additional_subscribe_topics() -> set[str]:
    """Collect additional subscribe topics from contract_topics.py.

    The _ADDITIONAL_SUBSCRIBE_TOPICS list in contract_topics.py contains
    topics that are subscribed to but not backed by a dedicated effect node
    contract (e.g., cross-repo command topics).
    """
    try:
        from omniintelligence.runtime.contract_topics import (
            _ADDITIONAL_SUBSCRIBE_TOPICS,
        )

        return set(_ADDITIONAL_SUBSCRIBE_TOPICS)
    except ImportError:
        return set()


# ---------------------------------------------------------------------------
# Known unwired topics (documented exceptions)
# ---------------------------------------------------------------------------
# These topics are declared in contracts but intentionally do not have a
# dispatch handler in the intelligence dispatch engine. Each entry documents
# WHY it is excluded.  When a handler IS wired, remove it from this set —
# the test will catch the change.

_KNOWN_UNWIRED_SUBSCRIBE_CMD: set[str] = {
    # Orchestrator sub-commands routed internally, not via dispatch engine
    "onex.cmd.omniintelligence.document-ingestion.v1",
    "onex.cmd.omniintelligence.quality-assessment.v1",
    # Bloom eval orchestrator: not yet wired to dispatch engine
    "onex.cmd.omniintelligence.bloom-eval-run.v1",
    # Code crawler: dispatched via canonical_topic_to_dispatch_alias in engine;
    # the subscribe topic uses canonical form but the route uses dispatch alias
    "onex.cmd.omniintelligence.code-crawl-requested.v1",
    # Promotion check: subscribe topic uses different name than dispatch route
    "onex.cmd.omniintelligence.promotion-check-requested.v1",
    # Protocol handler: not yet wired to dispatch engine
    "onex.cmd.omniintelligence.protocol-execute.v1",
    # Cross-repo topic: handled by omnimemory, not omniintelligence dispatch
    "onex.cmd.omnimemory.crawl-tick.v1",
}

_KNOWN_UNWIRED_SUBSCRIBE_EVT: set[str] = {
    # Cross-repo topics consumed by dedicated node handlers, not dispatch engine
    "onex.evt.omniclaude.llm-routing-decision.v1",
    "onex.evt.omniclaude.pattern-enforcement.v1",
    "onex.evt.omniclaude.routing-feedback.v1",
    # Intelligence pipeline internal events — nodes handle directly
    "onex.evt.omniintelligence.entity-extraction-completed.v1",
    "onex.evt.omniintelligence.intent-drift-detected.v1",
    "onex.evt.omniintelligence.intent-outcome-labeled.v1",
    "onex.evt.omniintelligence.intent-pattern-promoted.v1",
    "onex.evt.omniintelligence.pattern-matched.v1",
    "onex.evt.omniintelligence.vectorization-completed.v1",
    # Cross-repo topics consumed by dedicated crawl nodes
    "onex.evt.omnimemory.document-changed.v1",
    "onex.evt.omnimemory.document-discovered.v1",
}

_KNOWN_ORPHAN_DISPATCH_ROUTES: set[str] = {
    # Dispatch routes registered for observability/future use that do not
    # have a matching contract subscribe/publish topic yet.
    "onex.cmd.omniintelligence.ci-failure-detected-track.v1",
    "onex.cmd.omniintelligence.ci-failure-track.v1",
    "onex.cmd.omniintelligence.decision-recorded.v1",
    "onex.cmd.omniintelligence.intent-received.v1",
    "onex.cmd.omniintelligence.pattern-lifecycle-process.v1",
    "onex.cmd.omniintelligence.utilization-scoring.v1",
    "onex.evt.omniintelligence.code-entities-extracted-embed.v1",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDispatchParity:
    """Verify every subscribed topic has a dispatch handler and vice-versa."""

    def test_contract_subscribe_topics_exist(self) -> None:
        """Smoke test: at least some contract subscribe topics are discovered."""
        topics = _collect_contract_subscribe_topics()
        assert len(topics) > 0, "No contract subscribe topics found"

    def test_dispatch_route_topics_exist(self) -> None:
        """Smoke test: at least some dispatch route topics are discovered."""
        topics = _collect_dispatch_route_topics()
        assert len(topics) > 0, "No dispatch route topics found"

    def test_every_subscribed_cmd_topic_has_dispatch_handler(self) -> None:
        """Every onex.cmd.* subscribe topic must have a dispatch route.

        This is the core parity check. A command topic declared in a
        contract's subscribe_topics but missing from the dispatch engine
        means published commands go into the void.

        Known unwired topics are tracked in _KNOWN_UNWIRED_SUBSCRIBE_CMD.
        The test fails only on NEW violations not in that set.
        """
        contract_topics = _collect_contract_subscribe_topics()
        additional_topics = _collect_additional_subscribe_topics()
        dispatch_topics = _collect_dispatch_route_topics()

        # Combine all subscribed command topics
        all_subscribed_cmd: dict[str, str] = {}  # topic -> source node
        for node_name, topics in contract_topics.items():
            for topic in topics:
                if ".cmd." in topic:
                    all_subscribed_cmd[topic] = node_name
        for topic in additional_topics:
            if ".cmd." in topic:
                all_subscribed_cmd[topic] = "_ADDITIONAL_SUBSCRIBE_TOPICS"

        # Check each subscribed command topic has a dispatch route
        missing: list[str] = []
        known_missing: list[str] = []
        for topic, source in sorted(all_subscribed_cmd.items()):
            # Check both canonical and dispatch forms
            if (
                topic not in dispatch_topics
                and _to_dispatch(topic) not in dispatch_topics
            ):
                if topic in _KNOWN_UNWIRED_SUBSCRIBE_CMD:
                    known_missing.append(f"  [known] {topic} ({source})")
                else:
                    missing.append(f"  {topic} (declared in {source})")

        if known_missing:
            print(
                f"\nKnown unwired cmd topics ({len(known_missing)}):\n"
                + "\n".join(known_missing)
            )

        if missing:
            pytest.fail(
                f"NEW command topics with NO dispatch handler ({len(missing)}):\n"
                + "\n".join(missing)
                + "\n\nThese topics accept commands but have no registered "
                "handler — requests will go into the void. "
                "If intentional, add to _KNOWN_UNWIRED_SUBSCRIBE_CMD."
            )

    def test_every_subscribed_evt_topic_has_dispatch_handler(self) -> None:
        """Every onex.evt.* subscribe topic must have a dispatch route.

        Event topics can also be subscribed to (e.g., pattern-learned
        events routed to the storage handler).

        Known unwired topics are tracked in _KNOWN_UNWIRED_SUBSCRIBE_EVT.
        """
        contract_topics = _collect_contract_subscribe_topics()
        dispatch_topics = _collect_dispatch_route_topics()

        all_subscribed_evt: dict[str, str] = {}
        for node_name, topics in contract_topics.items():
            for topic in topics:
                if ".evt." in topic:
                    all_subscribed_evt[topic] = node_name

        missing: list[str] = []
        known_missing: list[str] = []
        for topic, source in sorted(all_subscribed_evt.items()):
            if (
                topic not in dispatch_topics
                and _to_dispatch(topic) not in dispatch_topics
            ):
                if topic in _KNOWN_UNWIRED_SUBSCRIBE_EVT:
                    known_missing.append(f"  [known] {topic} ({source})")
                else:
                    missing.append(f"  {topic} (declared in {source})")

        if known_missing:
            print(
                f"\nKnown unwired evt topics ({len(known_missing)}):\n"
                + "\n".join(known_missing)
            )

        if missing:
            pytest.fail(
                f"NEW event topics with NO dispatch handler ({len(missing)}):\n"
                + "\n".join(missing)
                + "\n\nThese topics are subscribed to but have no registered "
                "handler — events will be consumed but not processed. "
                "If intentional, add to _KNOWN_UNWIRED_SUBSCRIBE_EVT."
            )

    def test_every_dispatch_route_has_contract_subscription(self) -> None:
        """Every dispatch route topic should trace back to a contract.

        A dispatch handler registered for a topic that no contract
        subscribes to is dead code — it will never receive messages.

        Note: Some routes use dispatch-format topics (.commands./.events.)
        while contracts use canonical format (.cmd./.evt.). We normalize
        before comparing.
        """
        contract_topics = _collect_contract_subscribe_topics()
        additional_topics = _collect_additional_subscribe_topics()
        dispatch_topics = _collect_dispatch_route_topics()

        # Build set of all subscribed topics (canonical form)
        all_subscribed: set[str] = set()
        for topics in contract_topics.values():
            all_subscribed.update(topics)
        all_subscribed.update(additional_topics)

        # Also add the publish-side event topics that trigger dispatch
        # (e.g., pattern-learned, pattern-stored are published events that
        # trigger the storage/projection handlers).
        all_published: set[str] = set()
        for child in sorted(_NODES_DIR.iterdir()):
            if not child.is_dir() or child.name.startswith(("_", ".")):
                continue
            contract_path = child / "contract.yaml"
            if not contract_path.exists():
                continue
            with open(contract_path) as f:
                contract: Any = yaml.safe_load(f)
            if not isinstance(contract, dict):
                continue
            event_bus = contract.get("event_bus", {})
            if isinstance(event_bus, dict):
                pub_topics = event_bus.get("publish_topics", [])
                if isinstance(pub_topics, list):
                    all_published.update(
                        str(t).removeprefix("{env}.") for t in pub_topics if t
                    )

        # Review pairing publish topics
        review_contract = _REVIEW_PAIRING_DIR / "contract.yaml"
        if review_contract.exists():
            with open(review_contract) as f:
                contract = yaml.safe_load(f)
            if isinstance(contract, dict):
                event_bus = contract.get("event_bus", {})
                if isinstance(event_bus, dict):
                    pub_topics = event_bus.get("publish_topics", [])
                    if isinstance(pub_topics, list):
                        all_published.update(
                            str(t).removeprefix("{env}.") for t in pub_topics if t
                        )

        # A dispatch route is justified if its topic appears in either
        # subscribe_topics OR publish_topics (event-driven routes react
        # to published events, not just subscribed commands).
        all_known = all_subscribed | all_published

        orphaned: list[str] = []
        known_orphaned: list[str] = []
        for topic in sorted(dispatch_topics):
            canonical = _to_canonical(topic)
            if canonical not in all_known:
                if canonical in _KNOWN_ORPHAN_DISPATCH_ROUTES:
                    known_orphaned.append(f"  [known] {topic}")
                else:
                    orphaned.append(f"  {topic} (canonical: {canonical})")

        if known_orphaned:
            print(
                f"\nKnown orphan dispatch routes ({len(known_orphaned)}):\n"
                + "\n".join(known_orphaned)
            )

        if orphaned:
            pytest.fail(
                f"NEW dispatch routes with NO matching contract topic ({len(orphaned)}):\n"
                + "\n".join(orphaned)
                + "\n\nThese routes are registered but no contract declares "
                "a matching subscribe or publish topic. They may be dead code. "
                "If intentional, add to _KNOWN_ORPHAN_DISPATCH_ROUTES."
            )

    def test_known_unwired_sets_not_stale(self) -> None:
        """Known-unwired sets must not contain topics that ARE now wired.

        If a topic was added to _KNOWN_UNWIRED_* but later gets a dispatch
        handler, it should be removed from the known set. This test catches
        stale entries.
        """
        dispatch_topics = _collect_dispatch_route_topics()

        stale_cmd: list[str] = []
        for topic in sorted(_KNOWN_UNWIRED_SUBSCRIBE_CMD):
            if topic in dispatch_topics or _to_dispatch(topic) in dispatch_topics:
                stale_cmd.append(f"  {topic}")

        stale_evt: list[str] = []
        for topic in sorted(_KNOWN_UNWIRED_SUBSCRIBE_EVT):
            if topic in dispatch_topics or _to_dispatch(topic) in dispatch_topics:
                stale_evt.append(f"  {topic}")

        contract_topics = _collect_contract_subscribe_topics()
        additional_topics = _collect_additional_subscribe_topics()
        all_subscribed: set[str] = set()
        for topics in contract_topics.values():
            all_subscribed.update(topics)
        all_subscribed.update(additional_topics)
        # Also add publish topics
        for child in sorted(_NODES_DIR.iterdir()):
            if not child.is_dir() or child.name.startswith(("_", ".")):
                continue
            contract_path = child / "contract.yaml"
            if not contract_path.exists():
                continue
            with open(contract_path) as f:
                contract: Any = yaml.safe_load(f)
            if isinstance(contract, dict):
                event_bus = contract.get("event_bus", {})
                if isinstance(event_bus, dict):
                    pub_topics = event_bus.get("publish_topics", [])
                    if isinstance(pub_topics, list):
                        all_subscribed.update(
                            str(t).removeprefix("{env}.") for t in pub_topics if t
                        )

        stale_orphan: list[str] = []
        for topic in sorted(_KNOWN_ORPHAN_DISPATCH_ROUTES):
            if topic in all_subscribed:
                stale_orphan.append(f"  {topic}")

        errors: list[str] = []
        if stale_cmd:
            errors.append(
                "Stale _KNOWN_UNWIRED_SUBSCRIBE_CMD (now wired):\n"
                + "\n".join(stale_cmd)
            )
        if stale_evt:
            errors.append(
                "Stale _KNOWN_UNWIRED_SUBSCRIBE_EVT (now wired):\n"
                + "\n".join(stale_evt)
            )
        if stale_orphan:
            errors.append(
                "Stale _KNOWN_ORPHAN_DISPATCH_ROUTES (now in contracts):\n"
                + "\n".join(stale_orphan)
            )
        if errors:
            pytest.fail(
                "Known-unwired sets contain stale entries — remove them:\n\n"
                + "\n\n".join(errors)
            )

    def test_parity_summary(self) -> None:
        """Print a summary of dispatch parity for visibility."""
        contract_topics = _collect_contract_subscribe_topics()
        additional_topics = _collect_additional_subscribe_topics()
        dispatch_topics = _collect_dispatch_route_topics()

        total_subscribed = sum(len(t) for t in contract_topics.values())
        total_subscribed += len(additional_topics)

        print("\n--- Dispatch Parity Summary ---")
        print(f"Contract nodes with subscribe_topics: {len(contract_topics)}")
        print(f"Total subscribed topics: {total_subscribed}")
        print(f"Additional subscribe topics: {len(additional_topics)}")
        print(f"Dispatch route topics: {len(dispatch_topics)}")
        print("-------------------------------\n")
