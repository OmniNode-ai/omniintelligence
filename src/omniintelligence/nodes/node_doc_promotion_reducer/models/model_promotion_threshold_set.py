# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Promotion threshold set model — per-source-type promotion gates.

Defines the gate values for each source type. The handler dispatches on
source_type to select the correct threshold set.

Ticket: OMN-2395
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_doc_promotion_reducer.models.enum_context_item_source_type import (
    EnumContextItemSourceType,
)


class ModelPromotionThresholdSet(BaseModel):
    """Per-source-type promotion gate configuration.

    Gates for QUARANTINE→VALIDATED (Q→V):
        quarantine_to_validated_runs: Minimum scored_runs required.
                                      None means item starts at VALIDATED.

    Gates for VALIDATED→SHARED (V→S):
        validated_to_shared_runs:    Minimum scored_runs.
        validated_to_shared_used_rate: Minimum used_rate.
        validated_to_shared_signal_floor: Minimum cumulative positive signals.
                                           0 means no floor (v0 hook-derived behaviour).

    Demotion gate for VALIDATED→QUARANTINE:
        validated_to_quarantine_hurt_rate: Maximum hurt_rate before demotion.
    """

    model_config = {"frozen": True, "extra": "ignore"}

    source_type: EnumContextItemSourceType

    # Q→V gate (None = not applicable, item starts at VALIDATED)
    quarantine_to_validated_runs: int | None = Field(default=10, ge=1)

    # V→S gates
    validated_to_shared_runs: int = Field(default=30, ge=1)
    validated_to_shared_used_rate: float = Field(default=0.25, ge=0.0, le=1.0)
    validated_to_shared_signal_floor: int = Field(default=0, ge=0)

    # Demotion gate (VALIDATED→QUARANTINE)
    validated_to_quarantine_hurt_rate: float = Field(default=0.50, ge=0.0, le=1.0)


# ===========================================================================
# Canonical threshold sets per source type
# ===========================================================================

THRESHOLD_SETS: dict[EnumContextItemSourceType, ModelPromotionThresholdSet] = {
    # STATIC_STANDARDS: Starts at VALIDATED. Lower used_rate bar.
    # 10 V→S runs with 0.10 used_rate and 5 positive signals minimum.
    EnumContextItemSourceType.STATIC_STANDARDS: ModelPromotionThresholdSet(
        source_type=EnumContextItemSourceType.STATIC_STANDARDS,
        quarantine_to_validated_runs=None,  # starts VALIDATED
        validated_to_shared_runs=10,
        validated_to_shared_used_rate=0.10,
        validated_to_shared_signal_floor=5,
        validated_to_quarantine_hurt_rate=0.40,
    ),
    # REPO_DERIVED: Starts at QUARANTINE. Moderate bar.
    # 5 Q→V runs, then 20 V→S runs with 0.15 used_rate and 5 positive signals.
    EnumContextItemSourceType.REPO_DERIVED: ModelPromotionThresholdSet(
        source_type=EnumContextItemSourceType.REPO_DERIVED,
        quarantine_to_validated_runs=5,
        validated_to_shared_runs=20,
        validated_to_shared_used_rate=0.15,
        validated_to_shared_signal_floor=5,
        validated_to_quarantine_hurt_rate=0.45,
    ),
    # MEMORY_HOOK: v0 hook-derived thresholds — unchanged.
    EnumContextItemSourceType.MEMORY_HOOK: ModelPromotionThresholdSet(
        source_type=EnumContextItemSourceType.MEMORY_HOOK,
        quarantine_to_validated_runs=10,
        validated_to_shared_runs=30,
        validated_to_shared_used_rate=0.25,
        validated_to_shared_signal_floor=0,  # no floor
        validated_to_quarantine_hurt_rate=0.50,
    ),
    # MEMORY_LEARNED: same as MEMORY_HOOK
    EnumContextItemSourceType.MEMORY_LEARNED: ModelPromotionThresholdSet(
        source_type=EnumContextItemSourceType.MEMORY_LEARNED,
        quarantine_to_validated_runs=10,
        validated_to_shared_runs=30,
        validated_to_shared_used_rate=0.25,
        validated_to_shared_signal_floor=0,
        validated_to_quarantine_hurt_rate=0.50,
    ),
    # MEMORY_MANUAL: same as MEMORY_HOOK
    EnumContextItemSourceType.MEMORY_MANUAL: ModelPromotionThresholdSet(
        source_type=EnumContextItemSourceType.MEMORY_MANUAL,
        quarantine_to_validated_runs=10,
        validated_to_shared_runs=30,
        validated_to_shared_used_rate=0.25,
        validated_to_shared_signal_floor=0,
        validated_to_quarantine_hurt_rate=0.50,
    ),
}


__all__ = ["ModelPromotionThresholdSet", "THRESHOLD_SETS"]
