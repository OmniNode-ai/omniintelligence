"""
Optimistic Updates Testing with Event-Driven Backend

Tests the optimistic update patterns for the Knowledge feature,
ensuring UI responsiveness while maintaining data consistency
through event-driven backend integration.

Error Event Validation:
-----------------------
This test suite validates error events in optimistic update scenarios including:
- Rollback event structure and content
- Failure event payload fields
- Conflict resolution error messages
- Error context propagation
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.integration.error_assertions import (
    ErrorAssertions,
    assert_rollback_event,
)


class OptimisticUpdateTestSuite:
    """Test suite for optimistic update patterns in Knowledge feature"""

    def __init__(self):
        self.session_id = f"optimistic_test_{uuid.uuid4().hex[:8]}"
        self.websocket_events = []
        self.simulated_latency = 0.5  # 500ms simulated network latency

    def generate_test_knowledge_item(self) -> dict[str, Any]:
        """Generate a test knowledge item for optimistic update testing"""
        return {
            "id": f"test_item_{uuid.uuid4().hex[:8]}",
            "title": f"Test Knowledge Item {datetime.now().isoformat()}",
            "url": f"https://test-{self.session_id}.example.com/doc",
            "source_id": f"test_source_{self.session_id}",
            "metadata": {
                "knowledge_type": "test_data",
                "tags": ["test", "optimistic_update"],
                "test_session": self.session_id,
                "created_for": "optimistic_update_test",
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }


class MockWebSocketHandler:
    """Mock WebSocket handler for testing real-time updates"""

    def __init__(self):
        self.connected_clients = []
        self.event_queue = asyncio.Queue()
        self.message_history = []

    async def connect_client(self, client_id: str):
        """Simulate client connection"""
        mock_client = {
            "client_id": client_id,
            "connected_at": datetime.now().isoformat(),
            "events_received": [],
        }
        self.connected_clients.append(mock_client)
        return mock_client

    async def send_event(self, event_type: str, data: dict[str, Any]):
        """Simulate sending event to all connected clients"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "session_id": data.get("session_id"),
        }

        self.message_history.append(event)

        for client in self.connected_clients:
            client["events_received"].append(event)

        await self.event_queue.put(event)

    async def get_next_event(self, timeout: float = 5.0) -> dict[str, Any]:
        """Get next event from queue with timeout"""
        try:
            return await asyncio.wait_for(self.event_queue.get(), timeout=timeout)
        except TimeoutError:
            return None


@pytest.fixture
async def optimistic_test_suite():
    """Fixture providing optimistic update test suite"""
    suite = OptimisticUpdateTestSuite()
    yield suite
    # Cleanup after test
    print(f"✅ Optimistic update test session {suite.session_id} completed")


@pytest.fixture
async def mock_websocket():
    """Fixture providing mock WebSocket handler"""
    handler = MockWebSocketHandler()
    yield handler


@pytest.fixture
async def mock_knowledge_service():
    """Mock knowledge service with simulated latency"""
    service = AsyncMock()

    async def delayed_create(*args, **kwargs):
        """Simulate network latency for create operations"""
        await asyncio.sleep(0.5)  # 500ms latency
        return {
            "success": True,
            "item": kwargs.get("item_data", {}),
            "created_at": datetime.now().isoformat(),
        }

    async def delayed_update(*args, **kwargs):
        """Simulate network latency for update operations"""
        await asyncio.sleep(0.3)  # 300ms latency
        return {
            "success": True,
            "item": kwargs.get("updates", {}),
            "updated_at": datetime.now().isoformat(),
        }

    async def delayed_delete(*args, **kwargs):
        """Simulate network latency for delete operations"""
        await asyncio.sleep(0.2)  # 200ms latency
        return {"success": True}

    service.create_item.side_effect = delayed_create
    service.update_item.side_effect = delayed_update
    service.delete_item.side_effect = delayed_delete

    return service


class TestOptimisticKnowledgeUpdates:
    """Test optimistic update patterns for Knowledge feature"""

    @pytest.mark.asyncio
    async def test_optimistic_knowledge_item_creation(
        self, optimistic_test_suite, mock_websocket, mock_knowledge_service
    ):
        """Test optimistic UI updates during knowledge item creation"""

        # 1. Generate test knowledge item
        test_item = optimistic_test_suite.generate_test_knowledge_item()
        client = await mock_websocket.connect_client("test_client_1")

        # 2. Simulate optimistic UI update (immediate)
        optimistic_start = time.time()
        await mock_websocket.send_event(
            "knowledge_item_creating",
            {
                "item": test_item,
                "optimistic": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )
        optimistic_duration = time.time() - optimistic_start

        # 3. Verify optimistic update is immediate
        assert (
            optimistic_duration < 0.1
        ), f"Optimistic update should be immediate, took {optimistic_duration:.3f}s"

        # 4. Simulate backend processing (with latency)
        backend_start = time.time()
        backend_result = await mock_knowledge_service.create_item(item_data=test_item)
        backend_duration = time.time() - backend_start

        # 5. Verify backend processing has expected latency
        assert (
            backend_duration >= 0.4
        ), f"Backend should have latency, took {backend_duration:.3f}s"
        assert backend_result["success"] is True

        # 6. Send confirmation event
        await mock_websocket.send_event(
            "knowledge_item_created",
            {
                "item": backend_result["item"],
                "optimistic": False,
                "confirmed": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 7. Verify event sequence
        client_events = client["events_received"]
        assert len(client_events) == 2
        assert client_events[0]["type"] == "knowledge_item_creating"
        assert client_events[0]["data"]["optimistic"] is True
        assert client_events[1]["type"] == "knowledge_item_created"
        assert client_events[1]["data"]["confirmed"] is True

        print(
            f"✅ Optimistic creation: UI update in {optimistic_duration:.3f}s, backend in {backend_duration:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_optimistic_knowledge_item_updates(
        self, optimistic_test_suite, mock_websocket, mock_knowledge_service
    ):
        """Test optimistic UI updates during knowledge item editing"""

        # 1. Start with existing item
        existing_item = optimistic_test_suite.generate_test_knowledge_item()
        client = await mock_websocket.connect_client("test_client_2")

        # 2. Simulate user editing (optimistic update)
        updates = {
            "title": "Updated Title - Optimistic",
            "metadata": {
                **existing_item["metadata"],
                "last_updated": datetime.now().isoformat(),
                "edit_type": "optimistic",
            },
        }

        optimistic_start = time.time()
        await mock_websocket.send_event(
            "knowledge_item_updating",
            {
                "item_id": existing_item["id"],
                "updates": updates,
                "optimistic": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )
        optimistic_duration = time.time() - optimistic_start

        # 3. Verify immediate optimistic response
        assert optimistic_duration < 0.1, "Optimistic update should be immediate"

        # 4. Simulate backend processing
        backend_result = await mock_knowledge_service.update_item(
            item_id=existing_item["id"], updates=updates
        )

        # 5. Send backend confirmation
        confirmed_item = {**existing_item, **updates, **backend_result["item"]}
        await mock_websocket.send_event(
            "knowledge_item_updated",
            {
                "item": confirmed_item,
                "optimistic": False,
                "confirmed": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 6. Verify update sequence
        client_events = client["events_received"]
        assert len(client_events) == 2
        assert client_events[0]["data"]["optimistic"] is True
        assert client_events[1]["data"]["confirmed"] is True

        print(f"✅ Optimistic update completed in {optimistic_duration:.3f}s")

    @pytest.mark.asyncio
    async def test_rollback_on_creation_failure(
        self, optimistic_test_suite, mock_websocket, mock_knowledge_service
    ):
        """
        Test rollback behavior when optimistic creation fails.

        Error Event Validation:
        - Verifies rollback event has proper structure
        - Validates error message propagation to event
        - Confirms rollback flag is set correctly
        - Ensures item_id is included for client-side cleanup
        """

        # 1. Configure service to fail
        mock_knowledge_service.create_item.side_effect = Exception(
            "Backend service error"
        )

        test_item = optimistic_test_suite.generate_test_knowledge_item()
        client = await mock_websocket.connect_client("test_client_3")

        # 2. Send optimistic update
        await mock_websocket.send_event(
            "knowledge_item_creating",
            {
                "item": test_item,
                "optimistic": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 3. Attempt backend creation (will fail)
        captured_exception = None
        try:
            await mock_knowledge_service.create_item(item_data=test_item)
            raise AssertionError("Service should have failed")
        except Exception as e:
            captured_exception = e
            # 4. Send rollback event
            await mock_websocket.send_event(
                "knowledge_item_creation_failed",
                {
                    "item_id": test_item["id"],
                    "error": str(e),
                    "rollback": True,
                    "session_id": optimistic_test_suite.session_id,
                },
            )

        # 5. Verify rollback sequence
        client_events = client["events_received"]
        assert len(client_events) == 2
        assert client_events[0]["type"] == "knowledge_item_creating"
        assert client_events[1]["type"] == "knowledge_item_creation_failed"

        # Enhanced error event validation: Comprehensive rollback event check
        rollback_event = client_events[1]
        assert_rollback_event(
            rollback_event,
            expected_item_id=test_item["id"],
            expected_rollback_reason="Backend service error",
        )

        # Validate exception handling
        ErrorAssertions.assert_exception_handling(
            captured_exception,
            expected_exception_type=Exception,
            expected_message_contains="Backend service error",
        )

        # Verify rollback event provides complete context
        rollback_data = rollback_event["data"]
        assert "error" in rollback_data, "Rollback event should include error message"
        assert len(rollback_data["error"]) > 0, "Error message should not be empty"
        assert "item_id" in rollback_data, "Rollback event should include item_id"

        print("✅ Rollback on creation failure test passed")

    @pytest.mark.asyncio
    async def test_rollback_on_update_conflict(
        self, optimistic_test_suite, mock_websocket, mock_knowledge_service
    ):
        """
        Test rollback behavior when update conflicts with server state.

        Error Event Validation:
        - Verifies conflict event has proper error fields
        - Validates server_state is included for rollback
        - Confirms conflict reason describes the issue
        - Ensures rollback flag is properly set
        """

        existing_item = optimistic_test_suite.generate_test_knowledge_item()
        client = await mock_websocket.connect_client("test_client_4")

        # 1. Simulate optimistic update
        optimistic_updates = {"title": "Optimistic Title"}
        await mock_websocket.send_event(
            "knowledge_item_updating",
            {
                "item_id": existing_item["id"],
                "updates": optimistic_updates,
                "optimistic": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 2. Configure backend to return conflict
        mock_knowledge_service.update_item.side_effect = Exception(
            "Version conflict: item was modified by another user"
        )

        # 3. Attempt backend update (will conflict)
        conflict_exception = None
        try:
            await mock_knowledge_service.update_item(
                item_id=existing_item["id"], updates=optimistic_updates
            )
            raise AssertionError("Should have conflicted")
        except Exception as e:
            conflict_exception = e
            # 4. Send conflict resolution event
            await mock_websocket.send_event(
                "knowledge_item_update_conflict",
                {
                    "item_id": existing_item["id"],
                    "conflict_reason": str(e),
                    "server_state": existing_item,  # Server's current state
                    "rollback_to_server": True,
                    "session_id": optimistic_test_suite.session_id,
                },
            )

        # 5. Verify conflict handling
        client_events = client["events_received"]
        assert len(client_events) == 2
        assert client_events[1]["type"] == "knowledge_item_update_conflict"

        # Enhanced error event validation: Comprehensive conflict event check
        conflict_event = client_events[1]
        assert_rollback_event(
            conflict_event,
            expected_item_id=existing_item["id"],
            expected_rollback_reason="Version conflict",
            should_have_original_state=True,
        )

        # Validate conflict exception
        ErrorAssertions.assert_exception_handling(
            conflict_exception,
            expected_exception_type=Exception,
            expected_message_contains="Version conflict",
        )

        # Verify conflict event includes necessary fields
        conflict_data = conflict_event["data"]
        assert "conflict_reason" in conflict_data, "Conflict event should have reason"
        assert (
            "server_state" in conflict_data
        ), "Conflict event should include server state"
        assert (
            "rollback_to_server" in conflict_data
        ), "Conflict event should have rollback flag"
        assert (
            conflict_data["rollback_to_server"] is True
        ), "Should rollback to server state"

        # Validate conflict reason is descriptive
        conflict_reason = conflict_data["conflict_reason"]
        assert len(conflict_reason) > 0, "Conflict reason should not be empty"
        assert (
            "conflict" in conflict_reason.lower()
            or "modified" in conflict_reason.lower()
        ), f"Conflict reason should describe the conflict: {conflict_reason}"

        # Validate server_state provides rollback data
        server_state = conflict_data["server_state"]
        assert isinstance(server_state, dict), "Server state should be dict"
        assert "id" in server_state, "Server state should include item ID"

        print("✅ Update conflict rollback test passed")

    @pytest.mark.asyncio
    async def test_concurrent_optimistic_updates(
        self, optimistic_test_suite, mock_websocket, mock_knowledge_service
    ):
        """Test handling of concurrent optimistic updates from multiple clients"""

        existing_item = optimistic_test_suite.generate_test_knowledge_item()

        # Connect multiple clients
        client1 = await mock_websocket.connect_client("concurrent_client_1")
        client2 = await mock_websocket.connect_client("concurrent_client_2")

        # 1. Client 1 makes optimistic update
        updates1 = {"title": "Client 1 Update", "metadata": {"editor": "client1"}}
        await mock_websocket.send_event(
            "knowledge_item_updating",
            {
                "item_id": existing_item["id"],
                "updates": updates1,
                "optimistic": True,
                "client_id": "concurrent_client_1",
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 2. Client 2 makes optimistic update (concurrent)
        updates2 = {"title": "Client 2 Update", "metadata": {"editor": "client2"}}
        await mock_websocket.send_event(
            "knowledge_item_updating",
            {
                "item_id": existing_item["id"],
                "updates": updates2,
                "optimistic": True,
                "client_id": "concurrent_client_2",
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 3. Simulate server resolving conflict (last-write-wins for test)
        final_state = {**existing_item, **updates2, "resolved_by": "server"}
        mock_knowledge_service.update_item.return_value = {
            "success": True,
            "item": final_state,
            "conflict_resolution": "last_write_wins",
        }

        # 4. Send final resolution to all clients
        await mock_websocket.send_event(
            "knowledge_item_resolved",
            {
                "item": final_state,
                "resolution_strategy": "last_write_wins",
                "winning_client": "concurrent_client_2",
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 5. Verify both clients received all events
        assert len(client1["events_received"]) == 3  # update1, update2, resolution
        assert len(client2["events_received"]) == 3  # update1, update2, resolution

        # Both clients should see the same final resolution
        final_event1 = client1["events_received"][-1]
        final_event2 = client2["events_received"][-1]
        assert final_event1 == final_event2
        assert final_event1["type"] == "knowledge_item_resolved"

        print("✅ Concurrent optimistic updates test passed")

    @pytest.mark.asyncio
    async def test_sync_after_offline_period(
        self, optimistic_test_suite, mock_websocket, mock_knowledge_service
    ):
        """Test synchronization after client has been offline"""

        client = await mock_websocket.connect_client("offline_client")

        # 1. Simulate client going offline (miss some events)
        offline_changes = []
        for i in range(3):
            change = {
                "item_id": f"missed_item_{i}",
                "change_type": "update",
                "timestamp": datetime.now().isoformat(),
                "missed_while_offline": True,
            }
            offline_changes.append(change)

        # 2. Client comes back online and requests sync
        await mock_websocket.send_event(
            "client_reconnected",
            {
                "client_id": "offline_client",
                "last_seen": (datetime.now().timestamp() - 300),  # 5 minutes ago
                "request_sync": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 3. Server sends missed events
        await mock_websocket.send_event(
            "sync_missed_changes",
            {
                "client_id": "offline_client",
                "missed_changes": offline_changes,
                "sync_complete": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        # 4. Verify sync events
        client_events = client["events_received"]
        sync_events = [e for e in client_events if "sync" in e["type"]]
        assert len(sync_events) == 1
        assert sync_events[0]["data"]["sync_complete"] is True
        assert len(sync_events[0]["data"]["missed_changes"]) == 3

        print("✅ Offline sync test passed")


class TestEventDrivenBackendIntegration:
    """Test event-driven backend integration patterns"""

    @pytest.mark.asyncio
    async def test_document_update_event_flow(
        self, optimistic_test_suite, mock_websocket
    ):
        """Test document update events propagate correctly through system"""

        # 1. Create mock services
        services = {
            "intelligence": AsyncMock(),
            "search": AsyncMock(),
            "bridge": AsyncMock(),
            "knowledge": AsyncMock(),
        }

        # 2. Simulate document update event
        document_event = {
            "event_type": "document_updated",
            "document_id": f"doc_{optimistic_test_suite.session_id}",
            "changes": ["content", "metadata"],
            "source_service": "intelligence",
            "timestamp": datetime.now().isoformat(),
        }

        # 3. Simulate event routing to services
        routing_results = {}
        for service_name, service in services.items():
            service.process_document_event.return_value = {
                "success": True,
                "processed_at": datetime.now().isoformat(),
                "service": service_name,
            }

            result = await service.process_document_event(document_event)
            routing_results[service_name] = result

        # 4. Verify all services processed the event
        for service_name, result in routing_results.items():
            assert result["success"] is True
            assert result["service"] == service_name
            services[service_name].process_document_event.assert_called_once_with(
                document_event
            )

        # 5. Simulate consolidated update to frontend
        await mock_websocket.send_event(
            "document_processing_complete",
            {
                "document_id": document_event["document_id"],
                "services_processed": list(routing_results.keys()),
                "processing_results": routing_results,
                "session_id": optimistic_test_suite.session_id,
            },
        )

        print("✅ Document update event flow test passed")

    @pytest.mark.asyncio
    async def test_event_ordering_and_consistency(
        self, optimistic_test_suite, mock_websocket
    ):
        """Test that events maintain proper ordering and consistency"""

        item_id = f"ordered_item_{optimistic_test_suite.session_id}"
        client = await mock_websocket.connect_client("ordering_client")

        # 1. Send sequence of events that must maintain order
        ordered_events = [
            {"type": "item_created", "item_id": item_id, "sequence": 1},
            {
                "type": "item_updated",
                "item_id": item_id,
                "sequence": 2,
                "field": "title",
            },
            {
                "type": "item_updated",
                "item_id": item_id,
                "sequence": 3,
                "field": "metadata",
            },
            {
                "type": "item_processed",
                "item_id": item_id,
                "sequence": 4,
                "status": "complete",
            },
        ]

        for event in ordered_events:
            await mock_websocket.send_event(
                event["type"],
                {
                    **event,
                    "timestamp": time.time(),
                    "session_id": optimistic_test_suite.session_id,
                },
            )
            await asyncio.sleep(0.1)  # Small delay to ensure ordering

        # 2. Verify events were received in correct order
        client_events = client["events_received"]
        assert len(client_events) == 4

        for i, event in enumerate(client_events):
            expected_sequence = i + 1
            assert event["data"]["sequence"] == expected_sequence

        # 3. Verify no event was lost or duplicated
        sequences = [e["data"]["sequence"] for e in client_events]
        assert sequences == [1, 2, 3, 4]
        assert len(set(sequences)) == 4  # No duplicates

        print("✅ Event ordering and consistency test passed")


@pytest.mark.asyncio
async def test_optimistic_update_performance_benchmarks(
    optimistic_test_suite, mock_websocket
):
    """Test performance benchmarks for optimistic updates"""

    await mock_websocket.connect_client("perf_client")

    # Test optimistic update latency
    update_times = []
    for i in range(10):
        start_time = time.time()
        await mock_websocket.send_event(
            "knowledge_item_updating",
            {
                "item_id": f"perf_item_{i}",
                "updates": {"title": f"Performance Test {i}"},
                "optimistic": True,
                "session_id": optimistic_test_suite.session_id,
            },
        )
        end_time = time.time()
        update_times.append(end_time - start_time)

    # Performance assertions
    avg_update_time = sum(update_times) / len(update_times)
    max_update_time = max(update_times)

    assert (
        avg_update_time < 0.05
    ), f"Average optimistic update time {avg_update_time:.3f}s should be < 50ms"
    assert (
        max_update_time < 0.1
    ), f"Max optimistic update time {max_update_time:.3f}s should be < 100ms"

    print(
        f"✅ Performance benchmark: avg={avg_update_time:.3f}s, max={max_update_time:.3f}s"
    )


if __name__ == "__main__":
    # Run specific test for development
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "demo":

        async def demo_optimistic_updates():
            suite = OptimisticUpdateTestSuite()
            websocket = MockWebSocketHandler()

            print("🚀 Demo: Optimistic Update Flow")

            # Demo optimistic creation
            test_item = suite.generate_test_knowledge_item()
            client = await websocket.connect_client("demo_client")

            print("1. Sending optimistic update...")
            await websocket.send_event(
                "knowledge_item_creating",
                {"item": test_item, "optimistic": True, "session_id": suite.session_id},
            )

            print("2. Simulating backend processing...")
            await asyncio.sleep(0.5)

            print("3. Sending confirmation...")
            await websocket.send_event(
                "knowledge_item_created",
                {"item": test_item, "confirmed": True, "session_id": suite.session_id},
            )

            print(
                f"✅ Demo complete. Client received {len(client['events_received'])} events"
            )
            for i, event in enumerate(client["events_received"]):
                print(
                    f"   Event {i+1}: {event['type']} - optimistic: {event['data'].get('optimistic', False)}"
                )

        asyncio.run(demo_optimistic_updates())
