"""Unit tests for IntentTopic enum and intent event envelope models.

Validates:
    - IntentTopic enum members exist and have correct string values
    - Envelope models are importable, frozen, and reject datetime.now() defaults
    - emitted_at field is required (no default)
    - Envelope models accept valid payloads

Reference: OMN-2487
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from omnibase_core.enums.intelligence.enum_intent_class import EnumIntentClass

# ============================================================================
# Topic enum tests
# ============================================================================


@pytest.mark.unit
class TestIntentTopicEnum:
    """Tests for IntentTopic Kafka topic name registry."""

    def test_intent_classified_topic_value(self) -> None:
        """INTENT_CLASSIFIED topic name matches ONEX canonical format."""
        from omniintelligence.topics import IntentTopic

        assert IntentTopic.INTENT_CLASSIFIED == "onex.evt.intent.classified.v1"

    def test_intent_drift_detected_topic_value(self) -> None:
        """INTENT_DRIFT_DETECTED topic name matches ONEX canonical format."""
        from omniintelligence.topics import IntentTopic

        assert IntentTopic.INTENT_DRIFT_DETECTED == "onex.evt.intent.drift.detected.v1"

    def test_intent_outcome_labeled_topic_value(self) -> None:
        """INTENT_OUTCOME_LABELED topic name matches ONEX canonical format."""
        from omniintelligence.topics import IntentTopic

        assert (
            IntentTopic.INTENT_OUTCOME_LABELED == "onex.evt.intent.outcome.labeled.v1"
        )

    def test_intent_pattern_promoted_topic_value(self) -> None:
        """INTENT_PATTERN_PROMOTED topic name matches ONEX canonical format."""
        from omniintelligence.topics import IntentTopic

        assert (
            IntentTopic.INTENT_PATTERN_PROMOTED == "onex.evt.intent.pattern.promoted.v1"
        )

    def test_all_topics_are_four(self) -> None:
        """IntentTopic enum has exactly 4 members."""
        from omniintelligence.topics import IntentTopic

        assert len(IntentTopic) == 4

    def test_all_topics_start_with_onex_evt_intent(self) -> None:
        """All intent topics follow the onex.evt.intent.* producer namespace."""
        from omniintelligence.topics import IntentTopic

        for topic in IntentTopic:
            assert str(topic).startswith("onex.evt.intent."), (
                f"Topic {topic!r} does not start with 'onex.evt.intent.'"
            )

    def test_all_topics_end_with_v1(self) -> None:
        """All intent topics are versioned v1."""
        from omniintelligence.topics import IntentTopic

        for topic in IntentTopic:
            assert str(topic).endswith(".v1"), (
                f"Topic {topic!r} does not end with '.v1'"
            )

    def test_topic_str_coercion(self) -> None:
        """IntentTopic values coerce to plain strings (StrEnum behaviour)."""
        from omniintelligence.topics import IntentTopic

        value = IntentTopic.INTENT_CLASSIFIED
        assert isinstance(str(value), str)
        assert str(value) == "onex.evt.intent.classified.v1"

    def test_topic_equality_with_string(self) -> None:
        """IntentTopic members compare equal to their string values."""
        from omniintelligence.topics import IntentTopic

        assert IntentTopic.INTENT_CLASSIFIED == "onex.evt.intent.classified.v1"
        assert IntentTopic.INTENT_DRIFT_DETECTED == "onex.evt.intent.drift.detected.v1"
        assert (
            IntentTopic.INTENT_OUTCOME_LABELED == "onex.evt.intent.outcome.labeled.v1"
        )
        assert (
            IntentTopic.INTENT_PATTERN_PROMOTED == "onex.evt.intent.pattern.promoted.v1"
        )

    def test_intent_topic_importable_from_package(self) -> None:
        """IntentTopic is importable from the omniintelligence package root."""
        from omniintelligence.topics import IntentTopic

        assert IntentTopic is not None

    def test_no_duplicate_topic_values(self) -> None:
        """All IntentTopic values are unique (no duplicate strings)."""
        from omniintelligence.topics import IntentTopic

        values = [str(t) for t in IntentTopic]
        assert len(values) == len(set(values)), "Duplicate topic values detected"


# ============================================================================
# Envelope model tests — ModelIntentClassifiedEnvelope
# ============================================================================


@pytest.mark.unit
class TestModelIntentClassifiedEnvelope:
    """Tests for ModelIntentClassifiedEnvelope (onex.evt.intent.classified.v1)."""

    def _make_envelope(self, **overrides: object) -> object:
        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentClassifiedEnvelope,
        )

        defaults: dict[str, object] = {
            "session_id": "sess-abc",
            "correlation_id": str(uuid4()),
            "intent_class": EnumIntentClass.REFACTOR,
            "confidence": 0.9,
            "fallback": False,
            "emitted_at": datetime.now(tz=UTC),
        }
        defaults.update(overrides)
        return ModelIntentClassifiedEnvelope(**defaults)  # type: ignore[arg-type]

    def test_valid_envelope_creates_successfully(self) -> None:
        """Envelope accepts valid fields."""
        envelope = self._make_envelope()
        assert envelope is not None

    def test_envelope_is_frozen(self) -> None:
        """Envelope model is immutable (frozen=True)."""
        from pydantic import ValidationError

        envelope = self._make_envelope()
        with pytest.raises((TypeError, ValidationError)):
            envelope.session_id = "mutated"  # type: ignore[misc]

    def test_emitted_at_is_required(self) -> None:
        """emitted_at field is required — no default provided."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentClassifiedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentClassifiedEnvelope(
                session_id="sess-abc",
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.REFACTOR,
                confidence=0.9,
                # emitted_at omitted — must raise
            )

    def test_default_event_type(self) -> None:
        """Default event_type is 'IntentClassified'."""
        envelope = self._make_envelope()
        assert envelope.event_type == "IntentClassified"  # type: ignore[union-attr]

    def test_confidence_bounds(self) -> None:
        """Confidence must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentClassifiedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentClassifiedEnvelope(
                session_id="s",
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.REFACTOR,
                confidence=1.1,
                emitted_at=datetime.now(tz=UTC),
            )

    def test_extra_fields_ignored(self) -> None:
        """Extra fields are silently ignored (extra='ignore')."""
        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentClassifiedEnvelope,
        )

        envelope = ModelIntentClassifiedEnvelope(
            session_id="s",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.ANALYSIS,
            confidence=0.8,
            emitted_at=datetime.now(tz=UTC),
            unknown_future_field="ignored",  # type: ignore[call-arg]
        )
        assert envelope is not None


# ============================================================================
# Envelope model tests — ModelIntentDriftDetectedEnvelope
# ============================================================================


@pytest.mark.unit
class TestModelIntentDriftDetectedEnvelope:
    """Tests for ModelIntentDriftDetectedEnvelope (onex.evt.intent.drift.detected.v1)."""

    def _make_envelope(self, **overrides: object) -> object:
        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentDriftDetectedEnvelope,
        )

        defaults: dict[str, object] = {
            "session_id": "sess-drift",
            "correlation_id": str(uuid4()),
            "declared_intent": EnumIntentClass.REFACTOR,
            "observed_intent": EnumIntentClass.BUGFIX,
            "drift_score": 0.7,
            "emitted_at": datetime.now(tz=UTC),
        }
        defaults.update(overrides)
        return ModelIntentDriftDetectedEnvelope(**defaults)  # type: ignore[arg-type]

    def test_valid_envelope_creates_successfully(self) -> None:
        """Envelope accepts valid fields."""
        envelope = self._make_envelope()
        assert envelope is not None

    def test_envelope_is_frozen(self) -> None:
        """Envelope model is immutable (frozen=True)."""
        from pydantic import ValidationError

        envelope = self._make_envelope()
        with pytest.raises((TypeError, ValidationError)):
            envelope.session_id = "mutated"  # type: ignore[misc]

    def test_emitted_at_is_required(self) -> None:
        """emitted_at field is required — no default provided."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentDriftDetectedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentDriftDetectedEnvelope(
                session_id="sess-drift",
                correlation_id=str(uuid4()),
                declared_intent=EnumIntentClass.REFACTOR,
                observed_intent=EnumIntentClass.BUGFIX,
                drift_score=0.7,
                # emitted_at omitted
            )

    def test_default_event_type(self) -> None:
        """Default event_type is 'IntentDriftDetected'."""
        envelope = self._make_envelope()
        assert envelope.event_type == "IntentDriftDetected"  # type: ignore[union-attr]

    def test_drift_score_bounds(self) -> None:
        """drift_score must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentDriftDetectedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentDriftDetectedEnvelope(
                session_id="s",
                correlation_id=str(uuid4()),
                declared_intent=EnumIntentClass.REFACTOR,
                observed_intent=EnumIntentClass.BUGFIX,
                drift_score=1.5,  # out of range
                emitted_at=datetime.now(tz=UTC),
            )


# ============================================================================
# Envelope model tests — ModelIntentOutcomeLabeledEnvelope
# ============================================================================


@pytest.mark.unit
class TestModelIntentOutcomeLabeledEnvelope:
    """Tests for ModelIntentOutcomeLabeledEnvelope (onex.evt.intent.outcome.labeled.v1)."""

    def _make_envelope(self, **overrides: object) -> object:
        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentOutcomeLabeledEnvelope,
        )

        defaults: dict[str, object] = {
            "session_id": "sess-outcome",
            "correlation_id": str(uuid4()),
            "intent_class": EnumIntentClass.FEATURE,
            "success": True,
            "cost_usd": 0.05,
            "emitted_at": datetime.now(tz=UTC),
        }
        defaults.update(overrides)
        return ModelIntentOutcomeLabeledEnvelope(**defaults)  # type: ignore[arg-type]

    def test_valid_envelope_creates_successfully(self) -> None:
        """Envelope accepts valid fields."""
        envelope = self._make_envelope()
        assert envelope is not None

    def test_envelope_is_frozen(self) -> None:
        """Envelope model is immutable (frozen=True)."""
        from pydantic import ValidationError

        envelope = self._make_envelope()
        with pytest.raises((TypeError, ValidationError)):
            envelope.success = False  # type: ignore[misc]

    def test_emitted_at_is_required(self) -> None:
        """emitted_at field is required — no default provided."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentOutcomeLabeledEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentOutcomeLabeledEnvelope(
                session_id="sess-outcome",
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.FEATURE,
                success=True,
                # emitted_at omitted
            )

    def test_default_event_type(self) -> None:
        """Default event_type is 'IntentOutcomeLabeled'."""
        envelope = self._make_envelope()
        assert envelope.event_type == "IntentOutcomeLabeled"  # type: ignore[union-attr]

    def test_cost_usd_default_is_zero(self) -> None:
        """cost_usd defaults to 0.0 when not specified."""
        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentOutcomeLabeledEnvelope,
        )

        envelope = ModelIntentOutcomeLabeledEnvelope(
            session_id="sess-outcome",
            correlation_id=str(uuid4()),
            intent_class=EnumIntentClass.FEATURE,
            success=True,
            emitted_at=datetime.now(tz=UTC),
        )
        assert envelope.cost_usd == 0.0

    def test_cost_usd_non_negative(self) -> None:
        """cost_usd must be >= 0."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentOutcomeLabeledEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentOutcomeLabeledEnvelope(
                session_id="sess-outcome",
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.FEATURE,
                success=True,
                cost_usd=-0.01,  # negative cost
                emitted_at=datetime.now(tz=UTC),
            )


# ============================================================================
# Envelope model tests — ModelIntentPatternPromotedEnvelope
# ============================================================================


@pytest.mark.unit
class TestModelIntentPatternPromotedEnvelope:
    """Tests for ModelIntentPatternPromotedEnvelope (onex.evt.intent.pattern.promoted.v1)."""

    def _make_envelope(self, **overrides: object) -> object:
        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentPatternPromotedEnvelope,
        )

        defaults: dict[str, object] = {
            "pattern_id": uuid4(),
            "correlation_id": str(uuid4()),
            "intent_class": EnumIntentClass.REFACTOR,
            "pattern_signature": "Use dataclasses for mutable value objects",
            "promotion_confidence": 0.85,
            "emitted_at": datetime.now(tz=UTC),
        }
        defaults.update(overrides)
        return ModelIntentPatternPromotedEnvelope(**defaults)  # type: ignore[arg-type]

    def test_valid_envelope_creates_successfully(self) -> None:
        """Envelope accepts valid fields."""
        envelope = self._make_envelope()
        assert envelope is not None

    def test_envelope_is_frozen(self) -> None:
        """Envelope model is immutable (frozen=True)."""
        from pydantic import ValidationError

        envelope = self._make_envelope()
        with pytest.raises((TypeError, ValidationError)):
            envelope.promotion_confidence = 0.5  # type: ignore[misc]

    def test_emitted_at_is_required(self) -> None:
        """emitted_at field is required — no default provided."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentPatternPromotedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentPatternPromotedEnvelope(
                pattern_id=uuid4(),
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.REFACTOR,
                pattern_signature="sig",
                promotion_confidence=0.85,
                # emitted_at omitted
            )

    def test_default_event_type(self) -> None:
        """Default event_type is 'IntentPatternPromoted'."""
        envelope = self._make_envelope()
        assert envelope.event_type == "IntentPatternPromoted"  # type: ignore[union-attr]

    def test_pattern_signature_min_length(self) -> None:
        """pattern_signature must be non-empty."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentPatternPromotedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentPatternPromotedEnvelope(
                pattern_id=uuid4(),
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.REFACTOR,
                pattern_signature="",  # empty string
                promotion_confidence=0.85,
                emitted_at=datetime.now(tz=UTC),
            )

    def test_pattern_signature_max_length(self) -> None:
        """pattern_signature must not exceed 500 characters."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentPatternPromotedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentPatternPromotedEnvelope(
                pattern_id=uuid4(),
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.REFACTOR,
                pattern_signature="x" * 501,  # 501 chars
                promotion_confidence=0.85,
                emitted_at=datetime.now(tz=UTC),
            )

    def test_promotion_confidence_bounds(self) -> None:
        """promotion_confidence must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        from omniintelligence.models.events.model_intent_event_envelopes import (
            ModelIntentPatternPromotedEnvelope,
        )

        with pytest.raises(ValidationError):
            ModelIntentPatternPromotedEnvelope(
                pattern_id=uuid4(),
                correlation_id=str(uuid4()),
                intent_class=EnumIntentClass.REFACTOR,
                pattern_signature="valid sig",
                promotion_confidence=1.1,  # out of range
                emitted_at=datetime.now(tz=UTC),
            )

    def test_pattern_id_is_uuid(self) -> None:
        """pattern_id field accepts UUID objects."""
        envelope = self._make_envelope()
        assert isinstance(envelope.pattern_id, UUID)  # type: ignore[union-attr]


# ============================================================================
# Cross-cutting: envelope models importable from models.events package
# ============================================================================


@pytest.mark.unit
class TestIntentEnvelopePackageExports:
    """Verify envelope models are accessible via models.events package."""

    def test_classified_envelope_importable_from_package(self) -> None:
        """ModelIntentClassifiedEnvelope importable from models.events."""
        from omniintelligence.models.events import (
            ModelIntentClassifiedEnvelope,
        )

        assert ModelIntentClassifiedEnvelope is not None

    def test_drift_envelope_importable_from_package(self) -> None:
        """ModelIntentDriftDetectedEnvelope importable from models.events."""
        from omniintelligence.models.events import (
            ModelIntentDriftDetectedEnvelope,
        )

        assert ModelIntentDriftDetectedEnvelope is not None

    def test_outcome_envelope_importable_from_package(self) -> None:
        """ModelIntentOutcomeLabeledEnvelope importable from models.events."""
        from omniintelligence.models.events import (
            ModelIntentOutcomeLabeledEnvelope,
        )

        assert ModelIntentOutcomeLabeledEnvelope is not None

    def test_pattern_promoted_envelope_importable_from_package(self) -> None:
        """ModelIntentPatternPromotedEnvelope importable from models.events."""
        from omniintelligence.models.events import (
            ModelIntentPatternPromotedEnvelope,
        )

        assert ModelIntentPatternPromotedEnvelope is not None

    def test_intent_topic_in_all(self) -> None:
        """IntentTopic members appear in __all__ of topics module."""
        import omniintelligence.topics as topics_module

        assert "IntentTopic" in topics_module.__all__

    def test_envelope_models_in_events_all(self) -> None:
        """All 4 envelope models appear in models.events.__all__."""
        import omniintelligence.models.events as events_module

        for name in (
            "ModelIntentClassifiedEnvelope",
            "ModelIntentDriftDetectedEnvelope",
            "ModelIntentOutcomeLabeledEnvelope",
            "ModelIntentPatternPromotedEnvelope",
        ):
            assert name in events_module.__all__, (
                f"{name} missing from models.events.__all__"
            )
