"""
Pattern Usage Tracker

Tracks pattern usage from Kafka events and updates database.
Handles concurrent updates with proper locking to avoid race conditions.

Created: 2025-10-28
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID

import asyncpg
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Prometheus metrics
pattern_usage_tracked = Counter(
    "pattern_usage_tracked_total",
    "Total pattern usages tracked",
    ["source_type"],  # manifest, action, routing
)

pattern_usage_errors = Counter(
    "pattern_usage_errors_total",
    "Total errors tracking pattern usage",
    ["error_type"],
)

pattern_update_duration = Histogram(
    "pattern_usage_update_duration_seconds",
    "Time to update pattern usage in database",
)


class UsageTracker:
    """
    Tracks pattern usage and updates database.

    Monitors Kafka events for pattern usage:
    - agent-manifest-injections: Patterns included in agent manifests
    - agent-actions: Patterns referenced in agent tool calls
    - agent-routing-decisions: Patterns influencing routing

    Updates pattern_lineage_nodes:
    - Increments usage_count
    - Updates last_used_at timestamp
    - Adds agent name to used_by_agents array (if not present)
    """

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize usage tracker.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
        self._update_lock = asyncio.Lock()
        self._batch_updates: Dict[str, Set[str]] = (
            {}
        )  # pattern_id -> set of agent names
        self._batch_size = 50
        self._batch_timeout = 5.0  # seconds
        self._batch_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background batch processing."""
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._batch_processor())
            logger.info("Started usage tracker batch processor")

    async def stop(self):
        """Stop background batch processing and flush pending updates."""
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        # Flush remaining updates
        await self._flush_batch()
        logger.info("Stopped usage tracker batch processor")

    async def track_manifest_usage(
        self,
        patterns: List[Dict],
        agent_name: str,
        correlation_id: UUID,
    ):
        """
        Track patterns from manifest injection.

        Args:
            patterns: List of pattern objects with 'pattern_id' or 'name'
            agent_name: Name of agent using patterns
            correlation_id: Correlation ID for tracing
        """
        pattern_ids = self._extract_pattern_ids(patterns)

        if not pattern_ids:
            logger.debug(
                f"No pattern IDs found in manifest for agent={agent_name}, "
                f"correlation_id={correlation_id}"
            )
            return

        logger.info(
            f"Tracking manifest usage: {len(pattern_ids)} patterns "
            f"for agent={agent_name}, correlation_id={correlation_id}"
        )

        # Add to batch
        async with self._update_lock:
            for pattern_id in pattern_ids:
                if pattern_id not in self._batch_updates:
                    self._batch_updates[pattern_id] = set()
                self._batch_updates[pattern_id].add(agent_name)

        pattern_usage_tracked.labels(source_type="manifest").inc(len(pattern_ids))

    async def track_action_usage(
        self,
        action_data: Dict,
        agent_name: str,
        correlation_id: UUID,
    ):
        """
        Track patterns from agent action.

        Args:
            action_data: Action data containing pattern references
            agent_name: Name of agent performing action
            correlation_id: Correlation ID for tracing
        """
        # Extract pattern IDs from action data
        pattern_ids = self._extract_pattern_ids_from_action(action_data)

        if not pattern_ids:
            return

        logger.info(
            f"Tracking action usage: {len(pattern_ids)} patterns "
            f"for agent={agent_name}, correlation_id={correlation_id}"
        )

        # Add to batch
        async with self._update_lock:
            for pattern_id in pattern_ids:
                if pattern_id not in self._batch_updates:
                    self._batch_updates[pattern_id] = set()
                self._batch_updates[pattern_id].add(agent_name)

        pattern_usage_tracked.labels(source_type="action").inc(len(pattern_ids))

    async def track_routing_usage(
        self,
        routing_data: Dict,
        agent_name: str,
        correlation_id: UUID,
    ):
        """
        Track patterns influencing routing decision.

        Args:
            routing_data: Routing data with pattern references
            agent_name: Name of selected agent
            correlation_id: Correlation ID for tracing
        """
        # Extract pattern IDs from routing data
        pattern_ids = self._extract_pattern_ids_from_routing(routing_data)

        if not pattern_ids:
            return

        logger.info(
            f"Tracking routing usage: {len(pattern_ids)} patterns "
            f"for agent={agent_name}, correlation_id={correlation_id}"
        )

        # Add to batch
        async with self._update_lock:
            for pattern_id in pattern_ids:
                if pattern_id not in self._batch_updates:
                    self._batch_updates[pattern_id] = set()
                self._batch_updates[pattern_id].add(agent_name)

        pattern_usage_tracked.labels(source_type="routing").inc(len(pattern_ids))

    async def _batch_processor(self):
        """Background task to process batched updates periodically."""
        while True:
            try:
                await asyncio.sleep(self._batch_timeout)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processor: {e}", exc_info=True)
                pattern_usage_errors.labels(error_type="batch_processor").inc()

    async def _flush_batch(self):
        """Flush pending batch updates to database."""
        if not self._batch_updates:
            return

        # Take snapshot of current batch and clear
        async with self._update_lock:
            updates = dict(self._batch_updates)
            self._batch_updates.clear()

        if not updates:
            return

        logger.info(f"Flushing {len(updates)} pattern usage updates")

        with pattern_update_duration.time():
            try:
                await self._bulk_update_usage(updates)
                logger.info(f"Successfully flushed {len(updates)} pattern updates")
            except Exception as e:
                logger.error(f"Error flushing batch updates: {e}", exc_info=True)
                pattern_usage_errors.labels(error_type="batch_flush").inc()

    async def _bulk_update_usage(self, updates: Dict[str, Set[str]]):
        """
        Bulk update pattern usage in database.

        Uses PostgreSQL's array operations to handle concurrent updates safely.

        Args:
            updates: Dict mapping pattern_id to set of agent names
        """
        if not updates:
            return

        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for pattern_id, agent_names in updates.items():
                    try:
                        # Update usage_count, last_used_at, and used_by_agents
                        # Use array_append with DISTINCT to avoid duplicates
                        result = await conn.execute(
                            """
                            UPDATE pattern_lineage_nodes
                            SET
                                usage_count = usage_count + 1,
                                last_used_at = $1,
                                used_by_agents = array(
                                    SELECT DISTINCT unnest(
                                        used_by_agents || $2::text[]
                                    )
                                )
                            WHERE pattern_id = $3
                            """,
                            datetime.now(timezone.utc),
                            list(agent_names),
                            pattern_id,
                        )

                        # Check if pattern was found
                        if result == "UPDATE 0":
                            logger.warning(
                                f"Pattern not found for update: pattern_id={pattern_id}"
                            )
                            pattern_usage_errors.labels(
                                error_type="pattern_not_found"
                            ).inc()

                    except Exception as e:
                        logger.error(
                            f"Error updating pattern usage for {pattern_id}: {e}",
                            exc_info=True,
                        )
                        pattern_usage_errors.labels(error_type="update_failed").inc()

    def _extract_pattern_ids(self, patterns: List[Dict]) -> List[str]:
        """
        Extract pattern IDs from pattern objects.

        Handles various pattern formats:
        - {'pattern_id': 'id'}
        - {'id': 'id'}
        - {'name': 'pattern_name'}

        Args:
            patterns: List of pattern dictionaries

        Returns:
            List of pattern IDs (strings)
        """
        pattern_ids = []

        for pattern in patterns:
            if isinstance(pattern, dict):
                # Try different field names
                pattern_id = (
                    pattern.get("pattern_id")
                    or pattern.get("id")
                    or pattern.get("name")
                )

                if pattern_id:
                    # Convert to string if UUID
                    if isinstance(pattern_id, UUID):
                        pattern_id = str(pattern_id)
                    pattern_ids.append(pattern_id)
            elif isinstance(pattern, str):
                # Pattern ID provided directly as string
                pattern_ids.append(pattern)

        return pattern_ids

    def _extract_pattern_ids_from_action(self, action_data: Dict) -> List[str]:
        """
        Extract pattern IDs from agent action data.

        Looks for pattern references in:
        - action_data['patterns']
        - action_data['pattern_ids']
        - action_data['metadata']['patterns']

        Args:
            action_data: Action event data

        Returns:
            List of pattern IDs
        """
        pattern_ids = []

        # Check direct pattern fields
        if "patterns" in action_data:
            pattern_ids.extend(self._extract_pattern_ids(action_data["patterns"]))

        if "pattern_ids" in action_data:
            ids = action_data["pattern_ids"]
            if isinstance(ids, list):
                pattern_ids.extend(ids)
            elif isinstance(ids, str):
                pattern_ids.append(ids)

        # Check metadata
        if "metadata" in action_data and isinstance(action_data["metadata"], dict):
            metadata = action_data["metadata"]
            if "patterns" in metadata:
                pattern_ids.extend(self._extract_pattern_ids(metadata["patterns"]))

        return pattern_ids

    def _extract_pattern_ids_from_routing(self, routing_data: Dict) -> List[str]:
        """
        Extract pattern IDs from routing decision data.

        Looks for pattern references in:
        - routing_data['patterns_used']
        - routing_data['confidence_components']['patterns']
        - routing_data['context']['patterns']

        Args:
            routing_data: Routing decision event data

        Returns:
            List of pattern IDs
        """
        pattern_ids = []

        # Check patterns_used field
        if "patterns_used" in routing_data:
            pattern_ids.extend(self._extract_pattern_ids(routing_data["patterns_used"]))

        # Check confidence components
        if "confidence_components" in routing_data:
            components = routing_data["confidence_components"]
            if isinstance(components, dict) and "patterns" in components:
                pattern_ids.extend(self._extract_pattern_ids(components["patterns"]))

        # Check context
        if "context" in routing_data and isinstance(routing_data["context"], dict):
            context = routing_data["context"]
            if "patterns" in context:
                pattern_ids.extend(self._extract_pattern_ids(context["patterns"]))

        return pattern_ids
