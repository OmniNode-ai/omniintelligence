# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Data sources for populating the episode replay buffer.

Provides adapters for loading RL episodes from different backends:
- PostgresEpisodeSource: Historical episodes from omnidash_analytics
- KafkaEpisodeSource: Real-time episode streaming (stub)
"""

from omniintelligence.rl.data_sources.kafka_source import KafkaEpisodeSource
from omniintelligence.rl.data_sources.postgres_source import PostgresEpisodeSource

__all__ = ["KafkaEpisodeSource", "PostgresEpisodeSource"]
