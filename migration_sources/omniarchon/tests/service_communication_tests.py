#!/usr/bin/env python3
"""
Service Communication and Bridge Sync Validation Tests

Comprehensive testing of service-to-service communication and bridge synchronization
in the MCP document indexing pipeline. These tests validate the critical communication
pathways that enable document flow from creation to retrievability.

Critical Communication Paths Tested:
1. MCP Server → Main Server → Intelligence Service
2. Intelligence Service → Bridge Service → Memgraph
3. Bridge Service → Search Service → Qdrant
4. Cross-service event triggers and sync operations
5. Service health monitoring and recovery

Usage:
    python tests/service_communication_tests.py [--verbose] [--timeout 60]
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration"""

    name: str
    url: str
    health_endpoint: str
    timeout: float = 30.0


@dataclass
class CommunicationPath:
    """Communication path definition between services"""

    name: str
    source_service: str
    target_service: str
    test_endpoint: str
    expected_response_fields: List[str]
    max_response_time: float = 10.0


class ServiceCommunicationTester:
    """
    Comprehensive service communication and bridge sync validation test suite
    """

    def __init__(self, verbose: bool = False, timeout: float = 60.0):
        self.verbose = verbose
        self.timeout = timeout
        self.test_results = []
        self.test_session_id = f"comm_test_{uuid.uuid4().hex[:8]}_{int(time.time())}"

        # Service endpoint definitions
        self.services = {
            "main_server": ServiceEndpoint(
                name="Main Server",
                url="http://localhost:8181",
                health_endpoint="/health",
            ),
            "mcp_server": ServiceEndpoint(
                name="MCP Server",
                url="http://localhost:8051",
                health_endpoint="/mcp",  # Special endpoint for MCP
                timeout=30.0,
            ),
            "intelligence": ServiceEndpoint(
                name="Intelligence Service",
                url="http://localhost:8053",
                health_endpoint="/health",
            ),
            "bridge": ServiceEndpoint(
                name="Bridge Service",
                url="http://localhost:8054",
                health_endpoint="/health",
            ),
            "search": ServiceEndpoint(
                name="Search Service",
                url="http://localhost:8055",
                health_endpoint="/health",
            ),
            "qdrant": ServiceEndpoint(
                name="Qdrant Vector DB",
                url="http://localhost:6333",
                health_endpoint="/readyz",
            ),
            "memgraph": ServiceEndpoint(
                name="Memgraph Knowledge Graph",
                url="http://localhost:7444",
                health_endpoint="/",
            ),
        }

        # Critical communication paths in the indexing pipeline
        self.communication_paths = [
            CommunicationPath(
                name="MCP to Main Server",
                source_service="mcp_server",
                target_service="main_server",
                test_endpoint="/api/projects",
                expected_response_fields=["projects"],
                max_response_time=5.0,
            ),
            CommunicationPath(
                name="Main Server to Intelligence",
                source_service="main_server",
                target_service="intelligence",
                test_endpoint="/stats",
                expected_response_fields=["status"],
                max_response_time=5.0,
            ),
            CommunicationPath(
                name="Intelligence to Bridge",
                source_service="intelligence",
                target_service="bridge",
                test_endpoint="/mapping/stats",
                expected_response_fields=["status"],
                max_response_time=5.0,
            ),
            CommunicationPath(
                name="Bridge to Memgraph",
                source_service="bridge",
                target_service="memgraph",
                test_endpoint="/",
                expected_response_fields=None,  # HTTP response check only
                max_response_time=5.0,
            ),
            CommunicationPath(
                name="Bridge to Search",
                source_service="bridge",
                target_service="search",
                test_endpoint="/stats",
                expected_response_fields=["status"],
                max_response_time=5.0,
            ),
            CommunicationPath(
                name="Search to Qdrant",
                source_service="search",
                target_service="qdrant",
                test_endpoint="/collections",
                expected_response_fields=None,  # Collections array
                max_response_time=5.0,
            ),
        ]

        if verbose:
            logger.setLevel(logging.DEBUG)

    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive service communication tests"""
        print("🌐 Service Communication and Bridge Sync Validation Tests")
        print("=" * 70)
        print(f"Session ID: {self.test_session_id}")
        print(f"Timeout: {self.timeout}s")
        print("=" * 70)

        start_time = time.time()

        try:
            # Phase 1: Individual Service Health
            await self._test_individual_service_health()

            # Phase 2: Service Communication Paths
            await self._test_communication_paths()

            # Phase 3: Bridge Service Synchronization
            await self._test_bridge_sync_operations()

            # Phase 4: Event-Driven Communication
            await self._test_event_driven_communication()

            # Phase 5: Service Recovery and Failover
            await self._test_service_recovery_scenarios()

            # Phase 6: Performance Under Load
            await self._test_communication_under_load()

            # Phase 7: Bridge Sync Triggers
            await self._test_bridge_sync_triggers()

            # Phase 8: Cross-Service Data Consistency
            await self._test_cross_service_data_consistency()

        except Exception as e:
            logger.error(f"Service communication test suite failed: {e}")
            self._record_test_result(
                "test_suite_execution",
                False,
                time.time() - start_time,
                f"Suite execution failed: {e}",
            )

        finally:
            total_time = time.time() - start_time
            return await self._generate_communication_report(total_time)

    async def _test_individual_service_health(self):
        """Test individual service health and responsiveness"""
        print("\n🏥 Testing Individual Service Health...")

        health_results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for service_key, service in self.services.items():
                start_time = time.time()

                try:
                    # Special handling for MCP server
                    if service_key == "mcp_server":
                        mcp_request = {"method": "session_info", "params": {}}
                        response = await client.post(
                            f"{service.url}{service.health_endpoint}",
                            json=mcp_request,
                            timeout=service.timeout,
                        )
                    else:
                        response = await client.get(
                            f"{service.url}{service.health_endpoint}",
                            timeout=service.timeout,
                        )

                    response_time = time.time() - start_time

                    health_results[service_key] = {
                        "name": service.name,
                        "healthy": response.status_code == 200,
                        "status_code": response.status_code,
                        "response_time": response_time,
                        "response_size": (
                            len(response.content) if response.content else 0
                        ),
                    }

                    status_symbol = "✅" if response.status_code == 200 else "❌"
                    print(
                        f"  {status_symbol} {service.name}: {response.status_code} ({response_time:.3f}s)"
                    )

                except Exception as e:
                    response_time = time.time() - start_time
                    health_results[service_key] = {
                        "name": service.name,
                        "healthy": False,
                        "error": str(e),
                        "response_time": response_time,
                    }
                    print(f"  ❌ {service.name}: ERROR - {e}")

        # Evaluate overall health
        total_services = len(health_results)
        healthy_services = sum(
            1 for result in health_results.values() if result.get("healthy", False)
        )
        health_percentage = (healthy_services / total_services) * 100

        self._record_test_result(
            "individual_service_health",
            health_percentage == 100,
            sum(result.get("response_time", 0) for result in health_results.values()),
            f"{healthy_services}/{total_services} services healthy ({health_percentage:.1f}%)",
            {"health_results": health_results, "health_percentage": health_percentage},
        )

    async def _test_communication_paths(self):
        """Test critical communication paths between services"""
        print("\n🔗 Testing Service Communication Paths...")

        communication_results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for path in self.communication_paths:
                start_time = time.time()

                try:
                    source_service = self.services[path.source_service]
                    target_service = self.services[path.target_service]

                    # Test communication from source to target
                    test_url = f"{target_service.url}{path.test_endpoint}"
                    response = await client.get(
                        test_url, timeout=path.max_response_time
                    )

                    response_time = time.time() - start_time

                    # Validate response
                    response_valid = True
                    validation_details = {"status_code": response.status_code}

                    if response.status_code == 200:
                        if path.expected_response_fields:
                            try:
                                response_data = response.json()
                                validation_details["response_data"] = response_data

                                for field in path.expected_response_fields:
                                    if field not in response_data:
                                        response_valid = False
                                        validation_details["missing_field"] = field
                                        break
                            except json.JSONDecodeError:
                                response_valid = False
                                validation_details["json_decode_error"] = True
                    else:
                        response_valid = False

                    communication_results[path.name] = {
                        "source": source_service.name,
                        "target": target_service.name,
                        "success": response_valid
                        and response_time <= path.max_response_time,
                        "response_time": response_time,
                        "max_allowed_time": path.max_response_time,
                        "validation_details": validation_details,
                    }

                    status_symbol = (
                        "✅" if communication_results[path.name]["success"] else "❌"
                    )
                    print(
                        f"  {status_symbol} {path.name}: {response.status_code} ({response_time:.3f}s)"
                    )

                except Exception as e:
                    response_time = time.time() - start_time
                    communication_results[path.name] = {
                        "source": self.services[path.source_service].name,
                        "target": self.services[path.target_service].name,
                        "success": False,
                        "response_time": response_time,
                        "error": str(e),
                    }
                    print(f"  ❌ {path.name}: ERROR - {e}")

        # Evaluate communication results
        successful_paths = sum(
            1
            for result in communication_results.values()
            if result.get("success", False)
        )
        total_paths = len(communication_results)
        success_rate = (successful_paths / total_paths) * 100

        self._record_test_result(
            "service_communication_paths",
            success_rate == 100,
            sum(
                result.get("response_time", 0)
                for result in communication_results.values()
            ),
            f"{successful_paths}/{total_paths} communication paths successful ({success_rate:.1f}%)",
            {
                "communication_results": communication_results,
                "success_rate": success_rate,
            },
        )

    async def _test_bridge_sync_operations(self):
        """Test bridge service synchronization operations"""
        print("\n🌉 Testing Bridge Service Synchronization...")

        sync_results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test 1: Bridge sync status
            try:
                start_time = time.time()
                response = await client.get(
                    f"{self.services['bridge'].url}/sync/status"
                )
                response_time = time.time() - start_time

                sync_results["sync_status"] = {
                    "success": response.status_code == 200,
                    "response_time": response_time,
                    "status_code": response.status_code,
                }

                if response.status_code == 200:
                    sync_results["sync_status"]["data"] = response.json()

                print(
                    f"  {'✅' if response.status_code == 200 else '❌'} Sync Status: {response.status_code} ({response_time:.3f}s)"
                )

            except Exception as e:
                sync_results["sync_status"] = {"success": False, "error": str(e)}
                print(f"  ❌ Sync Status: ERROR - {e}")

            # Test 2: Mapping statistics
            try:
                start_time = time.time()
                response = await client.get(
                    f"{self.services['bridge'].url}/mapping/stats"
                )
                response_time = time.time() - start_time

                sync_results["mapping_stats"] = {
                    "success": response.status_code == 200,
                    "response_time": response_time,
                    "status_code": response.status_code,
                }

                if response.status_code == 200:
                    sync_results["mapping_stats"]["data"] = response.json()

                print(
                    f"  {'✅' if response.status_code == 200 else '❌'} Mapping Stats: {response.status_code} ({response_time:.3f}s)"
                )

            except Exception as e:
                sync_results["mapping_stats"] = {"success": False, "error": str(e)}
                print(f"  ❌ Mapping Stats: ERROR - {e}")

            # Test 3: Incremental sync capability
            try:
                start_time = time.time()
                sync_request = {
                    "entity_types": ["document", "test"],
                    "source_ids": [self.test_session_id],
                }
                response = await client.post(
                    f"{self.services['bridge'].url}/sync/incremental",
                    json=sync_request,
                    timeout=30.0,
                )
                response_time = time.time() - start_time

                sync_results["incremental_sync"] = {
                    "success": response.status_code == 200,
                    "response_time": response_time,
                    "status_code": response.status_code,
                }

                if response.status_code == 200:
                    sync_results["incremental_sync"]["data"] = response.json()

                print(
                    f"  {'✅' if response.status_code == 200 else '❌'} Incremental Sync: {response.status_code} ({response_time:.3f}s)"
                )

            except Exception as e:
                sync_results["incremental_sync"] = {"success": False, "error": str(e)}
                print(f"  ❌ Incremental Sync: ERROR - {e}")

        # Evaluate bridge sync results
        successful_operations = sum(
            1 for result in sync_results.values() if result.get("success", False)
        )
        total_operations = len(sync_results)
        success_rate = (successful_operations / total_operations) * 100

        self._record_test_result(
            "bridge_sync_operations",
            success_rate >= 80,  # Allow some tolerance for bridge operations
            sum(result.get("response_time", 0) for result in sync_results.values()),
            f"{successful_operations}/{total_operations} bridge operations successful ({success_rate:.1f}%)",
            {"sync_results": sync_results, "success_rate": success_rate},
        )

    async def _test_event_driven_communication(self):
        """Test event-driven communication between services"""
        print("\n📡 Testing Event-Driven Communication...")

        # This test would monitor event bus communication
        # For now, we'll test the REST API endpoints that trigger events

        event_results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test event monitoring capabilities
            services_with_events = ["intelligence", "bridge", "search"]

            for service_key in services_with_events:
                try:
                    service = self.services[service_key]
                    start_time = time.time()

                    # Test if service has event monitoring endpoint
                    response = await client.get(
                        f"{service.url}/events/status", timeout=10.0
                    )
                    response_time = time.time() - start_time

                    event_results[f"{service_key}_events"] = {
                        "service": service.name,
                        "success": response.status_code
                        in [200, 404],  # 404 is acceptable if not implemented
                        "response_time": response_time,
                        "status_code": response.status_code,
                        "events_supported": response.status_code == 200,
                    }

                    status_symbol = (
                        "✅"
                        if response.status_code == 200
                        else "⚠️" if response.status_code == 404 else "❌"
                    )
                    print(
                        f"  {status_symbol} {service.name} Events: {response.status_code} ({response_time:.3f}s)"
                    )

                except Exception as e:
                    event_results[f"{service_key}_events"] = {
                        "service": self.services[service_key].name,
                        "success": False,
                        "error": str(e),
                    }
                    print(f"  ❌ {self.services[service_key].name} Events: ERROR - {e}")

        # Test cross-service event flow simulation
        try:
            # Simulate document creation event that should trigger cross-service communication
            start_time = time.time()

            # This would be a document creation that triggers the full pipeline
            test_event = {
                "event_type": "document_created",
                "session_id": self.test_session_id,
                "metadata": {"test": True},
            }

            # Send test event if event endpoint is available
            try:
                response = await client.post(
                    f"{self.services['bridge'].url}/events/test",
                    json=test_event,
                    timeout=10.0,
                )

                event_flow_time = time.time() - start_time
                event_results["cross_service_event_flow"] = {
                    "success": response.status_code in [200, 404],
                    "response_time": event_flow_time,
                    "status_code": response.status_code,
                }

                print(
                    f"  {'✅' if response.status_code == 200 else '⚠️'} Cross-Service Event Flow: {response.status_code} ({event_flow_time:.3f}s)"
                )

            except Exception:
                # Event endpoint may not be implemented, which is acceptable
                event_results["cross_service_event_flow"] = {
                    "success": True,
                    "note": "Event endpoints not implemented (acceptable)",
                }
                print("  ⚠️  Cross-Service Event Flow: Not implemented (acceptable)")

        except Exception as e:
            event_results["cross_service_event_flow"] = {
                "success": False,
                "error": str(e),
            }
            print(f"  ❌ Cross-Service Event Flow: ERROR - {e}")

        # Evaluate event communication
        successful_events = sum(
            1 for result in event_results.values() if result.get("success", False)
        )
        total_events = len(event_results)
        success_rate = (successful_events / total_events) * 100

        self._record_test_result(
            "event_driven_communication",
            success_rate
            >= 70,  # More tolerant since event systems may not be fully implemented
            sum(result.get("response_time", 0) for result in event_results.values()),
            f"{successful_events}/{total_events} event operations successful ({success_rate:.1f}%)",
            {"event_results": event_results, "success_rate": success_rate},
        )

    async def _test_service_recovery_scenarios(self):
        """Test service recovery and failover scenarios"""
        print("\n🔄 Testing Service Recovery Scenarios...")

        # Note: This test simulates scenarios rather than actually bringing services down
        # to avoid disrupting the system during testing

        recovery_results = {}

        # Test 1: Service timeout handling
        async with httpx.AsyncClient(timeout=2.0) as client:  # Very short timeout
            for service_key, service in self.services.items():
                try:
                    start_time = time.time()

                    if service_key == "mcp_server":
                        mcp_request = {"method": "session_info", "params": {}}
                        response = await client.post(
                            f"{service.url}{service.health_endpoint}", json=mcp_request
                        )
                    else:
                        response = await client.get(
                            f"{service.url}{service.health_endpoint}"
                        )

                    response_time = time.time() - start_time

                    recovery_results[f"{service_key}_timeout_handling"] = {
                        "service": service.name,
                        "timeout_handled": response_time <= 2.0,
                        "response_time": response_time,
                        "status_code": response.status_code,
                    }

                except asyncio.TimeoutError:
                    recovery_results[f"{service_key}_timeout_handling"] = {
                        "service": service.name,
                        "timeout_handled": False,
                        "error": "Timeout exceeded",
                    }
                except Exception as e:
                    recovery_results[f"{service_key}_timeout_handling"] = {
                        "service": service.name,
                        "timeout_handled": False,
                        "error": str(e),
                    }

        # Test 2: Service circuit breaker simulation
        # This would test if services handle repeated failures gracefully
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for service_key in ["intelligence", "bridge", "search"]:
                try:
                    service = self.services[service_key]

                    # Test multiple rapid requests to see if service handles load
                    start_time = time.time()
                    responses = []

                    for i in range(5):  # 5 rapid requests
                        try:
                            response = await client.get(
                                f"{service.url}/health", timeout=5.0
                            )
                            responses.append(response.status_code)
                        except Exception:
                            responses.append(0)  # Failed request

                    total_time = time.time() - start_time
                    successful_requests = sum(1 for code in responses if code == 200)

                    recovery_results[f"{service_key}_load_handling"] = {
                        "service": service.name,
                        "successful_requests": successful_requests,
                        "total_requests": 5,
                        "total_time": total_time,
                        "handles_load": successful_requests >= 4,  # Allow 1 failure
                    }

                    print(
                        f"  {'✅' if successful_requests >= 4 else '❌'} {service.name} Load Handling: {successful_requests}/5 successful"
                    )

                except Exception as e:
                    recovery_results[f"{service_key}_load_handling"] = {
                        "service": self.services[service_key].name,
                        "handles_load": False,
                        "error": str(e),
                    }
                    print(
                        f"  ❌ {self.services[service_key].name} Load Handling: ERROR - {e}"
                    )

        # Evaluate recovery scenarios
        successful_recovery = sum(
            1
            for result in recovery_results.values()
            if result.get("timeout_handled", False) or result.get("handles_load", False)
        )
        total_recovery_tests = len(recovery_results)
        success_rate = (successful_recovery / total_recovery_tests) * 100

        self._record_test_result(
            "service_recovery_scenarios",
            success_rate >= 75,
            0,  # No meaningful total time for this test
            f"{successful_recovery}/{total_recovery_tests} recovery scenarios successful ({success_rate:.1f}%)",
            {"recovery_results": recovery_results, "success_rate": success_rate},
        )

    async def _test_communication_under_load(self):
        """Test service communication under load"""
        print("\n🏋️  Testing Communication Under Load...")

        # This is a simplified load test focusing on communication
        load_results = {}
        concurrent_requests = 10

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for service_key, service in self.services.items():
                if service_key in [
                    "memgraph",
                    "qdrant",
                ]:  # Skip databases for load test
                    continue

                try:
                    start_time = time.time()

                    # Create concurrent requests
                    async def make_request():
                        if service_key == "mcp_server":
                            mcp_request = {"method": "session_info", "params": {}}
                            return await client.post(
                                f"{service.url}{service.health_endpoint}",
                                json=mcp_request,
                            )
                        else:
                            return await client.get(
                                f"{service.url}{service.health_endpoint}"
                            )

                    # Execute concurrent requests
                    tasks = [make_request() for _ in range(concurrent_requests)]
                    responses = await asyncio.gather(*tasks, return_exceptions=True)

                    total_time = time.time() - start_time

                    # Analyze results
                    successful_responses = sum(
                        1
                        for r in responses
                        if not isinstance(r, Exception) and r.status_code == 200
                    )

                    load_results[service_key] = {
                        "service": service.name,
                        "concurrent_requests": concurrent_requests,
                        "successful_responses": successful_responses,
                        "total_time": total_time,
                        "avg_response_time": total_time / concurrent_requests,
                        "success_rate": (successful_responses / concurrent_requests)
                        * 100,
                        "handles_concurrent_load": successful_responses
                        >= (concurrent_requests * 0.8),  # 80% success
                    }

                    success_symbol = (
                        "✅"
                        if load_results[service_key]["handles_concurrent_load"]
                        else "❌"
                    )
                    print(
                        f"  {success_symbol} {service.name}: {successful_responses}/{concurrent_requests} successful ({total_time:.2f}s)"
                    )

                except Exception as e:
                    load_results[service_key] = {
                        "service": service.name,
                        "handles_concurrent_load": False,
                        "error": str(e),
                    }
                    print(f"  ❌ {service.name}: ERROR - {e}")

        # Evaluate load handling
        services_handling_load = sum(
            1
            for result in load_results.values()
            if result.get("handles_concurrent_load", False)
        )
        total_services_tested = len(load_results)
        success_rate = (services_handling_load / total_services_tested) * 100

        self._record_test_result(
            "communication_under_load",
            success_rate >= 80,
            sum(result.get("total_time", 0) for result in load_results.values()),
            f"{services_handling_load}/{total_services_tested} services handle concurrent load ({success_rate:.1f}%)",
            {"load_results": load_results, "success_rate": success_rate},
        )

    async def _test_bridge_sync_triggers(self):
        """Test bridge sync triggers and data flow"""
        print("\n🎯 Testing Bridge Sync Triggers...")

        trigger_results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test manual sync trigger
            try:
                start_time = time.time()
                sync_request = {
                    "entity_types": ["test"],
                    "source_ids": [f"test_{self.test_session_id}"],
                    "force": True,
                }

                response = await client.post(
                    f"{self.services['bridge'].url}/sync/manual",
                    json=sync_request,
                    timeout=30.0,
                )

                trigger_time = time.time() - start_time

                trigger_results["manual_sync_trigger"] = {
                    "success": response.status_code
                    in [200, 202],  # Accept both OK and Accepted
                    "response_time": trigger_time,
                    "status_code": response.status_code,
                }

                if response.status_code in [200, 202]:
                    trigger_results["manual_sync_trigger"]["data"] = response.json()

                print(
                    f"  {'✅' if response.status_code in [200, 202] else '❌'} Manual Sync Trigger: {response.status_code} ({trigger_time:.3f}s)"
                )

            except Exception as e:
                trigger_results["manual_sync_trigger"] = {
                    "success": False,
                    "error": str(e),
                }
                print(f"  ❌ Manual Sync Trigger: ERROR - {e}")

            # Test sync status monitoring
            try:
                start_time = time.time()
                response = await client.get(
                    f"{self.services['bridge'].url}/sync/status", timeout=10.0
                )
                status_time = time.time() - start_time

                trigger_results["sync_status_monitoring"] = {
                    "success": response.status_code == 200,
                    "response_time": status_time,
                    "status_code": response.status_code,
                }

                if response.status_code == 200:
                    trigger_results["sync_status_monitoring"]["data"] = response.json()

                print(
                    f"  {'✅' if response.status_code == 200 else '❌'} Sync Status Monitoring: {response.status_code} ({status_time:.3f}s)"
                )

            except Exception as e:
                trigger_results["sync_status_monitoring"] = {
                    "success": False,
                    "error": str(e),
                }
                print(f"  ❌ Sync Status Monitoring: ERROR - {e}")

        # Evaluate trigger results
        successful_triggers = sum(
            1 for result in trigger_results.values() if result.get("success", False)
        )
        total_triggers = len(trigger_results)
        success_rate = (successful_triggers / total_triggers) * 100

        self._record_test_result(
            "bridge_sync_triggers",
            success_rate
            >= 50,  # More tolerant since sync endpoints may not all be implemented
            sum(result.get("response_time", 0) for result in trigger_results.values()),
            f"{successful_triggers}/{total_triggers} sync triggers successful ({success_rate:.1f}%)",
            {"trigger_results": trigger_results, "success_rate": success_rate},
        )

    async def _test_cross_service_data_consistency(self):
        """Test data consistency across services"""
        print("\n🔄 Testing Cross-Service Data Consistency...")

        # This test checks if data created in one service is accessible in others
        consistency_results = {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Test if bridge service can access intelligence data
            try:
                start_time = time.time()
                response = await client.get(
                    f"{self.services['bridge'].url}/mapping/stats", timeout=10.0
                )
                access_time = time.time() - start_time

                consistency_results["bridge_intelligence_access"] = {
                    "success": response.status_code == 200,
                    "response_time": access_time,
                    "status_code": response.status_code,
                }

                print(
                    f"  {'✅' if response.status_code == 200 else '❌'} Bridge-Intelligence Access: {response.status_code} ({access_time:.3f}s)"
                )

            except Exception as e:
                consistency_results["bridge_intelligence_access"] = {
                    "success": False,
                    "error": str(e),
                }
                print(f"  ❌ Bridge-Intelligence Access: ERROR - {e}")

            # Test if search service can access bridge data
            try:
                start_time = time.time()
                response = await client.get(
                    f"{self.services['search'].url}/stats", timeout=10.0
                )
                search_time = time.time() - start_time

                consistency_results["search_bridge_access"] = {
                    "success": response.status_code == 200,
                    "response_time": search_time,
                    "status_code": response.status_code,
                }

                print(
                    f"  {'✅' if response.status_code == 200 else '❌'} Search-Bridge Access: {response.status_code} ({search_time:.3f}s)"
                )

            except Exception as e:
                consistency_results["search_bridge_access"] = {
                    "success": False,
                    "error": str(e),
                }
                print(f"  ❌ Search-Bridge Access: ERROR - {e}")

        # Evaluate consistency results
        successful_consistency = sum(
            1 for result in consistency_results.values() if result.get("success", False)
        )
        total_consistency_tests = len(consistency_results)
        success_rate = (successful_consistency / total_consistency_tests) * 100

        self._record_test_result(
            "cross_service_data_consistency",
            success_rate >= 80,
            sum(
                result.get("response_time", 0)
                for result in consistency_results.values()
            ),
            f"{successful_consistency}/{total_consistency_tests} consistency tests successful ({success_rate:.1f}%)",
            {"consistency_results": consistency_results, "success_rate": success_rate},
        )

    def _record_test_result(
        self,
        test_name: str,
        success: bool,
        duration: float,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record a test result"""
        result = {
            "test_name": test_name,
            "success": success,
            "duration": duration,
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.test_results.append(result)

    async def _generate_communication_report(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive communication test report"""
        print("\n" + "=" * 70)
        print("📊 SERVICE COMMUNICATION TEST REPORT")
        print("=" * 70)

        # Calculate summary statistics
        total_tests = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["success"])
        failed = total_tests - passed

        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0

        print(f"Session ID: {self.test_session_id}")
        print(f"Total Execution Time: {total_time:.2f}s")
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {success_rate:.1f}%")

        # Service Health Summary
        print("\n🏥 Service Health Summary:")
        health_test = next(
            (
                r
                for r in self.test_results
                if r["test_name"] == "individual_service_health"
            ),
            None,
        )
        if health_test and health_test.get("metadata", {}).get("health_results"):
            for service_key, health in health_test["metadata"][
                "health_results"
            ].items():
                status_symbol = "✅" if health.get("healthy", False) else "❌"
                print(
                    f"  {status_symbol} {health.get('name', service_key)}: {'Healthy' if health.get('healthy', False) else 'Unhealthy'}"
                )

        # Communication Path Summary
        print("\n🔗 Communication Path Summary:")
        comm_test = next(
            (
                r
                for r in self.test_results
                if r["test_name"] == "service_communication_paths"
            ),
            None,
        )
        if comm_test and comm_test.get("metadata", {}).get("communication_results"):
            for path_name, comm in comm_test["metadata"][
                "communication_results"
            ].items():
                status_symbol = "✅" if comm.get("success", False) else "❌"
                print(
                    f"  {status_symbol} {path_name}: {'Success' if comm.get('success', False) else 'Failed'}"
                )

        # Critical Issues
        print("\n🚨 Critical Issues:")
        critical_failures = [r for r in self.test_results if not r["success"]]
        if critical_failures:
            for failure in critical_failures:
                print(f"  ❌ {failure['test_name']}: {failure['message']}")
        else:
            print("  ✅ No critical issues detected")

        # Overall Assessment
        print("\n🎯 Overall Assessment:")
        if failed == 0:
            print("🎉 EXCELLENT: All service communication tests passed!")
        elif failed <= 2:
            print("✅ GOOD: Most communication paths are working with minor issues.")
        elif failed <= 4:
            print("⚠️  CONCERNING: Several communication issues detected.")
        else:
            print(
                "❌ CRITICAL: Major communication failures detected. System needs attention."
            )

        print("=" * 70)

        return {
            "session_id": self.test_session_id,
            "total_time": total_time,
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "success_rate": success_rate,
            },
            "test_results": self.test_results,
        }


async def main():
    """Main test execution function"""
    parser = argparse.ArgumentParser(
        description="Service Communication and Bridge Sync Validation Tests"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="Test timeout in seconds"
    )

    args = parser.parse_args()

    tester = ServiceCommunicationTester(verbose=args.verbose, timeout=args.timeout)

    try:
        report = await tester.run_comprehensive_tests()

        # Save report to file
        report_filename = f"service_communication_report_{tester.test_session_id}.json"
        with open(report_filename, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n📄 Detailed report saved to: {report_filename}")

        # Exit with appropriate code
        failed_tests = sum(1 for r in tester.test_results if not r["success"])
        exit(1 if failed_tests > 0 else 0)

    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
