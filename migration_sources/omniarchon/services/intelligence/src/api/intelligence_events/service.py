"""
Intelligence Events Service

Service layer for querying and aggregating intelligence events from multiple sources.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class IntelligenceEventsService:
    """
    Service for querying intelligence events across multiple tables.

    Aggregates data from:
    - agent_actions (from omniclaude)
    - agent_routing_decisions (from omniarchon)
    """

    def __init__(self, db_pool=None):
        """
        Initialize intelligence events service.

        Args:
            db_pool: asyncpg database connection pool
        """
        self.db_pool = db_pool
        self.logger = logging.getLogger("IntelligenceEventsService")

    async def get_events_stream(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        correlation_id: Optional[UUID] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get aggregated event stream from multiple sources.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type (agent_action, routing_decision, error)
            agent_name: Filter by agent name
            correlation_id: Filter by correlation ID
            hours: Time window in hours

        Returns:
            Dictionary with events list and metadata
        """
        if not self.db_pool:
            self.logger.warning("Database pool not available, returning mock data")
            return self._get_mock_events(limit, event_type, agent_name, hours)

        self.logger.info(
            f"Fetching events stream | limit={limit} | type={event_type} | "
            f"agent={agent_name} | hours={hours}"
        )

        # Calculate time threshold
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Fetch events from different sources
        agent_actions = []
        routing_decisions = []

        try:
            async with self.db_pool.acquire() as conn:
                # Fetch agent actions
                if event_type is None or event_type == "agent_action":
                    agent_actions = await self._fetch_agent_actions(
                        conn, time_threshold, agent_name, correlation_id, limit
                    )

                # Fetch routing decisions
                if event_type is None or event_type == "routing_decision":
                    routing_decisions = await self._fetch_routing_decisions(
                        conn, time_threshold, agent_name, correlation_id, limit
                    )

        except Exception as e:
            self.logger.error(f"Error fetching events from database: {e}")
            # Fall back to mock data on error
            return self._get_mock_events(limit, event_type, agent_name, hours)

        # Combine and format events
        events = self._combine_and_format_events(
            agent_actions, routing_decisions, limit
        )

        # Calculate metadata
        event_counts = Counter(event["type"] for event in events)
        time_range = self._calculate_time_range(events)

        return {
            "events": events,
            "total": len(events),
            "time_range": time_range,
            "event_counts": dict(event_counts),
        }

    async def _fetch_agent_actions(
        self,
        conn,
        time_threshold: datetime,
        agent_name: Optional[str],
        correlation_id: Optional[UUID],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fetch agent actions from database"""
        query = """
            SELECT
                id,
                correlation_id,
                agent_name,
                action_type,
                action_name,
                action_details,
                duration_ms,
                created_at
            FROM agent_actions
            WHERE created_at >= $1
        """
        params = [time_threshold]
        param_idx = 2

        if agent_name:
            query += f" AND agent_name = ${param_idx}"
            params.append(agent_name)
            param_idx += 1

        if correlation_id:
            query += f" AND correlation_id = ${param_idx}"
            params.append(correlation_id)
            param_idx += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        try:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error fetching agent_actions: {e}")
            return []

    async def _fetch_routing_decisions(
        self,
        conn,
        time_threshold: datetime,
        agent_name: Optional[str],
        correlation_id: Optional[UUID],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fetch routing decisions from database"""
        # Note: agent_routing_decisions references execution_traces, need to join
        query = """
            SELECT
                ard.id,
                et.correlation_id,
                ard.agent_selected as agent_name,
                ard.confidence_score,
                ard.routing_strategy,
                ard.decision_duration_ms,
                ard.query_text,
                ard.alternatives,
                ard.created_at
            FROM agent_routing_decisions ard
            JOIN execution_traces et ON ard.trace_id = et.id
            WHERE ard.created_at >= $1
        """
        params = [time_threshold]
        param_idx = 2

        if agent_name:
            query += f" AND ard.agent_selected = ${param_idx}"
            params.append(agent_name)
            param_idx += 1

        if correlation_id:
            query += f" AND et.correlation_id = ${param_idx}"
            params.append(correlation_id)
            param_idx += 1

        query += f" ORDER BY ard.created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        try:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error fetching agent_routing_decisions: {e}")
            return []

    def _combine_and_format_events(
        self,
        agent_actions: List[Dict[str, Any]],
        routing_decisions: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Combine and format events from different sources"""
        events = []

        # Format agent actions
        for action in agent_actions:
            event = {
                "id": action["id"],
                "type": "error" if action["action_type"] == "error" else "agent_action",
                "timestamp": action["created_at"],
                "correlation_id": action["correlation_id"],
                "agent_name": action["agent_name"],
                "data": {
                    "action_type": action["action_type"],
                    "action_name": action["action_name"],
                    "duration_ms": action.get("duration_ms"),
                    "details": action.get("action_details", {}),
                },
            }
            events.append(event)

        # Format routing decisions
        for decision in routing_decisions:
            event = {
                "id": decision["id"],
                "type": "routing_decision",
                "timestamp": decision["created_at"],
                "correlation_id": decision["correlation_id"],
                "agent_name": decision["agent_name"],
                "data": {
                    "confidence_score": float(decision["confidence_score"]),
                    "routing_strategy": decision["routing_strategy"],
                    "decision_duration_ms": decision.get("decision_duration_ms"),
                    "query_text": decision.get("query_text"),
                    "alternatives": decision.get("alternatives"),
                },
            }
            events.append(event)

        # Sort by timestamp descending
        events.sort(key=lambda x: x["timestamp"], reverse=True)

        # Apply limit
        return events[:limit]

    def _calculate_time_range(
        self, events: List[Dict[str, Any]]
    ) -> Dict[str, datetime]:
        """Calculate time range from events"""
        if not events:
            now = datetime.now(timezone.utc)
            return {"start_time": now, "end_time": now}

        timestamps = [event["timestamp"] for event in events]
        return {
            "start_time": min(timestamps),
            "end_time": max(timestamps),
        }

    def _get_mock_events(
        self,
        limit: int,
        event_type: Optional[str],
        agent_name: Optional[str],
        hours: int,
    ) -> Dict[str, Any]:
        """Generate mock events for testing/fallback"""
        from uuid import uuid4

        now = datetime.now(timezone.utc)
        events = []

        # Generate mock agent actions
        if event_type is None or event_type == "agent_action":
            for i in range(min(limit // 2, 10)):
                events.append(
                    {
                        "id": uuid4(),
                        "type": "agent_action",
                        "timestamp": now - timedelta(minutes=i * 5),
                        "correlation_id": uuid4(),
                        "agent_name": agent_name or "test-agent",
                        "data": {
                            "action_type": "tool_call",
                            "action_name": "Read",
                            "duration_ms": 150,
                            "details": {"file_path": "/test/file.py"},
                        },
                    }
                )

        # Generate mock routing decisions
        if event_type is None or event_type == "routing_decision":
            for i in range(min(limit // 2, 10)):
                events.append(
                    {
                        "id": uuid4(),
                        "type": "routing_decision",
                        "timestamp": now - timedelta(minutes=i * 5 + 2),
                        "correlation_id": uuid4(),
                        "agent_name": agent_name or "agent-test",
                        "data": {
                            "confidence_score": 0.85,
                            "routing_strategy": "pattern_replay",
                            "decision_duration_ms": 45,
                            "query_text": "Test query",
                        },
                    }
                )

        # Sort by timestamp descending
        events.sort(key=lambda x: x["timestamp"], reverse=True)

        event_counts = Counter(event["type"] for event in events)

        return {
            "events": events[:limit],
            "total": len(events[:limit]),
            "time_range": {
                "start_time": now - timedelta(hours=hours),
                "end_time": now,
            },
            "event_counts": dict(event_counts),
        }
