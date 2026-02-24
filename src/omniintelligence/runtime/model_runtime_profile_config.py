# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Runtime profile configuration model for node selection."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelRuntimeProfileConfig(BaseModel):
    """Optional runtime profile configuration for node selection.

    Allows filtering which nodes are loaded based on profile configuration.
    Useful for running subset of nodes in development or specialized deployments.

    Attributes:
        profile_name: Profile name identifier.
        node_types: List of node types to include (compute, effect, reducer, orchestrator).
        node_names: Optional list of specific node names to include.
        exclude_nodes: Optional list of node names to exclude.
    """

    profile_name: str = Field(
        default="default",
        description="Profile name identifier",
        examples=["default", "development", "compute-only", "minimal"],
    )

    node_types: list[Literal["compute", "effect", "reducer", "orchestrator"]] = Field(
        default=["compute", "effect", "reducer", "orchestrator"],
        description="Node types to include in this profile",
    )

    node_names: list[str] | None = Field(
        default=None,
        description="Specific node names to include (None means all matching types)",
    )

    exclude_nodes: list[str] | None = Field(
        default=None,
        description="Node names to exclude from this profile",
    )

    model_config = ConfigDict(
        extra="forbid",
    )


__all__ = ["ModelRuntimeProfileConfig"]
