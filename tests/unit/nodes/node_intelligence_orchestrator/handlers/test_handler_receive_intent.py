# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Unit tests for the orchestrator intent reception handler.

Tests verify that:
    - handle_receive_intent correctly logs and returns a receipt for a single intent
    - handle_receive_intents processes batches and returns receipts for each
    - Empty intent batches return empty receipt lists
    - Correlation IDs are threaded through to receipts
    - Receipt fields match the input intent fields

Ticket: OMN-2034
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import pytest
from omnibase_core.models.reducer.model_intent import ModelIntent
from omnibase_core.models.reducer.payloads.model_extension_payloads import (
    ModelPayloadExtension,
)
from pydantic import ValidationError

from omniintelligence.nodes.node_intelligence_orchestrator.handlers.handler_receive_intent import (
    handle_receive_intent,
    handle_receive_intents,
)
from omniintelligence.nodes.node_intelligence_orchestrator.models.model_intent_receipt import (
    ModelIntentReceipt,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_correlation_id() -> UUID:
    """Fixed correlation ID for tracing tests."""
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_pattern_id() -> str:
    """Fixed pattern ID for intent tests."""
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture
def sample_extension_payload(sample_pattern_id: str) -> ModelPayloadExtension:
    """Create a sample ModelPayloadExtension for testing."""
    return ModelPayloadExtension(
        extension_type="omniintelligence.pattern_lifecycle_update",
        plugin_name="omniintelligence",
        data={
            "pattern_id": sample_pattern_id,
            "from_status": "candidate",
            "to_status": "validated",
            "trigger": "promote_direct",
        },
    )


@pytest.fixture
def sample_intent(
    sample_extension_payload: ModelPayloadExtension,
    sample_pattern_id: str,
) -> ModelIntent:
    """Create a sample ModelIntent for testing."""
    return ModelIntent(
        intent_type="extension",
        target=f"postgres://patterns/{sample_pattern_id}",
        payload=sample_extension_payload,
    )


@pytest.fixture
def sample_intent_with_priority(
    sample_extension_payload: ModelPayloadExtension,
    sample_pattern_id: str,
) -> ModelIntent:
    """Create a sample ModelIntent with high priority."""
    return ModelIntent(
        intent_type="extension",
        target=f"postgres://patterns/{sample_pattern_id}",
        payload=sample_extension_payload,
        priority=5,
    )


# =============================================================================
# Tests: handle_receive_intent (single intent)
# =============================================================================


class TestHandleReceiveIntent:
    """Tests for single intent reception."""

    def test_receives_intent_successfully(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Intent is received and receipt confirms success."""
        receipt = handle_receive_intent(sample_intent)

        assert receipt.received is True
        assert receipt.intent_id == sample_intent.intent_id
        assert receipt.intent_type == "extension"
        assert "postgres://patterns/" in receipt.target

    def test_receipt_preserves_intent_id(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Receipt intent_id matches the input intent's intent_id."""
        receipt = handle_receive_intent(sample_intent)
        assert receipt.intent_id == sample_intent.intent_id

    def test_receipt_preserves_intent_type(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Receipt intent_type matches the input intent's intent_type."""
        receipt = handle_receive_intent(sample_intent)
        assert receipt.intent_type == sample_intent.intent_type

    def test_receipt_preserves_target(
        self,
        sample_intent: ModelIntent,
        sample_pattern_id: str,
    ) -> None:
        """Receipt target matches the input intent's target."""
        receipt = handle_receive_intent(sample_intent)
        assert receipt.target == f"postgres://patterns/{sample_pattern_id}"

    def test_correlation_id_threaded_to_receipt(
        self,
        sample_intent: ModelIntent,
        sample_correlation_id: UUID,
    ) -> None:
        """Correlation ID is threaded through to the receipt."""
        receipt = handle_receive_intent(
            sample_intent,
            correlation_id=sample_correlation_id,
        )
        assert receipt.correlation_id == sample_correlation_id

    def test_receipt_without_correlation_id(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Receipt has None correlation_id when not provided."""
        receipt = handle_receive_intent(sample_intent)
        assert receipt.correlation_id is None

    def test_receipt_has_received_at_timestamp(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Receipt has a received_at timestamp."""
        receipt = handle_receive_intent(sample_intent)
        assert receipt.received_at is not None

    def test_receipt_has_descriptive_message(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Receipt message describes the received intent."""
        receipt = handle_receive_intent(sample_intent)
        assert "extension" in receipt.message
        assert "postgres://patterns/" in receipt.message

    def test_receipt_is_frozen(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Receipt model is immutable (frozen)."""
        receipt = handle_receive_intent(sample_intent)
        with pytest.raises(ValidationError):
            receipt.received = False  # type: ignore[misc]

    def test_logs_intent_reception(
        self,
        sample_intent: ModelIntent,
        sample_correlation_id: UUID,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Handler logs intent reception with structured fields."""
        with caplog.at_level(logging.INFO):
            handle_receive_intent(
                sample_intent,
                correlation_id=sample_correlation_id,
            )

        assert "Intent received from reducer" in caplog.text

    def test_handles_high_priority_intent(
        self,
        sample_intent_with_priority: ModelIntent,
    ) -> None:
        """Handler processes high-priority intents correctly."""
        receipt = handle_receive_intent(sample_intent_with_priority)
        assert receipt.received is True
        assert receipt.intent_type == "extension"


# =============================================================================
# Tests: handle_receive_intents (batch)
# =============================================================================


class TestHandleReceiveIntents:
    """Tests for batch intent reception."""

    def test_empty_batch_returns_empty_list(
        self,
    ) -> None:
        """Empty intent tuple returns empty receipt list."""
        receipts = handle_receive_intents(())
        assert receipts == []

    def test_single_intent_batch(
        self,
        sample_intent: ModelIntent,
    ) -> None:
        """Single-intent batch returns one receipt."""
        receipts = handle_receive_intents((sample_intent,))
        assert len(receipts) == 1
        assert receipts[0].received is True

    def test_multiple_intents_batch(
        self,
        sample_extension_payload: ModelPayloadExtension,
    ) -> None:
        """Multiple intents produce one receipt each."""
        intents = tuple(
            ModelIntent(
                intent_type="extension",
                target=f"postgres://patterns/target-{i}",
                payload=sample_extension_payload,
            )
            for i in range(3)
        )

        receipts = handle_receive_intents(intents)
        assert len(receipts) == 3
        assert all(r.received for r in receipts)

    def test_batch_correlation_id_threaded(
        self,
        sample_intent: ModelIntent,
        sample_correlation_id: UUID,
    ) -> None:
        """Correlation ID is threaded to all receipts in a batch."""
        receipts = handle_receive_intents(
            (sample_intent,),
            correlation_id=sample_correlation_id,
        )
        assert all(r.correlation_id == sample_correlation_id for r in receipts)

    def test_batch_receipt_intent_ids_are_unique(
        self,
        sample_extension_payload: ModelPayloadExtension,
    ) -> None:
        """Each receipt in a batch has a unique intent_id."""
        intents = tuple(
            ModelIntent(
                intent_type="extension",
                target=f"postgres://patterns/target-{i}",
                payload=sample_extension_payload,
            )
            for i in range(3)
        )

        receipts = handle_receive_intents(intents)
        intent_ids = [r.intent_id for r in receipts]
        assert len(set(intent_ids)) == 3

    def test_batch_logs_processing(
        self,
        sample_intent: ModelIntent,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Batch handler logs processing start and completion."""
        with caplog.at_level(logging.INFO):
            handle_receive_intents((sample_intent,))

        assert "Processing intent batch from reducer" in caplog.text
        assert "Intent batch processing complete" in caplog.text


# =============================================================================
# Tests: ModelIntentReceipt model
# =============================================================================


class TestModelIntentReceipt:
    """Tests for the ModelIntentReceipt model."""

    def test_create_receipt(self) -> None:
        """ModelIntentReceipt can be created with required fields."""
        receipt = ModelIntentReceipt(
            received=True,
            intent_id=uuid4(),
            intent_type="extension",
            target="postgres://patterns/test",
        )
        assert receipt.received is True
        assert receipt.intent_type == "extension"

    def test_receipt_default_message(self) -> None:
        """ModelIntentReceipt has a default message."""
        receipt = ModelIntentReceipt(
            received=True,
            intent_id=uuid4(),
            intent_type="extension",
            target="postgres://patterns/test",
        )
        assert receipt.message == "Intent received and recorded"

    def test_receipt_custom_message(self) -> None:
        """ModelIntentReceipt accepts a custom message."""
        receipt = ModelIntentReceipt(
            received=True,
            intent_id=uuid4(),
            intent_type="extension",
            target="postgres://patterns/test",
            message="Custom receipt message",
        )
        assert receipt.message == "Custom receipt message"

    def test_receipt_forbids_extra_fields(self) -> None:
        """ModelIntentReceipt rejects extra fields."""
        with pytest.raises(ValidationError):
            ModelIntentReceipt(
                received=True,
                intent_id=uuid4(),
                intent_type="extension",
                target="postgres://patterns/test",
                extra_field="not allowed",  # type: ignore[call-arg]
            )
