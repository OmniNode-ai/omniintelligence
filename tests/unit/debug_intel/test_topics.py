# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for DebugIntelTopic enum.

Ticket: OMN-3556
"""

import pytest

from omniintelligence.debug_intel.topics import DebugIntelTopic


@pytest.mark.unit
def test_all_debug_intel_topics_are_string_values() -> None:
    """All DebugIntelTopic members must have correct string values."""
    assert (
        str(DebugIntelTopic.CI_FAILURE_DETECTED)
        == "onex.cmd.omniintelligence.ci-failure-detected.v1"
    )
    assert (
        str(DebugIntelTopic.CI_RECOVERY_DETECTED)
        == "onex.cmd.omniintelligence.ci-recovery-detected.v1"
    )
    assert (
        str(DebugIntelTopic.DEBUG_TRIGGER_RECORD_CREATED)
        == "onex.evt.omniintelligence.debug-trigger-record-created.v1"
    )
    assert (
        str(DebugIntelTopic.DEBUG_FIX_RECORD_CREATED)
        == "onex.evt.omniintelligence.debug-fix-record-created.v1"
    )


@pytest.mark.unit
def test_debug_intel_topic_is_strlike() -> None:
    """DebugIntelTopic members must be usable as strings directly."""
    topic = DebugIntelTopic.CI_FAILURE_DETECTED
    assert isinstance(topic, str)
    assert topic.startswith("onex.")
