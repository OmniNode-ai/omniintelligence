# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern Promotion Effect - Promotes provisional patterns to validated status.

This node follows the ONEX declarative pattern:
    - EFFECT node for database writes (pattern status updates) and Kafka events
    - Evaluates patterns against rolling window promotion thresholds
    - Lightweight shell that delegates to handlers via dependency injection
    - Pattern: "Contract-driven, handlers wired externally"

Promotion Criteria (configurable via request):
    - Pattern status is 'provisional'
    - injection_count_rolling_20 >= MIN_INJECTION_COUNT (5)
    - success_rate >= MIN_SUCCESS_RATE (0.6 / 60%)
    - failure_streak < MAX_FAILURE_STREAK (3)
    - Not in disabled_patterns_current table

Published Events:
    - onex.evt.omniintelligence.pattern-promoted.v1

Reference:
    - OMN-1680: Auto-promote logic for provisional patterns
    - OMN-1678: Rolling window metrics (dependency)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from omnibase_core.nodes.node_effect import NodeEffect

from omniintelligence.nodes.pattern_promotion_effect.handlers.handler_promotion import (
    ProtocolKafkaPublisher,
    ProtocolPatternRepository,
    check_and_promote_patterns,
)
from omniintelligence.nodes.pattern_promotion_effect.models import (
    ModelPromotionCheckRequest,
    ModelPromotionCheckResult,
)

if TYPE_CHECKING:
    from omnibase_core.models.container.model_onex_container import ModelONEXContainer


logger = logging.getLogger(__name__)


class NodePatternPromotionEffect(NodeEffect):
    """Effect node for promoting provisional patterns to validated status.

    This effect node evaluates provisional patterns against rolling window
    success metrics and promotes those meeting the configured thresholds.
    It is a lightweight shell that delegates actual processing to handler
    functions.

    Promotion Gates (all must pass):
        1. Injection Count: injection_count_rolling_20 >= 5
        2. Success Rate: success_rate >= 60%
        3. Failure Streak: failure_streak < 3
        4. Not Disabled: Pattern not in disabled_patterns_current

    Dependency Injection:
        Adapters are injected via setter methods:
        - set_repository(): Pattern repository for database operations
        - set_kafka_producer(): Kafka producer for event emission

    Example:
        ```python
        from omnibase_core.models.container import ModelONEXContainer
        from omniintelligence.nodes.pattern_promotion_effect import (
            NodePatternPromotionEffect,
        )

        # Create effect node
        container = ModelONEXContainer()
        effect = NodePatternPromotionEffect(container)

        # Wire dependencies
        effect.set_repository(pattern_repo)
        effect.set_kafka_producer(kafka_producer)

        # Check and promote patterns
        request = ModelPromotionCheckRequest(dry_run=False)
        result = await effect.execute(request)
        print(f"Promoted {len(result.patterns_promoted)} patterns")
        ```
    """

    def __init__(self, container: ModelONEXContainer) -> None:
        """Initialize the effect node.

        Args:
            container: ONEX dependency injection container.
        """
        super().__init__(container)

        # Injected dependencies
        self._repository: ProtocolPatternRepository | None = None
        self._kafka_producer: ProtocolKafkaPublisher | None = None
        self._topic_env_prefix: str = "dev"

    def set_repository(self, repository: ProtocolPatternRepository) -> None:
        """Inject the pattern repository (database adapter).

        Args:
            repository: Pattern repository instance implementing
                ProtocolPatternRepository (asyncpg.Connection compatible).
        """
        self._repository = repository

    def set_kafka_producer(self, producer: ProtocolKafkaPublisher) -> None:
        """Set the Kafka producer for event emission.

        Args:
            producer: Kafka producer instance implementing ProtocolKafkaPublisher.
        """
        self._kafka_producer = producer

    def set_topic_env_prefix(self, prefix: str) -> None:
        """Set the environment prefix for Kafka topics.

        Args:
            prefix: Environment prefix (e.g., "dev", "prod").
        """
        self._topic_env_prefix = prefix

    @property
    def has_repository(self) -> bool:
        """Check if repository is configured."""
        return self._repository is not None

    @property
    def has_kafka_producer(self) -> bool:
        """Check if Kafka producer is configured."""
        return self._kafka_producer is not None

    @property
    def topic_env_prefix(self) -> str:
        """Get the configured Kafka topic environment prefix."""
        return self._topic_env_prefix

    async def execute(
        self, request: ModelPromotionCheckRequest
    ) -> ModelPromotionCheckResult:
        """Execute the effect node to check and promote patterns.

        Evaluates all provisional patterns against the promotion gates
        and promotes those meeting all criteria. Supports dry_run mode
        to preview promotions without committing.

        Note:
            The request model's min_success_count, min_success_rate, and
            min_sample_size parameters are NOT used in the current
            implementation. The handler uses fixed thresholds defined
            in handler_promotion.py (MIN_INJECTION_COUNT=5, MIN_SUCCESS_RATE=0.6,
            MAX_FAILURE_STREAK=3). This may be enhanced in a future version.

        Args:
            request: The promotion check request with criteria and options.

        Returns:
            ModelPromotionCheckResult with promotion outcomes.
        """
        correlation_id = request.correlation_id

        if self._repository is None:
            logger.error(
                "Repository not configured for pattern promotion",
                extra={"correlation_id": str(correlation_id) if correlation_id else None},
            )
            return ModelPromotionCheckResult(
                dry_run=request.dry_run,
                patterns_checked=0,
                patterns_eligible=0,
                patterns_promoted=[],
                correlation_id=correlation_id,
            )

        try:
            logger.debug(
                "Executing pattern promotion check",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "dry_run": request.dry_run,
                },
            )

            result = await check_and_promote_patterns(
                repository=self._repository,
                producer=self._kafka_producer,
                dry_run=request.dry_run,
                correlation_id=correlation_id,
                topic_env_prefix=self._topic_env_prefix,
            )

            logger.info(
                "Pattern promotion check completed",
                extra={
                    "correlation_id": str(correlation_id) if correlation_id else None,
                    "patterns_checked": result.patterns_checked,
                    "patterns_eligible": result.patterns_eligible,
                    "patterns_promoted": len(result.patterns_promoted),
                    "dry_run": result.dry_run,
                },
            )

            return result

        except Exception as e:
            logger.exception(
                "Error during pattern promotion check: %s",
                str(e),
                extra={"correlation_id": str(correlation_id) if correlation_id else None},
            )
            return ModelPromotionCheckResult(
                dry_run=request.dry_run,
                patterns_checked=0,
                patterns_eligible=0,
                patterns_promoted=[],
                correlation_id=correlation_id,
            )


__all__ = ["NodePatternPromotionEffect"]
