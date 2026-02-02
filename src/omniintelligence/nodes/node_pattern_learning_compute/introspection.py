"""ONEX Introspection Support for Pattern Learning Compute Node.

This module provides introspection capabilities for the pattern learning
compute node, enabling standardized node discovery, metadata exposure,
and contract retrieval.

Part of OMN-1663: PATLEARN-008 Node shell + contract activation.
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


class PatternLearningErrorCode(Enum):
    """Error codes for pattern learning operations.

    These codes map to the error handling configuration in contract.yaml.
    """

    PATLEARN_001 = "PATLEARN_001"  # Input validation failed
    PATLEARN_002 = "PATLEARN_002"  # Pattern learning computation error

    def get_number(self) -> int:
        """Get the numeric portion of the error code."""
        return int(self.value.split("_")[1])

    def get_description(self) -> str:
        """Get the description for this error code."""
        descriptions = {
            "PATLEARN_001": "Input validation failed (e.g., empty training data, invalid parameters)",
            "PATLEARN_002": "Error during pattern learning computation",
        }
        return descriptions.get(self.value, "Unknown error")

    def get_exit_code(self) -> int:
        """Get the exit code for this error."""
        # PATLEARN_001 is non-recoverable, PATLEARN_002 is recoverable
        return 1 if self.value == "PATLEARN_001" else 2


@dataclass(frozen=True)
class PatternLearningMetadataLoader:
    """Metadata loader for pattern learning compute node.

    Provides node metadata for introspection, sourced from contract.yaml.
    """

    node_name: str = "pattern_learning_compute"
    node_version: ModelSemVer = field(
        default_factory=lambda: ModelSemVer(major=1, minor=0, patch=0)
    )
    node_description: str = (
        "Compute node that aggregates and summarizes observed code patterns. "
        "Orchestrates a 4-phase pipeline: feature extraction, clustering, "
        "confidence scoring, and deduplication. This node describes STRUCTURE, "
        "not IMPORTANCE - all thresholds are inputs, not decisions made here."
    )

    @property
    def input_state_class(self) -> type[BaseModel]:
        """Return the input state model class."""
        from omniintelligence.nodes.node_pattern_learning_compute.models import (
            ModelPatternLearningInput,
        )

        return ModelPatternLearningInput

    @property
    def output_state_class(self) -> type[BaseModel]:
        """Return the output state model class."""
        from omniintelligence.nodes.node_pattern_learning_compute.models import (
            ModelPatternLearningOutput,
        )

        return ModelPatternLearningOutput

    @property
    def error_codes_class(self) -> type[Enum]:
        """Return the error codes enum class."""
        return PatternLearningErrorCode


class PatternLearningIntrospection(MixinNodeIntrospection):
    """Introspection support for pattern learning compute node.

    This class provides standardized introspection capabilities following
    the ONEX pattern. It enables:
    - Node discovery through --introspect CLI flag
    - Contract and schema exposure
    - Capability advertisement
    - Event channel configuration

    Usage:
        # Generate introspection response
        response = PatternLearningIntrospection.get_introspection_response()

        # Handle --introspect CLI command
        if "--introspect" in sys.argv:
            PatternLearningIntrospection.handle_introspect_command()
    """

    _metadata_loader: PatternLearningMetadataLoader | None = None

    @classmethod
    def get_metadata_loader(cls) -> PatternLearningMetadataLoader:
        """Get the metadata loader instance.

        Returns:
            PatternLearningMetadataLoader with node metadata.
        """
        if cls._metadata_loader is None:
            cls._metadata_loader = PatternLearningMetadataLoader()
        return cls._metadata_loader

    @classmethod
    def get_node_author(cls) -> str:
        """Return the node author."""
        return "OmniNode Team"

    @classmethod
    def _get_node_category(cls) -> str:
        """Return node category."""
        return "compute"

    @classmethod
    def _get_node_tags(cls) -> list[str]:
        """Return node tags from contract.yaml metadata."""
        return [
            "ONEX",
            "compute",
            "pattern-learning",
            "pattern-aggregation",
            "clustering",
            "deduplication",
        ]

    @classmethod
    def _get_node_maturity(cls) -> str:
        """Return node maturity level."""
        return "stable"

    @classmethod
    def _get_node_use_cases(cls) -> list[str]:
        """Return node use cases."""
        return [
            "Aggregate code patterns from training data",
            "Cluster similar patterns by structural similarity",
            "Score pattern confidence for promotion decisions",
            "Deduplicate overlapping patterns",
            "Split patterns by promotion threshold into candidates vs learned",
        ]

    @classmethod
    def get_runtime_dependencies(cls) -> list[str]:
        """Return runtime dependencies."""
        return ["omnibase_core", "pydantic"]

    @classmethod
    def get_cli_entrypoint(cls) -> str:
        """Return CLI entrypoint command."""
        return "python -m omniintelligence.nodes.node_pattern_learning_compute"


# Convenience function for direct introspection access
def get_introspection_response() -> ModelNodeIntrospectionResponse:
    """Get the introspection response for pattern learning compute node.

    Returns:
        ModelNodeIntrospectionResponse with all node metadata and capabilities.
    """
    return PatternLearningIntrospection.get_introspection_response()


__all__ = [
    "PatternLearningErrorCode",
    "PatternLearningIntrospection",
    "PatternLearningMetadataLoader",
    "get_introspection_response",
]
