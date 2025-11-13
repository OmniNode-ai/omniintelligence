#!/usr/bin/env python3
"""
ARCHON SYSTEM RECOVERY PROCEDURES
==================================

Implements comprehensive system recovery for the Archon platform including:
- Service dependency validation and recovery
- Connection pool management and cleanup
- Resource management and optimization
- Automated health monitoring and recovery
- Service orchestration improvements

Usage:
    python scripts/system_recovery.py --action [recovery|monitor|validate|cleanup]
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import psutil

import docker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("system_recovery.log")],
)
logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Configuration for a service in the recovery system."""

    name: str
    container_name: str
    port: int
    health_endpoint: str
    dependencies: List[str]
    critical: bool = True
    restart_timeout: int = 120
    max_retries: int = 3


@dataclass
class ServiceStatus:
    """Current status of a service."""

    name: str
    running: bool
    healthy: bool
    port_accessible: bool
    dependencies_met: bool
    last_check: datetime
    error_message: Optional[str] = None


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""

    success: bool
    services_recovered: List[str]
    services_failed: List[str]
    total_time: float
    errors: List[str]


class ArchonSystemRecovery:
    """Comprehensive system recovery and monitoring for Archon platform."""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.project_root = Path(__file__).parent.parent
        self.recovery_log = []
        self.service_configs = self._load_service_configs()
        self.recovery_start_time = None

    def _load_service_configs(self) -> Dict[str, ServiceConfig]:
        """Load service configurations from docker-compose.yml."""
        services = {
            "memgraph": ServiceConfig(
                name="memgraph",
                container_name="archon-memgraph",
                port=7444,
                health_endpoint="/",
                dependencies=[],
                critical=True,
                restart_timeout=60,
            ),
            "qdrant": ServiceConfig(
                name="qdrant",
                container_name="archon-qdrant",
                port=6333,
                health_endpoint="/readyz",
                dependencies=[],
                critical=True,
                restart_timeout=90,
            ),
            "bridge": ServiceConfig(
                name="bridge",
                container_name="archon-bridge",
                port=8054,
                health_endpoint="/health",
                dependencies=["memgraph"],
                critical=True,
                restart_timeout=120,
            ),
            "intelligence": ServiceConfig(
                name="intelligence",
                container_name="archon-intelligence",
                port=8053,
                health_endpoint="/health",
                dependencies=["memgraph", "bridge"],
                critical=True,
                restart_timeout=120,
            ),
            "search": ServiceConfig(
                name="search",
                container_name="archon-search",
                port=8055,
                health_endpoint="/health",
                dependencies=["qdrant", "memgraph", "intelligence", "bridge"],
                critical=True,
                restart_timeout=180,
            ),
            "server": ServiceConfig(
                name="server",
                container_name="archon-server",
                port=8181,
                health_endpoint="/health",
                dependencies=["memgraph", "intelligence"],
                critical=True,
                restart_timeout=120,
            ),
            "mcp": ServiceConfig(
                name="mcp",
                container_name="archon-mcp",
                port=8051,
                health_endpoint="/health",
                dependencies=["server"],
                critical=True,
                restart_timeout=120,
            ),
            "frontend": ServiceConfig(
                name="frontend",
                container_name="archon-ui",
                port=3737,
                health_endpoint="/",
                dependencies=["server"],
                critical=False,
                restart_timeout=90,
            ),
        }
        return services

    async def log_recovery_action(self, action: str, details: Dict[str, Any]):
        """Log recovery actions with timestamp."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
        }
        self.recovery_log.append(log_entry)
        logger.info(f"Recovery Action: {action} - {details}")

    async def check_service_status(
        self, service_config: ServiceConfig
    ) -> ServiceStatus:
        """Check comprehensive status of a service."""
        try:
            # Check container status
            container = self.docker_client.containers.get(service_config.container_name)
            running = container.status == "running"

            # Check port accessibility
            port_accessible = False
            if running:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(
                            f"http://localhost:{service_config.port}{service_config.health_endpoint}"
                        )
                        port_accessible = response.status_code < 500
                except:
                    port_accessible = False

            # Check dependencies
            dependencies_met = True
            for dep_name in service_config.dependencies:
                if dep_name in self.service_configs:
                    dep_status = await self.check_service_status(
                        self.service_configs[dep_name]
                    )
                    if not (dep_status.running and dep_status.healthy):
                        dependencies_met = False
                        break

            healthy = running and port_accessible and dependencies_met

            return ServiceStatus(
                name=service_config.name,
                running=running,
                healthy=healthy,
                port_accessible=port_accessible,
                dependencies_met=dependencies_met,
                last_check=datetime.now(),
            )

        except docker.errors.NotFound:
            return ServiceStatus(
                name=service_config.name,
                running=False,
                healthy=False,
                port_accessible=False,
                dependencies_met=False,
                last_check=datetime.now(),
                error_message="Container not found",
            )
        except Exception as e:
            return ServiceStatus(
                name=service_config.name,
                running=False,
                healthy=False,
                port_accessible=False,
                dependencies_met=False,
                last_check=datetime.now(),
                error_message=str(e),
            )

    async def cleanup_system_resources(self):
        """Clean up system resources before recovery."""
        await self.log_recovery_action("resource_cleanup", {"stage": "starting"})

        try:
            # Clean up Docker resources
            logger.info("Cleaning up Docker resources...")

            # Remove dead containers
            dead_containers = self.docker_client.containers.list(
                filters={"status": "dead"}
            )
            for container in dead_containers:
                try:
                    container.remove()
                    logger.info(f"Removed dead container: {container.name}")
                except Exception as e:
                    logger.warning(
                        f"Failed to remove dead container {container.name}: {e}"
                    )

            # Clean up unused networks
            try:
                subprocess.run(
                    ["docker", "network", "prune", "-f"],
                    capture_output=True,
                    timeout=30,
                )
                logger.info("Cleaned up unused Docker networks")
            except Exception as e:
                logger.warning(f"Failed to clean up networks: {e}")

            # Clean up volumes for failed services only
            failed_services = ["archon-memgraph", "archon-search", "archon-ui"]
            for service_name in failed_services:
                try:
                    container = self.docker_client.containers.get(service_name)
                    if container.status in ["exited", "dead"]:
                        container.remove(force=True)
                        logger.info(f"Force removed failed container: {service_name}")
                except docker.errors.NotFound:
                    logger.info(f"Container {service_name} not found (already cleaned)")
                except Exception as e:
                    logger.warning(f"Failed to remove container {service_name}: {e}")

            # Clear system cache if high memory usage
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 80:
                logger.warning(f"High memory usage: {memory_percent}%")
                # Force garbage collection in Python
                import gc

                gc.collect()

                # Drop caches if on Linux
                try:
                    if os.path.exists("/proc/sys/vm/drop_caches"):
                        subprocess.run(
                            ["sudo", "sysctl", "vm.drop_caches=3"],
                            capture_output=True,
                            timeout=10,
                        )
                        logger.info("Dropped system caches")
                except Exception as e:
                    logger.warning(f"Failed to drop caches: {e}")

            await self.log_recovery_action("resource_cleanup", {"stage": "completed"})

        except Exception as e:
            await self.log_recovery_action(
                "resource_cleanup", {"stage": "failed", "error": str(e)}
            )
            raise

    async def restart_service_with_dependencies(self, service_name: str) -> bool:
        """Restart a service and ensure its dependencies are running."""
        if service_name not in self.service_configs:
            logger.error(f"Unknown service: {service_name}")
            return False

        service_config = self.service_configs[service_name]

        try:
            await self.log_recovery_action(
                "service_restart", {"service": service_name, "stage": "starting"}
            )

            # First, ensure all dependencies are healthy
            for dep_name in service_config.dependencies:
                if dep_name in self.service_configs:
                    dep_status = await self.check_service_status(
                        self.service_configs[dep_name]
                    )
                    if not dep_status.healthy:
                        logger.info(
                            f"Restarting dependency {dep_name} for {service_name}"
                        )
                        success = await self.restart_service_with_dependencies(dep_name)
                        if not success:
                            logger.error(f"Failed to restart dependency {dep_name}")
                            return False

            # Stop the service gracefully
            try:
                container = self.docker_client.containers.get(
                    service_config.container_name
                )
                if container.status == "running":
                    logger.info(f"Stopping {service_name}...")
                    container.stop(timeout=30)
                    container.wait(timeout=60)

                # Remove container to ensure clean restart
                container.remove()
                logger.info(f"Removed container for {service_name}")

            except docker.errors.NotFound:
                logger.info(
                    f"Container {service_config.container_name} not found, will create new"
                )
            except Exception as e:
                logger.warning(f"Error stopping {service_name}: {e}")

            # Wait a moment for cleanup
            await asyncio.sleep(5)

            # Restart using docker-compose
            logger.info(f"Starting {service_name} with docker-compose...")

            # Determine compose command based on service
            if service_name == "agents":
                compose_cmd = [
                    "docker",
                    "compose",
                    "--profile",
                    "agents",
                    "up",
                    "-d",
                    service_config.container_name,
                ]
            else:
                compose_cmd = [
                    "docker",
                    "compose",
                    "up",
                    "-d",
                    service_config.container_name,
                ]

            result = subprocess.run(
                compose_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=service_config.restart_timeout,
            )

            if result.returncode != 0:
                logger.error(f"Failed to start {service_name}: {result.stderr}")
                await self.log_recovery_action(
                    "service_restart",
                    {
                        "service": service_name,
                        "stage": "failed",
                        "error": result.stderr,
                    },
                )
                return False

            # Wait for service to be healthy
            logger.info(f"Waiting for {service_name} to become healthy...")
            max_wait = service_config.restart_timeout
            wait_interval = 5
            waited = 0

            while waited < max_wait:
                status = await self.check_service_status(service_config)
                if status.healthy:
                    logger.info(f"Service {service_name} is now healthy")
                    await self.log_recovery_action(
                        "service_restart",
                        {
                            "service": service_name,
                            "stage": "completed",
                            "wait_time": waited,
                        },
                    )
                    return True

                if status.error_message:
                    logger.warning(
                        f"Service {service_name} error: {status.error_message}"
                    )

                await asyncio.sleep(wait_interval)
                waited += wait_interval
                logger.info(f"Waiting for {service_name}... ({waited}/{max_wait}s)")

            logger.error(
                f"Service {service_name} failed to become healthy within {max_wait}s"
            )
            await self.log_recovery_action(
                "service_restart",
                {"service": service_name, "stage": "timeout", "wait_time": waited},
            )
            return False

        except Exception as e:
            logger.error(f"Exception restarting {service_name}: {e}")
            await self.log_recovery_action(
                "service_restart",
                {"service": service_name, "stage": "exception", "error": str(e)},
            )
            return False

    async def perform_system_recovery(self) -> RecoveryResult:
        """Perform comprehensive system recovery."""
        self.recovery_start_time = time.time()
        await self.log_recovery_action("system_recovery", {"stage": "starting"})

        try:
            # Step 1: Resource cleanup
            logger.info("=== STEP 1: System Resource Cleanup ===")
            await self.cleanup_system_resources()

            # Step 2: Check current system status
            logger.info("=== STEP 2: System Status Assessment ===")
            service_statuses = {}
            failed_services = []

            for service_name, service_config in self.service_configs.items():
                status = await self.check_service_status(service_config)
                service_statuses[service_name] = status

                if not status.healthy and service_config.critical:
                    failed_services.append(service_name)
                    logger.warning(
                        f"Service {service_name} is unhealthy: running={status.running}, port_accessible={status.port_accessible}, deps_met={status.dependencies_met}"
                    )

            # Step 3: Recovery in dependency order
            logger.info("=== STEP 3: Service Recovery ===")

            # Define recovery order based on dependencies
            recovery_order = [
                "memgraph",  # Base dependency
                "qdrant",  # Base dependency
                "bridge",  # Depends on memgraph
                "intelligence",  # Depends on memgraph, bridge
                "search",  # Depends on qdrant, memgraph, intelligence, bridge
                "server",  # Depends on memgraph, intelligence
                "mcp",  # Depends on server
                "frontend",  # Depends on server
            ]

            services_recovered = []
            services_failed = []

            for service_name in recovery_order:
                if service_name in failed_services:
                    logger.info(f"Recovering service: {service_name}")
                    success = await self.restart_service_with_dependencies(service_name)

                    if success:
                        services_recovered.append(service_name)
                        logger.info(f"✅ Successfully recovered {service_name}")
                    else:
                        services_failed.append(service_name)
                        logger.error(f"❌ Failed to recover {service_name}")

                        # For critical services, this might be a blocker
                        if self.service_configs[service_name].critical:
                            logger.error(
                                f"Critical service {service_name} recovery failed!"
                            )
                else:
                    # Check if service is actually healthy
                    status = await self.check_service_status(
                        self.service_configs[service_name]
                    )
                    if status.healthy:
                        logger.info(f"✅ Service {service_name} already healthy")
                    else:
                        logger.warning(
                            f"⚠️ Service {service_name} shows unhealthy, attempting recovery"
                        )
                        success = await self.restart_service_with_dependencies(
                            service_name
                        )
                        if success:
                            services_recovered.append(service_name)
                        else:
                            services_failed.append(service_name)

            # Step 4: Final validation
            logger.info("=== STEP 4: Final System Validation ===")
            await asyncio.sleep(10)  # Allow systems to stabilize

            final_statuses = {}
            all_critical_healthy = True

            for service_name, service_config in self.service_configs.items():
                status = await self.check_service_status(service_config)
                final_statuses[service_name] = status

                if service_config.critical and not status.healthy:
                    all_critical_healthy = False
                    logger.error(
                        f"Critical service {service_name} still unhealthy after recovery"
                    )

            # Step 5: Test MCP functionality
            logger.info("=== STEP 5: MCP Functionality Test ===")
            mcp_test_success = await self.test_mcp_functionality()

            total_time = time.time() - self.recovery_start_time

            recovery_result = RecoveryResult(
                success=all_critical_healthy and mcp_test_success,
                services_recovered=services_recovered,
                services_failed=services_failed,
                total_time=total_time,
                errors=[],
            )

            await self.log_recovery_action(
                "system_recovery",
                {"stage": "completed", "result": asdict(recovery_result)},
            )

            # Generate recovery report
            await self.generate_recovery_report(recovery_result, final_statuses)

            return recovery_result

        except Exception as e:
            total_time = time.time() - (self.recovery_start_time or time.time())
            error_result = RecoveryResult(
                success=False,
                services_recovered=[],
                services_failed=list(self.service_configs.keys()),
                total_time=total_time,
                errors=[str(e)],
            )

            await self.log_recovery_action(
                "system_recovery", {"stage": "failed", "error": str(e)}
            )

            return error_result

    async def test_mcp_functionality(self) -> bool:
        """Test core MCP functionality including document creation."""
        try:
            logger.info("Testing MCP document creation functionality...")

            # Test basic MCP server connectivity
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test health endpoint
                health_response = await client.get("http://localhost:8051/")
                if health_response.status_code >= 400:
                    logger.error(
                        f"MCP server health check failed: {health_response.status_code}"
                    )
                    return False

                logger.info("✅ MCP server is accessible")

                # Test document creation via server API (which MCP uses)
                test_doc_data = {
                    "title": "System Recovery Test Document",
                    "content": {
                        "recovery_timestamp": datetime.now().isoformat(),
                        "test_purpose": "Validate document creation functionality after system recovery",
                    },
                    "document_type": "system_test",
                    "tags": ["system_recovery", "test"],
                }

                # First, get or create a test project
                projects_response = await client.get(
                    "http://localhost:8181/api/projects"
                )
                if projects_response.status_code == 200:
                    projects = projects_response.json()
                    if projects:
                        project_id = projects[0]["project_id"]
                    else:
                        # Create test project
                        create_project_response = await client.post(
                            "http://localhost:8181/api/projects",
                            json={
                                "title": "System Recovery Test Project",
                                "description": "Temporary project for testing system recovery",
                            },
                        )
                        if create_project_response.status_code == 201:
                            project_id = create_project_response.json()["project_id"]
                        else:
                            logger.error("Failed to create test project")
                            return False
                else:
                    logger.error("Failed to fetch projects")
                    return False

                # Test document creation
                doc_response = await client.post(
                    f"http://localhost:8181/api/projects/{project_id}/documents",
                    json=test_doc_data,
                )

                if doc_response.status_code == 201:
                    doc_data = doc_response.json()
                    logger.info(
                        f"✅ Document creation successful: {doc_data['document_id']}"
                    )

                    # Clean up test document
                    delete_response = await client.delete(
                        f"http://localhost:8181/api/projects/{project_id}/documents/{doc_data['document_id']}"
                    )

                    if delete_response.status_code == 200:
                        logger.info("✅ Test document cleanup successful")

                    return True
                else:
                    logger.error(
                        f"Document creation failed: {doc_response.status_code} - {doc_response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"MCP functionality test failed: {e}")
            return False

    async def generate_recovery_report(
        self, result: RecoveryResult, final_statuses: Dict[str, ServiceStatus]
    ):
        """Generate comprehensive recovery report."""
        report = {
            "recovery_summary": {
                "timestamp": datetime.now().isoformat(),
                "success": result.success,
                "total_time_seconds": result.total_time,
                "services_recovered": result.services_recovered,
                "services_failed": result.services_failed,
            },
            "final_service_status": {
                name: {
                    "healthy": status.healthy,
                    "running": status.running,
                    "port_accessible": status.port_accessible,
                    "dependencies_met": status.dependencies_met,
                    "error": status.error_message,
                }
                for name, status in final_statuses.items()
            },
            "recovery_log": self.recovery_log,
        }

        # Save report
        report_path = (
            self.project_root
            / f"system_recovery_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Recovery report saved to: {report_path}")

        # Print summary
        print("\n" + "=" * 80)
        print("ARCHON SYSTEM RECOVERY SUMMARY")
        print("=" * 80)
        print(f"Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        print(f"Total Time: {result.total_time:.1f} seconds")
        print(f"Services Recovered: {len(result.services_recovered)}")
        print(f"Services Failed: {len(result.services_failed)}")

        if result.services_recovered:
            print("\n✅ Recovered Services:")
            for service in result.services_recovered:
                print(f"   - {service}")

        if result.services_failed:
            print("\n❌ Failed Services:")
            for service in result.services_failed:
                print(f"   - {service}")

        print(f"\nDetailed report: {report_path}")
        print("=" * 80)

    async def continuous_monitoring(self, check_interval: int = 60):
        """Continuous system monitoring with auto-recovery."""
        logger.info(f"Starting continuous monitoring (check every {check_interval}s)")

        consecutive_failures = {}

        while True:
            try:
                # Check all services
                unhealthy_services = []

                for service_name, service_config in self.service_configs.items():
                    if service_config.critical:
                        status = await self.check_service_status(service_config)

                        if not status.healthy:
                            unhealthy_services.append(service_name)
                            consecutive_failures[service_name] = (
                                consecutive_failures.get(service_name, 0) + 1
                            )

                            logger.warning(
                                f"Service {service_name} unhealthy (failure #{consecutive_failures[service_name]})"
                            )

                            # Auto-recovery after 2 consecutive failures
                            if consecutive_failures[service_name] >= 2:
                                logger.info(
                                    f"Triggering auto-recovery for {service_name}"
                                )
                                success = await self.restart_service_with_dependencies(
                                    service_name
                                )

                                if success:
                                    consecutive_failures[service_name] = 0
                                    logger.info(
                                        f"Auto-recovery successful for {service_name}"
                                    )
                                else:
                                    logger.error(
                                        f"Auto-recovery failed for {service_name}"
                                    )
                        else:
                            # Reset failure count on successful health check
                            consecutive_failures[service_name] = 0

                if not unhealthy_services:
                    logger.info("All critical services healthy ✅")

                await asyncio.sleep(check_interval)

            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(check_interval)

    async def validate_system_stability(self) -> bool:
        """Validate system stability over time."""
        logger.info("Performing system stability validation...")

        stability_checks = 5
        check_interval = 30

        for i in range(stability_checks):
            logger.info(f"Stability check {i+1}/{stability_checks}")

            all_healthy = True
            for service_name, service_config in self.service_configs.items():
                if service_config.critical:
                    status = await self.check_service_status(service_config)
                    if not status.healthy:
                        logger.warning(
                            f"Service {service_name} unhealthy during stability check"
                        )
                        all_healthy = False

            if not all_healthy:
                logger.error("System failed stability check")
                return False

            if i < stability_checks - 1:  # Don't sleep after last check
                await asyncio.sleep(check_interval)

        logger.info("✅ System stability validation passed")
        return True


async def main():
    """Main entry point for system recovery."""
    parser = argparse.ArgumentParser(description="Archon System Recovery")
    parser.add_argument(
        "--action",
        choices=["recovery", "monitor", "validate", "cleanup"],
        default="recovery",
        help="Action to perform",
    )
    parser.add_argument(
        "--monitor-interval",
        type=int,
        default=60,
        help="Monitoring check interval in seconds",
    )

    args = parser.parse_args()

    recovery_system = ArchonSystemRecovery()

    try:
        if args.action == "recovery":
            result = await recovery_system.perform_system_recovery()
            sys.exit(0 if result.success else 1)

        elif args.action == "monitor":
            await recovery_system.continuous_monitoring(args.monitor_interval)

        elif args.action == "validate":
            success = await recovery_system.validate_system_stability()
            sys.exit(0 if success else 1)

        elif args.action == "cleanup":
            await recovery_system.cleanup_system_resources()

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
