# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ONEX Introspection Support for Pattern Promotion Effect Node.

This module provides introspection capabilities for the pattern promotion
effect node, enabling standardized node discovery, metadata exposure,
and contract retrieval.

Part of OMN-1680: Auto-promote logic for provisional patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from omnibase_core.mixins.mixin_introspection import MixinNodeIntrospection
from omnibase_core.models.primitives.model_semver import ModelSemVer

if TYPE_CHECKING:
    from omnibase_core.models.core.model_node_introspection_response import (
        ModelNodeIntrospectionResponse,
    )
    from pydantic import BaseModel


class PatternPromotionErrorCode(Enum):
    """Error codes for pattern promotion operations.

    These codes map to the error handling configuration for the promotion effect.
    """

    PROMO_001 = "PROMO_001"  # Input validation failed
    PROMO_002 = "PROMO_002"  # Database operation error
    PROMO_003 = "PROMO_003"  # Kafka publish error
    PROMO_004 = "PROMO_004"  # Promotion criteria evaluation error

    def get_number(self) -> int:
        """Get the numeric portion of the error code."""
        return int(self.value.split("_")[1])

    def get_description(self) -> str:
        """Get the description for this error code."""
        descriptions = {
            "PROMO_001": "Input validation failed (e.g., invalid request parameters)",
            "PROMO_002": "Error during database operation (pattern status update)",
            "PROMO_003": "Error publishing Kafka event (pattern-promoted event)",
            "PROMO_004": "Error evaluating promotion criteria against rolling window metrics",
        }
        return descriptions.get(self.value, "Unknown error")

    def get_exit_code(self) -> int:
        """Get the exit code for this error."""
        # PROMO_001 is non-recoverable, others are recoverable
        return 1 if self.value == "PROMO_001" else 2


@dataclass(frozen=True)
class PatternPromotionMetadataLoader:
    """Metadata loader for pattern promotion effect node.

    Provides node metadata for introspection, sourced from node implementation.
    """

    node_name: str = "pattern_promotion_effect"
    node_version: ModelSemVer = field(
        default_factory=lambda: ModelSemVer(major=1, minor=0, patch=0)
    )
    node_description: str = (
        "Effect node that promotes provisional patterns to validated status based on "
        "rolling window success metrics. Evaluates patterns against configurable "
        "promotion gates (injection count, success rate, failure streak) and publishes "
        "Kafka events for promoted patterns. Supports dry_run mode for previewing "
        "promotions without committing changes."
    )

    @property
    def input_state_class(self) -> type[BaseModel]:
        """Return the input state model class."""
        from omniintelligence.nodes.node_pattern_promotion_effect.models import (
            ModelPromotionCheckRequest,
        )

        return ModelPromotionCheckRequest

    @property
    def output_state_class(self) -> type[BaseModel]:
        """Return the output state model class."""
        from omniintelligence.nodes.node_pattern_promotion_effect.models import (
            ModelPromotionCheckResult,
        )

        return ModelPromotionCheckResult

    @property
    def error_codes_class(self) -> type[Enum]:
        """Return the error codes enum class."""
        return PatternPromotionErrorCode


class PatternPromotionIntrospection(MixinNodeIntrospection):
    """Introspection support for pattern promotion effect node.

    This class provides standardized introspection capabilities following
    the ONEX pattern. It enables:
    - Node discovery through --introspect CLI flag
    - Contract and schema exposure
    - Capability advertisement
    - Event channel configuration

    Usage:
        # Generate introspection response
        response = PatternPromotionIntrospection.get_introspection_response()

        # Handle --introspect CLI command
        if "--introspect" in sys.argv:
            PatternPromotionIntrospection.handle_introspect_command()
    """

    _metadata_loader: PatternPromotionMetadataLoader | None = None

    @classmethod
    def get_metadata_loader(cls) -> PatternPromotionMetadataLoader:
        """Get the metadata loader instance.

        Returns:
            PatternPromotionMetadataLoader with node metadata.
        """
        if cls._metadata_loader is None:
            cls._metadata_loader = PatternPromotionMetadataLoader()
        return cls._metadata_loader

    @classmethod
    def get_node_author(cls) -> str:
        """Return the node author."""
        return "OmniNode Team"

    @classmethod
    def _get_node_category(cls) -> str:
        """Return node category."""
        return "effect"

    @classmethod
    def _get_node_tags(cls) -> list[str]:
        """Return node tags from node metadata."""
        return [
            "ONEX",
            "effect",
            "pattern-promotion",
            "rolling-window",
            "kafka",
            "database",
            "state-transition",
            "provisional-to-validated",
        ]

    @classmethod
    def _get_node_maturity(cls) -> str:
        """Return node maturity level."""
        return "stable"

    @classmethod
    def _get_node_use_cases(cls) -> list[str]:
        """Return node use cases."""
        return [
            "Automatically promote provisional patterns meeting success thresholds",
            "Evaluate patterns against rolling window metrics (last 20 injections)",
            "Publish Kafka events for pattern state transitions",
            "Support dry_run mode for promotion previews",
            "Gate promotions on injection count, success rate, and failure streak",
            "Prevent promotion of disabled patterns",
        ]

    @classmethod
    def get_runtime_dependencies(cls) -> list[str]:
        """Return runtime dependencies."""
        return ["omnibase_core", "pydantic", "asyncpg", "confluent-kafka"]

    @classmethod
    def get_cli_entrypoint(cls) -> str:
        """Return CLI entrypoint command."""
        return "python -m omniintelligence.runtime.stub_launcher --node-type effect --node-name node_pattern_promotion_effect"


# Convenience function for direct introspection access
def get_introspection_response() -> ModelNodeIntrospectionResponse:
    """Get the introspection response for pattern promotion effect node.

    Returns:
        ModelNodeIntrospectionResponse with all node metadata and capabilities.
    """
    return PatternPromotionIntrospection.get_introspection_response()


__all__ = [
    "PatternPromotionErrorCode",
    "PatternPromotionIntrospection",
    "PatternPromotionMetadataLoader",
    "get_introspection_response",
]
