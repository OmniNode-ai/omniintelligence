# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Runtime timeout models: the contract-loaded budgets of the runtime and its callers (OMN-21623)."""

from omniintelligence.models.runtime_timeouts.model_runtime_timeouts import (
    ModelRuntimeTimeouts,
    ModelRuntimeTimeoutsLoadError,
    runtime_timeouts,
)

__all__ = [
    "ModelRuntimeTimeouts",
    "ModelRuntimeTimeoutsLoadError",
    "runtime_timeouts",
]
