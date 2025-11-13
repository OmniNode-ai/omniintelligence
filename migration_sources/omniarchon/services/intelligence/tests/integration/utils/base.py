#!/usr/bin/env python3
"""
Base classes for handler integration tests.

Provides reusable test methods and utilities for handler testing,
including success verification, concurrent processing, and performance measurement.

Author: Archon Intelligence Team
Date: 2025-10-15
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

from .assertions import (
    assert_correlation_id_preserved,
    assert_routing_context,
    assert_unique_correlation_ids,
)


class HandlerTestBase:
    """
    Base class for handler integration tests.

    Provides common test patterns used across all handler tests:
    - Handler success verification
    - Concurrent request processing
    - Performance measurement
    - Router initialization

    Usage:
        class TestMyHandler(HandlerTestBase):
            @pytest.mark.asyncio
            async def test_handler_success(self, handler, event, mock_router):
                publish_call = await self.verify_handler_success(
                    handler, event, mock_router
                )
    """

    async def verify_handler_success(
        self, handler: Any, event: Any, mock_router: AsyncMock
    ) -> Any:
        """
        Verify handler processes event successfully.

        Args:
            handler: Handler instance to test
            event: Event to process
            mock_router: Mocked router instance

        Returns:
            Mock publish call args for further assertions

        Raises:
            AssertionError: If handler fails or publish not called

        Example:
            publish_call = await self.verify_handler_success(
                handler, event, mock_router
            )
            assert publish_call[1]["topic"] == "expected.topic.v1"
        """
        result = await handler.handle_event(event)
        assert result is True, "Handler should return True on success"
        mock_router.publish.assert_called_once()
        return mock_router.publish.call_args

    async def verify_handler_failure(
        self, handler: Any, event: Any, mock_router: AsyncMock
    ) -> Any:
        """
        Verify handler handles failure gracefully.

        Args:
            handler: Handler instance to test
            event: Event that should trigger failure
            mock_router: Mocked router instance

        Returns:
            Mock publish call args for error response assertions

        Raises:
            AssertionError: If handler doesn't fail as expected

        Example:
            publish_call = await self.verify_handler_failure(
                handler, error_event, mock_router
            )
            assert "error" in publish_call[1]["event"].payload["details"]
        """
        result = await handler.handle_event(event)
        assert result is False, "Handler should return False on failure"
        mock_router.publish.assert_called_once()
        return mock_router.publish.call_args

    async def verify_concurrent_processing(
        self,
        handler: Any,
        events: List[Any],
        expected_count: int,
        verify_unique_ids: bool = True,
    ):
        """
        Verify concurrent request handling.

        Args:
            handler: Handler instance to test
            events: List of events to process concurrently
            expected_count: Expected number of successful publications
            verify_unique_ids: Whether to verify unique correlation IDs (default: True)

        Raises:
            AssertionError: If concurrent processing fails

        Example:
            await self.verify_concurrent_processing(
                handler, events=[event1, event2, event3], expected_count=3
            )
        """
        results = await asyncio.gather(*[handler.handle_event(e) for e in events])
        assert all(results), "All concurrent requests should succeed"
        assert (
            handler._router.publish.call_count == expected_count
        ), f"Expected {expected_count} publications, got {handler._router.publish.call_count}"

        if verify_unique_ids:
            assert_unique_correlation_ids(
                handler._router.publish.call_args_list, expected_count
            )

    async def measure_performance(
        self, handler: Any, event: Any, max_time_ms: Optional[float] = None
    ) -> float:
        """
        Measure handler performance in milliseconds.

        Args:
            handler: Handler instance to test
            event: Event to process
            max_time_ms: Optional maximum time threshold in milliseconds

        Returns:
            Elapsed time in milliseconds

        Raises:
            AssertionError: If handler fails or exceeds max_time_ms

        Example:
            elapsed = await self.measure_performance(handler, event, max_time_ms=500)
            print(f"Handler took {elapsed:.2f}ms")
        """
        start = time.time()
        result = await handler.handle_event(event)
        elapsed = (time.time() - start) * 1000

        assert result is True, "Handler should succeed for performance test"

        if max_time_ms is not None:
            assert (
                elapsed < max_time_ms
            ), f"Handler took {elapsed:.2f}ms, exceeds {max_time_ms}ms threshold"

        return elapsed

    async def measure_batch_throughput(
        self,
        handler: Any,
        events: List[Any],
        max_time_ms: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Measure batch processing throughput.

        Args:
            handler: Handler instance to test
            events: List of events to process
            max_time_ms: Optional maximum time threshold in milliseconds

        Returns:
            Dict with throughput metrics:
                - total_time_ms: Total elapsed time
                - throughput_per_sec: Requests per second
                - avg_time_per_request_ms: Average time per request

        Raises:
            AssertionError: If any event fails or exceeds max_time_ms

        Example:
            metrics = await self.measure_batch_throughput(
                handler, events, max_time_ms=5000
            )
            print(f"Throughput: {metrics['throughput_per_sec']:.2f} req/s")
        """
        event_count = len(events)
        start = time.time()
        results = await asyncio.gather(*[handler.handle_event(e) for e in events])
        elapsed = (time.time() - start) * 1000

        assert all(results), "All batch events should succeed"

        if max_time_ms is not None:
            assert (
                elapsed < max_time_ms
            ), f"Batch took {elapsed:.2f}ms, exceeds {max_time_ms}ms threshold"

        throughput = event_count / (elapsed / 1000)
        avg_time = elapsed / event_count

        return {
            "total_time_ms": elapsed,
            "throughput_per_sec": throughput,
            "avg_time_per_request_ms": avg_time,
        }

    def verify_response_structure(
        self, publish_call: Any, expected_topic: str, original_correlation_id: str
    ):
        """
        Verify common response structure (topic, correlation ID, routing context).

        Args:
            publish_call: Mock publish call args
            expected_topic: Expected topic string
            original_correlation_id: Original request correlation ID

        Raises:
            AssertionError: If response structure is invalid

        Example:
            self.verify_response_structure(
                publish_call,
                expected_topic="omninode.codegen.response.analyze.v1",
                original_correlation_id=request.correlation_id
            )
        """
        # Verify topic
        topic = publish_call[1]["topic"]
        assert topic == expected_topic, f"Expected topic {expected_topic}, got {topic}"

        # Verify event and correlation ID
        event = publish_call[1]["event"]
        assert_correlation_id_preserved(event, original_correlation_id)

        # Verify routing context
        context = publish_call[1]["context"]
        assert_routing_context(
            context, requires_persistence=True, is_cross_service=True
        )

        # Verify key matches correlation ID
        key = publish_call[1]["key"]
        assert (
            key == original_correlation_id
        ), f"Expected key {original_correlation_id}, got {key}"

    async def verify_router_initialization(
        self, handler: Any, event: Any, mock_router_class_patch: Any
    ):
        """
        Verify handler initializes router if not already initialized.

        Args:
            handler: Handler instance (with _router_initialized=False)
            event: Event to process
            mock_router_class_patch: Patched HybridEventRouter class

        Raises:
            AssertionError: If router not initialized or publish not called

        Example:
            with patch("handlers.base_response_publisher.HybridEventRouter") as mock_class:
                mock_router = AsyncMock()
                mock_class.return_value = mock_router
                await self.verify_router_initialization(handler, event, mock_class)
        """
        mock_router = mock_router_class_patch.return_value

        result = await handler.handle_event(event)
        assert result is True, "Handler should succeed"

        mock_router.initialize.assert_called_once()
        mock_router.publish.assert_called_once()

    async def verify_publish_failure_recovery(
        self, handler: Any, event: Any, mock_router: AsyncMock, caplog: Any
    ):
        """
        Verify handler recovers gracefully from publish failures.

        Args:
            handler: Handler instance
            event: Event to process
            mock_router: Mocked router with publish failure
            caplog: Pytest log capture fixture

        Raises:
            AssertionError: If handler doesn't handle publish failure gracefully

        Example:
            mock_router.publish.side_effect = Exception("Kafka unavailable")
            await self.verify_publish_failure_recovery(
                handler, event, mock_router, caplog
            )
        """
        result = await handler.handle_event(event)
        assert result is True, "Handler should still succeed (non-blocking publish)"

        # Verify error was logged
        assert any(
            "Failed to publish" in record.message for record in caplog.records
        ), "Publish failure should be logged"
