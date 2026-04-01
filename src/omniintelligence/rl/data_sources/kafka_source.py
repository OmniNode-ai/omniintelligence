# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Kafka data source for real-time RL episode streaming.

Stub implementation — will be completed when real-time episode
collection is implemented.

Ticket: OMN-5562
"""

from __future__ import annotations

import os

from omniintelligence.rl.buffer import EpisodeReplayBuffer


class KafkaEpisodeSource:
    """Stream RL episodes from Kafka for real-time buffer population.

    Not yet implemented. This source will consume from the
    ``onex.evt.omniintelligence.rl-episode-completed.v1`` topic
    and add episodes to the replay buffer in real time.
    """

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        if bootstrap_servers is None:
            bootstrap_servers = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
        self._bootstrap_servers = bootstrap_servers

    async def populate_buffer(
        self,
        buffer: EpisodeReplayBuffer,
    ) -> int:
        """Stream episodes from Kafka into the replay buffer.

        Args:
            buffer: Target replay buffer to populate.

        Raises:
            NotImplementedError: Always — Kafka source not yet implemented.
        """
        raise NotImplementedError("Kafka source not yet implemented")  # stub-ok
