# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern definition and role models for ONEX architectural patterns."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternRole(BaseModel):
    """A single role within an architectural pattern.

    Represents one participant in a multi-node pattern, identified by its
    base class inheritance. For example, a compute role is identified by
    inheriting from ``NodeCompute`` with ``MixinHandlerRouting`` as its
    distinguishing mixin.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    role_name: str = Field(description="Role identifier, e.g. 'compute', 'effect'")
    base_class: str = Field(
        description="Base class name that identifies this role, e.g. 'NodeCompute'"
    )
    distinguishing_mixin: str | None = Field(
        default=None,
        description="Mixin that distinguishes this role from others, e.g. 'MixinHandlerRouting'",
    )
    required: bool = Field(
        default=True,
        description="Whether this role is required for the pattern to be complete",
    )
    description: str = Field(
        default="",
        description="Human-readable description of this role's purpose in the pattern",
    )


class ModelPatternDefinition(BaseModel):
    """An architectural pattern definition composed of multiple roles.

    Defines a reusable architectural pattern (e.g., a four-node ONEX pattern)
    by enumerating its constituent roles and their identifying characteristics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    pattern_name: str = Field(
        description="Unique name for this pattern, e.g. 'onex_four_node'"
    )
    pattern_type: str = Field(
        description="Category of pattern, e.g. 'node_family', 'pipeline', 'saga'"
    )
    description: str = Field(
        default="",
        description="Human-readable description of the pattern's purpose",
    )
    roles: list[ModelPatternRole] = Field(
        default_factory=list,
        description="Ordered list of roles that compose this pattern",
    )
    when_to_use: str = Field(
        default="",
        description="Guidance on when this pattern should be applied",
    )
    canonical_instance: str | None = Field(
        default=None,
        description=(
            "Path or name of a canonical example of this pattern in the codebase, "
            "e.g. 'node_pattern_storage_effect'"
        ),
    )
