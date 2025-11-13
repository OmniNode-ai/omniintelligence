"""
Quality Assessment Event Handler

Handles quality assessment request events and publishes completed/failed responses.
Implements event-driven quality assessment for code, documents, and compliance checks.

Handles 3 event types:
1. CODE_ASSESSMENT_REQUESTED → CODE_ASSESSMENT_COMPLETED/FAILED
2. DOCUMENT_ASSESSMENT_REQUESTED → DOCUMENT_ASSESSMENT_COMPLETED/FAILED
3. COMPLIANCE_CHECK_REQUESTED → COMPLIANCE_CHECK_COMPLETED/FAILED

Created: 2025-10-22
Purpose: Event-driven quality assessment integration for Phase 1
"""

# Import create_default_client - handle conflict with root config/ directory
import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from src.archon_services.quality.comprehensive_onex_scorer import (
    ComprehensiveONEXScorer,
)
from src.events.models.quality_assessment_events import (
    EnumQualityAssessmentErrorCode,
    EnumQualityAssessmentEventType,
    ModelCodeAssessmentCompletedPayload,
    ModelCodeAssessmentFailedPayload,
    ModelComplianceCheckCompletedPayload,
    ModelComplianceCheckFailedPayload,
    ModelDocumentAssessmentCompletedPayload,
    ModelDocumentAssessmentFailedPayload,
    QualityAssessmentEventHelpers,
)
from src.handlers.base_response_publisher import BaseResponsePublisher

# Resolve the correct config module path
_config_module_path = Path(__file__).parent.parent / "config" / "http_client_config.py"
if _config_module_path.exists():
    # Load the module directly from the file
    _spec = importlib.util.spec_from_file_location(
        "_http_client_config", _config_module_path
    )
    _http_client_config = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_http_client_config)
    create_default_client = _http_client_config.create_default_client
else:
    # Fallback to standard import (for when src is properly in path)
    from config.http_client_config import create_default_client

logger = logging.getLogger(__name__)


class QualityAssessmentHandler(BaseResponsePublisher):
    """
    Handle quality assessment request events and publish results.

    Event Flow:
        1. Consume {CODE|DOCUMENT|COMPLIANCE}_ASSESSMENT_REQUESTED event
        2. Extract payload and perform assessment
        3. Publish _COMPLETED (success) or _FAILED (error)

    Topics:
        Code Assessment:
        - Request: dev.archon-intelligence.quality.code-assessment-requested.v1
        - Completed: dev.archon-intelligence.quality.code-assessment-completed.v1
        - Failed: dev.archon-intelligence.quality.code-assessment-failed.v1

        Document Assessment:
        - Request: dev.archon-intelligence.quality.document-assessment-requested.v1
        - Completed: dev.archon-intelligence.quality.document-assessment-completed.v1
        - Failed: dev.archon-intelligence.quality.document-assessment-failed.v1

        Compliance Check:
        - Request: dev.archon-intelligence.quality.compliance-check-requested.v1
        - Completed: dev.archon-intelligence.quality.compliance-check-completed.v1
        - Failed: dev.archon-intelligence.quality.compliance-check-failed.v1
    """

    # Topic constants
    CODE_ASSESSMENT_TOPICS = {
        "request": "dev.archon-intelligence.quality.code-assessment-requested.v1",
        "completed": "dev.archon-intelligence.quality.code-assessment-completed.v1",
        "failed": "dev.archon-intelligence.quality.code-assessment-failed.v1",
    }

    DOCUMENT_ASSESSMENT_TOPICS = {
        "request": "dev.archon-intelligence.quality.document-assessment-requested.v1",
        "completed": "dev.archon-intelligence.quality.document-assessment-completed.v1",
        "failed": "dev.archon-intelligence.quality.document-assessment-failed.v1",
    }

    COMPLIANCE_CHECK_TOPICS = {
        "request": "dev.archon-intelligence.quality.compliance-check-requested.v1",
        "completed": "dev.archon-intelligence.quality.compliance-check-completed.v1",
        "failed": "dev.archon-intelligence.quality.compliance-check-failed.v1",
    }

    def __init__(
        self,
        quality_scorer: Optional[ComprehensiveONEXScorer] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        base_url: str = "http://localhost:8053",
    ):
        """
        Initialize Quality Assessment handler.

        Args:
            quality_scorer: Optional quality scorer instance (for backward compatibility)
            http_client: Optional HTTP client for service calls
            base_url: Base URL for intelligence service
        """
        super().__init__()
        self.quality_scorer = quality_scorer or ComprehensiveONEXScorer()
        self.http_client = http_client or create_default_client()
        self.base_url = base_url
        self.metrics = {
            "events_handled": 0,
            "events_failed": 0,
            "total_processing_time_ms": 0.0,
            "code_assessments": 0,
            "document_assessments": 0,
            "compliance_checks": 0,
        }

    def can_handle(self, event_type: str) -> bool:
        """
        Check if this handler can process the given event type.

        Args:
            event_type: Event type string

        Returns:
            True if event type is a quality assessment request
        """
        return event_type in [
            # Code Assessment
            EnumQualityAssessmentEventType.CODE_ASSESSMENT_REQUESTED.value,
            "CODE_ASSESSMENT_REQUESTED",
            "quality.code-assessment-requested",
            "omninode.quality.event.code_assessment_requested.v1",
            # Document Assessment
            EnumQualityAssessmentEventType.DOCUMENT_ASSESSMENT_REQUESTED.value,
            "DOCUMENT_ASSESSMENT_REQUESTED",
            "quality.document-assessment-requested",
            "omninode.quality.event.document_assessment_requested.v1",
            # Compliance Check
            EnumQualityAssessmentEventType.COMPLIANCE_CHECK_REQUESTED.value,
            "COMPLIANCE_CHECK_REQUESTED",
            "quality.compliance-check-requested",
            "omninode.quality.event.compliance_check_requested.v1",
        ]

    async def handle_event(self, event: Any) -> bool:
        """
        Handle quality assessment request event.

        Routes to appropriate handler based on event type.

        Args:
            event: Event envelope with quality assessment payload

        Returns:
            True if handled successfully, False otherwise
        """
        start_time = time.perf_counter()
        correlation_id = None

        try:
            # Extract event data
            correlation_id = self._get_correlation_id(event)
            event_type = self._get_event_type(event)

            # Route to appropriate handler
            if (
                "code_assessment" in event_type.lower()
                or "code-assessment" in event_type.lower()
            ):
                return await self._handle_code_assessment(
                    event, correlation_id, start_time
                )
            elif (
                "document_assessment" in event_type.lower()
                or "document-assessment" in event_type.lower()
            ):
                return await self._handle_document_assessment(
                    event, correlation_id, start_time
                )
            elif (
                "compliance_check" in event_type.lower()
                or "compliance-check" in event_type.lower()
            ):
                return await self._handle_compliance_check(
                    event, correlation_id, start_time
                )
            else:
                logger.error(
                    f"Unknown event type: {event_type} | correlation_id={correlation_id}"
                )
                self.metrics["events_failed"] += 1
                return False

        except Exception as e:
            logger.error(
                f"Quality assessment handler failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )
            self.metrics["events_failed"] += 1
            return False

    async def _handle_code_assessment(
        self, event: Any, correlation_id: UUID, start_time: float
    ) -> bool:
        """Handle CODE_ASSESSMENT_REQUESTED event."""
        try:
            payload = self._get_payload(event)

            # Extract required fields
            content = payload.get("content")
            source_path = payload.get("source_path", "")
            language = payload.get("language", "python")

            # Validate required fields
            if not content:
                await self._publish_code_failed(
                    correlation_id=correlation_id,
                    source_path=source_path or "unknown",
                    error_code=EnumQualityAssessmentErrorCode.INVALID_INPUT,
                    error_message="Missing required field: content",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                return False

            logger.info(
                f"Processing CODE_ASSESSMENT_REQUESTED | correlation_id={correlation_id} | "
                f"source_path={source_path} | language={language}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/assess/code"
            request_payload = {
                "content": content,
                "source_path": source_path,
                "language": language,
            }

            response = await self.http_client.post(
                url, json=request_payload, timeout=30.0
            )
            response.raise_for_status()
            assessment = response.json()

            # Extract metrics from HTTP response
            quality_score = assessment.get("quality_score", 0.0)
            onex_compliance = assessment.get("onex_compliance_score", 0.0)
            complexity = assessment.get("complexity", {})
            maintainability = assessment.get("maintainability", {})

            # Create and publish completed event
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_code_completed(
                correlation_id=correlation_id,
                source_path=source_path,
                quality_score=quality_score,
                architectural_compliance=onex_compliance,
                complexity_score=complexity.get("score", 0.0),
                maintainability_score=maintainability.get("score", 0.0),
                patterns_count=len(assessment.get("patterns", [])),
                issues_count=len(assessment.get("issues", [])),
                recommendations_count=len(assessment.get("recommendations", [])),
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["code_assessments"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"CODE_ASSESSMENT_COMPLETED published | correlation_id={correlation_id} | "
                f"quality_score={quality_score:.2f} | processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during code assessment | correlation_id={correlation_id} | status={e.response.status_code}",
                exc_info=True,
            )

            payload = self._get_payload(event)
            source_path = payload.get("source_path", "unknown")
            duration_ms = (time.perf_counter() - start_time) * 1000

            error_code = EnumQualityAssessmentErrorCode.EXTERNAL_SERVICE_ERROR
            if e.response.status_code == 400:
                error_code = EnumQualityAssessmentErrorCode.INVALID_INPUT
            elif e.response.status_code == 408 or e.response.status_code == 504:
                error_code = EnumQualityAssessmentErrorCode.TIMEOUT

            await self._publish_code_failed(
                correlation_id=correlation_id,
                source_path=source_path,
                error_code=error_code,
                error_message=f"HTTP error: {e.response.status_code} - {e.response.text}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"status_code": e.response.status_code},
            )

            self.metrics["events_failed"] += 1
            return False

        except httpx.TimeoutException as e:
            logger.error(
                f"Timeout during code assessment | correlation_id={correlation_id}",
                exc_info=True,
            )

            payload = self._get_payload(event)
            source_path = payload.get("source_path", "unknown")
            duration_ms = (time.perf_counter() - start_time) * 1000

            await self._publish_code_failed(
                correlation_id=correlation_id,
                source_path=source_path,
                error_code=EnumQualityAssessmentErrorCode.TIMEOUT,
                error_message=f"Request timeout: {str(e)}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"exception_type": "TimeoutException"},
            )

            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(
                f"Code assessment failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            payload = self._get_payload(event)
            source_path = payload.get("source_path", "unknown")
            duration_ms = (time.perf_counter() - start_time) * 1000

            await self._publish_code_failed(
                correlation_id=correlation_id,
                source_path=source_path,
                error_code=EnumQualityAssessmentErrorCode.INTERNAL_ERROR,
                error_message=f"Assessment failed: {str(e)}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"exception_type": type(e).__name__},
            )

            self.metrics["events_failed"] += 1
            return False

    async def _handle_document_assessment(
        self, event: Any, correlation_id: UUID, start_time: float
    ) -> bool:
        """Handle DOCUMENT_ASSESSMENT_REQUESTED event."""
        try:
            payload = self._get_payload(event)

            # Extract required fields
            content = payload.get("content")

            # Validate required fields
            if not content:
                await self._publish_document_failed(
                    correlation_id=correlation_id,
                    error_code=EnumQualityAssessmentErrorCode.INVALID_INPUT,
                    error_message="Missing required field: content",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                return False

            logger.info(
                f"Processing DOCUMENT_ASSESSMENT_REQUESTED | correlation_id={correlation_id}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/assess/document"
            request_payload = {
                "content": content,
                "doc_type": payload.get("doc_type", "markdown"),
                "metadata": payload.get("metadata", {}),
            }

            response = await self.http_client.post(
                url, json=request_payload, timeout=30.0
            )
            response.raise_for_status()
            assessment = response.json()

            # Extract metrics from HTTP response
            quality_score = assessment.get("quality_score", 0.0)
            completeness_score = assessment.get("completeness_score", 0.0)
            structure_score = assessment.get("structure_score", 0.0)
            clarity_score = assessment.get("clarity_score", 0.0)
            word_count = assessment.get("word_count", 0)
            section_count = assessment.get("section_count", 0)

            # Create and publish completed event
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_completed(
                correlation_id=correlation_id,
                quality_score=quality_score,
                completeness_score=completeness_score,
                structure_score=structure_score,
                clarity_score=clarity_score,
                word_count=word_count,
                section_count=section_count,
                recommendations_count=2,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["document_assessments"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"DOCUMENT_ASSESSMENT_COMPLETED published | correlation_id={correlation_id} | "
                f"quality_score={quality_score:.2f} | processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during document assessment | correlation_id={correlation_id} | status={e.response.status_code}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            error_code = EnumQualityAssessmentErrorCode.EXTERNAL_SERVICE_ERROR
            if e.response.status_code == 400:
                error_code = EnumQualityAssessmentErrorCode.INVALID_INPUT

            await self._publish_document_failed(
                correlation_id=correlation_id,
                error_code=error_code,
                error_message=f"HTTP error: {e.response.status_code} - {e.response.text}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"status_code": e.response.status_code},
            )

            self.metrics["events_failed"] += 1
            return False

        except httpx.TimeoutException as e:
            logger.error(
                f"Timeout during document assessment | correlation_id={correlation_id}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_failed(
                correlation_id=correlation_id,
                error_code=EnumQualityAssessmentErrorCode.TIMEOUT,
                error_message=f"Request timeout: {str(e)}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"exception_type": "TimeoutException"},
            )

            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(
                f"Document assessment failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_document_failed(
                correlation_id=correlation_id,
                error_code=EnumQualityAssessmentErrorCode.INTERNAL_ERROR,
                error_message=f"Assessment failed: {str(e)}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"exception_type": type(e).__name__},
            )

            self.metrics["events_failed"] += 1
            return False

    async def _handle_compliance_check(
        self, event: Any, correlation_id: UUID, start_time: float
    ) -> bool:
        """Handle COMPLIANCE_CHECK_REQUESTED event."""
        try:
            payload = self._get_payload(event)

            # Extract required fields
            content = payload.get("content")
            architecture_type = payload.get("architecture_type", "onex")

            # Validate required fields
            if not content:
                await self._publish_compliance_failed(
                    correlation_id=correlation_id,
                    error_code=EnumQualityAssessmentErrorCode.INVALID_INPUT,
                    error_message="Missing required field: content",
                    retry_allowed=False,
                    processing_time_ms=(time.perf_counter() - start_time) * 1000,
                )
                self.metrics["events_failed"] += 1
                return False

            logger.info(
                f"Processing COMPLIANCE_CHECK_REQUESTED | correlation_id={correlation_id} | "
                f"architecture_type={architecture_type}"
            )

            # Make HTTP request to intelligence service
            url = f"{self.base_url}/compliance/check"
            request_payload = {
                "content": content,
                "rules": payload.get("rules", []),
                "context": {"architecture_type": architecture_type},
            }

            response = await self.http_client.post(
                url, json=request_payload, timeout=30.0
            )
            response.raise_for_status()
            assessment = response.json()

            # Extract metrics from HTTP response
            compliance_score = assessment.get("compliance_score", 0.0)
            violations_count = assessment.get("violations_count", 0)
            recommendations_count = assessment.get("recommendations_count", 0)

            # Create and publish completed event
            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_compliance_completed(
                correlation_id=correlation_id,
                compliance_score=compliance_score,
                violations_count=violations_count,
                recommendations_count=recommendations_count,
                architecture_type=architecture_type,
                processing_time_ms=duration_ms,
            )

            self.metrics["events_handled"] += 1
            self.metrics["compliance_checks"] += 1
            self.metrics["total_processing_time_ms"] += duration_ms

            logger.info(
                f"COMPLIANCE_CHECK_COMPLETED published | correlation_id={correlation_id} | "
                f"compliance_score={compliance_score:.2f} | processing_time_ms={duration_ms:.2f}"
            )

            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during compliance check | correlation_id={correlation_id} | status={e.response.status_code}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            error_code = EnumQualityAssessmentErrorCode.EXTERNAL_SERVICE_ERROR
            if e.response.status_code == 400:
                error_code = EnumQualityAssessmentErrorCode.INVALID_INPUT

            await self._publish_compliance_failed(
                correlation_id=correlation_id,
                error_code=error_code,
                error_message=f"HTTP error: {e.response.status_code} - {e.response.text}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"status_code": e.response.status_code},
            )

            self.metrics["events_failed"] += 1
            return False

        except httpx.TimeoutException as e:
            logger.error(
                f"Timeout during compliance check | correlation_id={correlation_id}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_compliance_failed(
                correlation_id=correlation_id,
                error_code=EnumQualityAssessmentErrorCode.TIMEOUT,
                error_message=f"Request timeout: {str(e)}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"exception_type": "TimeoutException"},
            )

            self.metrics["events_failed"] += 1
            return False

        except Exception as e:
            logger.error(
                f"Compliance check failed | correlation_id={correlation_id} | error={e}",
                exc_info=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self._publish_compliance_failed(
                correlation_id=correlation_id,
                error_code=EnumQualityAssessmentErrorCode.INTERNAL_ERROR,
                error_message=f"Compliance check failed: {str(e)}",
                retry_allowed=True,
                processing_time_ms=duration_ms,
                error_details={"exception_type": type(e).__name__},
            )

            self.metrics["events_failed"] += 1
            return False

    # ============================================================================
    # Response Publishing Methods
    # ============================================================================

    async def _publish_code_completed(
        self,
        correlation_id: UUID,
        source_path: str,
        quality_score: float,
        architectural_compliance: float,
        complexity_score: float,
        maintainability_score: float,
        patterns_count: int,
        issues_count: int,
        recommendations_count: int,
        processing_time_ms: float,
    ) -> None:
        """Publish CODE_ASSESSMENT_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            payload = ModelCodeAssessmentCompletedPayload(
                source_path=source_path,
                quality_score=quality_score,
                architectural_compliance=architectural_compliance,
                complexity_score=complexity_score,
                maintainability_score=maintainability_score,
                patterns_count=patterns_count,
                issues_count=issues_count,
                recommendations_count=recommendations_count,
                processing_time_ms=processing_time_ms,
                cache_hit=False,
            )

            event_envelope = QualityAssessmentEventHelpers.create_event_envelope(
                event_type="code_assessment_completed",
                payload=payload,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.CODE_ASSESSMENT_TOPICS["completed"],
                event=event_envelope,
                key=str(correlation_id),
            )

        except Exception as e:
            logger.error(
                f"Failed to publish code completed response: {e}", exc_info=True
            )
            raise

    async def _publish_code_failed(
        self,
        correlation_id: UUID,
        source_path: str,
        error_code: EnumQualityAssessmentErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish CODE_ASSESSMENT_FAILED event."""
        try:
            await self._ensure_router_initialized()

            payload = ModelCodeAssessmentFailedPayload(
                source_path=source_path,
                error_message=error_message,
                error_code=error_code,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details or {},
            )

            event_envelope = QualityAssessmentEventHelpers.create_event_envelope(
                event_type="code_assessment_failed",
                payload=payload,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.CODE_ASSESSMENT_TOPICS["failed"],
                event=event_envelope,
                key=str(correlation_id),
            )

        except Exception as e:
            logger.error(f"Failed to publish code failed response: {e}", exc_info=True)
            raise

    async def _publish_document_completed(
        self,
        correlation_id: UUID,
        quality_score: float,
        completeness_score: float,
        structure_score: float,
        clarity_score: float,
        word_count: int,
        section_count: int,
        recommendations_count: int,
        processing_time_ms: float,
    ) -> None:
        """Publish DOCUMENT_ASSESSMENT_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            payload = ModelDocumentAssessmentCompletedPayload(
                quality_score=quality_score,
                completeness_score=completeness_score,
                structure_score=structure_score,
                clarity_score=clarity_score,
                word_count=word_count,
                section_count=section_count,
                recommendations_count=recommendations_count,
                processing_time_ms=processing_time_ms,
                cache_hit=False,
            )

            event_envelope = QualityAssessmentEventHelpers.create_event_envelope(
                event_type="document_assessment_completed",
                payload=payload,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.DOCUMENT_ASSESSMENT_TOPICS["completed"],
                event=event_envelope,
                key=str(correlation_id),
            )

        except Exception as e:
            logger.error(
                f"Failed to publish document completed response: {e}", exc_info=True
            )
            raise

    async def _publish_document_failed(
        self,
        correlation_id: UUID,
        error_code: EnumQualityAssessmentErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish DOCUMENT_ASSESSMENT_FAILED event."""
        try:
            await self._ensure_router_initialized()

            payload = ModelDocumentAssessmentFailedPayload(
                error_message=error_message,
                error_code=error_code,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details or {},
            )

            event_envelope = QualityAssessmentEventHelpers.create_event_envelope(
                event_type="document_assessment_failed",
                payload=payload,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.DOCUMENT_ASSESSMENT_TOPICS["failed"],
                event=event_envelope,
                key=str(correlation_id),
            )

        except Exception as e:
            logger.error(
                f"Failed to publish document failed response: {e}", exc_info=True
            )
            raise

    async def _publish_compliance_completed(
        self,
        correlation_id: UUID,
        compliance_score: float,
        violations_count: int,
        recommendations_count: int,
        architecture_type: str,
        processing_time_ms: float,
    ) -> None:
        """Publish COMPLIANCE_CHECK_COMPLETED event."""
        try:
            await self._ensure_router_initialized()

            payload = ModelComplianceCheckCompletedPayload(
                compliance_score=compliance_score,
                violations_count=violations_count,
                recommendations_count=recommendations_count,
                architecture_type=architecture_type,
                processing_time_ms=processing_time_ms,
                cache_hit=False,
            )

            event_envelope = QualityAssessmentEventHelpers.create_event_envelope(
                event_type="compliance_check_completed",
                payload=payload,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.COMPLIANCE_CHECK_TOPICS["completed"],
                event=event_envelope,
                key=str(correlation_id),
            )

        except Exception as e:
            logger.error(
                f"Failed to publish compliance completed response: {e}", exc_info=True
            )
            raise

    async def _publish_compliance_failed(
        self,
        correlation_id: UUID,
        error_code: EnumQualityAssessmentErrorCode,
        error_message: str,
        retry_allowed: bool,
        processing_time_ms: float,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish COMPLIANCE_CHECK_FAILED event."""
        try:
            await self._ensure_router_initialized()

            payload = ModelComplianceCheckFailedPayload(
                error_message=error_message,
                error_code=error_code,
                retry_allowed=retry_allowed,
                processing_time_ms=processing_time_ms,
                error_details=error_details or {},
            )

            event_envelope = QualityAssessmentEventHelpers.create_event_envelope(
                event_type="compliance_check_failed",
                payload=payload,
                correlation_id=correlation_id,
            )

            await self._router.publish(
                topic=self.COMPLIANCE_CHECK_TOPICS["failed"],
                event=event_envelope,
                key=str(correlation_id),
            )

        except Exception as e:
            logger.error(
                f"Failed to publish compliance failed response: {e}", exc_info=True
            )
            raise

    def _get_event_type(self, event: Any) -> str:
        """Extract event type from event metadata."""
        if isinstance(event, dict):
            # Check metadata first (omnibase_core pattern)
            metadata = event.get("metadata", {})
            if "event_type" in metadata:
                return metadata["event_type"]
            # Fallback to top-level (legacy pattern)
            return event.get("event_type", "")
        else:
            # For object access
            metadata = getattr(event, "metadata", {})
            if isinstance(metadata, dict) and "event_type" in metadata:
                return metadata["event_type"]
            return getattr(event, "event_type", "")

    def get_handler_name(self) -> str:
        """Get handler name for registration."""
        return "QualityAssessmentHandler"

    def get_metrics(self) -> Dict[str, Any]:
        """Get handler metrics."""
        total_events = self.metrics["events_handled"] + self.metrics["events_failed"]
        success_rate = (
            self.metrics["events_handled"] / total_events if total_events > 0 else 1.0
        )
        avg_processing_time = (
            self.metrics["total_processing_time_ms"] / self.metrics["events_handled"]
            if self.metrics["events_handled"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time,
            "handler_name": self.get_handler_name(),
        }
