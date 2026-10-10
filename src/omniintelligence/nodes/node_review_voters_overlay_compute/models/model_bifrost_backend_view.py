# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""The part of a lab delegation overlay a review voter reads (OMN-20910).

The delegation overlay (``bifrost_lane_overlay.v3``, typed in omnibase_infra by
``ModelBifrostLaneOverlay``) already carries the lab's endpoint facts. A voter
that names a ``backend_id`` reads that backend's endpoint from it, so a
backend that moves is moved once, for delegation and review alike. Only the
fields a voter needs are read; the rest of the document is that model's
business.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

BIFROST_LANE_OVERLAY_SCHEMA_VERSION = "bifrost_lane_overlay.v3"


class ModelBifrostBackendView(BaseModel):
    """One delegation backend: its id, endpoint and recorded served model."""

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    backend_id: str
    endpoint_url: str | None = None
    served_model_id: str | None = None


class ModelBifrostOverlayView(BaseModel):
    """A delegation overlay, reduced to its schema version and backends."""

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    schema_version: str
    lane: str
    backends: tuple[ModelBifrostBackendView, ...]


__all__ = [
    "BIFROST_LANE_OVERLAY_SCHEMA_VERSION",
    "ModelBifrostBackendView",
    "ModelBifrostOverlayView",
]
