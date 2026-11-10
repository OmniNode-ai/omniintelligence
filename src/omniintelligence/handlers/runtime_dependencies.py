# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Build the runtime dependencies the intelligence plugin hands to contract handlers.

Holds ``register_contract_handler_dependencies`` (the constructor dependencies of
contract-declared handlers, below) and ``build_bloom_eval_llm_client`` (moved from
``runtime/plugin.py``, which the file-shape ratchet allows only to shrink).

Register the constructor dependencies of contract-declared handlers.

The one runtime auto-wires every node contract this package announces through
``omnibase_infra.runtime.auto_wiring.wire_from_manifest``. Its handler resolver
(``ServiceHandlerResolver``) can supply a constructor parameter only from the
node registry's explicit dependency map, the container, or the three known
injectables (``event_bus``, ``container``, ``ownership_query``). A handler class
that declares any other required parameter (a store, a repository, a config)
reaches the resolver's last step and raises
``TypeError: Handler ... requires constructor parameters [...]``. Under
``ONEX_WIRING_STRICT_MODE`` (the dev runtime) that error takes the whole boot
down.

The plugin that owns the real stores builds them before the kernel wires the
manifest, so it is the plugin that declares the wiring: this function builds one
instance of each such handler from the plugin's own dependencies and registers it
in the container for the resolver's container step. Every dependency except the
two the handlers type as optional is required and must not be ``None``: a missing
store fails here, loudly, at plugin wiring, never as a default inside a handler.

``llm_client`` is the one dependency the handler types ``| None`` on purpose:
``HandlerEvaluateCompliance`` answers every call without a client with its typed
"LLM client is not configured" error result. The plugin passes what the dispatch
route already passes.

Ticket: OMN-23431
"""

from __future__ import annotations

import logging
import os
from typing import Any

from omnibase_core.models.container.model_onex_container import ModelONEXContainer

from omniintelligence.debug_intel.protocols import ProtocolDebugStore
from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_streak import (
    HandlerStreak,
)
from omniintelligence.nodes.node_ci_failure_tracker_effect.handlers.handler_trigger_record import (
    HandlerTriggerRecord,
)
from omniintelligence.nodes.node_intent_classifier_compute.handlers.handler_intent_classification import (
    DEFAULT_CLASSIFICATION_CONFIG,
    HandlerIntentClassification,
)
from omniintelligence.nodes.node_intent_classifier_compute.models.model_classification_config import (
    ModelClassificationConfig,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.handler_compute import (
    HandlerEvaluateCompliance,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ProtocolLlmClient,
)
from omniintelligence.nodes.node_pattern_promotion_effect.handlers.handler_promotion import (
    HandlerPromotion,
)
from omniintelligence.protocols import ProtocolKafkaPublisher, ProtocolPatternRepository


async def register_contract_handler_dependencies(
    container: ModelONEXContainer,
    debug_store: ProtocolDebugStore,
    pattern_repository: ProtocolPatternRepository,
    kafka_publisher: ProtocolKafkaPublisher | None,
    *,
    classification_config: ModelClassificationConfig = DEFAULT_CLASSIFICATION_CONFIG,
    llm_client: ProtocolLlmClient | None = None,
) -> list[str]:
    """Register one constructed instance per dependency-taking contract handler.

    Args:
        container: The runtime container the resolver reads at its container step.
        debug_store: The debug-intelligence store (``failure_streaks`` and the
            CI failure tables).
        pattern_repository: The pattern repository the promotion handler writes.
        kafka_publisher: The event publisher; ``None`` when the event bus has no
            publish signature (the handlers type it optional).
        classification_config: The intent classifier configuration; the package's
            own default, the one ``AdapterIntentClassifier`` runs on.
        llm_client: The compliance LLM client; ``None`` when none is configured.

    Returns:
        The handler class names registered, in registration order.
    """
    instances: list[object] = [
        HandlerStreak(store=debug_store),
        HandlerTriggerRecord(store=debug_store, kafka_producer=kafka_publisher),
        HandlerPromotion(repository=pattern_repository, producer=kafka_publisher),
        HandlerIntentClassification(config=classification_config),
        HandlerEvaluateCompliance(
            llm_client=llm_client, kafka_producer=kafka_publisher
        ),
    ]
    for instance in instances:
        await container.service_registry.register_instance(
            interface=type(instance), instance=instance
        )
    return [type(instance).__name__ for instance in instances]


logger = logging.getLogger(__name__)

_BLOOM_EVAL_GENERATOR_URL_ENV_VAR = "LLM_CODER_FAST_URL"
_BLOOM_EVAL_JUDGE_URL_ENV_VAR = "LLM_DEEPSEEK_R1_URL"


def build_bloom_eval_llm_client(
    *,
    event_publisher: Any,
    correlation_id: str,
) -> Any:
    """Build EvalLLMClient when Bloom eval endpoint configuration is present."""
    generator_url = os.getenv(_BLOOM_EVAL_GENERATOR_URL_ENV_VAR, "").strip()
    judge_url = os.getenv(_BLOOM_EVAL_JUDGE_URL_ENV_VAR, "").strip()
    if not generator_url or not judge_url:
        logger.warning(
            "Bloom eval runtime handler wired without EvalLLMClient: %s and %s "
            "must both be set (correlation_id=%s)",
            _BLOOM_EVAL_GENERATOR_URL_ENV_VAR,
            _BLOOM_EVAL_JUDGE_URL_ENV_VAR,
            correlation_id,
        )
        return None

    from omniintelligence.adapters.eval_llm_client import EvalLLMClient

    return EvalLLMClient(
        generator_url=generator_url,
        judge_url=judge_url,
        event_publisher=event_publisher,
        correlation_id=correlation_id,
    )


__all__ = ["build_bloom_eval_llm_client", "register_contract_handler_dependencies"]
