# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Receipts for a batch of reducer intents, in input order."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_intelligence_orchestrator.models.model_intent_receipt import (
    ModelIntentReceipt,
)


class ModelReceiveIntentsResponse(BaseModel):
    """Receipts for a batch of reducer intents, in input order."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    receipts: tuple[ModelIntentReceipt, ...]


__all__ = ["ModelReceiveIntentsResponse"]
