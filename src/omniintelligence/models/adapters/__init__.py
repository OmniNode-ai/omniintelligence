# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adapter models: the contract-loaded timeout budgets of the transport and LLM clients (OMN-21623)."""

from omniintelligence.models.adapters.model_adapter_settings import (
    ModelAdapterSettings,
    ModelAdapterSettingsLoadError,
    adapter_settings,
)

__all__ = [
    "ModelAdapterSettings",
    "ModelAdapterSettingsLoadError",
    "adapter_settings",
]
