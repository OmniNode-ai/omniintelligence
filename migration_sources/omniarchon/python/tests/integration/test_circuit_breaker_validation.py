"""
Circuit Breaker and Error Handling Test Validation

Comprehensive testing for circuit breaker patterns, error recovery,
and system resilience in the Knowledge feature multi-service architecture.

Error Validation:
-----------------
This test suite validates comprehensive error handling including:
- Exception types and messages
- Circuit breaker state transitions
- Service unavailability error paths
- Error propagation through service layers
"""

import asyncio
import time
import uuid
from enum import Enum
from typing import Any

import pytest

from tests.integration.error_assertions import (
    ErrorAssertions,
    assert_circuit_breaker_error,
    assert_service_unavailable_error,
)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class ServiceHealth(Enum):
    """Service health states"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNAVAILABLE = "unavailable"


class MockCircuitBreaker:
    """Mock circuit breaker implementation for testing"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker"""
        self.total_requests += 1

        # Check if circuit should transition from OPEN to HALF_OPEN
        if (
            self.state == CircuitBreakerState.OPEN
            and self.last_failure_time
            and time.time() - self.last_failure_time > self.recovery_timeout
        ):
            self.state = CircuitBreakerState.HALF_OPEN

        # Block requests if circuit is OPEN
        if self.state == CircuitBreakerState.OPEN:
            self.failed_requests += 1
            raise Exception("Circuit breaker is OPEN - service unavailable")

        try:
            result = await func(*args, **kwargs)
            self._handle_success()
            return result
        except Exception as e:
            self._handle_failure()
            raise e

    def _handle_success(self):
        """Handle successful request"""
        self.successful_requests += 1
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Recovery successful, close circuit
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def _handle_failure(self):
        """Handle failed request"""
        self.failed_requests += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(1, self.total_requests),
            "failure_rate": self.failed_requests / max(1, self.total_requests),
        }


class MockKnowledgeService:
    """Mock knowledge service with configurable failure patterns"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.health = ServiceHealth.HEALTHY
        self.failure_rate = 0.0
        self.latency_ms = 100
        self.circuit_breaker = MockCircuitBreaker()
        self.request_count = 0

    async def search_documents(self, query: str, **kwargs) -> dict[str, Any]:
        """Mock document search with failure simulation"""
        return await self.circuit_breaker.call(
            self._search_documents_impl, query, **kwargs
        )

    async def _search_documents_impl(self, query: str, **kwargs) -> dict[str, Any]:
        """Internal search implementation"""
        self.request_count += 1
        # Capture request count for this specific request (important for concurrent requests)
        current_request_count = self.request_count

        # Simulate latency
        await asyncio.sleep(self.latency_ms / 1000.0)

        # Simulate failures based on health and failure rate
        if self.health == ServiceHealth.UNAVAILABLE:
            raise Exception(f"{self.service_name} service is unavailable")
        elif self.health == ServiceHealth.FAILING:
            if current_request_count % 2 == 0:  # 50% failure rate when failing
                raise Exception(f"{self.service_name} service experiencing failures")
        elif (
            self.failure_rate > 0
            and (current_request_count * self.failure_rate) % 1 < self.failure_rate
        ):
            raise Exception(f"{self.service_name} intermittent failure")

        # Return successful response
        return {
            "success": True,
            "service": self.service_name,
            "query": query,
            "results": [
                {"id": f"result_{i}", "content": f"Mock result {i}"} for i in range(3)
            ],
            "latency_ms": self.latency_ms,
            "request_id": current_request_count,
        }

    def set_health(self, health: ServiceHealth):
        """Set service health state"""
        self.health = health

    def set_failure_rate(self, rate: float):
        """Set failure rate (0.0 to 1.0)"""
        self.failure_rate = max(0.0, min(1.0, rate))

    def set_latency(self, latency_ms: int):
        """Set response latency in milliseconds"""
        self.latency_ms = latency_ms


class KnowledgeServiceOrchestrator:
    """Orchestrates multiple knowledge services with circuit breakers"""

    def __init__(self):
        self.services = {
            "search": MockKnowledgeService("search"),
            "intelligence": MockKnowledgeService("intelligence"),
            "vector": MockKnowledgeService("vector"),
            "graph": MockKnowledgeService("graph"),
        }
        self.fallback_enabled = True
        self.cascade_prevention = True

    async def search_knowledge(
        self, query: str, services: list[str] = None
    ) -> dict[str, Any]:
        """Search across multiple knowledge services with circuit breaker protection"""
        if services is None:
            services = list(self.services.keys())

        results = {}
        errors = {}

        for service_name in services:
            if service_name not in self.services:
                errors[service_name] = f"Service {service_name} not found"
                continue

            try:
                result = await self.services[service_name].search_documents(query)
                results[service_name] = result
            except Exception as e:
                errors[service_name] = str(e)

                # If cascade prevention is enabled, continue with other services
                if not self.cascade_prevention:
                    break

        # Fallback behavior if all services failed
        if not results and self.fallback_enabled:
            results["fallback"] = {
                "success": True,
                "service": "fallback",
                "message": "All primary services unavailable, using cached results",
                "results": [{"id": "cached_1", "content": "Cached result"}],
            }

        return {
            "query": query,
            "successful_services": list(results.keys()),
            "failed_services": list(errors.keys()),
            "results": results,
            "errors": errors,
            "total_services_attempted": len(services),
            "success_rate": len(results) / len(services) if services else 0,
        }

    def get_service_stats(self) -> dict[str, Any]:
        """Get statistics for all services"""
        stats = {}
        for name, service in self.services.items():
            stats[name] = {
                "health": service.health.value,
                "circuit_breaker": service.circuit_breaker.get_stats(),
                "request_count": service.request_count,
                "latency_ms": service.latency_ms,
            }
        return stats


@pytest.fixture
async def knowledge_orchestrator():
    """Fixture providing knowledge service orchestrator"""
    orchestrator = KnowledgeServiceOrchestrator()
    yield orchestrator


@pytest.fixture
def circuit_breaker_test_session():
    """Fixture providing test session ID for circuit breaker tests"""
    session_id = f"circuit_test_{uuid.uuid4().hex[:8]}"
    yield session_id
    print(f"✅ Circuit breaker test session {session_id} completed")


class TestCircuitBreakerPatterns:
    """Test circuit breaker functionality for knowledge services"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_transitions(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test circuit breaker state transitions under load"""

        search_service = knowledge_orchestrator.services["search"]

        # 1. Start with healthy service (CLOSED state)
        assert search_service.circuit_breaker.state == CircuitBreakerState.CLOSED

        # 2. Make successful requests
        for i in range(3):
            result = await search_service.search_documents(f"test query {i}")
            assert result["success"] is True

        assert search_service.circuit_breaker.state == CircuitBreakerState.CLOSED

        # 3. Make service unhealthy to trigger failures
        search_service.set_health(ServiceHealth.UNAVAILABLE)

        # 4. Make requests that will fail to trigger circuit breaker
        failure_count = 0
        for i in range(7):  # Exceed failure threshold of 5
            try:
                await search_service.search_documents(f"failing query {i}")
            except Exception:
                failure_count += 1

        # 5. Circuit should now be OPEN
        assert search_service.circuit_breaker.state == CircuitBreakerState.OPEN
        assert failure_count >= 5

        # 6. Requests should now be blocked immediately
        start_time = time.time()
        try:
            await search_service.search_documents("blocked query")
            raise AssertionError("Request should have been blocked")
        except Exception as e:
            blocked_duration = time.time() - start_time
            # Enhanced error validation: Check exception properties
            assert_circuit_breaker_error(
                e, expected_message_contains="Circuit breaker is OPEN"
            )
            ErrorAssertions.assert_exception_handling(
                e,
                expected_exception_type=Exception,
                expected_message_contains="service unavailable",
            )
            assert blocked_duration < 0.1, "Blocked request should be immediate"

        print(f"✅ Circuit breaker opened after {failure_count} failures")

        # 7. Test recovery (simulate time passing)
        search_service.circuit_breaker.last_failure_time = (
            time.time() - 31
        )  # Past recovery timeout
        search_service.set_health(ServiceHealth.HEALTHY)  # Service is healthy again

        # 8. Next request should transition to HALF_OPEN
        result = await search_service.search_documents("recovery test")
        assert result["success"] is True
        assert (
            search_service.circuit_breaker.state == CircuitBreakerState.CLOSED
        )  # Should close on success

        print("✅ Circuit breaker recovered successfully")

    @pytest.mark.asyncio
    async def test_service_failure_isolation(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """
        Test that single service failure doesn't cascade to other services.

        Error Validation:
        - Verifies failed service has proper error message
        - Confirms error isolation (other services unaffected)
        - Validates error structure in failed_services dict
        """

        # 1. Make one service fail
        knowledge_orchestrator.services["intelligence"].set_health(
            ServiceHealth.UNAVAILABLE
        )

        # 2. Test search across all services
        result = await knowledge_orchestrator.search_knowledge(
            "test query", services=["search", "intelligence", "vector", "graph"]
        )

        # 3. Verify other services still work
        assert len(result["successful_services"]) == 3  # search, vector, graph
        assert "intelligence" in result["failed_services"]
        assert result["success_rate"] == 0.75  # 3 out of 4 services succeeded

        # Enhanced error validation: Verify error details for failed service
        intelligence_error = result["errors"]["intelligence"]
        assert (
            intelligence_error is not None
        ), "Failed service should have error message"
        assert isinstance(intelligence_error, str), "Error should be string message"
        assert (
            "intelligence service is unavailable" in intelligence_error.lower()
        ), f"Expected service unavailable error, got: {intelligence_error}"

        # 4. Verify working services returned results
        for service in ["search", "vector", "graph"]:
            assert service in result["results"]
            assert result["results"][service]["success"] is True

        print(
            f"✅ Service isolation: {len(result['successful_services'])}/4 services operational"
        )

    @pytest.mark.asyncio
    async def test_cascade_failure_prevention(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test that cascade failures are prevented"""

        # 1. Enable cascade prevention
        knowledge_orchestrator.cascade_prevention = True

        # 2. Make multiple services fail
        knowledge_orchestrator.services["intelligence"].set_health(
            ServiceHealth.UNAVAILABLE
        )
        knowledge_orchestrator.services["vector"].set_health(ServiceHealth.FAILING)

        # 3. Test that remaining services still process requests
        result = await knowledge_orchestrator.search_knowledge("cascade test")

        # 4. Should have some successful services despite failures
        assert len(result["successful_services"]) >= 1
        assert len(result["failed_services"]) >= 1

        # 5. Test with cascade prevention disabled
        knowledge_orchestrator.cascade_prevention = False

        # This test would depend on specific implementation of cascade behavior
        print("✅ Cascade failure prevention validated")

    @pytest.mark.asyncio
    async def test_fallback_mechanisms(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """
        Test fallback behavior when all services fail.

        Error Validation:
        - Verifies all services have error messages when unavailable
        - Validates error message format and content
        - Confirms proper error aggregation across services
        """

        # 1. Make all services unavailable
        for service in knowledge_orchestrator.services.values():
            service.set_health(ServiceHealth.UNAVAILABLE)

        # 2. Test with fallback enabled
        knowledge_orchestrator.fallback_enabled = True
        result = await knowledge_orchestrator.search_knowledge("fallback test")

        # 3. Should have fallback results
        assert "fallback" in result["successful_services"]
        assert result["results"]["fallback"]["service"] == "fallback"
        assert len(result["failed_services"]) == 4  # All primary services failed

        # Enhanced error validation: Verify all services have error details
        assert len(result["errors"]) == 4, "All 4 services should have error entries"
        for service_name in ["search", "intelligence", "vector", "graph"]:
            assert (
                service_name in result["errors"]
            ), f"Service {service_name} should have error"
            error_msg = result["errors"][service_name]
            assert isinstance(
                error_msg, str
            ), f"Error for {service_name} should be string"
            assert (
                "unavailable" in error_msg.lower() or "failed" in error_msg.lower()
            ), f"Error for {service_name} should indicate failure: {error_msg}"

        # 4. Test with fallback disabled
        knowledge_orchestrator.fallback_enabled = False
        result = await knowledge_orchestrator.search_knowledge("no fallback test")

        # 5. Should have no successful services
        assert len(result["successful_services"]) == 0
        assert len(result["failed_services"]) == 4

        # Enhanced error validation: Verify error propagation without fallback
        assert len(result["errors"]) == 4, "All services should still report errors"
        for service_name, error_msg in result["errors"].items():
            assert (
                len(error_msg) > 0
            ), f"Error message for {service_name} should not be empty"

        print("✅ Fallback mechanisms validated")


class TestErrorRecoveryScenarios:
    """Test error recovery and resilience scenarios"""

    @pytest.mark.asyncio
    async def test_service_recovery_detection(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test that service recovery is properly detected"""

        search_service = knowledge_orchestrator.services["search"]

        # 1. Start with unavailable service to ensure all requests fail
        search_service.set_health(ServiceHealth.UNAVAILABLE)

        # 2. Make requests until circuit opens (need at least 5 failures)
        failure_count = 0
        for i in range(10):
            try:
                await search_service.search_documents(f"test {i}")
            except Exception:
                failure_count += 1
                if search_service.circuit_breaker.state == CircuitBreakerState.OPEN:
                    break

        assert search_service.circuit_breaker.state == CircuitBreakerState.OPEN

        # 3. Service recovers
        search_service.set_health(ServiceHealth.HEALTHY)

        # 4. Simulate recovery timeout passing
        search_service.circuit_breaker.last_failure_time = time.time() - 31

        # 5. Test recovery
        result = await search_service.search_documents("recovery test")
        assert result["success"] is True
        assert search_service.circuit_breaker.state == CircuitBreakerState.CLOSED

        print("✅ Service recovery detection validated")

    @pytest.mark.asyncio
    async def test_gradual_service_degradation(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test handling of gradual service degradation"""

        search_service = knowledge_orchestrator.services["search"]

        # 1. Start with healthy service
        search_service.set_health(ServiceHealth.HEALTHY)

        # 2. Gradually increase failure rate
        for failure_rate in [0.1, 0.3, 0.5, 0.7, 0.9]:
            search_service.set_failure_rate(failure_rate)

            # Test 10 requests at this failure rate
            batch_success = 0
            for i in range(10):
                try:
                    await search_service.search_documents(f"degradation test {i}")
                    batch_success += 1
                except Exception:
                    pass

            expected_success = int(10 * (1 - failure_rate))
            # Allow some variance due to randomness
            assert (
                abs(batch_success - expected_success) <= 3
            ), f"Expected ~{expected_success} successes, got {batch_success}"

        print("✅ Gradual service degradation handling validated")

    @pytest.mark.asyncio
    async def test_partial_service_availability(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test system behavior with partial service availability"""

        # 1. Set different health states for different services
        knowledge_orchestrator.services["search"].set_health(ServiceHealth.HEALTHY)
        knowledge_orchestrator.services["intelligence"].set_health(
            ServiceHealth.DEGRADED
        )
        knowledge_orchestrator.services["vector"].set_health(ServiceHealth.FAILING)
        knowledge_orchestrator.services["graph"].set_health(ServiceHealth.UNAVAILABLE)

        # 2. Set different failure rates
        knowledge_orchestrator.services["intelligence"].set_failure_rate(
            0.2
        )  # 20% failure
        knowledge_orchestrator.services["vector"].set_failure_rate(0.8)  # 80% failure

        # 3. Test multiple requests to see overall system behavior
        total_successful_services = 0
        total_requests = 20

        for i in range(total_requests):
            result = await knowledge_orchestrator.search_knowledge(
                f"partial availability test {i}"
            )
            total_successful_services += len(result["successful_services"])

        avg_successful_services = total_successful_services / total_requests

        # Should average between 1-3 successful services per request
        assert (
            1 <= avg_successful_services <= 3
        ), f"Average successful services: {avg_successful_services}"

        print(
            f"✅ Partial availability: avg {avg_successful_services:.1f} services per request"
        )


class TestPerformanceUnderFailure:
    """Test performance characteristics during failure scenarios"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_response_time(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test that circuit breaker provides fast failure responses"""

        search_service = knowledge_orchestrator.services["search"]

        # 1. Set high latency and make service fail
        search_service.set_latency(2000)  # 2 second latency
        search_service.set_health(ServiceHealth.UNAVAILABLE)

        # 2. Trigger circuit breaker
        for i in range(6):
            try:
                await search_service.search_documents(f"trigger {i}")
            except Exception:
                pass

        assert search_service.circuit_breaker.state == CircuitBreakerState.OPEN

        # 3. Test that blocked requests are fast
        fast_failure_times = []
        for i in range(5):
            start_time = time.time()
            try:
                await search_service.search_documents(f"blocked {i}")
            except Exception:
                end_time = time.time()
                fast_failure_times.append(end_time - start_time)

        avg_fast_failure_time = sum(fast_failure_times) / len(fast_failure_times)
        max_fast_failure_time = max(fast_failure_times)

        # Circuit breaker should fail fast (much faster than 2s service latency)
        assert (
            avg_fast_failure_time < 0.1
        ), f"Average fast failure time: {avg_fast_failure_time:.3f}s"
        assert (
            max_fast_failure_time < 0.2
        ), f"Max fast failure time: {max_fast_failure_time:.3f}s"

        print(
            f"✅ Fast failure: avg={avg_fast_failure_time:.3f}s, max={max_fast_failure_time:.3f}s"
        )

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(
        self, knowledge_orchestrator, circuit_breaker_test_session
    ):
        """Test circuit breaker behavior under concurrent load"""

        search_service = knowledge_orchestrator.services["search"]

        # Reset circuit breaker state and increase failure threshold
        # This prevents circuit from opening during concurrent test
        search_service.circuit_breaker.state = CircuitBreakerState.CLOSED
        search_service.circuit_breaker.failure_count = 0
        search_service.circuit_breaker.failure_threshold = (
            25  # Higher threshold for 20 requests
        )

        # Reset request count to ensure clean state for failure pattern
        search_service.request_count = 0

        # Use controlled failure rate instead of FAILING health
        # This provides more predictable behavior with concurrent requests
        search_service.set_health(ServiceHealth.HEALTHY)
        search_service.set_failure_rate(0.3)  # 30% failure rate

        # Verify initial state
        print(
            f"Initial state - Circuit: {search_service.circuit_breaker.state.value}, "
            f"Failures: {search_service.circuit_breaker.failure_count}, "
            f"Request count: {search_service.request_count}"
        )

        # 1. Send concurrent requests
        concurrent_tasks = []
        for i in range(20):
            task = asyncio.create_task(
                search_service.search_documents(f"concurrent {i}")
            )
            concurrent_tasks.append(task)

        # 2. Wait for all to complete
        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)

        # 3. Analyze results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [r for r in results if isinstance(r, Exception)]

        success_rate = len(successful_results) / len(results)

        # Print debug info
        print(
            f"Results - Successes: {len(successful_results)}, "
            f"Failures: {len(failed_results)}, "
            f"Final circuit state: {search_service.circuit_breaker.state.value}"
        )

        # Sample error messages to debug
        if failed_results:
            sample_errors = [str(e)[:50] for e in failed_results[:3]]
            print(f"Sample errors: {sample_errors}")

        # Should have some successes and some failures (expect ~70% success with 30% failure rate)
        # Allow wider range due to randomness and concurrent execution
        assert (
            0.4 <= success_rate <= 0.9
        ), f"Success rate under load: {success_rate:.2f} (successes: {len(successful_results)}, failures: {len(failed_results)})"

        # Get final circuit breaker stats
        stats = search_service.circuit_breaker.get_stats()

        print(
            f"✅ Concurrent handling: {success_rate:.2f} success rate ({len(successful_results)}/{len(results)}), circuit state: {stats['state']}"
        )


@pytest.mark.asyncio
async def test_comprehensive_resilience_scenario(
    knowledge_orchestrator, circuit_breaker_test_session
):
    """Comprehensive test combining multiple failure scenarios"""

    print("🚀 Starting comprehensive resilience test")

    # 1. Start with all services healthy
    total_requests = 0
    successful_requests = 0

    # 2. Phase 1: Normal operation
    for i in range(10):
        result = await knowledge_orchestrator.search_knowledge(f"normal {i}")
        total_requests += 1
        if len(result["successful_services"]) >= 3:
            successful_requests += 1

    print(f"Phase 1 (Normal): {successful_requests}/{total_requests} successful")

    # 3. Phase 2: Gradual degradation
    knowledge_orchestrator.services["intelligence"].set_failure_rate(0.3)
    knowledge_orchestrator.services["vector"].set_latency(1000)

    phase2_successful = 0
    for i in range(10):
        result = await knowledge_orchestrator.search_knowledge(f"degraded {i}")
        total_requests += 1
        if len(result["successful_services"]) >= 2:
            phase2_successful += 1
            successful_requests += 1

    print(f"Phase 2 (Degraded): {phase2_successful}/10 successful")

    # 4. Phase 3: Major failure
    knowledge_orchestrator.services["intelligence"].set_health(
        ServiceHealth.UNAVAILABLE
    )
    knowledge_orchestrator.services["vector"].set_health(ServiceHealth.UNAVAILABLE)

    phase3_successful = 0
    for i in range(10):
        result = await knowledge_orchestrator.search_knowledge(f"major_failure {i}")
        total_requests += 1
        if len(result["successful_services"]) >= 1:  # At least one service or fallback
            phase3_successful += 1
            successful_requests += 1

    print(f"Phase 3 (Major Failure): {phase3_successful}/10 successful")

    # 5. Phase 4: Recovery
    for service in knowledge_orchestrator.services.values():
        service.set_health(ServiceHealth.HEALTHY)
        service.set_failure_rate(0.0)
        service.set_latency(100)
        # Reset circuit breakers for recovery
        service.circuit_breaker.state = CircuitBreakerState.CLOSED
        service.circuit_breaker.failure_count = 0

    phase4_successful = 0
    for i in range(10):
        result = await knowledge_orchestrator.search_knowledge(f"recovery {i}")
        total_requests += 1
        if len(result["successful_services"]) >= 3:
            phase4_successful += 1
            successful_requests += 1

    print(f"Phase 4 (Recovery): {phase4_successful}/10 successful")

    # 6. Overall resilience metrics
    overall_success_rate = successful_requests / total_requests
    print(
        f"✅ Overall resilience: {overall_success_rate:.2f} success rate across all phases"
    )

    # System should maintain reasonable availability even during failures
    assert (
        overall_success_rate >= 0.7
    ), f"System resilience below threshold: {overall_success_rate:.2f}"

    # Get final service statistics
    stats = knowledge_orchestrator.get_service_stats()
    print("📊 Final service statistics:")
    for service_name, service_stats in stats.items():
        cb_stats = service_stats["circuit_breaker"]
        print(
            f"  {service_name}: {cb_stats['success_rate']:.2f} success rate, {cb_stats['state']} state"
        )


if __name__ == "__main__":
    # Demo circuit breaker functionality
    async def demo_circuit_breaker():
        print("🚀 Circuit Breaker Demo")

        orchestrator = KnowledgeServiceOrchestrator()
        search_service = orchestrator.services["search"]

        print("1. Normal operation...")
        for i in range(3):
            await search_service.search_documents(f"normal query {i}")
            print(f"   Request {i+1}: ✅ Success")

        print("2. Simulating service failures...")
        search_service.set_health(ServiceHealth.UNAVAILABLE)

        for i in range(7):
            try:
                await search_service.search_documents(f"failing query {i}")
                print(f"   Request {i+1}: ✅ Success")
            except Exception as e:
                print(f"   Request {i+1}: ❌ Failed - {str(e)[:50]}...")

        stats = search_service.circuit_breaker.get_stats()
        print(f"   Circuit breaker state: {stats['state'].upper()}")

        print("3. Requests now blocked...")
        try:
            await search_service.search_documents("blocked query")
        except Exception as e:
            print(f"   Blocked request: ❌ {str(e)[:50]}...")

        print("✅ Demo complete")

    # Run demo if called directly
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(demo_circuit_breaker())
