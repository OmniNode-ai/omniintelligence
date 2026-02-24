# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""HandlerConfig - handler configuration from contract."""

from __future__ import annotations

from pydantic import BaseModel


class HandlerConfig(BaseModel):
    """Handler configuration from contract.

    Attributes:
        function: Function name to import and call.
        module: Module path containing the function.
        type: Handler type (async or sync). Defaults to async.
        description: Optional human-readable description.
    """

    function: str
    module: str
    type: str = "async"
    description: str | None = None
