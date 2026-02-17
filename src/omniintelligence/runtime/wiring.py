# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Intelligence domain handler wiring for kernel initialization.

This module provides the wire_intelligence_handlers function that instantiates
and registers intelligence domain handlers during plugin initialization.

The wiring follows the domain-driven design principle where Intelligence-specific
handler creation lives in this domain module rather than the generic runtime layer.

Handlers Wired:
    - HandlerPatternLearning: Pure compute handler for pattern aggregation pipeline
    - HandlerClaudeHookEvent: Claude Code hook event processing
    - record_session_outcome: Session feedback recording
    - check_and_promote_patterns: Pattern promotion lifecycle
    - check_and_demote_patterns: Pattern demotion lifecycle
    - handle_store_pattern: Pattern storage with governance

Note:
    Many intelligence handlers are pure functions rather than classes. These
    functions require per-call dependencies (database connections, Kafka producers)
    and cannot be fully wired at initialization time. This wiring module verifies
    importability and instantiates class-based handlers where possible.

Related:
    - OMN-1978: Integration test: kernel boots with PluginIntelligence
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnibase_infra.runtime.models import ModelDomainPluginConfig

logger = logging.getLogger(__name__)

# Handler import specifications: (module_path, attribute_name, is_class)
# Classes are instantiated; functions are verified importable only.
_HANDLER_SPECS: list[tuple[str, str, bool]] = [
    (
        "omniintelligence.nodes.node_pattern_learning_compute.handlers",
        "HandlerPatternLearning",
        True,
    ),
    (
        "omniintelligence.nodes.node_claude_hook_event_effect.handlers",
        "HandlerClaudeHookEvent",
        False,
    ),
    (
        "omniintelligence.nodes.node_pattern_feedback_effect.handlers",
        "record_session_outcome",
        False,
    ),
    (
        "omniintelligence.nodes.node_pattern_promotion_effect.handlers",
        "check_and_promote_patterns",
        False,
    ),
    (
        "omniintelligence.nodes.node_pattern_demotion_effect.handlers",
        "check_and_demote_patterns",
        False,
    ),
    (
        "omniintelligence.nodes.node_pattern_storage_effect.handlers",
        "handle_store_pattern",
        False,
    ),
]


async def wire_intelligence_handlers(
    pool: object,
    config: ModelDomainPluginConfig,
) -> list[str]:
    """Wire intelligence domain handlers into the container.

    Imports, validates, and (where possible) instantiates handlers for the
    intelligence pattern learning pipeline. Class-based handlers are
    instantiated; function-based handlers are verified importable.

    The pool parameter is accepted for future use when handlers need
    database connections wired at initialization time.

    Args:
        pool: Connection pool (opaque object, managed by plugin).
        config: Plugin configuration with container and correlation_id.

    Returns:
        List of service/handler names successfully wired.

    Raises:
        ImportError: If any required handler module cannot be imported.
    """
    correlation_id = config.correlation_id
    services_registered: list[str] = []

    for module_path, attr_name, is_class in _HANDLER_SPECS:
        mod = importlib.import_module(module_path)
        handler_attr = getattr(mod, attr_name)

        if is_class:
            # Instantiate class-based handlers (pure compute, no deps)
            _instance = handler_attr()
            logger.debug(
                "Instantiated %s (correlation_id=%s)",
                attr_name,
                correlation_id,
            )
        else:
            # Verify function-based handlers are importable
            if not callable(handler_attr):
                raise ImportError(f"{attr_name} in {module_path} is not callable")
            logger.debug(
                "Verified %s importable (correlation_id=%s)",
                attr_name,
                correlation_id,
            )

        services_registered.append(attr_name)

    logger.info(
        "Intelligence handlers wired: %d services (correlation_id=%s)",
        len(services_registered),
        correlation_id,
        extra={"services": services_registered},
    )

    # Store pool reference for future handler wiring that needs DB access
    _ = pool

    return services_registered


__all__: list[str] = [
    "wire_intelligence_handlers",
]
