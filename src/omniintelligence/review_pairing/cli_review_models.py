# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""CLI argument models for review_pairing.cli_review.

Defines ModelCliReviewArgs (pre-load CLI arguments) and ModelPersonaConfig
(loaded persona content). These are distinct from ModelPlanReviewerMultiCommand
which carries the loaded plan text — these models represent path/name arguments
before file content is loaded.

Ticket: OMN-6228
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ModelCliReviewArgs(BaseModel):
    """Validated CLI arguments for cli_review.

    Represents pre-load arguments — paths and names before file content is
    loaded. Distinct from ``ModelPlanReviewerMultiCommand`` which carries
    ``plan_text`` (loaded content). This model carries ``file`` (a path) and
    ``persona`` (a name) — pre-load arguments.

    Attributes:
        file: Absolute resolved path to the plan file to review.
        persona: Name of the persona to load from review_pairing/personas/.
            None means no persona injection.
        system_prompt_file: Path to a custom system prompt file. Mutually
            exclusive with persona (persona takes precedence if both given).
        run_id: Optional correlation ID for audit logging.

    Example::

        args = ModelCliReviewArgs(
            file=Path("/tmp/my-plan.md"),
            persona="analytical-strict",
            run_id="OMN-6228",
        )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Path = Field(description="Resolved absolute path to the plan file.")
    persona: str | None = Field(
        default=None,
        description="Persona name. Must match a file in review_pairing/personas/.",
    )
    system_prompt_file: Path | None = Field(
        default=None,
        description="Path to a custom system prompt .md file.",
    )
    run_id: str | None = Field(
        default=None,
        description="Optional correlation ID for audit logging.",
    )


class ModelPersonaConfig(BaseModel):
    """Loaded persona configuration.

    Attributes:
        name: Persona name (matches the filename stem).
        content: Full markdown content of the persona file.

    Example::

        config = ModelPersonaConfig(
            name="analytical-strict",
            content="# Persona: Analytical-Strict Reviewer\\n...",
        )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Persona identifier (filename stem).")
    content: str = Field(
        description="Full markdown content of the persona file.",
        min_length=1,
    )


__all__ = ["ModelCliReviewArgs", "ModelPersonaConfig"]
