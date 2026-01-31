# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Event envelope validation for Kafka consumer.

All events consumed by pattern_storage_effect must include these base fields
for idempotency handling and distributed tracing.

Reference: OMN-1669 (STORE-004)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ModelEventEnvelope(BaseModel):
    """Base event envelope with required fields for idempotency.

    All Kafka events must include these fields. The event_id is used
    as the idempotency key for deduplication.
    """

    event_id: UUID = Field(..., description="Unique event ID (idempotency key)")
    event_time: datetime = Field(..., description="Event timestamp (ISO8601)")
    producer_id: str = Field(..., description="Event producer identifier")
    schema_version: str = Field(..., description="Event schema version")
    correlation_id: UUID | None = Field(
        None, description="Optional correlation ID for tracing"
    )

    class Config:
        frozen = True
