# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One voter of the Hostile Reviewer gate, as the overlay declares it (OMN-20910)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_persona import (
    MAX_PERSONAS_PER_VOTER,
    ModelReviewPersona,
)

VOTER_ID_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"


class ModelReviewVoter(BaseModel):
    """A voter: where it is, which model, how it samples, what it stresses."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    voter_id: str = Field(
        pattern=VOTER_ID_PATTERN,
        description=(
            "Name the result, the quorum summary and the PR comment report this "
            "voter under. Names the role, not the model, so a model swap needs "
            "no rename."
        ),
    )
    provider: Literal["openai", "anthropic", "claude_code"] = "openai"
    model: str | None = Field(default=None, min_length=1)
    api_key_env: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        description="Environment variable NAME holding the API key; never its value.",
    )
    excluded_repositories: tuple[str, ...] = Field(
        default=(),
        description="Repository slugs or owner/repository names this cloud voter must never review.",
    )
    backend_id: str | None = Field(
        default=None,
        min_length=1,
        description="A backend of the overlay named by backend_overlay.",
    )
    endpoint_url: str | None = Field(
        default=None,
        min_length=1,
        description="An explicit OpenAI-compatible endpoint, for a voter no "
        "delegation backend describes.",
    )
    overflow_endpoint_urls: tuple[str, ...] = Field(
        default=(),
        description="Ordered OpenAI-compatible endpoints tried after the "
        "primary one, when it is full or unavailable: it answers 503 or 429, "
        "refuses the connection, or sends no reply within "
        "overflow_after_seconds. Each is the same voter on another host, with "
        "its model read from that endpoint like the primary's. Empty (the "
        "default) is the single-endpoint voter every pre-existing overlay "
        "declares.",
    )
    overflow_after_seconds: float | None = Field(
        default=None,
        gt=0.0,
        le=1800.0,
        description="How long the primary endpoint, and each overflow "
        "endpoint but the last, may take to reply before the next one is "
        "tried. Only with overflow_endpoint_urls. Absent: timeout_seconds. "
        "The last endpoint gets timeout_seconds and max_retries unless a "
        "chunked review assigns a smaller share of the whole-vote budget; "
        "then each endpoint gets one bounded attempt.",
    )
    model_id_source: Literal["served", "declared"] = Field(
        default="served",
        description="served: the endpoint's one /v1/models id, read at call "
        "time (OMN-18623). declared: send api_model_id, for an endpoint that "
        "serves several models.",
    )
    api_model_id: str = Field(default="")
    required: bool = Field(
        description="A required voter that is unreachable or fails makes the run "
        "fail, naming it. No default: every voter states it."
    )
    timeout_seconds: float = Field(gt=0.0, le=1800.0)
    review_deadline_seconds: float | None = Field(
        default=None,
        gt=0.0,
        le=7200.0,
        description="Hard ceiling on one whole review of this voter, every "
        "chunk included (OMN-20910). A review in N chunks gets N x "
        "timeout_seconds, at least one call's worst case, at most this. "
        "Absent: every review shares one call's worst case. At least "
        "timeout_seconds.",
    )
    max_retries: int | None = Field(default=None, ge=0, le=5)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    review_focus: str = Field(default="")
    enable_thinking: bool = Field(default=False)
    reasoning_effort: Literal["low", "medium", "high"] | None = Field(default=None)
    constrain_findings_schema: bool = Field(default=False)
    context_window_tokens: int = Field(default=32768, ge=8192)
    personas: tuple[ModelReviewPersona, ...] = Field(
        default=(),
        max_length=MAX_PERSONAS_PER_VOTER,
        description="review_voters_overlay.v2 only: focused passes of this one "
        "model. They widen the voter's coverage and never add a vote.",
    )
    claude_gateway: bool = Field(
        default=False,
        description="review_voters_overlay.v2 only: the endpoint is a Claude "
        "gateway host, so the voter's identity is anthropic#id=<model> "
        "whichever gateway host answers. Needs model_id_source declared.",
    )
    claude_gateway_endpoint_urls: tuple[str, ...] = Field(
        default=(),
        description="review_voters_overlay.v2 only: the entries of "
        "overflow_endpoint_urls that are further Claude gateway hosts (the "
        "same model, so the same identity). Every other overflow endpoint "
        "answers with its own identity.",
    )

    @property
    def uses_v2_fields(self) -> bool:
        return bool(
            self.personas or self.claude_gateway or self.claude_gateway_endpoint_urls
        )

    @property
    def inline_persona_count(self) -> int:
        """Persona passes run inside the gate; a voter without personas runs one."""
        inline = sum(1 for persona in self.personas if persona.mode == "inline")
        return max(1, inline)

    def _validate_personas(self) -> None:
        ids = [persona.persona_id for persona in self.personas]
        if len(set(ids)) != len(ids):
            raise ValueError(f"voter {self.voter_id!r} repeats a persona id: {ids}")
        if self.required and self.personas:
            first = self.personas[0]
            if first.tier != "required" or first.mode != "inline":
                raise ValueError(
                    f"voter {self.voter_id!r} is required, so its first persona "
                    f"{first.persona_id!r} must be tier required and mode inline "
                    "(the vote itself); got "
                    f"tier {first.tier} and mode {first.mode}"
                )

    def _validate_claude_gateway(self) -> None:
        if not self.claude_gateway:
            if self.claude_gateway_endpoint_urls:
                raise ValueError(
                    f"voter {self.voter_id!r} sets claude_gateway_endpoint_urls "
                    "without claude_gateway"
                )
            return
        if self.model_id_source != "declared" or not self.api_model_id.startswith(
            "claude-"
        ):
            raise ValueError(
                f"voter {self.voter_id!r} claude_gateway needs model_id_source "
                "'declared' and a Claude api_model_id: the identity is "
                "anthropic#id=<model>"
            )
        stray = [
            url
            for url in self.claude_gateway_endpoint_urls
            if url not in self.overflow_endpoint_urls
        ]
        if stray:
            raise ValueError(
                f"voter {self.voter_id!r} claude_gateway_endpoint_urls {stray} "
                "are not in its overflow_endpoint_urls"
            )

    @model_validator(mode="after")
    def _validate_shape(self) -> Self:
        self._validate_personas()
        if self.provider != "openai" and (
            self.claude_gateway or self.claude_gateway_endpoint_urls
        ):
            raise ValueError(
                f"voter {self.voter_id!r} claude_gateway needs an OpenAI-compatible "
                "gateway endpoint, not provider anthropic or claude_code"
            )
        if (
            self.review_deadline_seconds is not None
            and self.review_deadline_seconds < self.timeout_seconds
        ):
            raise ValueError(
                f"voter {self.voter_id!r} review_deadline_seconds "
                f"({self.review_deadline_seconds:g}) is below its timeout_seconds "
                f"({self.timeout_seconds:g}); a review needs at least one call"
            )
        if self.provider == "claude_code":
            if not self.model or not self.model.strip():
                raise ValueError(
                    f"voter {self.voter_id!r} provider claude_code requires model"
                )
            if (
                not self.model.startswith("claude-")
                or self.api_key_env is not None
                or self.backend_id is not None
                or self.endpoint_url is not None
                or self.overflow_endpoint_urls
                or self.overflow_after_seconds is not None
                or self.api_model_id
                or (
                    "model_id_source" in self.model_fields_set
                    and self.model_id_source != "declared"
                )
                or self.temperature is not None
                or self.top_p is not None
                or self.enable_thinking
                or self.reasoning_effort is not None
                or self.constrain_findings_schema
                or self.max_retries not in (None, 0)
                or any(not repo.strip() for repo in self.excluded_repositories)
            ):
                raise ValueError(
                    f"voter {self.voter_id!r} provider claude_code requires a Claude model "
                    "and host pool auth, without endpoint, API key, sampling or retry overrides"
                )
            return self
        if self.provider == "anthropic":
            if any(not repo.strip() for repo in self.excluded_repositories):
                raise ValueError(
                    f"voter {self.voter_id!r} has a blank excluded repository"
                )
            if not self.model or not self.model.strip() or not self.api_key_env:
                raise ValueError(
                    f"voter {self.voter_id!r} provider anthropic requires model and api_key_env"
                )
            if (
                self.backend_id is not None
                or self.endpoint_url is not None
                or self.overflow_endpoint_urls
                or self.overflow_after_seconds is not None
                or self.api_model_id
                or (
                    "model_id_source" in self.model_fields_set
                    and self.model_id_source != "declared"
                )
                or self.enable_thinking
                or self.reasoning_effort is not None
                or self.constrain_findings_schema
            ):
                raise ValueError(
                    f"voter {self.voter_id!r} provider anthropic cannot use endpoint, "
                    "backend, overflow, served model or OpenAI-only options"
                )
            if self.temperature is not None and self.temperature > 1:
                raise ValueError(
                    f"voter {self.voter_id!r} anthropic temperature exceeds 1"
                )
            if self.temperature is not None and self.top_p is not None:
                raise ValueError(
                    f"voter {self.voter_id!r} anthropic accepts temperature or top_p, not both"
                )
            return self
        if (
            self.model is not None
            or self.api_key_env is not None
            or self.excluded_repositories
        ):
            raise ValueError(
                f"voter {self.voter_id!r} model, api_key_env and excluded_repositories require provider anthropic"
            )
        if (self.backend_id is None) == (self.endpoint_url is None):
            raise ValueError(
                f"voter {self.voter_id!r} must name exactly one of backend_id "
                "or endpoint_url"
            )
        if self.overflow_after_seconds is not None and not self.overflow_endpoint_urls:
            raise ValueError(
                f"voter {self.voter_id!r} sets overflow_after_seconds but "
                "declares no overflow_endpoint_urls"
            )
        if self.overflow_after_seconds is not None and (
            self.overflow_after_seconds > self.timeout_seconds
        ):
            raise ValueError(
                f"voter {self.voter_id!r} overflow_after_seconds "
                f"({self.overflow_after_seconds:g}) exceeds its "
                f"timeout_seconds ({self.timeout_seconds:g}); the primary "
                "endpoint could never be given up on in time"
            )
        blank = [url for url in self.overflow_endpoint_urls if not url.strip()]
        if blank:
            raise ValueError(
                f"voter {self.voter_id!r} has a blank overflow_endpoint_urls entry"
            )
        if len(set(self.overflow_endpoint_urls)) != len(self.overflow_endpoint_urls):
            raise ValueError(
                f"voter {self.voter_id!r} repeats an overflow endpoint: "
                f"{list(self.overflow_endpoint_urls)}"
            )
        self._validate_claude_gateway()
        if self.model_id_source == "declared" and not self.api_model_id:
            raise ValueError(
                f"voter {self.voter_id!r} declares model_id_source 'declared' "
                "but no api_model_id"
            )
        if self.model_id_source == "served" and self.api_model_id:
            raise ValueError(
                f"voter {self.voter_id!r} reads its model from the endpoint "
                "(model_id_source 'served') and must not also declare "
                f"api_model_id {self.api_model_id!r}"
            )
        return self


__all__ = ["VOTER_ID_PATTERN", "ModelReviewVoter"]
