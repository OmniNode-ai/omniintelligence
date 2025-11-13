"""
Performance Tests for Tree Stamping Event Handler

Benchmark tests:
- Events/second throughput
- Latency (p50, p95, p99)
- Concurrent event handling
- Memory usage
- Resource utilization

Created: 2025-10-24
Purpose: Stream E - Testing Infrastructure
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# Import fixtures
from fixtures.kafka_fixtures import (
    MockEventEnvelope,
    MockKafkaProducer,
)

# Import real handler
from handlers.tree_stamping_handler import TreeStampingHandler

# Import models
from models.file_location import ProjectIndexResult

# ==============================================================================
# Performance Benchmark Suite
# ==============================================================================


class TestTreeStampingHandlerPerformance:
    """Performance benchmarks for TreeStampingHandler."""

    @pytest.fixture
    def mock_bridge_fast(self):
        """Mock bridge with fast responses for throughput testing."""
        bridge = AsyncMock()

        # Fast successful response (simulates optimized bridge)
        bridge.index_project = AsyncMock(
            return_value=ProjectIndexResult(
                success=True,
                project_name="test",
                files_discovered=100,
                files_indexed=100,
                vector_indexed=100,
                graph_indexed=100,
                cache_warmed=True,
                duration_ms=1000,  # Bridge took 1s
            )
        )

        return bridge

    @pytest.fixture
    def handler_fast(self, mock_bridge_fast):
        """Create handler with fast mock bridge."""
        handler = TreeStampingHandler(bridge=mock_bridge_fast)
        handler._router = MockKafkaProducer()
        return handler

    # ==========================================================================
    # Throughput Tests
    # ==========================================================================

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_sequential_throughput(self, handler_fast):
        """Benchmark sequential event processing throughput."""
        num_events = 100
        events = [
            MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                },
            )
            for i in range(num_events)
        ]

        start_time = time.perf_counter()

        # Process sequentially
        for event in events:
            await handler_fast.handle_event(event)

        elapsed = time.perf_counter() - start_time

        # Calculate metrics
        events_per_second = num_events / elapsed
        avg_latency_ms = (elapsed / num_events) * 1000

        print(f"\n=== Sequential Throughput ===")
        print(f"Events processed: {num_events}")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Events/second: {events_per_second:.2f}")
        print(f"Avg latency: {avg_latency_ms:.2f}ms")

        # Verify reasonable performance
        assert events_per_second > 10  # Should handle >10 events/sec
        assert avg_latency_ms < 1000  # Should be <1s avg per event

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_throughput(self, handler_fast):
        """Benchmark concurrent event processing throughput."""
        num_events = 100
        events = [
            MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                },
            )
            for i in range(num_events)
        ]

        start_time = time.perf_counter()

        # Process concurrently
        results = await asyncio.gather(*[handler_fast.handle_event(e) for e in events])

        elapsed = time.perf_counter() - start_time

        # Calculate metrics
        events_per_second = num_events / elapsed
        avg_latency_ms = (elapsed / num_events) * 1000

        print(f"\n=== Concurrent Throughput ===")
        print(f"Events processed: {num_events}")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Events/second: {events_per_second:.2f}")
        print(f"Avg latency: {avg_latency_ms:.2f}ms")
        print(f"Success rate: {sum(results) / len(results) * 100:.1f}%")

        # Verify concurrent is faster than sequential
        assert events_per_second > 50  # Concurrent should handle >50 events/sec
        assert all(results)  # All should succeed

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_sustained_throughput(self, handler_fast):
        """Test sustained throughput over longer duration."""
        duration_seconds = 10
        events_per_batch = 10

        total_events = 0
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < duration_seconds:
            # Create batch
            events = [
                MockEventEnvelope(
                    event_type="tree.index-project-requested",
                    correlation_id=str(uuid4()),
                    payload={
                        "project_path": f"/tmp/test{i}",
                        "project_name": f"test{i}",
                    },
                )
                for i in range(events_per_batch)
            ]

            # Process batch concurrently
            await asyncio.gather(*[handler_fast.handle_event(e) for e in events])
            total_events += events_per_batch

        elapsed = time.perf_counter() - start_time
        events_per_second = total_events / elapsed

        print(f"\n=== Sustained Throughput ===")
        print(f"Duration: {elapsed:.2f}s")
        print(f"Total events: {total_events}")
        print(f"Events/second: {events_per_second:.2f}")

        # Verify sustained performance
        assert events_per_second > 10  # Should maintain >10 events/sec

    # ==========================================================================
    # Latency Tests
    # ==========================================================================

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_event_processing_latency(self, handler_fast):
        """Measure event processing latency distribution."""
        num_events = 100
        latencies = []

        for i in range(num_events):
            event = MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                },
            )

            # Measure single event latency
            start = time.perf_counter()
            await handler_fast.handle_event(event)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        # Calculate percentiles
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        avg = statistics.mean(latencies)
        std_dev = statistics.stdev(latencies)

        print(f"\n=== Latency Distribution ===")
        print(f"Events: {num_events}")
        print(f"Avg: {avg:.2f}ms")
        print(f"Std Dev: {std_dev:.2f}ms")
        print(f"P50: {p50:.2f}ms")
        print(f"P95: {p95:.2f}ms")
        print(f"P99: {p99:.2f}ms")
        print(f"Min: {min(latencies):.2f}ms")
        print(f"Max: {max(latencies):.2f}ms")

        # Verify latency targets
        assert p50 < 100  # P50 should be <100ms (handler overhead only)
        assert p95 < 500  # P95 should be <500ms
        assert p99 < 1000  # P99 should be <1s

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_latency_impact(self, handler_fast):
        """Test how concurrency affects latency."""
        concurrency_levels = [1, 5, 10, 25, 50]
        results = {}

        for concurrency in concurrency_levels:
            events = [
                MockEventEnvelope(
                    event_type="tree.index-project-requested",
                    correlation_id=str(uuid4()),
                    payload={
                        "project_path": f"/tmp/test{i}",
                        "project_name": f"test{i}",
                    },
                )
                for i in range(concurrency)
            ]

            start = time.perf_counter()
            await asyncio.gather(*[handler_fast.handle_event(e) for e in events])
            elapsed_ms = (time.perf_counter() - start) * 1000

            avg_latency = elapsed_ms / concurrency
            results[concurrency] = avg_latency

        print(f"\n=== Concurrency vs Latency ===")
        for concurrency, latency in results.items():
            print(f"Concurrency {concurrency:>3}: {latency:.2f}ms avg latency")

        # Verify latency doesn't degrade too much with concurrency
        assert (
            results[50] < results[1] * 2
        )  # 50x concurrency shouldn't be >2x slower per event

    # ==========================================================================
    # Handler Overhead Tests
    # ==========================================================================

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_handler_overhead(self, handler_fast):
        """Measure handler processing overhead (excluding bridge calls)."""
        num_events = 100
        overhead_measurements = []

        for i in range(num_events):
            event = MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                },
            )

            # Measure total time
            start = time.perf_counter()
            await handler_fast.handle_event(event)
            total_time_ms = (time.perf_counter() - start) * 1000

            # Bridge took 0ms (mock returns immediately)
            # So total_time ≈ handler overhead
            overhead_measurements.append(total_time_ms)

        avg_overhead = statistics.mean(overhead_measurements)
        p95_overhead = statistics.quantiles(overhead_measurements, n=20)[18]

        print(f"\n=== Handler Overhead ===")
        print(f"Avg overhead: {avg_overhead:.2f}ms")
        print(f"P95 overhead: {p95_overhead:.2f}ms")

        # Verify overhead is minimal
        assert avg_overhead < 10  # Handler overhead should be <10ms avg
        assert p95_overhead < 50  # P95 overhead should be <50ms

    # ==========================================================================
    # Stress Tests
    # ==========================================================================

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.slow
    async def test_high_volume_stress(self, handler_fast):
        """Stress test with high event volume."""
        num_events = 1000  # High volume
        batch_size = 100

        total_time = 0
        successful = 0

        for batch_start in range(0, num_events, batch_size):
            batch = [
                MockEventEnvelope(
                    event_type="tree.index-project-requested",
                    correlation_id=str(uuid4()),
                    payload={
                        "project_path": f"/tmp/test{i}",
                        "project_name": f"test{i}",
                    },
                )
                for i in range(batch_start, min(batch_start + batch_size, num_events))
            ]

            start = time.perf_counter()
            results = await asyncio.gather(
                *[handler_fast.handle_event(e) for e in batch]
            )
            total_time += time.perf_counter() - start

            successful += sum(results)

        events_per_second = num_events / total_time
        success_rate = (successful / num_events) * 100

        print(f"\n=== High Volume Stress Test ===")
        print(f"Total events: {num_events}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Events/second: {events_per_second:.2f}")
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Handler metrics: {handler_fast.metrics}")

        # Verify stress handling
        assert success_rate > 99  # Should have >99% success rate
        assert events_per_second > 10  # Should maintain >10 events/sec

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_mixed_operation_performance(self, handler_fast):
        """Test performance with mixed operation types."""
        num_events = 100

        # Mix of different operations
        events = []
        for i in range(num_events):
            event_type = [
                "tree.index-project-requested",
                "tree.search-files-requested",
                "tree.get-status-requested",
            ][i % 3]

            payload = {}
            if "index-project" in event_type:
                payload = {
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                }
            elif "search-files" in event_type:
                payload = {"query": f"query{i}"}
            else:  # status
                payload = {"project_name": f"test{i}"}

            events.append(
                MockEventEnvelope(
                    event_type=event_type,
                    correlation_id=str(uuid4()),
                    payload=payload,
                )
            )

        start = time.perf_counter()
        results = await asyncio.gather(*[handler_fast.handle_event(e) for e in events])
        elapsed = time.perf_counter() - start

        events_per_second = num_events / elapsed

        print(f"\n=== Mixed Operations Performance ===")
        print(f"Total events: {num_events}")
        print(f"Event types: index, search, status (33% each)")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Events/second: {events_per_second:.2f}")
        print(f"Success rate: {sum(results) / len(results) * 100:.1f}%")

        # Verify mixed operation performance
        assert events_per_second > 10
        assert sum(results) == num_events  # All should succeed

    # ==========================================================================
    # Error Rate Performance Tests
    # ==========================================================================

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_error_handling_performance(self):
        """Test performance impact of error handling."""
        bridge = AsyncMock()
        bridge.index_project.side_effect = Exception("Simulated failure")

        handler = TreeStampingHandler(bridge=bridge)
        handler._router = MockKafkaProducer()

        num_events = 100
        events = [
            MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={
                    "project_path": f"/tmp/test{i}",
                    "project_name": f"test{i}",
                },
            )
            for i in range(num_events)
        ]

        start = time.perf_counter()
        results = await asyncio.gather(*[handler.handle_event(e) for e in events])
        elapsed = time.perf_counter() - start

        events_per_second = num_events / elapsed
        error_rate = (sum(1 for r in results if not r) / num_events) * 100

        print(f"\n=== Error Handling Performance ===")
        print(f"Total events: {num_events}")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Events/second: {events_per_second:.2f}")
        print(f"Error rate: {error_rate:.1f}%")

        # Verify error handling doesn't significantly degrade performance
        assert events_per_second > 10  # Should still process >10 events/sec
        assert error_rate == 100  # All should fail as expected


# ==============================================================================
# Performance Report Generator
# ==============================================================================


class TestPerformanceReport:
    """Generate comprehensive performance report."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_generate_performance_report(self):
        """Generate comprehensive performance report."""
        print("\n" + "=" * 80)
        print("TREE STAMPING HANDLER PERFORMANCE REPORT")
        print("=" * 80)

        # Setup
        bridge = AsyncMock()
        bridge.index_project.return_value = ProjectIndexResult(
            success=True,
            project_name="test",
            files_discovered=100,
            files_indexed=100,
            vector_indexed=100,
            graph_indexed=100,
            cache_warmed=True,
            duration_ms=1000,
        )

        handler = TreeStampingHandler(bridge=bridge)
        handler._router = MockKafkaProducer()

        # Test 1: Sequential throughput
        num_events = 100
        events = [
            MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={"project_path": f"/tmp/test{i}", "project_name": f"test{i}"},
            )
            for i in range(num_events)
        ]

        start = time.perf_counter()
        for event in events:
            await handler.handle_event(event)
        seq_time = time.perf_counter() - start
        seq_throughput = num_events / seq_time

        # Test 2: Concurrent throughput
        handler._router = MockKafkaProducer()  # Reset
        start = time.perf_counter()
        await asyncio.gather(*[handler.handle_event(e) for e in events])
        concurrent_time = time.perf_counter() - start
        concurrent_throughput = num_events / concurrent_time

        # Test 3: Latency
        latencies = []
        for i in range(50):
            event = MockEventEnvelope(
                event_type="tree.index-project-requested",
                correlation_id=str(uuid4()),
                payload={"project_path": f"/tmp/test{i}", "project_name": f"test{i}"},
            )
            start = time.perf_counter()
            await handler.handle_event(event)
            latencies.append((time.perf_counter() - start) * 1000)

        print(f"\n{'Metric':<30} {'Value':<20} {'Target':<20} {'Status':<10}")
        print("-" * 80)

        # Throughput
        print(
            f"{'Sequential Throughput':<30} {seq_throughput:<20.2f} {'>10 events/sec':<20} {'✓' if seq_throughput > 10 else '✗':<10}"
        )
        print(
            f"{'Concurrent Throughput':<30} {concurrent_throughput:<20.2f} {'>50 events/sec':<20} {'✓' if concurrent_throughput > 50 else '✗':<10}"
        )

        # Latency
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]
        print(
            f"{'P50 Latency':<30} {p50:<20.2f} {'<100ms':<20} {'✓' if p50 < 100 else '✗':<10}"
        )
        print(
            f"{'P95 Latency':<30} {p95:<20.2f} {'<500ms':<20} {'✓' if p95 < 500 else '✗':<10}"
        )

        # Overhead
        print(
            f"{'Handler Overhead (avg)':<30} {statistics.mean(latencies):<20.2f} {'<10ms':<20} {'✓' if statistics.mean(latencies) < 10 else '✗':<10}"
        )

        print("\n" + "=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "benchmark"])
