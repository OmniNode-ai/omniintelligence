# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""PostgreSQL data source for RL episode replay buffer.

Reads historical routing decision episodes from the omnidash_analytics
database (rl_episodes table) and reconstructs observation vectors using
ONLY data available at or before each episode's observation_timestamp.

CRITICAL: No future leakage — observations must use time-correct features only.

Architecture: Uses protocol-based pool injection to comply with ARCH-002.
The database pool is created externally (e.g., in runtime/adapters layer)
and injected via the constructor. No direct transport library imports.

Ticket: OMN-5562
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from omniintelligence.rl.buffer import Episode, EpisodeReplayBuffer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol for database pool (avoids direct asyncpg import per ARCH-002)
# ---------------------------------------------------------------------------


@runtime_checkable
class AsyncDBPool(Protocol):
    """Protocol for an async database connection pool.

    Matches the asyncpg.Pool interface for the methods we need.
    Allows injection of any compatible pool implementation.
    """

    async def fetch(self, query: str, *args: Any) -> list[Any]: ...

    async def fetchval(self, query: str, *args: Any) -> Any: ...

    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PostgresSourceConfig:
    """Configuration for the PostgreSQL episode source.

    Attributes:
        dsn: PostgreSQL connection string.
        table: Table name for rl_episodes.
        batch_size: Number of rows to fetch per query batch.
        max_episodes: Maximum number of episodes to load (0 = no limit).
    """

    dsn: str = ""
    table: str = "rl_episodes"
    batch_size: int = 1000
    max_episodes: int = 0

    @classmethod
    def from_env(cls) -> PostgresSourceConfig:
        """Create config from environment variables.

        Uses OMNIDASH_ANALYTICS_DSN if set, otherwise constructs from
        standard POSTGRES_* variables targeting omnidash_analytics.
        """
        dsn = os.environ.get("OMNIDASH_ANALYTICS_DSN", "")
        if not dsn:
            host = os.environ.get("POSTGRES_HOST", "localhost")
            port = os.environ.get("POSTGRES_PORT", "5436")
            user = os.environ.get("POSTGRES_USER", "postgres")
            password = os.environ.get("POSTGRES_PASSWORD", "")
            database = os.environ.get("OMNIDASH_ANALYTICS_DB", "omnidash_analytics")
            dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        return cls(dsn=dsn)


# ---------------------------------------------------------------------------
# PostgresEpisodeSource
# ---------------------------------------------------------------------------


class PostgresEpisodeSource:
    """Load RL episodes from PostgreSQL omnidash_analytics database.

    Reads from the rl_episodes table and reconstructs observation vectors
    using ONLY data available at or before each episode's observation_timestamp.

    The observation column stores the pre-computed feature vector as JSONB.
    This ensures time-correctness: the feature vector was computed at
    decision time and does NOT contain future information.

    The database pool MUST be injected via constructor. This follows
    ARCH-002: no direct transport imports in domain code.

    Usage::

        # Pool created in runtime/adapters layer
        pool = await asyncpg.create_pool(dsn=config.dsn)
        source = PostgresEpisodeSource(config, pool=pool)

        buffer = EpisodeReplayBuffer()
        await source.populate_buffer(buffer)
    """

    def __init__(
        self,
        config: PostgresSourceConfig,
        pool: AsyncDBPool,
    ) -> None:
        self._config = config
        self._pool = pool

    async def close(self) -> None:
        """Close the connection pool."""
        await self._pool.close()

    async def count_eligible(self) -> int:
        """Count the number of completed episodes available.

        Returns:
            Number of completed episodes in rl_episodes table.
        """
        sql = _count_sql(self._config.table)
        row = await self._pool.fetchval(sql)
        return int(row) if row else 0

    async def populate_buffer(
        self,
        buffer: EpisodeReplayBuffer,
        *,
        since: datetime | None = None,
    ) -> int:
        """Load episodes from PostgreSQL into the replay buffer.

        Fetches episodes in batches to control memory usage. Each row's
        observation column contains the pre-computed feature vector that
        was recorded at decision time (no future leakage).

        Args:
            buffer: Target replay buffer to populate.
            since: Optional lower bound on observation_timestamp.

        Returns:
            Number of episodes loaded.
        """
        loaded = 0
        offset = 0

        while True:
            if self._config.max_episodes > 0 and loaded >= self._config.max_episodes:
                break

            remaining = self._config.batch_size
            if self._config.max_episodes > 0:
                remaining = min(remaining, self._config.max_episodes - loaded)

            sql = _build_fetch_sql(
                table=self._config.table,
                since=since,
            )

            rows = await self._pool.fetch(sql, offset, remaining)
            if not rows:
                break

            for row in rows:
                episode = _row_to_episode(row)
                if episode is not None:
                    buffer.add(episode)
                    loaded += 1

            offset += len(rows)

            if len(rows) < remaining:
                break

        logger.info(
            "Loaded %d episodes from %s into replay buffer",
            loaded,
            self._config.table,
        )
        return loaded


# ---------------------------------------------------------------------------
# SQL builders
# ---------------------------------------------------------------------------


def _count_sql(table: str) -> str:
    """Build SQL to count eligible episodes."""
    return f"SELECT COUNT(*) FROM {table} WHERE status = 'completed'"


def _build_fetch_sql(
    table: str,
    since: datetime | None = None,
) -> str:
    """Build the SQL query for fetching episodes.

    Args:
        table: Table name.
        since: Optional lower bound on observation_timestamp.

    Returns:
        SQL query string with $1=offset, $2=limit parameters.
    """
    where_clauses = ["status = 'completed'"]
    if since is not None:
        where_clauses.append(f"observation_timestamp >= '{since.isoformat()}'")

    where = " AND ".join(where_clauses)
    return f"""
SELECT
    id,
    observation_timestamp,
    observation,
    action_index,
    reward,
    value_estimate,
    log_prob
FROM {table}
WHERE {where}
ORDER BY observation_timestamp ASC
OFFSET $1
LIMIT $2
"""


# ---------------------------------------------------------------------------
# Row conversion
# ---------------------------------------------------------------------------


def _row_to_episode(row: Any) -> Episode | None:
    """Convert a database row to an Episode.

    The observation column is expected to be a JSONB array of floats
    representing the feature vector computed at decision time.

    Args:
        row: Database record with dict-like access (e.g., asyncpg.Record).

    Returns:
        Episode instance, or None if the row is malformed.
    """
    try:
        observation = row["observation"]
        if isinstance(observation, str):
            observation = json.loads(observation)

        if not isinstance(observation, list):
            logger.warning(
                "Skipping episode %s: observation is not a list",
                row.get("id", "unknown"),
            )
            return None

        return Episode(
            observation=[float(x) for x in observation],
            action=int(row["action_index"]),
            reward=float(row["reward"]),
            value_estimate=float(row.get("value_estimate", 0.0) or 0.0),
            log_prob=float(row.get("log_prob", 0.0) or 0.0),
            timestamp=row.get("observation_timestamp"),
            episode_id=str(row["id"]) if row.get("id") is not None else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Skipping malformed episode row: %s", exc)
        return None
