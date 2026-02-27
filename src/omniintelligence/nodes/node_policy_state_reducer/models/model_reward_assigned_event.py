# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Re-export canonical ModelRewardAssignedEvent from omnibase_core.

Local definition replaced in OMN-2928 (gap:164320af CONTRACT_DRIFT fix).
Canonical model lives at omnibase_core.models.objective.model_reward_assigned_event.

Consumed from: ``onex.evt.omnimemory.reward-assigned.v1``
"""

from __future__ import annotations

from omnibase_core.models.objective.model_reward_assigned_event import (
    ModelRewardAssignedEvent,
)

__all__ = ["ModelRewardAssignedEvent"]
