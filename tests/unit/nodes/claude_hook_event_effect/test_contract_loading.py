# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Unit tests for NodeClaudeHookEventEffect contract loading.

Tests the _load_publish_topic_from_contract() method which handles
edge cases for loading publish topics from the node's contract.yaml file.

Reference: OMN-1551 - Contract-driven topic resolution
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestLoadPublishTopicFromContract:
    """Tests for _load_publish_topic_from_contract method."""

    @patch(
        "omniintelligence.nodes.claude_hook_event_effect.node.load_event_bus_subcontract"
    )
    def test_load_topic_missing_contract(
        self, mock_load_subcontract: MagicMock, mock_onex_container: MagicMock
    ) -> None:
        """Test that missing contract file returns None.

        When the contract file does not exist or cannot be loaded,
        load_event_bus_subcontract returns None, and the method
        should return None.
        """
        # Arrange: Simulate missing contract file
        mock_load_subcontract.return_value = None

        # Act: Import and instantiate the node
        # Import inside test to ensure patch is applied during __init__
        from omniintelligence.nodes.claude_hook_event_effect.node import (
            NodeClaudeHookEventEffect,
        )

        node = NodeClaudeHookEventEffect(mock_onex_container)

        # Assert: publish_topic_suffix should be None
        assert node.publish_topic_suffix is None
        mock_load_subcontract.assert_called_once()

    @patch(
        "omniintelligence.nodes.claude_hook_event_effect.node.load_event_bus_subcontract"
    )
    def test_load_topic_empty_publish_topics(
        self, mock_load_subcontract: MagicMock, mock_onex_container: MagicMock
    ) -> None:
        """Test that empty publish_topics list returns None.

        When the contract exists but has no publish_topics configured,
        the method should return None.
        """
        # Arrange: Simulate contract with empty publish_topics
        mock_subcontract = MagicMock()
        mock_subcontract.publish_topics = []
        mock_load_subcontract.return_value = mock_subcontract

        # Act: Import and instantiate the node
        from omniintelligence.nodes.claude_hook_event_effect.node import (
            NodeClaudeHookEventEffect,
        )

        node = NodeClaudeHookEventEffect(mock_onex_container)

        # Assert: publish_topic_suffix should be None
        assert node.publish_topic_suffix is None
        mock_load_subcontract.assert_called_once()

    @patch(
        "omniintelligence.nodes.claude_hook_event_effect.node.load_event_bus_subcontract"
    )
    def test_load_topic_single_topic_success(
        self, mock_load_subcontract: MagicMock, mock_onex_container: MagicMock
    ) -> None:
        """Test that single publish topic is returned correctly.

        When the contract has exactly one publish topic configured,
        that topic should be returned.
        """
        # Arrange: Simulate contract with single publish topic
        expected_topic = "onex.evt.omniintelligence.intent-classified.v1"
        mock_subcontract = MagicMock()
        mock_subcontract.publish_topics = [expected_topic]
        mock_load_subcontract.return_value = mock_subcontract

        # Act: Import and instantiate the node
        from omniintelligence.nodes.claude_hook_event_effect.node import (
            NodeClaudeHookEventEffect,
        )

        node = NodeClaudeHookEventEffect(mock_onex_container)

        # Assert: publish_topic_suffix should be the configured topic
        assert node.publish_topic_suffix == expected_topic
        mock_load_subcontract.assert_called_once()

    @patch(
        "omniintelligence.nodes.claude_hook_event_effect.node.load_event_bus_subcontract"
    )
    def test_load_topic_multiple_topics_uses_first(
        self, mock_load_subcontract: MagicMock, mock_onex_container: MagicMock
    ) -> None:
        """Test that multiple publish topics returns the first one.

        When the contract has multiple publish topics configured,
        only the first topic should be returned. This follows the
        current implementation which uses publish_topics[0].
        """
        # Arrange: Simulate contract with multiple publish topics
        first_topic = "onex.evt.omniintelligence.intent-classified.v1"
        second_topic = "onex.evt.omniintelligence.analysis-completed.v1"
        third_topic = "onex.evt.omniintelligence.pattern-detected.v1"
        mock_subcontract = MagicMock()
        mock_subcontract.publish_topics = [first_topic, second_topic, third_topic]
        mock_load_subcontract.return_value = mock_subcontract

        # Act: Import and instantiate the node
        from omniintelligence.nodes.claude_hook_event_effect.node import (
            NodeClaudeHookEventEffect,
        )

        node = NodeClaudeHookEventEffect(mock_onex_container)

        # Assert: publish_topic_suffix should be the FIRST topic only
        assert node.publish_topic_suffix == first_topic
        mock_load_subcontract.assert_called_once()

    @patch(
        "omniintelligence.nodes.claude_hook_event_effect.node.load_event_bus_subcontract"
    )
    def test_set_publish_topic_suffix_overrides_contract(
        self, mock_load_subcontract: MagicMock, mock_onex_container: MagicMock
    ) -> None:
        """Test that set_publish_topic_suffix overrides contract-loaded value.

        The set_publish_topic_suffix method should allow explicit override
        of the contract-loaded topic suffix.
        """
        # Arrange: Simulate contract with a topic
        contract_topic = "onex.evt.omniintelligence.intent-classified.v1"
        override_topic = "onex.evt.custom.override-topic.v1"
        mock_subcontract = MagicMock()
        mock_subcontract.publish_topics = [contract_topic]
        mock_load_subcontract.return_value = mock_subcontract

        # Act: Import, instantiate, and override
        from omniintelligence.nodes.claude_hook_event_effect.node import (
            NodeClaudeHookEventEffect,
        )

        node = NodeClaudeHookEventEffect(mock_onex_container)

        # Verify contract-loaded value first
        assert node.publish_topic_suffix == contract_topic

        # Override with explicit value
        node.set_publish_topic_suffix(override_topic)

        # Assert: publish_topic_suffix should be the override value
        assert node.publish_topic_suffix == override_topic
