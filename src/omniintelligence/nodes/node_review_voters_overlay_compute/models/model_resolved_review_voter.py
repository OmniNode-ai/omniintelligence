# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A voter with its endpoint resolved (OMN-20910)."""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_review_voter import (
    ModelReviewVoter,
)

if TYPE_CHECKING:
    from omniintelligence.review_pairing.models_external_review import (
        ModelEndpointConfig,
    )

_DEFAULT_PORTS: dict[str, int] = {"http": 80, "https": 443}


class ModelResolvedReviewVoter(BaseModel):
    """A voter plus the base URL it resolved to and where that came from."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    voter: ModelReviewVoter
    base_url: str = Field(description="scheme://host[:port][/prefix], no API path.")
    source: str = Field(description="'backend <id> in <file>' or 'endpoint_url'.")
    backend_served_model_id: str | None = Field(
        default=None,
        description="The served model the delegation overlay records for the "
        "backend; reported only. A served voter reads its id from the endpoint.",
    )

    @property
    def voter_id(self) -> str:
        return self.voter.voter_id

    @property
    def host_port(self) -> tuple[str, int]:
        parsed = urllib.parse.urlsplit(self.base_url)
        port = parsed.port or _DEFAULT_PORTS[parsed.scheme]
        return parsed.hostname or "", port

    def endpoint_config(self) -> ModelEndpointConfig:
        """The adapter's per-call config for this voter.

        ``env_var`` is empty on purpose: the overlay is the one place a voter's
        endpoint is set, so no environment variable can redirect it.
        """
        from omniintelligence.review_pairing.models_external_review import (
            ModelEndpointConfig,
        )

        voter = self.voter
        return ModelEndpointConfig(
            env_var="",
            default_url=self.base_url,
            kind="code_review",
            timeout_seconds=voter.timeout_seconds,
            api_model_id=voter.api_model_id,
            model_id_source=voter.model_id_source,
            enable_thinking=voter.enable_thinking,
            max_retries=voter.max_retries,
            constrain_findings_schema=voter.constrain_findings_schema,
            temperature=voter.temperature,
            top_p=voter.top_p,
            review_focus=voter.review_focus,
            reasoning_effort=voter.reasoning_effort,
        )

    def describe(self) -> str:
        voter = self.voter
        if voter.model_id_source == "declared":
            model = f"model {voter.api_model_id} (declared)"
        elif self.backend_served_model_id:
            model = (
                "model served by the endpoint (the backend overlay records "
                f"{self.backend_served_model_id})"
            )
        else:
            model = "model served by the endpoint"
        temperature = (
            "default" if voter.temperature is None else f"{voter.temperature:g}"
        )
        top_p = "default" if voter.top_p is None else f"{voter.top_p:g}"
        focus = "focus=yes" if voter.review_focus else "focus=none"
        role = "required" if voter.required else "optional"
        return (
            f"{voter.voter_id} [{role}] -> {self.base_url} via {self.source}; "
            f"{model}; temperature={temperature} top_p={top_p}; {focus}; "
            f"timeout={voter.timeout_seconds:g}s"
        )


__all__ = ["ModelResolvedReviewVoter"]
