# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests verifying correlation_id UUID alignment for code analysis event models.

Regression tests for OMN-2839: CONTRACT_DRIFT gap — correlation_id was typed
as str | None in omniintelligence producers, causing DLQ failures when omnimemory
consumers (which require UUID) attempted to deserialize null or string values.

Fix: correlation_id in all three code analysis payload models is now UUID | None.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from omniintelligence.enums.enum_analysis_operation_type import (
    EnumAnalysisOperationType,
)
from omniintelligence.models.events import (
    ModelCodeAnalysisCompletedPayload,
    ModelCodeAnalysisFailedPayload,
    ModelCodeAnalysisRequestPayload,
)


@pytest.mark.unit
class TestCodeAnalysisCorrelationIdType:
    """Verify correlation_id is UUID | None in all three code analysis models."""

    def test_request_payload_accepts_uuid(self) -> None:
        correlation_id = uuid4()
        payload = ModelCodeAnalysisRequestPayload(
            correlation_id=correlation_id,
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        )
        assert payload.correlation_id == correlation_id
        assert isinstance(payload.correlation_id, UUID)

    def test_request_payload_accepts_none(self) -> None:
        payload = ModelCodeAnalysisRequestPayload(
            correlation_id=None,
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        )
        assert payload.correlation_id is None

    def test_request_payload_default_is_none(self) -> None:
        payload = ModelCodeAnalysisRequestPayload(
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        )
        assert payload.correlation_id is None

    def test_completed_payload_accepts_uuid(self) -> None:
        correlation_id = uuid4()
        payload = ModelCodeAnalysisCompletedPayload(correlation_id=correlation_id)
        assert payload.correlation_id == correlation_id
        assert isinstance(payload.correlation_id, UUID)

    def test_completed_payload_accepts_none(self) -> None:
        payload = ModelCodeAnalysisCompletedPayload(correlation_id=None)
        assert payload.correlation_id is None

    def test_completed_payload_default_is_none(self) -> None:
        payload = ModelCodeAnalysisCompletedPayload()
        assert payload.correlation_id is None

    def test_failed_payload_accepts_uuid(self) -> None:
        correlation_id = uuid4()
        payload = ModelCodeAnalysisFailedPayload(correlation_id=correlation_id)
        assert payload.correlation_id == correlation_id
        assert isinstance(payload.correlation_id, UUID)

    def test_failed_payload_accepts_none(self) -> None:
        payload = ModelCodeAnalysisFailedPayload(correlation_id=None)
        assert payload.correlation_id is None

    def test_failed_payload_default_is_none(self) -> None:
        payload = ModelCodeAnalysisFailedPayload()
        assert payload.correlation_id is None


@pytest.mark.unit
class TestCodeAnalysisCorrelationIdJsonRoundTrip:
    """Verify JSON serialization/deserialization of correlation_id as UUID.

    The consumer (omnimemory) receives JSON over Kafka. Pydantic must correctly
    round-trip a UUID string in JSON to a UUID object on deserialization.
    This simulates the cross-service boundary.
    """

    def test_request_payload_uuid_json_round_trip(self) -> None:
        correlation_id = uuid4()
        payload = ModelCodeAnalysisRequestPayload(
            correlation_id=correlation_id,
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        )
        serialized = payload.model_dump_json()
        data = json.loads(serialized)
        # UUID serializes to string in JSON
        assert data["correlation_id"] == str(correlation_id)
        # Deserialization from JSON string back to UUID
        reconstructed = ModelCodeAnalysisRequestPayload.model_validate_json(serialized)
        assert reconstructed.correlation_id == correlation_id
        assert isinstance(reconstructed.correlation_id, UUID)

    def test_completed_payload_uuid_json_round_trip(self) -> None:
        correlation_id = uuid4()
        payload = ModelCodeAnalysisCompletedPayload(correlation_id=correlation_id)
        serialized = payload.model_dump_json()
        data = json.loads(serialized)
        assert data["correlation_id"] == str(correlation_id)
        reconstructed = ModelCodeAnalysisCompletedPayload.model_validate_json(
            serialized
        )
        assert reconstructed.correlation_id == correlation_id
        assert isinstance(reconstructed.correlation_id, UUID)

    def test_failed_payload_uuid_json_round_trip(self) -> None:
        correlation_id = uuid4()
        payload = ModelCodeAnalysisFailedPayload(correlation_id=correlation_id)
        serialized = payload.model_dump_json()
        data = json.loads(serialized)
        assert data["correlation_id"] == str(correlation_id)
        reconstructed = ModelCodeAnalysisFailedPayload.model_validate_json(serialized)
        assert reconstructed.correlation_id == correlation_id
        assert isinstance(reconstructed.correlation_id, UUID)

    def test_null_correlation_id_json_round_trip(self) -> None:
        """Null correlation_id must survive JSON round-trip without rejection."""
        payload = ModelCodeAnalysisRequestPayload(
            correlation_id=None,
            operation_type=EnumAnalysisOperationType.QUALITY_ASSESSMENT,
        )
        serialized = payload.model_dump_json()
        data = json.loads(serialized)
        assert data["correlation_id"] is None
        reconstructed = ModelCodeAnalysisRequestPayload.model_validate_json(serialized)
        assert reconstructed.correlation_id is None

    def test_uuid_string_from_kafka_is_coerced_to_uuid(self) -> None:
        """Simulate receiving a UUID as a string from Kafka JSON.

        Pydantic v2 coerces UUID strings to UUID objects by default.
        This verifies the cross-service boundary works end-to-end.
        """
        correlation_id = uuid4()
        # Simulate Kafka JSON payload with UUID as string (as emitted by str serialization)
        kafka_json = json.dumps(
            {
                "correlation_id": str(correlation_id),
                "operation_type": EnumAnalysisOperationType.QUALITY_ASSESSMENT.value,
            }
        )
        reconstructed = ModelCodeAnalysisRequestPayload.model_validate_json(kafka_json)
        assert reconstructed.correlation_id == correlation_id
        assert isinstance(reconstructed.correlation_id, UUID)
