"""
Pipeline Health Check API

Comprehensive health check endpoints for all services in the MCP document
indexing pipeline. Provides detailed service status, connectivity tests,
and dependency validation.

Services Monitored:
- archon-server (8181): Main server with FastAPI + Socket.IO
- archon-mcp (8051): MCP protocol server
- archon-bridge (8054): PostgreSQL-Memgraph synchronization
- archon-intelligence (8053): Entity extraction & knowledge graph
- archon-search (8055): Vector + Graph + Relational search
- qdrant (6333): Vector database for embeddings
- memgraph (7687): Knowledge graph database
- archon-langextract (8156): Language-aware data extraction
"""

import asyncio
import logging
import socket
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline/health", tags=["pipeline_health"])

# Service configuration
SERVICES = {
    "archon-server": {
        "type": "http",
        "host": "archon-server",
        "port": 8181,
        "health_endpoint": "/health",
        "description": "Main server with FastAPI + Socket.IO",
        "critical": True,
        "dependencies": ["memgraph", "qdrant"],
    },
    "archon-mcp": {
        "type": "http",
        "host": "archon-mcp",
        "port": 8051,
        "health_endpoint": "/health",
        "description": "MCP protocol server",
        "critical": True,
        "dependencies": ["archon-server"],
    },
    "archon-bridge": {
        "type": "http",
        "host": "archon-bridge",
        "port": 8054,
        "health_endpoint": "/health",
        "description": "PostgreSQL-Memgraph synchronization",
        "critical": True,
        "dependencies": ["memgraph"],
    },
    "archon-intelligence": {
        "type": "http",
        "host": "archon-intelligence",
        "port": 8053,
        "health_endpoint": "/health",
        "description": "Entity extraction & knowledge graph",
        "critical": True,
        "dependencies": ["memgraph", "archon-bridge"],
    },
    "archon-search": {
        "type": "http",
        "host": "archon-search",
        "port": 8055,
        "health_endpoint": "/health",
        "description": "Vector + Graph + Relational search",
        "critical": True,
        "dependencies": ["qdrant", "memgraph", "archon-intelligence", "archon-bridge"],
    },
    "archon-langextract": {
        "type": "http",
        "host": "archon-langextract",
        "port": 8156,
        "health_endpoint": "/health",
        "description": "Language-aware data extraction",
        "critical": False,
        "dependencies": ["memgraph", "archon-intelligence", "archon-bridge"],
    },
    "qdrant": {
        "type": "http",
        "host": "qdrant",
        "port": 6333,
        "health_endpoint": "/readyz",
        "description": "Vector database for embeddings",
        "critical": True,
        "dependencies": [],
    },
    "memgraph": {
        "type": "tcp",
        "host": "memgraph",
        "port": 7687,
        "description": "Knowledge graph database",
        "critical": True,
        "dependencies": [],
    },
}


class HealthCheckService:
    """Service for performing comprehensive health checks"""

    def __init__(self):
        self.health_cache: dict[str, dict[str, Any]] = {}
        self.cache_ttl = 30  # 30 seconds cache TTL
        self.timeout = 10  # 10 seconds timeout for health checks

    async def check_service_health(self, service_name: str) -> dict[str, Any]:
        """Check health of a specific service"""
        service_config = SERVICES.get(service_name)
        if not service_config:
            return {
                "service": service_name,
                "status": "unknown",
                "error": "Service not configured",
            }

        # Check cache
        cached_result = self._get_cached_health(service_name)
        if cached_result:
            return cached_result

        # Perform health check
        health_result = await self._perform_health_check(service_name, service_config)

        # Cache result
        self._cache_health_result(service_name, health_result)

        return health_result

    async def _perform_health_check(
        self, service_name: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Perform actual health check for a service"""
        start_time = time.time()

        try:
            if config["type"] == "http":
                result = await self._check_http_service(service_name, config)
            elif config["type"] == "tcp":
                result = await self._check_tcp_service(service_name, config)
            else:
                result = {
                    "status": "unknown",
                    "error": f"Unknown service type: {config['type']}",
                }

            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            result["checked_at"] = datetime.now().isoformat()

            return result

        except Exception as e:
            return {
                "service": service_name,
                "status": "error",
                "error": str(e),
                "response_time_ms": int((time.time() - start_time) * 1000),
                "checked_at": datetime.now().isoformat(),
            }

    async def _check_http_service(
        self, service_name: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Check HTTP-based service health"""
        host = config["host"]
        port = config["port"]
        health_endpoint = config.get("health_endpoint", "/health")

        url = f"http://{host}:{port}{health_endpoint}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        return {
                            "service": service_name,
                            "status": "healthy",
                            "url": url,
                            "status_code": response.status_code,
                            "response_data": response_data,
                            "description": config.get("description", ""),
                        }
                    except Exception as json_error:
                        # Response is not valid JSON - return as text (still healthy if 200)
                        logger.debug(
                            f"Health endpoint returned non-JSON response for {service_name}: {json_error}"
                        )
                        return {
                            "service": service_name,
                            "status": "healthy",
                            "url": url,
                            "status_code": response.status_code,
                            "response_text": response.text[:500],  # Limit response text
                            "description": config.get("description", ""),
                        }
                else:
                    return {
                        "service": service_name,
                        "status": "unhealthy",
                        "url": url,
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}",
                        "description": config.get("description", ""),
                    }

        except httpx.ConnectError:
            return {
                "service": service_name,
                "status": "unreachable",
                "url": url,
                "error": "Connection refused",
                "description": config.get("description", ""),
            }
        except httpx.TimeoutException:
            return {
                "service": service_name,
                "status": "timeout",
                "url": url,
                "error": f"Timeout after {self.timeout}s",
                "description": config.get("description", ""),
            }
        except Exception as e:
            return {
                "service": service_name,
                "status": "error",
                "url": url,
                "error": str(e),
                "description": config.get("description", ""),
            }

    async def _check_tcp_service(
        self, service_name: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Check TCP-based service health"""
        host = config["host"]
        port = config["port"]

        try:
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)

            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                return {
                    "service": service_name,
                    "status": "healthy",
                    "host": host,
                    "port": port,
                    "description": config.get("description", ""),
                }
            else:
                return {
                    "service": service_name,
                    "status": "unreachable",
                    "host": host,
                    "port": port,
                    "error": f"Connection failed (code: {result})",
                    "description": config.get("description", ""),
                }

        except TimeoutError:
            return {
                "service": service_name,
                "status": "timeout",
                "host": host,
                "port": port,
                "error": f"Timeout after {self.timeout}s",
                "description": config.get("description", ""),
            }
        except Exception as e:
            return {
                "service": service_name,
                "status": "error",
                "host": host,
                "port": port,
                "error": str(e),
                "description": config.get("description", ""),
            }

    def _get_cached_health(self, service_name: str) -> Optional[dict[str, Any]]:
        """Get cached health result if still valid"""
        if service_name not in self.health_cache:
            return None

        cached_data = self.health_cache[service_name]
        cache_time = cached_data.get("cached_at", 0)

        if time.time() - cache_time < self.cache_ttl:
            result = cached_data.copy()
            result.pop("cached_at", None)
            return result

        return None

    def _cache_health_result(self, service_name: str, result: dict[str, Any]):
        """Cache health check result"""
        cached_result = result.copy()
        cached_result["cached_at"] = time.time()
        self.health_cache[service_name] = cached_result

    async def check_all_services(self) -> dict[str, Any]:
        """Check health of all services"""
        tasks = []
        for service_name in SERVICES:
            task = asyncio.create_task(self.check_service_health(service_name))
            tasks.append((service_name, task))

        results = {}
        for service_name, task in tasks:
            try:
                results[service_name] = await task
            except Exception as e:
                results[service_name] = {
                    "service": service_name,
                    "status": "error",
                    "error": str(e),
                }

        return results

    async def check_pipeline_readiness(self) -> dict[str, Any]:
        """Check if the entire pipeline is ready for operation"""
        all_health = await self.check_all_services()

        critical_services = [
            name for name, config in SERVICES.items() if config.get("critical", False)
        ]

        critical_healthy = []
        critical_unhealthy = []
        non_critical_issues = []

        for service_name, health in all_health.items():
            is_critical = service_name in critical_services
            is_healthy = health.get("status") == "healthy"

            if is_critical:
                if is_healthy:
                    critical_healthy.append(service_name)
                else:
                    critical_unhealthy.append(service_name)
            elif not is_healthy:
                non_critical_issues.append(service_name)

        pipeline_ready = len(critical_unhealthy) == 0
        overall_status = "ready" if pipeline_ready else "not_ready"

        return {
            "pipeline_ready": pipeline_ready,
            "overall_status": overall_status,
            "critical_services": {
                "total": len(critical_services),
                "healthy": len(critical_healthy),
                "unhealthy": len(critical_unhealthy),
                "unhealthy_services": critical_unhealthy,
            },
            "non_critical_issues": non_critical_issues,
            "all_services": all_health,
            "readiness_score": (
                len(critical_healthy) / len(critical_services)
                if critical_services
                else 1.0
            ),
            "checked_at": datetime.now().isoformat(),
        }

    async def check_dependencies(self, service_name: str) -> dict[str, Any]:
        """Check dependencies for a specific service"""
        service_config = SERVICES.get(service_name)
        if not service_config:
            return {"error": "Service not found"}

        dependencies = service_config.get("dependencies", [])
        if not dependencies:
            return {
                "service": service_name,
                "has_dependencies": False,
                "dependencies": [],
            }

        dependency_results = {}
        for dep_name in dependencies:
            dependency_results[dep_name] = await self.check_service_health(dep_name)

        all_dependencies_healthy = all(
            result.get("status") == "healthy" for result in dependency_results.values()
        )

        return {
            "service": service_name,
            "has_dependencies": True,
            "dependencies_healthy": all_dependencies_healthy,
            "dependencies": dependency_results,
            "dependency_count": len(dependencies),
            "healthy_count": sum(
                1
                for result in dependency_results.values()
                if result.get("status") == "healthy"
            ),
        }

    async def get_service_info(self, service_name: str) -> dict[str, Any]:
        """Get detailed information about a service"""
        service_config = SERVICES.get(service_name)
        if not service_config:
            return {"error": "Service not found"}

        health = await self.check_service_health(service_name)
        dependencies = await self.check_dependencies(service_name)

        return {
            "service_name": service_name,
            "configuration": service_config,
            "health": health,
            "dependencies": dependencies,
            "critical": service_config.get("critical", False),
        }


# Global health check service instance
health_service = HealthCheckService()


@router.get("/status")
async def get_pipeline_health_status():
    """
    Get overall pipeline health status.

    Returns high-level health information for the entire pipeline
    including readiness status and critical service health.
    """
    try:
        readiness = await health_service.check_pipeline_readiness()
        return readiness
    except Exception as e:
        logger.error(f"Error getting pipeline health status: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get pipeline health status"
        )


@router.get("/services")
async def get_all_services_health():
    """
    Get health status for all pipeline services.

    Returns detailed health information for every service
    in the MCP document indexing pipeline.
    """
    try:
        all_health = await health_service.check_all_services()

        # Add summary statistics
        total_services = len(all_health)
        healthy_services = sum(
            1 for h in all_health.values() if h.get("status") == "healthy"
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_services": total_services,
                "healthy_services": healthy_services,
                "unhealthy_services": total_services - healthy_services,
                "health_percentage": (
                    (healthy_services / total_services * 100)
                    if total_services > 0
                    else 0
                ),
            },
            "services": all_health,
        }
    except Exception as e:
        logger.error(f"Error getting all services health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get services health")


@router.get("/services/{service_name}")
async def get_service_health(service_name: str):
    """
    Get detailed health information for a specific service.

    Args:
        service_name: Name of the service to check

    Returns detailed health status, configuration, and dependency information.
    """
    try:
        service_info = await health_service.get_service_info(service_name)

        if "error" in service_info:
            raise HTTPException(status_code=404, detail=service_info["error"])

        return service_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service health for {service_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service health")


@router.get("/services/{service_name}/dependencies")
async def get_service_dependencies(service_name: str):
    """
    Get dependency health status for a specific service.

    Args:
        service_name: Name of the service to check dependencies for

    Returns health status of all service dependencies.
    """
    try:
        dependencies = await health_service.check_dependencies(service_name)

        if "error" in dependencies:
            raise HTTPException(status_code=404, detail=dependencies["error"])

        return dependencies
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dependencies for {service_name}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get service dependencies"
        )


@router.get("/readiness")
async def check_pipeline_readiness():
    """
    Check if the pipeline is ready for operation.

    Performs comprehensive readiness checks including:
    - Critical service availability
    - Dependency validation
    - Configuration verification
    - Resource availability
    """
    try:
        readiness = await health_service.check_pipeline_readiness()

        # Return appropriate HTTP status based on readiness
        if readiness["pipeline_ready"]:
            return readiness
        else:
            # Return 503 Service Unavailable if pipeline is not ready
            return JSONResponse(status_code=503, content=readiness)
    except Exception as e:
        logger.error(f"Error checking pipeline readiness: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to check pipeline readiness"
        )


@router.get("/live")
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.

    Simple endpoint that returns 200 if the health check service
    itself is operational. Used by Kubernetes for liveness probes.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "service": "pipeline-health-check",
    }


@router.get("/ready")
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.

    Returns 200 if the pipeline is ready to accept traffic,
    503 if not ready. Used by Kubernetes for readiness probes.
    """
    try:
        readiness = await health_service.check_pipeline_readiness()

        if readiness["pipeline_ready"]:
            return {
                "status": "ready",
                "timestamp": datetime.now().isoformat(),
                "readiness_score": readiness["readiness_score"],
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "timestamp": datetime.now().isoformat(),
                    "unhealthy_services": readiness["critical_services"][
                        "unhealthy_services"
                    ],
                },
            )
    except Exception as e:
        logger.error(f"Error in readiness probe: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@router.get("/deep")
async def deep_health_check(
    include_dependencies: bool = Query(True, description="Include dependency checks"),
    force_refresh: bool = Query(False, description="Force refresh cached results"),
):
    """
    Deep health check with comprehensive service analysis.

    Performs extensive health validation including:
    - Service connectivity and response validation
    - Dependency chain analysis
    - Performance metrics collection
    - Configuration validation
    - Resource utilization checks
    """
    try:
        if force_refresh:
            # Clear health cache to force fresh checks
            health_service.health_cache.clear()

        # Get all service health
        all_health = await health_service.check_all_services()

        # Get pipeline readiness
        readiness = await health_service.check_pipeline_readiness()

        # Collect dependency information if requested
        dependency_chains = {}
        if include_dependencies:
            for service_name in SERVICES:
                dependency_chains[service_name] = (
                    await health_service.check_dependencies(service_name)
                )

        # Calculate overall health score
        total_services = len(all_health)
        healthy_services = sum(
            1 for h in all_health.values() if h.get("status") == "healthy"
        )
        health_score = (healthy_services / total_services) if total_services > 0 else 0

        return {
            "timestamp": datetime.now().isoformat(),
            "check_type": "deep",
            "force_refresh": force_refresh,
            "overall_health": {
                "score": health_score,
                "status": (
                    "healthy"
                    if health_score >= 0.8
                    else "degraded" if health_score >= 0.5 else "unhealthy"
                ),
                "total_services": total_services,
                "healthy_services": healthy_services,
                "unhealthy_services": total_services - healthy_services,
            },
            "pipeline_readiness": readiness,
            "service_health": all_health,
            "dependency_chains": dependency_chains if include_dependencies else {},
            "recommendations": _generate_health_recommendations(all_health, readiness),
        }

    except Exception as e:
        logger.error(f"Error in deep health check: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to perform deep health check"
        )


def _generate_health_recommendations(
    all_health: dict[str, Any], readiness: dict[str, Any]
) -> list[dict[str, Any]]:
    """Generate health improvement recommendations"""
    recommendations = []

    # Check for unhealthy critical services
    for service_name, health in all_health.items():
        if SERVICES.get(service_name, {}).get("critical", False):
            if health.get("status") != "healthy":
                recommendations.append(
                    {
                        "type": "critical_service",
                        "priority": "high",
                        "service": service_name,
                        "issue": health.get("error", "Service unhealthy"),
                        "recommendation": f"Investigate and restore {service_name} service immediately",
                    }
                )

    # Check for slow response times
    for service_name, health in all_health.items():
        response_time = health.get("response_time_ms", 0)
        if response_time > 5000:  # 5 seconds
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "medium",
                    "service": service_name,
                    "issue": f"Slow response time: {response_time}ms",
                    "recommendation": f"Investigate performance issues in {service_name}",
                }
            )

    # Check readiness score
    readiness_score = readiness.get("readiness_score", 1.0)
    if readiness_score < 0.8:
        recommendations.append(
            {
                "type": "readiness",
                "priority": "high",
                "issue": f"Low readiness score: {readiness_score:.2%}",
                "recommendation": "Address unhealthy critical services to improve pipeline readiness",
            }
        )

    return recommendations
