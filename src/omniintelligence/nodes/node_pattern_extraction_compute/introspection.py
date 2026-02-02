"""ONEX Introspection Support for Pattern Extraction Compute Node.

This module provides introspection capabilities for the pattern extraction
compute node, enabling standardized node discovery, metadata exposure,
and contract retrieval.

Part of OMN-1402: OmniClaude Learning Compute Node for Pattern Extraction.
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


class PatternExtractionErrorCode(Enum):
    """Error codes for pattern extraction operations.

    These codes map to the error handling configuration in contract.yaml.
    """

    PATTERN_001 = "PATTERN_001"  # Input validation failed
    PATTERN_002 = "PATTERN_002"  # Pattern extraction computation error
    PATTERN_003 = "PATTERN_003"  # Pattern confidence calculation error

    def get_number(self) -> int:
        """Get the numeric portion of the error code."""
        return int(self.value.split("_")[1])

    def get_description(self) -> str:
        """Get the description for this error code."""
        descriptions = {
            "PATTERN_001": "Input validation failed (e.g., invalid session format, missing required fields)",
            "PATTERN_002": "Error during pattern extraction computation",
            "PATTERN_003": "Error calculating pattern confidence scores",
        }
        return descriptions.get(self.value, "Unknown error")

    def get_exit_code(self) -> int:
        """Get the exit code for this error."""
        # PATTERN_001 is non-recoverable, others are recoverable
        return 1 if self.value == "PATTERN_001" else 2


@dataclass(frozen=True)
class PatternExtractionMetadataLoader:
    """Metadata loader for pattern extraction compute node.

    Provides node metadata for introspection, sourced from contract.yaml.
    """

    node_name: str = "pattern_extraction_compute"
    node_version: ModelSemVer = field(default_factory=lambda: ModelSemVer(major=1, minor=0, patch=0))
    node_description: str = (
        "Compute node that analyzes Claude Code session data to extract patterns "
        "and insights about codebases. Detects file access patterns, error patterns, "
        "architecture patterns, and tool usage patterns. This node is pure computation "
        "with no external dependencies."
    )

    @property
    def input_state_class(self) -> type[BaseModel]:
        """Return the input state model class."""
        from omniintelligence.nodes.node_pattern_extraction_compute.models import (
            ModelPatternExtractionInput,
        )

        return ModelPatternExtractionInput

    @property
    def output_state_class(self) -> type[BaseModel]:
        """Return the output state model class."""
        from omniintelligence.nodes.node_pattern_extraction_compute.models import (
            ModelPatternExtractionOutput,
        )

        return ModelPatternExtractionOutput

    @property
    def error_codes_class(self) -> type[Enum]:
        """Return the error codes enum class."""
        return PatternExtractionErrorCode


class PatternExtractionIntrospection(MixinNodeIntrospection):
    """Introspection support for pattern extraction compute node.

    This class provides standardized introspection capabilities following
    the ONEX pattern. It enables:
    - Node discovery through --introspect CLI flag
    - Contract and schema exposure
    - Capability advertisement
    - Event channel configuration

    Usage:
        # Generate introspection response
        response = PatternExtractionIntrospection.get_introspection_response()

        # Handle --introspect CLI command
        if "--introspect" in sys.argv:
            PatternExtractionIntrospection.handle_introspect_command()
    """

    _metadata_loader: PatternExtractionMetadataLoader | None = None

    @classmethod
    def get_metadata_loader(cls) -> PatternExtractionMetadataLoader:
        """Get the metadata loader instance.

        Returns:
            PatternExtractionMetadataLoader with node metadata.
        """
        if cls._metadata_loader is None:
            cls._metadata_loader = PatternExtractionMetadataLoader()
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
            "pattern-extraction",
            "session-analysis",
            "learning",
            "file-patterns",
            "error-patterns",
            "architecture-patterns",
            "tool-patterns",
        ]

    @classmethod
    def _get_node_maturity(cls) -> str:
        """Return node maturity level."""
        return "stable"

    @classmethod
    def _get_node_use_cases(cls) -> list[str]:
        """Return node use cases."""
        return [
            "Extract file access patterns from Claude Code sessions",
            "Identify error-prone files and fix sequences",
            "Discover architecture patterns and module boundaries",
            "Analyze tool usage patterns and preferences",
            "Build incremental knowledge base from session data",
        ]

    @classmethod
    def get_runtime_dependencies(cls) -> list[str]:
        """Return runtime dependencies."""
        return ["omnibase_core", "pydantic"]

    @classmethod
    def get_cli_entrypoint(cls) -> str:
        """Return CLI entrypoint command."""
        return "python -m omniintelligence.nodes.node_pattern_extraction_compute"


# Convenience function for direct introspection access
def get_introspection_response() -> ModelNodeIntrospectionResponse:
    """Get the introspection response for pattern extraction compute node.

    Returns:
        ModelNodeIntrospectionResponse with all node metadata and capabilities.
    """
    return PatternExtractionIntrospection.get_introspection_response()


__all__ = [
    "PatternExtractionErrorCode",
    "PatternExtractionIntrospection",
    "PatternExtractionMetadataLoader",
    "get_introspection_response",
]
