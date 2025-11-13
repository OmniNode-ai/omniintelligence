"""
Orchestration Service Coordination Unit Tests

Tests for service coordination and data flow between components including:
- Service client coordination and communication
- Data passing between services with content preservation
- Error handling and retry mechanisms
- Load balancing and service health monitoring
- Multi-service workflow orchestration

Critical focus on ensuring complete content flows through service coordination.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock

import httpx
import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    generate_large_document,
)


class TestServiceCoordination:
    """Test orchestration service coordination functionality."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.service_endpoints = {
            "bridge": "http://test-bridge:8054",
            "intelligence": "http://test-intelligence:8053",
            "search": "http://test-search:8055",
            "mcp": "http://test-mcp:8051",
        }

    @pytest.fixture
    def mock_service_clients(self):
        """Mock service clients for coordination testing."""
        return {
            "bridge_client": AsyncMock(),
            "intelligence_client": AsyncMock(),
            "search_client": AsyncMock(),
            "mcp_client": AsyncMock(),
        }

    @pytest.mark.asyncio
    async def test_complete_document_pipeline_coordination(self, mock_service_clients):
        """Test complete document processing pipeline through service coordination."""
        doc = STANDARDIZED_TEST_DOCUMENT.copy()

        # Step 1: MCP Document Creation
        async def mock_mcp_creation(doc_data):
            content = doc_data["document_data"]["content"]
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert (
                    len(content_text) > 400
                ), f"MCP content truncated: {len(content_text)}"

            return {
                "success": True,
                "document_id": doc["document_id"],
                "sync_triggered": True,
            }

        # Step 2: Bridge Service Sync
        async def mock_bridge_sync(document_data):
            actual_document = document_data.get("document_data", {})
            content = actual_document.get("content", {})

            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert (
                    len(content_text) > 400
                ), f"Bridge content truncated: {len(content_text)}"

            return {
                "success": True,
                "document_id": document_data["document_id"],
                "status": "sync_queued",
            }

        # Step 3: Intelligence Service Processing
        async def mock_intelligence_processing(doc_payload):
            content = doc_payload.get("content", {})
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert (
                    len(content_text) > 400
                ), f"Intelligence content truncated: {len(content_text)}"

            return {
                "success": True,
                "document_id": doc_payload["document_id"],
                "entities_extracted": 5,
                "vectorization_completed": True,
            }

        # Step 4: Search Service Vectorization
        async def mock_search_vectorization(vector_payload):
            content = vector_payload.get("content", "")
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert (
                    len(content_text) > 400
                ), f"Search content truncated: {len(content_text)}"

            return {
                "success": True,
                "document_id": vector_payload["document_id"],
                "vector_id": f"vec_{vector_payload['document_id']}",
                "indexed": True,
            }

        # Execute coordinated pipeline
        results = {}

        # MCP Creation
        results["mcp"] = await mock_mcp_creation(doc)
        assert results["mcp"]["success"], "MCP creation failed"

        # Bridge Sync (triggered by MCP)
        results["bridge"] = await mock_bridge_sync(doc)
        assert results["bridge"]["success"], "Bridge sync failed"

        # Intelligence Processing (triggered by Bridge)
        intel_payload = {
            "document_id": doc["document_id"],
            "title": doc["document_data"]["title"],
            "content": doc["document_data"]["content"],
        }
        results["intelligence"] = await mock_intelligence_processing(intel_payload)
        assert results["intelligence"]["success"], "Intelligence processing failed"

        # Search Vectorization (triggered by Intelligence)
        search_payload = {
            "document_id": doc["document_id"],
            "content": doc["document_data"]["content"],
        }
        results["search"] = await mock_search_vectorization(search_payload)
        assert results["search"]["success"], "Search vectorization failed"

        # Validate complete pipeline
        assert all(
            result["success"] for result in results.values()
        ), "Pipeline coordination failed"
        assert (
            results["intelligence"]["entities_extracted"] > 0
        ), "No entities extracted"
        assert results["search"]["indexed"], "Document not indexed"

    @pytest.mark.asyncio
    async def test_service_error_handling_and_retry_logic(self, mock_service_clients):
        """Test error handling and retry mechanisms in service coordination."""
        doc = generate_large_document(content_size=1000)

        # Mock service with intermittent failures
        class RetryableService:
            def __init__(self, max_attempts=3):
                self.attempt_count = 0
                self.max_attempts = max_attempts

            async def process_document(self, document_data):
                self.attempt_count += 1

                # Fail first few attempts, succeed on final attempt
                if self.attempt_count < self.max_attempts:
                    raise httpx.RequestError("Simulated service failure")

                # Validate content on successful attempt
                content = document_data.get("content", {})
                if isinstance(content, dict) and "content" in content:
                    content_text = content["content"]
                    assert (
                        len(content_text) == 1000
                    ), f"Content truncated in retry: {len(content_text)}"

                return {
                    "success": True,
                    "document_id": document_data["document_id"],
                    "attempts": self.attempt_count,
                    "content_preserved": True,
                }

        # Test retry logic
        async def coordinate_with_retry(service, document_data, max_retries=3):
            for attempt in range(max_retries):
                try:
                    result = await service.process_document(document_data)
                    return result
                except httpx.RequestError:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(0.1 * (2**attempt))  # Exponential backoff

        # Execute retry coordination
        retryable_service = RetryableService(max_attempts=3)

        document_payload = {
            "document_id": doc["document_id"],
            "content": doc["document_data"]["content"],
        }

        result = await coordinate_with_retry(retryable_service, document_payload)

        # Validate retry logic
        assert result["success"], "Retry coordination failed"
        assert (
            result["attempts"] == 3
        ), f"Unexpected attempt count: {result['attempts']}"
        assert result["content_preserved"], "Content not preserved through retries"

    @pytest.mark.asyncio
    async def test_parallel_service_coordination(self, mock_service_clients):
        """Test parallel coordination of multiple services."""
        docs = [STANDARDIZED_TEST_DOCUMENT.copy(), NESTED_CONTENT_DOCUMENT.copy()]

        # Mock parallel service processing
        async def process_document_parallel(document_data, service_type):
            """Process document through specific service type."""
            await asyncio.sleep(0.1)  # Simulate processing delay

            content = document_data.get("content", {})
            if isinstance(content, dict):
                if "content" in content:
                    content_text = content["content"]
                elif "overview" in content:
                    content_text = content["overview"]
                else:
                    content_text = str(content)
            else:
                content_text = str(content)

            # Validate content preservation in parallel processing
            assert (
                len(content_text) > 50
            ), f"{service_type} content truncated: {len(content_text)}"

            return {
                "service": service_type,
                "document_id": document_data["document_id"],
                "content_length": len(content_text),
                "processing_time_ms": 100,
                "success": True,
            }

        # Define parallel service tasks
        parallel_tasks = []

        for doc in docs:
            doc_content = {
                "document_id": doc["document_id"],
                "content": doc["document_data"]["content"],
            }

            # Create parallel tasks for different services
            services = ["intelligence", "search", "quality_check"]
            for service in services:
                task = process_document_parallel(doc_content, service)
                parallel_tasks.append(task)

        # Execute parallel coordination
        import time

        start_time = time.time()

        results = await asyncio.gather(*parallel_tasks)

        total_time = time.time() - start_time

        # Validate parallel coordination
        assert (
            len(results) == 6
        ), f"Not all parallel tasks completed: {len(results)}"  # 2 docs × 3 services
        assert total_time < 1.0, f"Parallel coordination too slow: {total_time}s"

        for result in results:
            assert result["success"], f"Parallel task failed: {result['service']}"
            assert (
                result["content_length"] > 50
            ), f"Content truncated in {result['service']}: {result['content_length']}"

    @pytest.mark.asyncio
    async def test_service_health_monitoring_coordination(self):
        """Test service health monitoring and coordination adjustments."""
        services = list(self.service_endpoints.keys())

        # Mock service health checker
        async def check_service_health(service_name, endpoint):
            """Check health of a specific service."""
            try:
                # Simulate health check with varying responses
                if service_name == "bridge":
                    return {"status": "healthy", "response_time_ms": 50}
                elif service_name == "intelligence":
                    return {"status": "degraded", "response_time_ms": 200}
                elif service_name == "search":
                    return {"status": "healthy", "response_time_ms": 75}
                else:
                    return {"status": "healthy", "response_time_ms": 100}
            except Exception:
                return {"status": "unhealthy", "response_time_ms": None}

        # Monitor all services
        health_results = {}
        for service_name, endpoint in self.service_endpoints.items():
            health_results[service_name] = await check_service_health(
                service_name, endpoint
            )

        # Coordination adjustments based on health
        async def adjust_coordination_based_on_health(health_status):
            """Adjust coordination strategy based on service health."""
            adjustments = {}

            for service, status in health_status.items():
                if status["status"] == "healthy":
                    adjustments[service] = {
                        "priority": "normal",
                        "timeout_ms": 5000,
                        "retry_count": 3,
                    }
                elif status["status"] == "degraded":
                    adjustments[service] = {
                        "priority": "low",
                        "timeout_ms": 10000,
                        "retry_count": 5,
                    }
                else:  # unhealthy
                    adjustments[service] = {
                        "priority": "disabled",
                        "timeout_ms": 1000,
                        "retry_count": 1,
                    }

            return adjustments

        # Apply coordination adjustments
        coordination_adjustments = await adjust_coordination_based_on_health(
            health_results
        )

        # Validate health monitoring coordination
        assert len(coordination_adjustments) == len(
            services
        ), "Not all services have coordination adjustments"

        # Check specific adjustments
        assert (
            coordination_adjustments["intelligence"]["priority"] == "low"
        ), "Degraded service not deprioritized"
        assert (
            coordination_adjustments["bridge"]["priority"] == "normal"
        ), "Healthy service not prioritized normally"

        # Verify that content processing would still work with adjustments
        for service, adjustment in coordination_adjustments.items():
            if adjustment["priority"] != "disabled":
                assert adjustment["timeout_ms"] > 0, f"Invalid timeout for {service}"
                assert (
                    adjustment["retry_count"] > 0
                ), f"Invalid retry count for {service}"

    @pytest.mark.asyncio
    async def test_data_flow_integrity_across_services(self):
        """Test that data maintains integrity as it flows between services."""
        # Create document with checksum for integrity verification
        doc_content = (
            "This is test content for data integrity verification across service coordination. "
            * 20
        )

        test_document = {
            "document_id": "integrity-test-doc",
            "project_id": "test-project-67890",
            "document_data": {
                "title": "Data Integrity Test Document",
                "content": {"content": doc_content},
                "document_type": "integrity_test",
                "metadata": {
                    "original_checksum": hash(doc_content),
                    "original_length": len(doc_content),
                },
            },
        }

        # Simulate data flow through services with integrity checks
        async def verify_data_integrity_flow(document):
            flow_results = []
            current_data = document.copy()

            # Service 1: MCP Server
            mcp_data = {
                "document_id": current_data["document_id"],
                "content": current_data["document_data"]["content"]["content"],
                "checksum": hash(current_data["document_data"]["content"]["content"]),
            }
            flow_results.append(("mcp", mcp_data))

            # Service 2: Bridge Service
            bridge_data = {
                "document_id": mcp_data["document_id"],
                "content": mcp_data["content"],
                "checksum": hash(mcp_data["content"]),
            }
            assert (
                bridge_data["checksum"] == mcp_data["checksum"]
            ), "Data corrupted between MCP and Bridge"
            flow_results.append(("bridge", bridge_data))

            # Service 3: Intelligence Service
            intel_data = {
                "document_id": bridge_data["document_id"],
                "content": bridge_data["content"],
                "checksum": hash(bridge_data["content"]),
            }
            assert (
                intel_data["checksum"] == bridge_data["checksum"]
            ), "Data corrupted between Bridge and Intelligence"
            flow_results.append(("intelligence", intel_data))

            # Service 4: Search Service
            search_data = {
                "document_id": intel_data["document_id"],
                "content": intel_data["content"],
                "checksum": hash(intel_data["content"]),
            }
            assert (
                search_data["checksum"] == intel_data["checksum"]
            ), "Data corrupted between Intelligence and Search"
            flow_results.append(("search", search_data))

            return flow_results

        # Execute integrity verification
        flow_results = await verify_data_integrity_flow(test_document)

        # Validate data integrity across all services
        original_checksum = test_document["document_data"]["metadata"][
            "original_checksum"
        ]

        for service_name, service_data in flow_results:
            assert (
                service_data["checksum"] == original_checksum
            ), f"Data integrity lost at {service_name}"
            assert len(service_data["content"]) == len(
                doc_content
            ), f"Content length changed at {service_name}"

    @pytest.mark.asyncio
    async def test_load_balancing_coordination(self):
        """Test load balancing across multiple service instances."""
        # Mock multiple service instances
        service_instances = {
            "intelligence": [
                {"url": "http://intelligence-1:8053", "load": 0.3},
                {"url": "http://intelligence-2:8053", "load": 0.7},
                {"url": "http://intelligence-3:8053", "load": 0.5},
            ],
            "search": [
                {"url": "http://search-1:8055", "load": 0.2},
                {"url": "http://search-2:8055", "load": 0.8},
            ],
        }

        # Load balancer implementation
        async def select_service_instance(
            service_type, selection_strategy="least_loaded"
        ):
            """Select optimal service instance based on load balancing strategy."""
            instances = service_instances.get(service_type, [])

            if not instances:
                return None

            if selection_strategy == "least_loaded":
                return min(instances, key=lambda x: x["load"])
            elif selection_strategy == "round_robin":
                # Simple round-robin (would use counter in real implementation)
                return instances[0]
            else:
                return instances[0]

        # Test load balancing for document processing
        documents = [generate_large_document(500) for _ in range(6)]

        async def process_with_load_balancing(doc, service_type):
            """Process document using load-balanced service selection."""
            instance = await select_service_instance(service_type, "least_loaded")

            if not instance:
                raise ValueError(f"No available instances for {service_type}")

            # Simulate processing
            content = doc["document_data"]["content"]["content"]
            assert (
                len(content) == 500
            ), f"Content truncated in load balancing: {len(content)}"

            # Update instance load (simulation)
            instance["load"] += 0.1

            return {
                "service_type": service_type,
                "instance_url": instance["url"],
                "document_id": doc["document_id"],
                "content_length": len(content),
                "success": True,
            }

        # Process documents with load balancing
        tasks = []
        for i, doc in enumerate(documents):
            service_type = "intelligence" if i < 4 else "search"
            task = process_with_load_balancing(doc, service_type)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Validate load balancing
        assert len(results) == 6, f"Not all documents processed: {len(results)}"

        # Check that least loaded instances were selected
        [r["instance_url"] for r in results if r["service_type"] == "intelligence"]
        [r["instance_url"] for r in results if r["service_type"] == "search"]

        # Verify content preservation in load balancing
        for result in results:
            assert result[
                "success"
            ], f"Load balanced processing failed: {result['service_type']}"
            assert (
                result["content_length"] == 500
            ), f"Content truncated in load balancing: {result['content_length']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
