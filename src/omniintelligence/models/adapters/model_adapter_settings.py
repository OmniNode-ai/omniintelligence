# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Timeout and retry budgets and default chat endpoints of the client adapters (OMN-21623).

The values live in ``adapters/adapter_settings.yaml``; this model validates that
contract and is the one way code reads it. Every field is required and unknown
fields are refused, so a file that omits or misspells one fails to load instead
of falling back to a value in code.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_SETTINGS_PATH: Path = (
    Path(__file__).resolve().parents[2] / "adapters" / "adapter_settings.yaml"
)


class ModelAdapterSettingsLoadError(RuntimeError):
    """Raised when ``adapter_settings.yaml`` is missing, malformed or incomplete."""


class ModelAdapterSettings(BaseModel):
    """The client adapters' timeout and retry budgets (seconds) and default chat endpoints.

    Attributes:
        http_timeout_s: ``HttpRestHandler`` request timeout.
        pg_timeout_s: ``PostgresHandler`` command timeout.
        kafka_poll_s: ``KafkaHandler`` consume poll timeout.
        kafka_produce_flush_s: ``KafkaHandler`` flush after one produce.
        kafka_close_flush_s: ``KafkaHandler`` flush on disconnect.
        eval_timeout_s: ``EvalLLMClient`` request timeout.
        eval_retry_s: ``EvalLLMClient`` base retry delay, doubled per attempt.
        gmail_fetch_s: Gmail intent URL content fetch timeout.
        gmail_embed_s: Gmail intent embedding call timeout.
        gmail_llm_s: Gmail intent reasoning-model call timeout.
        gemini_timeout_s: Gemini plan-reviewer config default timeout.
        gemini_chat_url: Gemini plan-reviewer config default chat endpoint.
        zai_timeout_s: Z.AI plan-reviewer config default timeout.
        zai_chat_url: Z.AI plan-reviewer config default chat endpoint.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    http_timeout_s: float = Field(gt=0)
    pg_timeout_s: float = Field(gt=0)
    kafka_poll_s: float = Field(gt=0)
    kafka_produce_flush_s: float = Field(gt=0)
    kafka_close_flush_s: float = Field(gt=0)
    eval_timeout_s: float = Field(gt=0)
    eval_retry_s: float = Field(gt=0)
    gmail_fetch_s: float = Field(gt=0)
    gmail_embed_s: float = Field(gt=0)
    gmail_llm_s: float = Field(gt=0)
    gemini_timeout_s: float = Field(gt=0)
    gemini_chat_url: str = Field(min_length=1)
    zai_timeout_s: float = Field(gt=0)
    zai_chat_url: str = Field(min_length=1)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelAdapterSettings:
        """Read and validate the adapter settings contract.

        Args:
            path: Optional override for the YAML path (tests only).

        Raises:
            ModelAdapterSettingsLoadError: If the file is missing, not a mapping,
                or fails validation.
        """
        source = path or _SETTINGS_PATH
        if not source.is_file():
            raise ModelAdapterSettingsLoadError(
                f"adapter_settings.yaml not found at {source}"
            )
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as exc:
            raise ModelAdapterSettingsLoadError(
                f"adapter_settings.yaml failed to load: {exc}"
            ) from exc


@cache
def adapter_settings() -> ModelAdapterSettings:
    """The shipped ``adapter_settings.yaml``, loaded once per process."""
    return ModelAdapterSettings.load()


__all__ = [
    "ModelAdapterSettings",
    "ModelAdapterSettingsLoadError",
    "adapter_settings",
]
