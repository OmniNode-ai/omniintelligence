# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Consumer module for pattern_storage_effect node.

Provides event envelope validation, Kafka consumer utilities,
and idempotency support for exactly-once processing.

Key Components:
    - PatternStorageConsumer: Main Kafka consumer with idempotency
    - ModelEventEnvelope: Event envelope validation model
    - IdempotencyGate: Atomic dedupe via INSERT ON CONFLICT
    - cleanup_processed_events: Background cleanup for processed events

Reference: OMN-1669 (STORE-004)
"""

from omniintelligence.nodes.pattern_storage_effect.consumer.consumer import (
    DEFAULT_CONSUMER_GROUP,
    DEFAULT_SUBSCRIBE_TOPIC,
    PatternStorageConsumer,
)
from omniintelligence.nodes.pattern_storage_effect.consumer.envelope import (
    ModelEventEnvelope,
)
from omniintelligence.nodes.pattern_storage_effect.consumer.idempotency import (
    IdempotencyGate,
    cleanup_processed_events,
)

__all__ = [
    "DEFAULT_CONSUMER_GROUP",
    "DEFAULT_SUBSCRIBE_TOPIC",
    "IdempotencyGate",
    "ModelEventEnvelope",
    "PatternStorageConsumer",
    "cleanup_processed_events",
]
