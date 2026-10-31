# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Model names omniintelligence addresses, injected as settings (OMN-21678).

A model name is a deployment fact, so the repository holds none: the deployment
overlay supplies each one through its environment variable and this model is the one
way code reads them. A name the overlay does not supply is ``DEFAULT_MODEL_NAME``, the
placeholder the eval and local embedding clients already send when no model is named.
"""

from __future__ import annotations

from functools import cache
from typing import ClassVar, Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Request placeholder when the overlay names no model.
DEFAULT_MODEL_NAME: Final[str] = "default"


class ModelLlmRoutingSettings(BaseSettings):
    """Model names supplied by the deployment overlay.

    Environment Variables:
        OMNIINTELLIGENCE_RL_EXPORT_MODELS: JSON object, Bifrost backend slug -> served
            model name, written into the exported routing config.
        OMNIINTELLIGENCE_GMAIL_INTENT_EMBEDDING_MODEL: Embedding model of the gmail
            intent evaluator.
        OMNIINTELLIGENCE_GMAIL_INTENT_CHAT_MODEL: Chat model of the gmail intent
            evaluator.
        OMNIINTELLIGENCE_UTILIZATION_SCORING_MODEL: Chat model that scores pattern
            utilization.
        OMNIINTELLIGENCE_PATTERN_COMPLIANCE_MODEL: Default pattern compliance
            evaluation model.
        OMNIINTELLIGENCE_EVAL_COST_RATES: JSON object, case-insensitive model id
            prefix -> [input USD per token, output USD per token] for the eval LLM
            client; a model that matches no prefix costs nothing.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    rl_export_models: dict[str, str] = Field(
        default_factory=dict,
        description="Served model name by Bifrost backend slug for the RL policy export",
        alias="OMNIINTELLIGENCE_RL_EXPORT_MODELS",
    )
    gmail_embed_model: str = Field(
        default=DEFAULT_MODEL_NAME,
        description="Embedding model of the gmail intent evaluator",
        alias="OMNIINTELLIGENCE_GMAIL_INTENT_EMBEDDING_MODEL",
    )
    gmail_chat_model: str = Field(
        default=DEFAULT_MODEL_NAME,
        description="Chat model of the gmail intent evaluator",
        alias="OMNIINTELLIGENCE_GMAIL_INTENT_CHAT_MODEL",
    )
    utilization_model: str = Field(
        default=DEFAULT_MODEL_NAME,
        description="Chat model that scores pattern utilization",
        alias="OMNIINTELLIGENCE_UTILIZATION_SCORING_MODEL",
    )
    compliance_model: str = Field(
        default=DEFAULT_MODEL_NAME,
        description="Default pattern compliance evaluation model",
        alias="OMNIINTELLIGENCE_PATTERN_COMPLIANCE_MODEL",
    )
    eval_cost_rates: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="Eval client cost in USD per token by model id prefix: (input, output)",
        alias="OMNIINTELLIGENCE_EVAL_COST_RATES",
    )


@cache
def llm_routing() -> ModelLlmRoutingSettings:
    """The overlay-supplied model names, read once per process."""
    return ModelLlmRoutingSettings()


__all__ = ["DEFAULT_MODEL_NAME", "ModelLlmRoutingSettings", "llm_routing"]
