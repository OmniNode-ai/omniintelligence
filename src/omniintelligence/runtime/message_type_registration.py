# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Intelligence domain message type registration.

Registers all intelligence wire models (Kafka event payloads, reducer FSM
payloads, and command inputs) with ``RegistryMessageType``.  This enables
type-based envelope routing and startup validation for the intelligence domain.

The registration list is intentionally explicit rather than derived from
contract YAML files.  Contract-driven discovery is acceptable as a future
enhancement, but an explicit list keeps the registration deterministic and
auditable.

Design:
    - All registrations use ``domain="intelligence"``
    - ``handler_id`` matches the node directory name
    - ``category`` follows topic naming: ``.cmd.`` -> COMMAND, ``.evt.`` -> EVENT
    - Reducer FSM payloads use COMMAND category (internal dispatch)
    - Fan-out registration (multiple handlers for one type) uses repeated
      ``register_simple()`` calls, which trigger the merge path

Related:
    - OMN-2039: Register intelligence message types in RegistryMessageType
    - OMN-937: Central Message Type Registry implementation
"""

from __future__ import annotations

import logging

from omnibase_infra.enums import EnumMessageCategory
from omnibase_infra.runtime.registry import RegistryMessageType

logger = logging.getLogger(__name__)

INTELLIGENCE_DOMAIN = "intelligence"
"""Owning domain for all intelligence message types."""

# Total number of unique message types registered.
# Used in tests and validate_startup logging.
EXPECTED_MESSAGE_TYPE_COUNT = 13


def register_intelligence_message_types(
    registry: RegistryMessageType,
) -> list[str]:
    """Register all intelligence wire models with the message type registry.

    This function registers 13 message types spanning:
    - 5 Kafka event models (published by effect nodes)
    - 4 Kafka command/event models (consumed by effect nodes)
    - 1 external input model (session outcome)
    - 3 reducer FSM payloads (internal dispatch)

    The registry is NOT frozen by this function.  The caller is responsible
    for calling ``registry.freeze()`` after all domains have registered.

    Args:
        registry: An unfrozen RegistryMessageType instance.

    Returns:
        List of registered message type names (for logging).

    Raises:
        ModelOnexError: If registry is already frozen.
        MessageTypeRegistryError: If any registration fails validation.
    """
    registered: list[str] = []

    # =========================================================================
    # Kafka Event Models (published by effect nodes) -- EVENT category
    # =========================================================================

    # 1. Intent classification result (claude hook -> intent classified)
    registry.register_simple(
        message_type="ModelClaudeHookResult",
        handler_id="node_claude_hook_event_effect",
        category=EnumMessageCategory.EVENT,
        domain=INTELLIGENCE_DOMAIN,
        description="Intent classification result published after claude hook processing",
    )
    registered.append("ModelClaudeHookResult")

    # 2. Pattern stored confirmation
    registry.register_simple(
        message_type="ModelPatternStoredEvent",
        handler_id="node_pattern_storage_effect",
        category=EnumMessageCategory.EVENT,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern stored confirmation event",
    )
    registered.append("ModelPatternStoredEvent")

    # 3. Pattern promoted event
    registry.register_simple(
        message_type="ModelPatternPromotedEvent",
        handler_id="node_pattern_storage_effect",
        category=EnumMessageCategory.EVENT,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern promotion event (provisional -> validated)",
    )
    registered.append("ModelPatternPromotedEvent")

    # 4. Pattern deprecated event
    registry.register_simple(
        message_type="ModelPatternDeprecatedEvent",
        handler_id="node_pattern_demotion_effect",
        category=EnumMessageCategory.EVENT,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern deprecation event (validated -> deprecated)",
    )
    registered.append("ModelPatternDeprecatedEvent")

    # 5. Pattern lifecycle transitioned event
    registry.register_simple(
        message_type="ModelPatternLifecycleTransitionedEvent",
        handler_id="node_pattern_lifecycle_effect",
        category=EnumMessageCategory.EVENT,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern lifecycle state transition completed",
    )
    registered.append("ModelPatternLifecycleTransitionedEvent")

    # =========================================================================
    # Kafka Command Models (consumed by effect nodes) -- COMMAND category
    # =========================================================================

    # 6. Claude Code hook event (cmd topic)
    registry.register_simple(
        message_type="ModelClaudeCodeHookEvent",
        handler_id="node_claude_hook_event_effect",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Claude Code hook event command input",
    )
    registered.append("ModelClaudeCodeHookEvent")

    # 7. Pattern storage input (consumed from evt topic: pattern-learned)
    registry.register_simple(
        message_type="ModelPatternStorageInput",
        handler_id="node_pattern_storage_effect",
        category=EnumMessageCategory.EVENT,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern storage input consumed from pattern-learned topic",
    )
    registered.append("ModelPatternStorageInput")

    # 8. Pattern lifecycle event (cmd topic)
    #    Topic: onex.cmd.omniintelligence.pattern-lifecycle-transition.v1
    #    Published by promotion/demotion effects, consumed by lifecycle effect.
    registry.register_simple(
        message_type="ModelPatternLifecycleEvent",
        handler_id="node_pattern_lifecycle_effect",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern lifecycle event command consumed by lifecycle effect node",
    )
    registered.append("ModelPatternLifecycleEvent")

    # 9. Pattern lifecycle transition command (cmd topic)
    registry.register_simple(
        message_type="ModelPayloadUpdatePatternStatus",
        handler_id="node_pattern_lifecycle_effect",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern lifecycle transition command input",
    )
    registered.append("ModelPayloadUpdatePatternStatus")

    # =========================================================================
    # External Input Model -- COMMAND category
    # =========================================================================

    # 10. Claude session outcome (consumed by feedback effect)
    registry.register_simple(
        message_type="ClaudeSessionOutcome",
        handler_id="node_pattern_feedback_effect",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Claude session outcome for pattern feedback recording",
    )
    registered.append("ClaudeSessionOutcome")

    # =========================================================================
    # Reducer FSM Payloads (internal dispatch) -- COMMAND category
    # =========================================================================

    # 11. Ingestion FSM payload
    registry.register_simple(
        message_type="ModelIngestionPayload",
        handler_id="node_intelligence_reducer",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Ingestion FSM payload for reducer state transitions",
    )
    registered.append("ModelIngestionPayload")

    # 12. Pattern learning FSM payload
    registry.register_simple(
        message_type="ModelPatternLearningPayload",
        handler_id="node_intelligence_reducer",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Pattern learning FSM payload for reducer state transitions",
    )
    registered.append("ModelPatternLearningPayload")

    # 13. Quality assessment FSM payload
    registry.register_simple(
        message_type="ModelQualityAssessmentPayload",
        handler_id="node_intelligence_reducer",
        category=EnumMessageCategory.COMMAND,
        domain=INTELLIGENCE_DOMAIN,
        description="Quality assessment FSM payload for reducer state transitions",
    )
    registered.append("ModelQualityAssessmentPayload")

    logger.info(
        "Registered %d intelligence message types with RegistryMessageType",
        len(registered),
    )

    return registered


__all__ = [
    "EXPECTED_MESSAGE_TYPE_COUNT",
    "INTELLIGENCE_DOMAIN",
    "register_intelligence_message_types",
]
