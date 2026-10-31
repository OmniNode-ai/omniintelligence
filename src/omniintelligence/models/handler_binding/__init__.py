# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Handler binding models: resolving handlers from node contracts (OMN-21679)."""

from omniintelligence.models.handler_binding.model_contract_handler_binding import (
    ModelContractHandlerBinding,
)

bind_contract_handler = ModelContractHandlerBinding().bind

__all__ = ["ModelContractHandlerBinding", "bind_contract_handler"]
