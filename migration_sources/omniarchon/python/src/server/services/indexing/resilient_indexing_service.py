"""
Resilient Indexing Service for Archon

Provides robust document indexing with retry logic, circuit breaker patterns,
dead letter queue, and graceful degradation for the real-time indexing pipeline.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import httpx
from server.config.logfire_config import get_logger

logger = get_logger(__name__)


class IndexingStatus(Enum):
    """Indexing operation status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


@dataclass
class IndexingRequest:
    """Represents a document indexing request"""

    document_id: str
    project_id: str
    title: str
    content: dict[str, Any]
    document_type: str
    metadata: dict[str, Any]
    created_at: datetime
    retry_count: int = 0
    status: IndexingStatus = IndexingStatus.PENDING
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a service"""

    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    next_retry_time: Optional[datetime] = None


class ResilientIndexingService:
    """
    Resilient document indexing service with comprehensive error handling.

    Features:
    - Exponential backoff retry logic
    - Circuit breaker pattern for service failures
    - Dead letter queue for permanently failed operations
    - Graceful degradation when services are unavailable
    - Performance monitoring and health checks
    """

    def __init__(self):
        """Initialize the resilient indexing service"""
        self.indexing_queue: list[IndexingRequest] = []
        self.dead_letter_queue: list[IndexingRequest] = []
        self.circuit_breakers: dict[str, CircuitBreakerState] = {}
        self.processing = False

        # Configuration from environment variables
        self.max_retries = int(os.getenv("INDEXING_MAX_RETRIES", "3"))
        self.retry_base_delay = int(os.getenv("INDEXING_RETRY_DELAY", "1000"))  # ms
        self.timeout = int(os.getenv("INDEXING_TIMEOUT", "30"))  # seconds
        self.batch_size = int(os.getenv("INDEXING_BATCH_SIZE", "50"))
        self.batch_delay = int(os.getenv("INDEXING_BATCH_DELAY", "100"))  # ms
        self.circuit_breaker_threshold = int(
            os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5")
        )
        self.circuit_breaker_timeout = int(
            os.getenv("CIRCUIT_BREAKER_TIMEOUT", "30000")
        )  # ms
        self.dlq_max_size = int(os.getenv("DLQ_MAX_SIZE", "1000"))
        self.graceful_degradation = (
            os.getenv("GRACEFUL_DEGRADATION", "true").lower() == "true"
        )

        # Service URLs
        self.intelligence_service_url = os.getenv(
            "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
        )
        self.search_service_url = os.getenv(
            "SEARCH_SERVICE_URL", "http://archon-search:8055"
        )
        self.bridge_service_url = os.getenv(
            "BRIDGE_SERVICE_URL", "http://archon-bridge:8054"
        )

        # Initialize circuit breakers
        for service in ["intelligence", "search", "bridge"]:
            self.circuit_breakers[service] = CircuitBreakerState()

        logger.info(
            f"ResilientIndexingService initialized | max_retries={self.max_retries} | "
            f"timeout={self.timeout}s | batch_size={self.batch_size}"
        )

    async def start_processing(self):
        """Start the background processing loop"""
        if self.processing:
            logger.warning("Indexing service is already processing")
            return

        self.processing = True
        logger.info("Starting resilient indexing service processing loop")

        try:
            while self.processing:
                await self._process_batch()
                await asyncio.sleep(self.batch_delay / 1000.0)  # Convert ms to seconds
        except Exception as e:
            logger.error(f"Processing loop error: {e}")
        finally:
            self.processing = False

    async def stop_processing(self):
        """Stop the background processing loop"""
        logger.info("Stopping resilient indexing service")
        self.processing = False

    async def queue_document_indexing(self, request: IndexingRequest) -> bool:
        """
        Queue a document for indexing.

        Returns:
            bool: True if queued successfully, False if rejected
        """
        try:
            # Validate request
            if not request.document_id or not request.project_id:
                logger.warning("Invalid indexing request: missing required fields")
                return False

            # Check if auto-indexing is enabled
            if os.getenv("AUTO_INDEXING_ENABLED", "true").lower() != "true":
                logger.info(
                    f"Auto-indexing disabled, rejecting request for {request.document_id}"
                )
                return False

            # Add to queue
            self.indexing_queue.append(request)

            logger.info(
                f"Document queued for indexing | document_id={request.document_id} | "
                f"queue_size={len(self.indexing_queue)}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to queue document indexing: {e}")
            return False

    async def _process_batch(self):
        """Process a batch of indexing requests"""
        if not self.indexing_queue:
            return

        # Get batch of requests to process
        batch = self.indexing_queue[: self.batch_size]

        # Process requests in parallel with limited concurrency
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent operations
        tasks = [
            self._process_request_with_semaphore(semaphore, request)
            for request in batch
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        # Clean up processed requests from queue
        processed_ids = [req.document_id for req in batch]
        self.indexing_queue = [
            req for req in self.indexing_queue if req.document_id not in processed_ids
        ]

    async def _process_request_with_semaphore(
        self, semaphore: asyncio.Semaphore, request: IndexingRequest
    ):
        """Process a single request with concurrency control"""
        async with semaphore:
            await self._process_single_request(request)

    async def _process_single_request(self, request: IndexingRequest):
        """Process a single indexing request with comprehensive error handling"""
        try:
            request.status = IndexingStatus.PROCESSING

            logger.info(
                f"Processing indexing request | document_id={request.document_id} | "
                f"attempt={request.retry_count + 1}/{self.max_retries + 1}"
            )

            # Step 1: Intelligence service processing
            intelligence_success = await self._call_intelligence_service(request)

            if not intelligence_success:
                await self._handle_request_failure(
                    request, "Intelligence service processing failed"
                )
                return

            # Step 2: Search service vectorization (if intelligence succeeded)
            search_success = await self._call_search_service(request)

            if not search_success and not self.graceful_degradation:
                await self._handle_request_failure(
                    request, "Search service vectorization failed"
                )
                return

            # Step 3: Bridge service knowledge graph sync (optional)
            bridge_success = await self._call_bridge_service(request)

            # Consider success if at least intelligence service succeeded
            if intelligence_success:
                request.status = IndexingStatus.COMPLETED
                logger.info(
                    f"Document indexing completed | document_id={request.document_id} | "
                    f"intelligence={intelligence_success} | search={search_success} | "
                    f"bridge={bridge_success}"
                )

                # Update metrics
                await self._update_success_metrics(request)
            else:
                await self._handle_request_failure(request, "All indexing steps failed")

        except Exception as e:
            await self._handle_request_failure(request, f"Unexpected error: {e!s}")

    async def _call_intelligence_service(self, request: IndexingRequest) -> bool:
        """Call the intelligence service for document processing"""
        service_name = "intelligence"

        # Check circuit breaker
        if not self._check_circuit_breaker(service_name):
            logger.warning(f"Circuit breaker OPEN for {service_name} service")
            return False

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "document_id": request.document_id,
                    "project_id": request.project_id,
                    "title": request.title,
                    "content": request.content,
                    "document_type": request.document_type,
                    "metadata": request.metadata,
                }

                response = await client.post(
                    f"{self.intelligence_service_url}/process/document", json=payload
                )

                if response.status_code == 200:
                    self._record_service_success(service_name)
                    return True
                else:
                    self._record_service_failure(
                        service_name, f"HTTP {response.status_code}"
                    )
                    return False

        except (httpx.TimeoutException, httpx.ConnectTimeout) as e:
            self._record_service_failure(service_name, f"Timeout: {e!s}")
            return False
        except Exception as e:
            self._record_service_failure(service_name, f"Error: {e!s}")
            return False

    async def _call_search_service(self, request: IndexingRequest) -> bool:
        """Call the search service for vectorization"""
        service_name = "search"

        # Check circuit breaker
        if not self._check_circuit_breaker(service_name):
            logger.warning(f"Circuit breaker OPEN for {service_name} service")
            return False

        try:
            # Convert content to text for vectorization
            content_text = self._extract_text_content(request.content, request.title)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "document_id": request.document_id,
                    "project_id": request.project_id,
                    "content": content_text,
                    "metadata": {
                        **request.metadata,
                        "title": request.title,
                        "document_type": request.document_type,
                    },
                    "source_path": f"archon://projects/{request.project_id}/documents/{request.document_id}",
                }

                response = await client.post(
                    f"{self.search_service_url}/vectorize/document", json=payload
                )

                if response.status_code == 200:
                    self._record_service_success(service_name)
                    return True
                else:
                    self._record_service_failure(
                        service_name, f"HTTP {response.status_code}"
                    )
                    return False

        except Exception as e:
            self._record_service_failure(service_name, f"Error: {e!s}")
            return False

    async def _call_bridge_service(self, request: IndexingRequest) -> bool:
        """Call the bridge service for knowledge graph sync"""
        service_name = "bridge"

        # Check circuit breaker
        if not self._check_circuit_breaker(service_name):
            logger.warning(f"Circuit breaker OPEN for {service_name} service")
            return False

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "document_id": request.document_id,
                    "project_id": request.project_id,
                    "title": request.title,
                    "content": request.content,
                    "document_type": request.document_type,
                    "metadata": request.metadata,
                }

                response = await client.post(
                    f"{self.bridge_service_url}/sync/realtime-document", json=payload
                )

                if response.status_code == 200:
                    self._record_service_success(service_name)
                    return True
                else:
                    self._record_service_failure(
                        service_name, f"HTTP {response.status_code}"
                    )
                    return False

        except Exception as e:
            self._record_service_failure(service_name, f"Error: {e!s}")
            return False

    def _extract_text_content(self, content: dict[str, Any], title: str) -> str:
        """Extract text content from structured content"""
        if isinstance(content, dict):
            content_text = ""
            if "text" in content:
                content_text = content["text"]
            elif "overview" in content:
                content_text = content["overview"]
            elif "description" in content:
                content_text = content["description"]
            else:
                # Flatten all string values
                content_text = " ".join(
                    str(value)
                    for value in content.values()
                    if isinstance(value, str | int | float)
                )
        else:
            content_text = str(content)

        return f"{title}\n\n{content_text}".strip()

    async def _handle_request_failure(
        self, request: IndexingRequest, error_message: str
    ):
        """Handle a failed indexing request with retry logic"""
        request.last_error = error_message
        request.retry_count += 1

        if request.retry_count <= self.max_retries:
            # Schedule retry with exponential backoff
            delay_ms = self.retry_base_delay * (2 ** (request.retry_count - 1))
            request.next_retry_at = datetime.utcnow() + timedelta(milliseconds=delay_ms)
            request.status = IndexingStatus.RETRYING

            logger.warning(
                f"Indexing failed, scheduling retry | document_id={request.document_id} | "
                f"attempt={request.retry_count}/{self.max_retries + 1} | "
                f"retry_in={delay_ms}ms | error={error_message}"
            )

            # Re-queue for retry
            await asyncio.sleep(delay_ms / 1000.0)
            self.indexing_queue.append(request)
        else:
            # Move to dead letter queue
            request.status = IndexingStatus.DEAD_LETTER
            await self._move_to_dead_letter_queue(request)

            logger.error(
                f"Indexing permanently failed | document_id={request.document_id} | "
                f"max_retries_exceeded | error={error_message}"
            )

    async def _move_to_dead_letter_queue(self, request: IndexingRequest):
        """Move a failed request to the dead letter queue"""
        self.dead_letter_queue.append(request)

        # Cleanup old entries if DLQ is getting too large
        if len(self.dead_letter_queue) > self.dlq_max_size:
            # Remove oldest entries
            self.dead_letter_queue = self.dead_letter_queue[-self.dlq_max_size :]
            logger.warning(
                f"Dead letter queue cleanup performed, size: {len(self.dead_letter_queue)}"
            )

    def _check_circuit_breaker(self, service_name: str) -> bool:
        """Check if circuit breaker allows requests to the service"""
        breaker = self.circuit_breakers.get(service_name)
        if not breaker:
            return True

        now = datetime.utcnow()

        if breaker.state == "OPEN":
            # Check if enough time has passed to try half-open
            if breaker.next_retry_time and now >= breaker.next_retry_time:
                breaker.state = "HALF_OPEN"
                logger.info(f"Circuit breaker for {service_name} moving to HALF_OPEN")
                return True
            else:
                return False

        return True  # CLOSED or HALF_OPEN

    def _record_service_success(self, service_name: str):
        """Record a successful service call"""
        breaker = self.circuit_breakers.get(service_name)
        if breaker:
            breaker.failure_count = 0
            breaker.state = "CLOSED"
            breaker.last_failure_time = None
            breaker.next_retry_time = None

    def _record_service_failure(self, service_name: str, error: str):
        """Record a failed service call"""
        breaker = self.circuit_breakers.get(service_name)
        if not breaker:
            return

        breaker.failure_count += 1
        breaker.last_failure_time = datetime.utcnow()

        # Open circuit breaker if threshold exceeded
        if breaker.failure_count >= self.circuit_breaker_threshold:
            breaker.state = "OPEN"
            breaker.next_retry_time = datetime.utcnow() + timedelta(
                milliseconds=self.circuit_breaker_timeout
            )
            logger.warning(
                f"Circuit breaker OPEN for {service_name} | failures={breaker.failure_count} | "
                f"retry_after={self.circuit_breaker_timeout}ms"
            )

    async def _update_success_metrics(self, request: IndexingRequest):
        """Update success metrics for monitoring"""
        # This would integrate with your metrics system
        logger.debug(f"Indexing success metrics updated for {request.document_id}")

    async def get_service_health(self) -> dict[str, Any]:
        """Get comprehensive service health information"""
        return {
            "queue_size": len(self.indexing_queue),
            "dlq_size": len(self.dead_letter_queue),
            "processing": self.processing,
            "circuit_breakers": {
                name: {
                    "state": breaker.state,
                    "failure_count": breaker.failure_count,
                    "last_failure": (
                        breaker.last_failure_time.isoformat()
                        if breaker.last_failure_time
                        else None
                    ),
                }
                for name, breaker in self.circuit_breakers.items()
            },
            "configuration": {
                "max_retries": self.max_retries,
                "timeout": self.timeout,
                "batch_size": self.batch_size,
                "graceful_degradation": self.graceful_degradation,
            },
        }

    async def retry_dead_letter_queue(self) -> int:
        """Retry all items in the dead letter queue"""
        if not self.dead_letter_queue:
            return 0

        retry_count = 0
        items_to_retry = self.dead_letter_queue.copy()
        self.dead_letter_queue.clear()

        for request in items_to_retry:
            # Reset retry count for dead letter queue items
            request.retry_count = 0
            request.status = IndexingStatus.PENDING
            request.last_error = None

            if await self.queue_document_indexing(request):
                retry_count += 1

        logger.info(f"Retried {retry_count} items from dead letter queue")
        return retry_count


# Global singleton instance
_indexing_service: Optional[ResilientIndexingService] = None


def get_indexing_service() -> ResilientIndexingService:
    """Get the global indexing service instance"""
    global _indexing_service
    if _indexing_service is None:
        _indexing_service = ResilientIndexingService()
    return _indexing_service


async def queue_document_for_indexing(
    document_id: str,
    project_id: str,
    title: str,
    content: dict[str, Any],
    document_type: str,
    metadata: dict[str, Any],
) -> bool:
    """
    Convenience function to queue a document for resilient indexing.

    Returns:
        bool: True if queued successfully
    """
    service = get_indexing_service()

    request = IndexingRequest(
        document_id=document_id,
        project_id=project_id,
        title=title,
        content=content,
        document_type=document_type,
        metadata=metadata,
        created_at=datetime.utcnow(),
    )

    return await service.queue_document_indexing(request)
