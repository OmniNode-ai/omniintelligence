# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 OmniNode Team
"""Unit tests for intelligence message type registration.

Validates:
    - All 13 intelligence message types are registered
    - Registration happens correctly with proper categories and domains
    - Registry is queryable after freeze via has_message_type() and get_entry()
    - Registration after freeze() raises ModelOnexError
    - ModelPatternLifecycleEvent is COMMAND with lifecycle effect handler
    - validate_startup() returns no errors for a clean registry

Related:
    - OMN-2039: Register intelligence message types in RegistryMessageType
    - OMN-937: Central Message Type Registry implementation
"""

from __future__ import annotations

import pytest
from omnibase_core.models.errors import ModelOnexError
from omnibase_infra.enums import EnumMessageCategory
from omnibase_infra.runtime.registry import RegistryMessageType

from omniintelligence.runtime.message_type_registration import (
    EXPECTED_MESSAGE_TYPE_COUNT,
    INTELLIGENCE_DOMAIN,
    register_intelligence_message_types,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def registry() -> RegistryMessageType:
    """Create a fresh, unfrozen RegistryMessageType."""
    return RegistryMessageType()


@pytest.fixture
def frozen_registry(registry: RegistryMessageType) -> RegistryMessageType:
    """Create a registry with all intelligence types registered and frozen."""
    register_intelligence_message_types(registry)
    registry.freeze()
    return registry


# =============================================================================
# Registration Count
# =============================================================================


class TestRegistrationCount:
    """Verify correct number of message types registered."""

    def test_returns_13_registered_types(self, registry: RegistryMessageType) -> None:
        """register_intelligence_message_types returns 13 type names."""
        registered = register_intelligence_message_types(registry)
        assert len(registered) == EXPECTED_MESSAGE_TYPE_COUNT

    def test_registry_has_13_entries(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Frozen registry contains exactly 13 unique message type entries."""
        assert frozen_registry.entry_count == EXPECTED_MESSAGE_TYPE_COUNT

    def test_expected_count_constant_matches(self) -> None:
        """EXPECTED_MESSAGE_TYPE_COUNT constant is 13."""
        assert EXPECTED_MESSAGE_TYPE_COUNT == 13


# =============================================================================
# has_message_type Queries
# =============================================================================


class TestHasMessageType:
    """Verify all registered types are discoverable via has_message_type."""

    ALL_MESSAGE_TYPES = [
        # Kafka Event Models
        "ModelClaudeHookResult",
        "ModelPatternStoredEvent",
        "ModelPatternPromotedEvent",
        "ModelPatternDeprecatedEvent",
        "ModelPatternLifecycleTransitionedEvent",
        # Kafka Command/Event Models
        "ModelClaudeCodeHookEvent",
        "ModelPatternStorageInput",
        "ModelPatternLifecycleEvent",
        "ModelPayloadUpdatePatternStatus",
        # External Input
        "ClaudeSessionOutcome",
        # Reducer FSM Payloads
        "ModelIngestionPayload",
        "ModelPatternLearningPayload",
        "ModelQualityAssessmentPayload",
    ]

    @pytest.mark.parametrize("message_type", ALL_MESSAGE_TYPES)
    def test_has_message_type(
        self, frozen_registry: RegistryMessageType, message_type: str
    ) -> None:
        """Each registered type is discoverable via has_message_type."""
        assert frozen_registry.has_message_type(message_type), (
            f"Message type '{message_type}' should be registered"
        )

    def test_unregistered_type_not_found(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Unregistered type returns False."""
        assert not frozen_registry.has_message_type("NonExistentType")


# =============================================================================
# get_entry Queries
# =============================================================================


class TestGetEntry:
    """Verify entry details are correct for all registered types."""

    def test_all_entries_have_intelligence_domain(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Every registered entry has owning_domain='intelligence'."""
        for msg_type in TestHasMessageType.ALL_MESSAGE_TYPES:
            entry = frozen_registry.get_entry(msg_type)
            assert entry is not None, f"Entry for {msg_type} should exist"
            assert entry.domain_constraint.owning_domain == INTELLIGENCE_DOMAIN

    def test_all_entries_are_enabled(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Every registered entry is enabled."""
        for msg_type in TestHasMessageType.ALL_MESSAGE_TYPES:
            entry = frozen_registry.get_entry(msg_type)
            assert entry is not None
            assert entry.enabled is True

    def test_all_entries_have_descriptions(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Every registered entry has a non-empty description."""
        for msg_type in TestHasMessageType.ALL_MESSAGE_TYPES:
            entry = frozen_registry.get_entry(msg_type)
            assert entry is not None
            assert entry.description is not None and len(entry.description) > 0


# =============================================================================
# Category Validation
# =============================================================================


class TestCategoryAssignment:
    """Verify correct EnumMessageCategory assignment per type."""

    EVENT_TYPES = [
        "ModelClaudeHookResult",
        "ModelPatternStoredEvent",
        "ModelPatternPromotedEvent",
        "ModelPatternDeprecatedEvent",
        "ModelPatternLifecycleTransitionedEvent",
        "ModelPatternStorageInput",
    ]

    COMMAND_TYPES = [
        "ModelClaudeCodeHookEvent",
        "ModelPatternLifecycleEvent",
        "ModelPayloadUpdatePatternStatus",
        "ClaudeSessionOutcome",
        "ModelIngestionPayload",
        "ModelPatternLearningPayload",
        "ModelQualityAssessmentPayload",
    ]

    @pytest.mark.parametrize("message_type", EVENT_TYPES)
    def test_event_category(
        self, frozen_registry: RegistryMessageType, message_type: str
    ) -> None:
        """Event types have EVENT allowed category."""
        entry = frozen_registry.get_entry(message_type)
        assert entry is not None
        assert EnumMessageCategory.EVENT in entry.allowed_categories

    @pytest.mark.parametrize("message_type", COMMAND_TYPES)
    def test_command_category(
        self, frozen_registry: RegistryMessageType, message_type: str
    ) -> None:
        """Command types have COMMAND allowed category."""
        entry = frozen_registry.get_entry(message_type)
        assert entry is not None
        assert EnumMessageCategory.COMMAND in entry.allowed_categories


# =============================================================================
# Handler ID Validation
# =============================================================================


class TestHandlerIds:
    """Verify handler_id assignments match node directory names."""

    HANDLER_MAP = {
        "ModelClaudeHookResult": ("node_claude_hook_event_effect",),
        "ModelPatternStoredEvent": ("node_pattern_storage_effect",),
        "ModelPatternPromotedEvent": ("node_pattern_storage_effect",),
        "ModelPatternDeprecatedEvent": ("node_pattern_demotion_effect",),
        "ModelPatternLifecycleTransitionedEvent": ("node_pattern_lifecycle_effect",),
        "ModelClaudeCodeHookEvent": ("node_claude_hook_event_effect",),
        "ModelPatternStorageInput": ("node_pattern_storage_effect",),
        "ModelPatternLifecycleEvent": ("node_pattern_lifecycle_effect",),
        "ModelPayloadUpdatePatternStatus": ("node_pattern_lifecycle_effect",),
        "ClaudeSessionOutcome": ("node_pattern_feedback_effect",),
        "ModelIngestionPayload": ("node_intelligence_reducer",),
        "ModelPatternLearningPayload": ("node_intelligence_reducer",),
        "ModelQualityAssessmentPayload": ("node_intelligence_reducer",),
    }

    @pytest.mark.parametrize(
        "message_type,expected_handlers",
        list(HANDLER_MAP.items()),
    )
    def test_handler_id(
        self,
        frozen_registry: RegistryMessageType,
        message_type: str,
        expected_handlers: tuple[str, ...],
    ) -> None:
        """Handler IDs match the expected node directory names."""
        entry = frozen_registry.get_entry(message_type)
        assert entry is not None
        for handler_id in expected_handlers:
            assert handler_id in entry.handler_ids, (
                f"Expected handler '{handler_id}' for '{message_type}', "
                f"got {entry.handler_ids}"
            )


# =============================================================================
# Fan-Out Registration
# =============================================================================


class TestLifecycleEventRegistration:
    """Verify ModelPatternLifecycleEvent is registered as COMMAND with lifecycle handler."""

    def test_lifecycle_event_has_single_handler(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """ModelPatternLifecycleEvent routes to lifecycle effect (the consumer)."""
        entry = frozen_registry.get_entry("ModelPatternLifecycleEvent")
        assert entry is not None
        assert len(entry.handler_ids) == 1
        assert "node_pattern_lifecycle_effect" in entry.handler_ids

    def test_lifecycle_event_is_command(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """ModelPatternLifecycleEvent is COMMAND (topic is .cmd.)."""
        entry = frozen_registry.get_entry("ModelPatternLifecycleEvent")
        assert entry is not None
        assert EnumMessageCategory.COMMAND in entry.allowed_categories


# =============================================================================
# Freeze Enforcement
# =============================================================================


class TestFreezeEnforcement:
    """Verify registration after freeze raises ModelOnexError."""

    def test_registration_after_freeze_raises(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Calling register_simple after freeze raises ModelOnexError."""
        with pytest.raises(ModelOnexError):
            frozen_registry.register_simple(
                message_type="ShouldFail",
                handler_id="test-handler",
                category=EnumMessageCategory.EVENT,
                domain="test",
            )

    def test_register_function_after_freeze_raises(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """Calling register_intelligence_message_types on frozen registry raises."""
        with pytest.raises(ModelOnexError):
            register_intelligence_message_types(frozen_registry)


# =============================================================================
# Startup Validation
# =============================================================================


class TestStartupValidation:
    """Verify validate_startup() on a clean intelligence registry."""

    def test_no_validation_errors(self, frozen_registry: RegistryMessageType) -> None:
        """validate_startup() returns empty list (no errors)."""
        errors = frozen_registry.validate_startup()
        assert errors == [], f"Expected no validation errors, got: {errors}"

    def test_validation_with_available_handlers(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """validate_startup with all handler IDs available returns no errors."""
        all_handler_ids = {
            "node_claude_hook_event_effect",
            "node_pattern_storage_effect",
            "node_pattern_demotion_effect",
            "node_pattern_lifecycle_effect",
            "node_pattern_feedback_effect",
            "node_intelligence_reducer",
        }
        errors = frozen_registry.validate_startup(
            available_handler_ids=all_handler_ids,
        )
        assert errors == [], f"Expected no validation errors, got: {errors}"

    def test_validation_missing_handler_reports_error(
        self, frozen_registry: RegistryMessageType
    ) -> None:
        """validate_startup reports missing handlers when subset provided."""
        partial_handlers = {"node_claude_hook_event_effect"}
        errors = frozen_registry.validate_startup(
            available_handler_ids=partial_handlers,
        )
        assert len(errors) > 0, "Expected validation errors for missing handlers"


# =============================================================================
# Registry Properties
# =============================================================================


class TestRegistryProperties:
    """Verify registry metadata after intelligence registration."""

    def test_is_frozen(self, frozen_registry: RegistryMessageType) -> None:
        """Registry is frozen after registration."""
        assert frozen_registry.is_frozen

    def test_handler_count(self, frozen_registry: RegistryMessageType) -> None:
        """Registry tracks the correct number of unique handlers."""
        # 6 unique handler IDs across all 13 registrations
        assert frozen_registry.handler_count == 6

    def test_domain_count(self, frozen_registry: RegistryMessageType) -> None:
        """Registry tracks exactly 1 domain (intelligence)."""
        assert frozen_registry.domain_count == 1

    def test_intelligence_domain_constant(self) -> None:
        """INTELLIGENCE_DOMAIN is 'intelligence'."""
        assert INTELLIGENCE_DOMAIN == "intelligence"
