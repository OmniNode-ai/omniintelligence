"""
Workflow Coordinator HTTP Client - ONEX Effect Node

Async HTTP client for OmniNode Bridge Workflow Coordinator service with circuit breaker
pattern, retry logic, workflow polling, and comprehensive error handling.

ONEX Pattern: Effect Node (External HTTP I/O)
Performance Target: <30s for workflow trigger (synchronous), <5s for status queries
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from clients.workflow_coordinator_exceptions import (
    WorkflowAlreadyCompletedError,
    WorkflowCoordinatorError,
    WorkflowCoordinatorRateLimitError,
    WorkflowCoordinatorServerError,
    WorkflowCoordinatorTimeoutError,
    WorkflowCoordinatorUnavailableError,
    WorkflowCoordinatorValidationError,
    WorkflowNotFoundError,
)
from clients.workflow_coordinator_models import (
    CancelWorkflowResponse,
    CoordinationStrategy,
    ListActiveWorkflowsResponse,
    TriggerWorkflowRequest,
    TriggerWorkflowResponse,
    WorkflowNode,
    WorkflowStatus,
    WorkflowStatusResponse,
)
from infrastructure import AsyncCircuitBreaker, CircuitBreakerError

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class WorkflowCoordinatorClient:
    """
    Async HTTP client for OmniNode Bridge Workflow Coordinator service.

    ONEX Node Type: Effect (External HTTP I/O)

    Features:
    - Circuit breaker pattern (opens after 5 failures, resets after 60s)
    - Retry logic with exponential backoff (max 3 retries)
    - Timeout handling (30s default for triggers, 5s for queries)
    - Workflow polling with configurable intervals
    - Health check integration with periodic polling
    - Comprehensive error logging and metrics
    - Graceful degradation patterns

    Architecture:
    - Uses httpx async HTTP client for efficient connection pooling
    - Circuit breaker prevents cascade failures
    - Retries on transient errors (503, 429, timeouts)
    - Fails fast on validation errors (422, 400)

    Performance:
    - Target: <30s for workflow trigger, <5s for status queries
    - Circuit breaker prevents unnecessary retries when service is down
    - Health checks run every 30 seconds in background
    - Workflow polling with configurable intervals (default: 5s)

    Usage:
        async with WorkflowCoordinatorClient() as client:
            response = await client.trigger_workflow(request)
            status = await client.poll_workflow_completion(
                workflow_id=response.workflow_id,
                timeout_seconds=600
            )
    """

    def __init__(
        self,
        base_url: str = "http://omninode-bridge-workflow-coordinator:8006",
        default_timeout_seconds: float = 30.0,
        query_timeout_seconds: float = 5.0,
        max_retries: int = 3,
        circuit_breaker_enabled: bool = True,
    ):
        """
        Initialize workflow coordinator HTTP client.

        Args:
            base_url: Base URL for workflow coordinator service
            default_timeout_seconds: Default request timeout in seconds (default: 30.0)
            query_timeout_seconds: Timeout for query operations (default: 5.0)
            max_retries: Maximum retry attempts (default: 3)
            circuit_breaker_enabled: Enable circuit breaker (default: True)
        """
        self.base_url = base_url.rstrip("/")
        self.default_timeout_seconds = default_timeout_seconds
        self.query_timeout_seconds = query_timeout_seconds
        self.max_retries = max_retries

        # HTTP client with connection pooling
        self.client: Optional[httpx.AsyncClient] = None

        # Circuit breaker configuration
        self.circuit_breaker_enabled = circuit_breaker_enabled
        self.circuit_breaker: Optional[AsyncCircuitBreaker] = None

        if circuit_breaker_enabled:
            self.circuit_breaker = AsyncCircuitBreaker(
                failure_threshold=5,  # Open after 5 failures
                recovery_timeout_seconds=60,  # Reset after 60 seconds
                half_open_max_attempts=3,
                name="workflow_coordinator_service",
            )

        # Health check state
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_healthy: bool = True
        self._last_health_check: Optional[datetime] = None

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_errors": 0,
            "circuit_breaker_opens": 0,
            "retries_attempted": 0,
            "total_duration_ms": 0.0,
            "workflows_triggered": 0,
            "workflows_completed": 0,
            "workflows_failed": 0,
            "workflows_cancelled": 0,
        }

        logger.info(
            f"WorkflowCoordinatorClient initialized: base_url={base_url}, "
            f"timeout={default_timeout_seconds}s, max_retries={max_retries}, "
            f"circuit_breaker={circuit_breaker_enabled}"
        )

    # ========================================================================
    # Context Manager Protocol
    # ========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize HTTP client and start health checks."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.default_timeout_seconds),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            )

            # Start health check background task
            self._health_check_task = asyncio.create_task(self._periodic_health_check())

            logger.info("HTTP client connected and health checks started")

    async def close(self) -> None:
        """Close HTTP client and stop health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        if self.client:
            await self.client.aclose()
            self.client = None

            logger.info("HTTP client closed")

    # ========================================================================
    # Core Workflow API Methods
    # ========================================================================

    async def trigger_workflow(
        self,
        workflow_name: str,
        workflow_nodes: List[WorkflowNode],
        coordination_strategy: CoordinationStrategy = CoordinationStrategy.DAG,
        workflow_parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 3600,
        enable_checkpointing: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None,
    ) -> TriggerWorkflowResponse:
        """
        Trigger a new workflow execution.

        Args:
            workflow_name: Name/identifier of the workflow to execute
            workflow_nodes: List of nodes to execute in the workflow
            coordination_strategy: Workflow coordination strategy (default: DAG)
            workflow_parameters: Global workflow parameters
            timeout_seconds: Maximum time for workflow execution (default: 3600)
            enable_checkpointing: Enable workflow checkpointing (default: True)
            metadata: Additional workflow metadata
            timeout_override: Optional HTTP timeout override in seconds

        Returns:
            TriggerWorkflowResponse with workflow ID and initial status

        Raises:
            WorkflowCoordinatorUnavailableError: Service unavailable
            WorkflowCoordinatorTimeoutError: Request timed out
            WorkflowCoordinatorValidationError: Request validation failed
            WorkflowCoordinatorError: Other errors
        """
        if not self.client:
            raise WorkflowCoordinatorError(
                "Client not connected. Use async context manager."
            )

        # Build request
        request = TriggerWorkflowRequest(
            workflow_name=workflow_name,
            coordination_strategy=coordination_strategy,
            workflow_nodes=workflow_nodes,
            workflow_parameters=workflow_parameters or {},
            timeout_seconds=timeout_seconds,
            enable_checkpointing=enable_checkpointing,
            metadata=metadata or {},
        )

        # Execute with retry logic
        response = await self._execute_with_retry(
            method="POST",
            endpoint="/api/workflows/trigger",
            json_data=request.model_dump(),
            timeout_override=timeout_override,
            response_model=TriggerWorkflowResponse,
        )

        self.metrics["workflows_triggered"] += 1
        logger.info(f"Workflow triggered successfully: {response.workflow_id}")

        return response

    async def get_workflow_status(
        self, workflow_id: UUID, timeout_override: Optional[float] = None
    ) -> WorkflowStatusResponse:
        """
        Get detailed status of a workflow execution.

        Args:
            workflow_id: Workflow execution ID
            timeout_override: Optional timeout override (default: query_timeout_seconds)

        Returns:
            WorkflowStatusResponse with complete workflow status

        Raises:
            WorkflowNotFoundError: Workflow not found
            WorkflowCoordinatorError: Other errors
        """
        if not self.client:
            raise WorkflowCoordinatorError(
                "Client not connected. Use async context manager."
            )

        timeout = timeout_override or self.query_timeout_seconds

        response = await self._execute_with_retry(
            method="GET",
            endpoint=f"/api/workflows/{workflow_id}/status",
            timeout_override=timeout,
            response_model=WorkflowStatusResponse,
        )

        return response

    async def list_active_workflows(
        self, timeout_override: Optional[float] = None
    ) -> ListActiveWorkflowsResponse:
        """
        List all active workflows.

        Args:
            timeout_override: Optional timeout override (default: query_timeout_seconds)

        Returns:
            ListActiveWorkflowsResponse with list of active workflows

        Raises:
            WorkflowCoordinatorError: Request errors
        """
        if not self.client:
            raise WorkflowCoordinatorError(
                "Client not connected. Use async context manager."
            )

        timeout = timeout_override or self.query_timeout_seconds

        response = await self._execute_with_retry(
            method="GET",
            endpoint="/api/workflows/active",
            timeout_override=timeout,
            response_model=ListActiveWorkflowsResponse,
        )

        return response

    async def cancel_workflow(
        self, workflow_id: UUID, timeout_override: Optional[float] = None
    ) -> CancelWorkflowResponse:
        """
        Cancel a running workflow.

        Args:
            workflow_id: Workflow execution ID to cancel
            timeout_override: Optional timeout override

        Returns:
            CancelWorkflowResponse with cancellation status

        Raises:
            WorkflowNotFoundError: Workflow not found
            WorkflowAlreadyCompletedError: Workflow already completed
            WorkflowCoordinatorError: Other errors
        """
        if not self.client:
            raise WorkflowCoordinatorError(
                "Client not connected. Use async context manager."
            )

        timeout = timeout_override or self.default_timeout_seconds

        response = await self._execute_with_retry(
            method="POST",
            endpoint=f"/api/workflows/{workflow_id}/cancel",
            timeout_override=timeout,
            response_model=CancelWorkflowResponse,
        )

        self.metrics["workflows_cancelled"] += 1
        logger.info(f"Workflow cancelled successfully: {workflow_id}")

        return response

    async def poll_workflow_completion(
        self,
        workflow_id: UUID,
        timeout_seconds: int = 600,
        poll_interval_seconds: float = 5.0,
        raise_on_failure: bool = True,
    ) -> WorkflowStatusResponse:
        """
        Poll workflow status until completion or timeout.

        Args:
            workflow_id: Workflow execution ID to poll
            timeout_seconds: Maximum time to poll (default: 600s = 10 minutes)
            poll_interval_seconds: Interval between polls (default: 5.0s)
            raise_on_failure: Raise exception if workflow fails (default: True)

        Returns:
            WorkflowStatusResponse with final workflow status

        Raises:
            WorkflowCoordinatorTimeoutError: Polling timeout exceeded
            WorkflowCoordinatorError: Workflow failed (if raise_on_failure=True)
            WorkflowNotFoundError: Workflow not found

        Example:
            async with WorkflowCoordinatorClient() as client:
                trigger_response = await client.trigger_workflow(...)
                final_status = await client.poll_workflow_completion(
                    workflow_id=trigger_response.workflow_id,
                    timeout_seconds=600,
                    poll_interval_seconds=5.0
                )
        """
        start_time = time.perf_counter()
        last_status = None

        logger.info(
            f"Starting workflow polling: workflow_id={workflow_id}, "
            f"timeout={timeout_seconds}s, interval={poll_interval_seconds}s"
        )

        while True:
            elapsed = time.perf_counter() - start_time

            if elapsed > timeout_seconds:
                raise WorkflowCoordinatorTimeoutError(
                    f"Workflow polling timeout exceeded: {timeout_seconds}s",
                    timeout_seconds=timeout_seconds,
                )

            # Get current status
            status = await self.get_workflow_status(workflow_id)
            last_status = status

            # Log progress if changed
            if status.status != getattr(last_status, "status", None):
                logger.info(
                    f"Workflow status update: {workflow_id} -> {status.status} "
                    f"(progress: {status.progress_percentage:.1f}%)"
                )

            # Check terminal states
            if status.status == WorkflowStatus.COMPLETED:
                self.metrics["workflows_completed"] += 1
                logger.info(
                    f"Workflow completed successfully: {workflow_id} "
                    f"(duration: {status.duration_seconds:.2f}s)"
                )
                return status

            elif status.status == WorkflowStatus.FAILED:
                self.metrics["workflows_failed"] += 1
                error_msg = (
                    f"Workflow failed: {workflow_id} "
                    f"(error: {status.error_message or 'unknown'})"
                )
                logger.error(error_msg)

                if raise_on_failure:
                    raise WorkflowCoordinatorError(
                        error_msg,
                        response_data={
                            "workflow_id": str(workflow_id),
                            "error_message": status.error_message,
                            "failed_node_id": (
                                str(status.failed_node_id)
                                if status.failed_node_id
                                else None
                            ),
                        },
                    )
                return status

            elif status.status == WorkflowStatus.CANCELLED:
                logger.info(f"Workflow was cancelled: {workflow_id}")
                return status

            # Wait before next poll
            await asyncio.sleep(poll_interval_seconds)

    # ========================================================================
    # Request Execution with Retry Logic
    # ========================================================================

    async def _execute_with_retry(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None,
        response_model: Optional[type] = None,
    ) -> Any:
        """
        Execute request with exponential backoff retry logic.

        Retries on:
        - 503 Service Unavailable
        - 429 Rate Limit
        - Timeout errors
        - Connection errors

        Does NOT retry on:
        - 422 Validation errors
        - 400 Bad Request
        - 404 Not Found
        - 409 Conflict

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json_data: Optional JSON payload
            timeout_override: Optional timeout override
            response_model: Optional Pydantic model for response parsing

        Returns:
            Parsed response (response_model instance or dict)

        Raises:
            Various WorkflowCoordinatorError subclasses
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                # Execute the request
                result = await self._execute_request(
                    method=method,
                    endpoint=endpoint,
                    json_data=json_data,
                    timeout_override=timeout_override,
                    response_model=response_model,
                )

                # Success - record metrics
                self.metrics["successful_requests"] += 1
                if attempt > 0:
                    self.metrics["retries_attempted"] += attempt
                    logger.info(f"Request succeeded after {attempt} retries")

                return result

            except (
                WorkflowCoordinatorUnavailableError,
                WorkflowCoordinatorTimeoutError,
                WorkflowCoordinatorRateLimitError,
                WorkflowCoordinatorServerError,
            ) as e:
                last_error = e

                # Check if we should retry
                if attempt < self.max_retries:
                    # Calculate exponential backoff delay
                    delay = min(2**attempt, 10)  # Cap at 10 seconds

                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )

                    await asyncio.sleep(delay)
                    continue
                else:
                    # Max retries exceeded
                    logger.error(
                        f"Request failed after {self.max_retries + 1} attempts: {e}"
                    )
                    self.metrics["failed_requests"] += 1
                    raise

            except (
                WorkflowCoordinatorValidationError,
                WorkflowNotFoundError,
                WorkflowAlreadyCompletedError,
                WorkflowCoordinatorError,
            ) as e:
                # Don't retry validation errors or specific errors
                logger.error(f"Request failed with non-retryable error: {e}")
                self.metrics["failed_requests"] += 1
                raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error
        raise WorkflowCoordinatorError("Unknown error during request execution")

    async def _execute_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None,
        response_model: Optional[type] = None,
    ) -> Any:
        """
        Execute single HTTP request to workflow coordinator service.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json_data: Optional JSON payload
            timeout_override: Optional timeout override
            response_model: Optional Pydantic model for response

        Returns:
            Parsed response

        Raises:
            Various WorkflowCoordinatorError subclasses
        """
        start_time = time.perf_counter()
        self.metrics["total_requests"] += 1

        url = f"{self.base_url}{endpoint}"
        timeout = timeout_override or self.default_timeout_seconds

        try:
            logger.debug(f"Sending {method} request to {url}")

            # Execute with circuit breaker if enabled
            if self.circuit_breaker_enabled and self.circuit_breaker:
                response = await self.circuit_breaker.call_async(
                    self._make_http_request, method, url, json_data, timeout
                )
            else:
                response = await self._make_http_request(
                    method, url, json_data, timeout
                )

            # Parse response
            result = self._parse_response(response, response_model)

            # Record metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics["total_duration_ms"] += duration_ms

            logger.debug(f"Request completed in {duration_ms:.2f}ms")

            return result

        except httpx.TimeoutException as e:
            self.metrics["timeout_errors"] += 1
            logger.error(f"Request timed out after {timeout}s: {e}")
            raise WorkflowCoordinatorTimeoutError(
                f"Request timed out after {timeout}s", timeout_seconds=timeout
            )

        except httpx.NetworkError as e:
            logger.error(f"Network error occurred: {e}")
            raise WorkflowCoordinatorUnavailableError(
                f"Network error connecting to workflow coordinator service: {e}"
            )

        except CircuitBreakerError as e:
            self.metrics["circuit_breaker_opens"] += 1
            logger.error(f"Circuit breaker prevented request: {e}")
            raise WorkflowCoordinatorUnavailableError(
                "Circuit breaker is open - service unavailable"
            )

        except Exception as e:
            logger.error(f"Unexpected error during request: {e}", exc_info=True)
            raise WorkflowCoordinatorError(f"Unexpected error: {e}")

    async def _make_http_request(
        self, method: str, url: str, json_data: Optional[Dict[str, Any]], timeout: float
    ) -> httpx.Response:
        """
        Make the actual HTTP request.

        Separated to allow circuit breaker wrapping.

        Args:
            method: HTTP method
            url: Request URL
            json_data: Optional JSON payload
            timeout: Timeout in seconds

        Returns:
            HTTP response

        Raises:
            httpx exceptions
        """
        response = await self.client.request(
            method=method, url=url, json=json_data, timeout=timeout
        )

        return response

    def _parse_response(
        self, response: httpx.Response, response_model: Optional[type] = None
    ) -> Any:
        """
        Parse HTTP response into appropriate model or dict.

        Args:
            response: HTTP response
            response_model: Optional Pydantic model for parsing

        Returns:
            Parsed response (model instance or dict)

        Raises:
            Various WorkflowCoordinatorError subclasses based on status code
        """
        # Check status code
        if response.status_code == 200:
            try:
                data = response.json()

                if response_model:
                    return response_model(**data)
                return data

            except Exception as e:
                logger.error(f"Failed to parse response: {e}", exc_info=True)
                raise WorkflowCoordinatorError(f"Failed to parse response: {e}")

        elif response.status_code == 404:
            # Not found - extract workflow ID if present
            try:
                error_data = response.json()
                workflow_id = error_data.get("workflow_id")
                raise WorkflowNotFoundError(
                    workflow_id=workflow_id or "unknown",
                    message=error_data.get("message", "Workflow not found"),
                )
            except (ValueError, KeyError):
                raise WorkflowNotFoundError(workflow_id="unknown")

        elif response.status_code == 409:
            # Conflict - workflow already completed
            try:
                error_data = response.json()
                workflow_id = error_data.get("workflow_id")
                raise WorkflowAlreadyCompletedError(
                    workflow_id=workflow_id or "unknown",
                    message=error_data.get("message", "Workflow already completed"),
                )
            except (ValueError, KeyError):
                raise WorkflowAlreadyCompletedError(workflow_id="unknown")

        elif response.status_code == 422:
            # Validation error
            error_data = response.json()
            raise WorkflowCoordinatorValidationError(
                f"Request validation failed: {error_data}",
                validation_errors=error_data.get("detail", []),
            )

        elif response.status_code == 429:
            # Rate limit
            retry_after = response.headers.get("Retry-After")
            raise WorkflowCoordinatorRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
            )

        elif response.status_code == 503:
            # Service unavailable
            raise WorkflowCoordinatorUnavailableError(
                "Workflow coordinator service is temporarily unavailable"
            )

        elif 500 <= response.status_code < 600:
            # Server error
            error_data = response.json() if response.content else {}
            raise WorkflowCoordinatorServerError(
                f"Server error: {response.status_code}",
                status_code=response.status_code,
                response_data=error_data,
            )

        else:
            # Other error
            raise WorkflowCoordinatorError(
                f"Unexpected status code: {response.status_code}",
                status_code=response.status_code,
            )

    # ========================================================================
    # Health Checks
    # ========================================================================

    async def check_health(self) -> Dict[str, Any]:
        """
        Check health of workflow coordinator service.

        Returns:
            Health check result with service status and metrics
        """
        if not self.client:
            return {"healthy": False, "error": "Client not connected"}

        try:
            start_time = time.perf_counter()
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=2.0,  # Short timeout for health checks
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            is_healthy = response.status_code == 200
            self._is_healthy = is_healthy
            self._last_health_check = datetime.now(timezone.utc)

            return {
                "healthy": is_healthy,
                "status_code": response.status_code,
                "response_time_ms": duration_ms,
                "last_check": self._last_health_check.isoformat(),
            }

        except Exception as e:
            self._is_healthy = False
            self._last_health_check = datetime.now(timezone.utc)

            logger.warning(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "last_check": self._last_health_check.isoformat(),
            }

    async def _periodic_health_check(self) -> None:
        """
        Background task for periodic health checks.

        Runs every 30 seconds to monitor service health.
        """
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self.check_health()
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic health check: {e}", exc_info=True)

    # ========================================================================
    # Metrics and Monitoring
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive client metrics.

        Returns:
            Dictionary with request statistics and performance data
        """
        total_requests = self.metrics["total_requests"]

        return {
            **self.metrics,
            "success_rate": (
                self.metrics["successful_requests"] / total_requests
                if total_requests > 0
                else 0.0
            ),
            "avg_duration_ms": (
                self.metrics["total_duration_ms"] / self.metrics["successful_requests"]
                if self.metrics["successful_requests"] > 0
                else 0.0
            ),
            "circuit_breaker_state": (
                self.circuit_breaker.current_state
                if self.circuit_breaker
                else "disabled"
            ),
            "is_healthy": self._is_healthy,
            "last_health_check": (
                self._last_health_check.isoformat() if self._last_health_check else None
            ),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "timeout_errors": 0,
            "circuit_breaker_opens": 0,
            "retries_attempted": 0,
            "total_duration_ms": 0.0,
            "workflows_triggered": 0,
            "workflows_completed": 0,
            "workflows_failed": 0,
            "workflows_cancelled": 0,
        }
        logger.info("Metrics reset")
