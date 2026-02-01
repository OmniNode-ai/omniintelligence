# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ONEX Introspection Support for Pattern Demotion Effect Node.

This module provides introspection capabilities for the pattern demotion
effect node, enabling standardized node discovery, metadata exposure,
and contract retrieval.

Part of OMN-1681: Pattern demotion logic for validated patterns.
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


class PatternDemotionErrorCode(Enum):
    """Error codes for pattern demotion operations.

    These codes map to the error handling configuration for the demotion effect.
    """

    DEMO_001 = "DEMO_001"  # Input validation failed
    DEMO_002 = "DEMO_002"  # Database operation error
    DEMO_003 = "DEMO_003"  # Kafka publish error
    DEMO_004 = "DEMO_004"  # Demotion criteria evaluation error

    def get_number(self) -> int:
        """Get the numeric portion of the error code."""
        return int(self.value.split("_")[1])

    def get_description(self) -> str:
        """Get the description for this error code."""
        descriptions = {
            "DEMO_001": "Input validation failed (e.g., invalid request parameters)",
            "DEMO_002": "Error during database operation (pattern status update)",
            "DEMO_003": "Error publishing Kafka event (pattern-demoted event)",
            "DEMO_004": "Error evaluating demotion criteria against rolling window metrics",
        }
        return descriptions.get(self.value, "Unknown error")

    def get_exit_code(self) -> int:
        """Get the exit code for this error."""
        # DEMO_001 is non-recoverable, others are recoverable
        return 1 if self.value == "DEMO_001" else 2


@dataclass(frozen=True)
class PatternDemotionMetadataLoader:
    """Metadata loader for pattern demotion effect node.

    Provides node metadata for introspection, sourced from node implementation.
    """

    node_name: str = "pattern_demotion_effect"
    node_version: ModelSemVer = field(
        default_factory=lambda: ModelSemVer(major=1, minor=0, patch=0)
    )
    node_description: str = (
        "Effect node that demotes validated patterns to deprecated status based on "
        "rolling window failure metrics. Evaluates patterns against configurable "
        "demotion gates (injection count, failure rate, failure streak) and "
        "publishes Kafka events for demoted patterns. Supports dry_run mode for "
        "previewing demotions without committing changes."
    )

    @property
    def input_state_class(self) -> type[BaseModel]:
        """Return the input state model class."""
        from omniintelligence.nodes.node_pattern_demotion_effect.models import (
            ModelDemotionCheckRequest,
        )

        return ModelDemotionCheckRequest

    @property
    def output_state_class(self) -> type[BaseModel]:
        """Return the output state model class."""
        from omniintelligence.nodes.node_pattern_demotion_effect.models import (
            ModelDemotionCheckResult,
        )

        return ModelDemotionCheckResult

    @property
    def error_codes_class(self) -> type[Enum]:
        """Return the error codes enum class."""
        return PatternDemotionErrorCode


class PatternDemotionIntrospection(MixinNodeIntrospection):
    """Introspection support for pattern demotion effect node.

    This class provides standardized introspection capabilities following
    the ONEX pattern. It enables:
    - Node discovery through --introspect CLI flag
    - Contract and schema exposure
    - Capability advertisement
    - Event channel configuration

    Usage:
        # Generate introspection response
        response = PatternDemotionIntrospection.get_introspection_response()

        # Handle --introspect CLI command
        if "--introspect" in sys.argv:
            PatternDemotionIntrospection.handle_introspect_command()
    """

    _metadata_loader: PatternDemotionMetadataLoader | None = None

    @classmethod
    def get_metadata_loader(cls) -> PatternDemotionMetadataLoader:
        """Get the metadata loader instance.

        Returns:
            PatternDemotionMetadataLoader with node metadata.
        """
        if cls._metadata_loader is None:
            cls._metadata_loader = PatternDemotionMetadataLoader()
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
            "pattern-demotion",
            "rolling-window",
            "kafka",
            "database",
            "state-transition",
            "validated-to-deprecated",
        ]

    @classmethod
    def _get_node_maturity(cls) -> str:
        """Return node maturity level."""
        return "stable"

    @classmethod
    def _get_node_use_cases(cls) -> list[str]:
        """Return node use cases."""
        return [
            "Automatically demote validated patterns failing performance thresholds",
            "Evaluate patterns against rolling window metrics (last 20 injections)",
            "Publish Kafka events for pattern state transitions",
            "Support dry_run mode for demotion previews",
            "Gate demotions on injection count, failure rate, and failure streak",
            "Immediately demote manually disabled patterns (hard trigger bypasses cooldown)",
        ]

    @classmethod
    def get_runtime_dependencies(cls) -> list[str]:
        """Return runtime dependencies."""
        return ["omnibase_core", "pydantic", "asyncpg", "confluent-kafka"]

    @classmethod
    def get_cli_entrypoint(cls) -> str:
        """Return CLI entrypoint command."""
        return "python -m omniintelligence.nodes.node_pattern_demotion_effect"


# Convenience function for direct introspection access
def get_introspection_response() -> ModelNodeIntrospectionResponse:
    """Get the introspection response for pattern demotion effect node.

    Returns:
        ModelNodeIntrospectionResponse with all node metadata and capabilities.
    """
    return PatternDemotionIntrospection.get_introspection_response()


__all__ = [
    "PatternDemotionErrorCode",
    "PatternDemotionIntrospection",
    "PatternDemotionMetadataLoader",
    "get_introspection_response",
]
