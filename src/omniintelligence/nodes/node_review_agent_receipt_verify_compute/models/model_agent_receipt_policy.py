# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The injected policy of the agent receipt verifier (OMN-22175)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelAgentReceiptPolicy(BaseModel):
    """Overlay data: which voters are approved and which provenance is forbidden.

    Nothing in the node's code names a class, provider, endpoint or host; every
    value that decides a refusal arrives here. An empty ``approved_identities``
    approves no voter, so a policy with no roster refuses every receipt.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    approved_identities: tuple[str, ...] = ()
    forbidden_providers: tuple[str, ...] = ()
    forbidden_endpoint_classes: tuple[str, ...] = ()
    forbidden_endpoints: tuple[str, ...] = ()
    forbidden_hosts: tuple[str, ...] = ()


__all__ = ["ModelAgentReceiptPolicy"]
