# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ONEX Introspection Support for Pattern Storage Effect Node.

This module provides introspection capabilities for the pattern storage
effect node, enabling standardized node discovery, metadata exposure,
and contract retrieval.

Part of OMN-1668: Pattern storage effect node implementation.
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


class PatternStorageErrorCode(Enum):
    """Error codes for pattern storage operations.

    These codes map to the error handling configuration in contract.yaml.
    """

    PATSTORE_001 = "PATSTORE_001"  # Invalid state transition
    PATSTORE_002 = "PATSTORE_002"  # Pattern not found
    PATSTORE_003 = "PATSTORE_003"  # Governance validation failed
    PATSTORE_004 = "PATSTORE_004"  # Storage operation failed

    def get_number(self) -> int:
        """Get the numeric portion of the error code."""
        return int(self.value.split("_")[1])

    def get_description(self) -> str:
        """Get the description for this error code."""
        descriptions = {
            "PATSTORE_001": "Invalid state transition (e.g., CANDIDATE -> VALIDATED)",
            "PATSTORE_002": "Pattern not found in storage",
            "PATSTORE_003": "Governance validation failed (e.g., confidence below threshold)",
            "PATSTORE_004": "Storage operation failed (database error)",
        }
        return descriptions.get(self.value, "Unknown error")

    def get_exit_code(self) -> int:
        """Get the exit code for this error.

        PATSTORE_001 and PATSTORE_003 are non-recoverable (governance violations).
        PATSTORE_002 is non-recoverable (pattern not found).
        PATSTORE_004 may be recoverable (transient database error).
        """
        if self.value in ("PATSTORE_001", "PATSTORE_002", "PATSTORE_003"):
            return 1  # Non-recoverable
        return 2  # Potentially recoverable


@dataclass(frozen=True)
class PatternStorageMetadataLoader:
    """Metadata loader for pattern storage effect node.

    Provides node metadata for introspection, sourced from contract.yaml.
    """

    node_name: str = "pattern_storage_effect"
    node_version: ModelSemVer = field(
        default_factory=lambda: ModelSemVer(major=1, minor=0, patch=0)
    )
    node_description: str = (
        "Effect node that persists learned patterns with governance enforcement. "
        "Handles pattern storage with version tracking, idempotency, and state "
        "promotion with audit trail. Enforces governance invariants: confidence >= 0.5, "
        "unique (domain, signature_hash, version), and valid state transitions."
    )

    @property
    def input_state_class(self) -> type[BaseModel]:
        """Return the input state model class."""
        from omniintelligence.nodes.node_pattern_storage_effect.models import (
            ModelPatternStorageInput,
        )

        return ModelPatternStorageInput

    @property
    def output_state_class(self) -> type[BaseModel]:
        """Return the output state model class."""
        from omniintelligence.nodes.node_pattern_storage_effect.models import (
            ModelPatternStoredEvent,
        )

        return ModelPatternStoredEvent

    @property
    def error_codes_class(self) -> type[Enum]:
        """Return the error codes enum class."""
        return PatternStorageErrorCode


class PatternStorageIntrospection(MixinNodeIntrospection):
    """Introspection support for pattern storage effect node.

    This class provides standardized introspection capabilities following
    the ONEX pattern. It enables:
    - Node discovery through --introspect CLI flag
    - Contract and schema exposure
    - Capability advertisement
    - Event channel configuration

    Usage:
        # Generate introspection response
        response = PatternStorageIntrospection.get_introspection_response()

        # Handle --introspect CLI command
        if "--introspect" in sys.argv:
            PatternStorageIntrospection.handle_introspect_command()
    """

    _metadata_loader: PatternStorageMetadataLoader | None = None

    @classmethod
    def get_metadata_loader(cls) -> PatternStorageMetadataLoader:
        """Get the metadata loader instance.

        Returns:
            PatternStorageMetadataLoader with node metadata.
        """
        if cls._metadata_loader is None:
            cls._metadata_loader = PatternStorageMetadataLoader()
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
        """Return node tags from contract.yaml metadata."""
        return [
            "ONEX",
            "effect",
            "pattern-storage",
            "governance",
            "state-management",
            "audit-trail",
            "idempotent",
        ]

    @classmethod
    def _get_node_maturity(cls) -> str:
        """Return node maturity level."""
        return "stable"

    @classmethod
    def _get_node_use_cases(cls) -> list[str]:
        """Return node use cases."""
        return [
            "Store learned patterns with governance validation",
            "Track pattern versions with lineage management",
            "Enforce confidence threshold governance (>= 0.5)",
            "Manage pattern state transitions (candidate -> provisional -> validated)",
            "Record audit trail for state promotions",
            "Provide idempotent storage via (pattern_id, signature_hash)",
        ]

    @classmethod
    def get_runtime_dependencies(cls) -> list[str]:
        """Return runtime dependencies."""
        return ["omnibase_core", "pydantic"]

    @classmethod
    def get_cli_entrypoint(cls) -> str:
        """Return CLI entrypoint command."""
        return "python -m omniintelligence.runtime.stub_launcher --node-type effect --node-name node_pattern_storage_effect"


# Convenience function for direct introspection access
def get_introspection_response() -> ModelNodeIntrospectionResponse:
    """Get the introspection response for pattern storage effect node.

    Returns:
        ModelNodeIntrospectionResponse with all node metadata and capabilities.
    """
    return PatternStorageIntrospection.get_introspection_response()


__all__ = [
    "PatternStorageErrorCode",
    "PatternStorageIntrospection",
    "PatternStorageMetadataLoader",
    "get_introspection_response",
]
