"""
Intelligence service client for document enrichment.

Handles communication with the intelligence service including
timeout management, circuit breaker integration, and error handling.
"""

import asyncio
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import aiohttp
import structlog

from .config import get_config

logger = structlog.get_logger(__name__)


def get_intelligence_timeout(content_size: int, base_timeout: int = 900) -> int:
    """
    Get fixed timeout for intelligence service calls.

    NOTE: This function returns a fixed timeout value and does NOT adapt based on
    content size. The name was changed from calculate_adaptive_timeout() to reflect
    the actual behavior. Pattern matching against 25K+ patterns requires a consistent
    generous timeout regardless of file size.

    IMPORTANT: Uses base_timeout from config, not hardcoded values.
    This ensures we respect INTELLIGENCE_TIMEOUT environment variable.

    Args:
        content_size: File size in bytes (currently unused, kept for API compatibility)
        base_timeout: Configured timeout in seconds (from INTELLIGENCE_TIMEOUT env var)
                      Default: 900s (15 minutes)

    Returns:
        Timeout in seconds (fixed at base_timeout value)
    """
    # Return fixed timeout for all files
    # Pattern matching against 25K+ patterns can take >60s even for small files
    return base_timeout


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for intelligence service calls.

    Tracks failures and opens circuit to prevent cascading failures.
    """

    def __init__(
        self, failure_threshold: int = 5, timeout: int = 30, success_threshold: int = 3
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures to open circuit
            timeout: Seconds before attempting half-open
            success_threshold: Consecutive successes to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None

        self.logger = logger.bind(component="circuit_breaker")

    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.logger.info("circuit_entering_half_open")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            # Execute function
            result = await func(*args, **kwargs)

            # Record success
            self._on_success()

            return result

        except Exception as e:
            # Record failure
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset to half-open."""
        if self.last_failure_time is None:
            return False

        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.success_count += 1

        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.success_threshold:
                self.logger.info("circuit_closing", success_count=self.success_count)
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.logger.warning("circuit_opening", failure_count=self.failure_count)
            self.state = CircuitState.OPEN

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN


class IntelligenceServiceClient:
    """Client for intelligence service document processing."""

    def __init__(self):
        """Initialize intelligence service client."""
        self.config = get_config()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_breaker_threshold,
            timeout=self.config.circuit_breaker_timeout,
            success_threshold=self.config.circuit_breaker_success_threshold,
        )
        self.session: Optional[aiohttp.ClientSession] = None

        self.logger = logger.bind(
            component="intelligence_client",
            service_url=self.config.intelligence_service_url,
            instance_id=self.config.instance_id,
        )

    async def start(self) -> None:
        """Start HTTP session."""
        timeout = aiohttp.ClientTimeout(total=self.config.intelligence_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        self.logger.info("intelligence_client_started")

    async def stop(self) -> None:
        """Stop HTTP session."""
        if self.session:
            await self.session.close()
        self.logger.info("intelligence_client_stopped")

    async def process_document(
        self,
        file_path: str,
        content: str,
        project_name: str,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process document through intelligence service.

        Args:
            file_path: Path to the document
            content: Document content
            project_name: Project name
            correlation_id: Optional correlation ID for tracing

        Returns:
            Intelligence processing results

        Raises:
            Exception: If processing fails or circuit is open
        """
        if not self.session:
            raise RuntimeError("Client not started")

        log = self.logger.bind(
            file_path=file_path,
            project_name=project_name,
            correlation_id=correlation_id,
        )

        # Log detailed enrichment start
        log.info(
            "🔬 [ENRICHMENT] Starting document enrichment pipeline",
            content_size=len(content.encode("utf-8")) if content else 0,
            file_extension=(
                file_path.split(".")[-1] if file_path and "." in file_path else "none"
            ),
            circuit_breaker_enabled=self.config.circuit_breaker_enabled,
            circuit_state=(
                self.circuit_breaker.state.value
                if self.config.circuit_breaker_enabled
                else "disabled"
            ),
        )

        # Process with or without circuit breaker protection
        if self.config.circuit_breaker_enabled:
            result = await self.circuit_breaker.call(
                self._call_intelligence_service,
                file_path=file_path,
                content=content,
                project_name=project_name,
            )
        else:
            # Circuit breaker disabled - call directly
            result = await self._call_intelligence_service(
                file_path=file_path,
                content=content,
                project_name=project_name,
            )

        # Extract and log content hash from result
        content_hash = result.get("content_hash") or result.get("checksum")

        # Log detailed enrichment completion
        log.info(
            "✅ [ENRICHMENT] Document enrichment completed",
            has_entities=bool(result.get("entities")),
            entity_count=len(result.get("entities", [])),
            entity_types=list(
                set(
                    e.get("entity_type")
                    for e in result.get("entities", [])
                    if e.get("entity_type")
                )
            )[:10],
            has_patterns=bool(result.get("patterns")),
            pattern_count=len(result.get("patterns", [])),
            quality_score=result.get("quality_score"),
            has_embeddings=bool(result.get("embeddings_generated")),
            content_hash=(
                content_hash[:16] + "..."
                if content_hash and len(content_hash) > 16
                else content_hash
            ),
            has_content_hash=bool(content_hash),
            result_keys=list(result.keys()),
        )

        # Warn if hash is missing
        if not content_hash:
            log.warning(
                "⚠️  [HASH_MISSING] No content hash found in intelligence result - "
                "this may indicate the hash was not propagated through the pipeline",
                file_path=file_path,
            )

        return result

    async def _call_intelligence_service(
        self, file_path: str, content: str, project_name: str
    ) -> Dict[str, Any]:
        """
        Make HTTP call to intelligence service.

        Args:
            file_path: Path to the document
            content: Document content
            project_name: Project name

        Returns:
            Intelligence processing results

        Raises:
            Exception: If HTTP call fails
        """
        url = f"{self.config.intelligence_service_url}/process/document"

        # Extract filename from file_path
        filename = file_path.split("/")[-1] if file_path else "unknown"

        # Detect document type from extension
        doc_type = "code"  # default
        if filename.endswith((".md", ".txt", ".rst", ".adoc")):
            doc_type = "documentation"
        elif filename.endswith(
            (".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".conf")
        ):
            doc_type = "configuration"
        elif (
            "test_" in filename
            or "_test." in filename
            or ".test." in filename
            or ".spec." in filename
        ):
            doc_type = "test"

        # Extract file extension from filename
        file_extension = os.path.splitext(filename)[1] if filename else ""

        self.logger.debug(
            "file_extension_extracted",
            filename=filename,
            file_extension=file_extension,
            file_path=file_path,
        )

        # Build payload matching intelligence service API contract
        # Intelligence service expects: document_id, project_id, title, content, document_type, metadata
        payload = {
            "document_id": file_path,  # Use file_path as document_id
            "project_id": project_name,  # Rename to project_id
            "title": filename,  # Add filename as title
            "content": content,  # Keep as-is
            "document_type": doc_type,  # Add document type
            "metadata": {  # Add metadata object
                "file_path": file_path,
                "source": "kafka_enrichment",
                "file_extension": file_extension,  # File extension for language detection
            },
        }

        # Get fixed timeout for intelligence service call
        content_size = len(content.encode("utf-8")) if content else 0
        adaptive_timeout = get_intelligence_timeout(
            content_size, self.config.intelligence_timeout
        )

        self.logger.info(
            "🌐 [HTTP] Calling intelligence service",
            url=url,
            file_path=file_path,
            content_size=content_size,
            timeout_seconds=adaptive_timeout,
            configured_timeout=self.config.intelligence_timeout,
            document_type=doc_type,
            payload_fields=list(payload.keys()),
        )

        import time

        request_start_time = time.time()

        try:
            async with self.session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=adaptive_timeout)
            ) as response:
                request_duration_ms = (time.time() - request_start_time) * 1000

                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        "❌ [HTTP] Intelligence service returned error",
                        file_path=file_path,
                        status_code=response.status,
                        error_text=error_text[:500],  # Truncate for logging
                        request_duration_ms=request_duration_ms,
                    )
                    raise Exception(
                        f"Intelligence service returned {response.status}: {error_text}"
                    )

                result = await response.json()

                self.logger.info(
                    "✅ [HTTP] Intelligence service responded successfully",
                    file_path=file_path,
                    status_code=response.status,
                    request_duration_ms=request_duration_ms,
                    response_fields=list(result.keys()),
                    entities_extracted=len(result.get("entities", [])),
                    patterns_detected=len(result.get("patterns", [])),
                )

                return result

        except asyncio.TimeoutError:
            request_duration_ms = (time.time() - request_start_time) * 1000
            self.logger.error(
                "❌ [HTTP] Intelligence service timeout",
                file_path=file_path,
                content_size=content_size,
                timeout_seconds=adaptive_timeout,
                request_duration_ms=request_duration_ms,
            )
            raise Exception(
                f"Intelligence service request timed out after {adaptive_timeout}s"
            )

        except aiohttp.ClientError as e:
            request_duration_ms = (time.time() - request_start_time) * 1000
            self.logger.error(
                "❌ [HTTP] Intelligence service client error",
                file_path=file_path,
                error=str(e),
                error_type=type(e).__name__,
                request_duration_ms=request_duration_ms,
                exc_info=True,
            )
            raise Exception(f"Intelligence service client error: {e}")

    async def health_check(self) -> bool:
        """
        Check intelligence service health.

        Returns:
            True if service is healthy, False otherwise
        """
        if not self.session:
            return False

        url = f"{self.config.intelligence_service_url}/health"

        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200

        except Exception as e:
            self.logger.warning("health_check_failed", error=str(e))
            return False

    @property
    def circuit_state(self) -> str:
        """Get current circuit breaker state."""
        return self.circuit_breaker.state.value

    async def assess_code(
        self,
        source_path: str,
        content: str,
        language: str = "python",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Assess code quality through intelligence service.

        Args:
            source_path: Path to the code file
            content: Code content
            language: Programming language
            correlation_id: Optional correlation ID for tracing

        Returns:
            Code quality assessment results

        Raises:
            Exception: If assessment fails or circuit is open
        """
        if not self.session:
            raise RuntimeError("Client not started")

        log = self.logger.bind(
            source_path=source_path,
            language=language,
            correlation_id=correlation_id,
        )

        log.info(
            "assessing_code",
            circuit_breaker_enabled=self.config.circuit_breaker_enabled,
        )

        # Process with or without circuit breaker protection
        if self.config.circuit_breaker_enabled:
            result = await self.circuit_breaker.call(
                self._call_assess_code_endpoint,
                source_path=source_path,
                content=content,
                language=language,
            )
        else:
            # Circuit breaker disabled - call directly
            result = await self._call_assess_code_endpoint(
                source_path=source_path,
                content=content,
                language=language,
            )

        log.info(
            "code_assessed",
            quality_score=result.get("quality_score"),
            has_issues=bool(result.get("issues")),
        )

        return result

    async def _call_assess_code_endpoint(
        self, source_path: str, content: str, language: str
    ) -> Dict[str, Any]:
        """
        Make HTTP call to intelligence service /assess/code endpoint.

        Args:
            source_path: Path to the code file
            content: Code content
            language: Programming language

        Returns:
            Code quality assessment results

        Raises:
            Exception: If HTTP call fails
        """
        url = f"{self.config.intelligence_service_url}/assess/code"

        payload = {
            "source_path": source_path,
            "content": content,
            "language": language,
            "include_patterns": True,
            "include_compliance": True,
            "include_recommendations": True,
        }

        # Get fixed timeout for intelligence service call
        content_size = len(content.encode("utf-8")) if content else 0
        adaptive_timeout = get_intelligence_timeout(
            content_size, self.config.intelligence_timeout
        )

        self.logger.debug(
            "timeout_retrieved",
            source_path=source_path,
            content_size=content_size,
            timeout_seconds=adaptive_timeout,
            configured_timeout=self.config.intelligence_timeout,
        )

        try:
            async with self.session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=adaptive_timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Intelligence service returned {response.status}: {error_text}"
                    )

                return await response.json()

        except asyncio.TimeoutError:
            self.logger.error(
                "intelligence_service_timeout",
                source_path=source_path,
                content_size=content_size,
                timeout=adaptive_timeout,
            )
            raise Exception(
                f"Intelligence service request timed out after {adaptive_timeout}s"
            )

        except aiohttp.ClientError as e:
            self.logger.error(
                "intelligence_service_client_error",
                source_path=source_path,
                error=str(e),
            )
            raise Exception(f"Intelligence service client error: {e}")

    @property
    def is_healthy(self) -> bool:
        """Check if client is healthy (circuit closed)."""
        return not self.circuit_breaker.is_open
