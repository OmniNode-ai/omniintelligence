"""
Extraction Event Emitter for LangExtract Service

Emits extraction events to the DocumentEventBus for integration
with other Archon services and downstream processing.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from events.models.extraction_events import (
    BatchExtractionCompletedEvent,
    EntityEnrichmentCompletedEvent,
    ExtractionCompletedEvent,
    ExtractionFailedEvent,
    ExtractionStartedEvent,
    KnowledgeGraphUpdateEvent,
    LangExtractEventEnvelope,
    SemanticAnalysisEvent,
)

logger = logging.getLogger(__name__)


class ExtractionEventEmitter:
    """
    Event emitter for publishing LangExtract events to the DocumentEventBus.

    Integrates with the existing Archon event system to notify other services
    about extraction results and trigger downstream processing.
    """

    def __init__(
        self,
        bridge_service_url: str = "http://localhost:8054",
        intelligence_service_url: str = "http://localhost:8053",
        publisher_id: Optional[str] = None,
    ):
        """
        Initialize extraction event emitter.

        Args:
            bridge_service_url: URL of Bridge service for event publishing
            intelligence_service_url: URL of Intelligence service for coordination
            publisher_id: Optional publisher identifier
        """
        self.bridge_service_url = bridge_service_url
        self.intelligence_service_url = intelligence_service_url
        self.publisher_id = (
            publisher_id or f"langextract_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Event publishing configuration
        self.publishing_config = {
            "reliable_delivery": True,
            "retry_attempts": 3,
            "retry_delay_seconds": 2,
            "batch_publishing": False,
            "compression": False,
        }

        # Event routing configuration
        self.routing_config = {
            "extraction.started": ["intelligence", "search"],
            "extraction.completed": ["intelligence", "search", "bridge"],
            "extraction.failed": ["intelligence"],
            "semantic.analysis.completed": ["intelligence", "search"],
            "knowledge_graph.updated": ["intelligence", "search", "bridge"],
            "batch.extraction.completed": ["intelligence", "search"],
            "entity.enrichment.completed": ["intelligence", "search"],
        }

        # Publishing statistics
        self.stats = {
            "events_published": 0,
            "events_failed": 0,
            "events_retried": 0,
            "total_publish_time": 0.0,
        }

    async def emit_extraction_started(
        self,
        event: ExtractionStartedEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit extraction started event"""
        await self._publish_event(
            event_type="extraction.started",
            event_data=event,
            target_services=target_services,
        )

    async def emit_extraction_completed(
        self,
        event: ExtractionCompletedEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit extraction completed event"""
        await self._publish_event(
            event_type="extraction.completed",
            event_data=event,
            target_services=target_services,
        )

    async def emit_extraction_failed(
        self,
        event: ExtractionFailedEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit extraction failed event"""
        await self._publish_event(
            event_type="extraction.failed",
            event_data=event,
            target_services=target_services,
        )

    async def emit_semantic_analysis_completed(
        self,
        event: SemanticAnalysisEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit semantic analysis completed event"""
        await self._publish_event(
            event_type="semantic.analysis.completed",
            event_data=event,
            target_services=target_services,
        )

    async def emit_knowledge_graph_updated(
        self,
        event: KnowledgeGraphUpdateEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit knowledge graph updated event"""
        await self._publish_event(
            event_type="knowledge_graph.updated",
            event_data=event,
            target_services=target_services,
        )

    async def emit_batch_extraction_completed(
        self,
        event: BatchExtractionCompletedEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit batch extraction completed event"""
        await self._publish_event(
            event_type="batch.extraction.completed",
            event_data=event,
            target_services=target_services,
        )

    async def emit_entity_enrichment_completed(
        self,
        event: EntityEnrichmentCompletedEvent,
        target_services: Optional[List[str]] = None,
    ):
        """Emit entity enrichment completed event"""
        await self._publish_event(
            event_type="entity.enrichment.completed",
            event_data=event,
            target_services=target_services,
        )

    async def _publish_event(
        self,
        event_type: str,
        event_data: Any,
        target_services: Optional[List[str]] = None,
    ):
        """
        Publish event to DocumentEventBus.

        Args:
            event_type: Type of event being published
            event_data: Event payload data
            target_services: Optional list of target services
        """
        start_time = datetime.utcnow()

        try:
            # Determine target services
            if target_services is None:
                target_services = self.routing_config.get(event_type, ["intelligence"])

            # Create event envelope
            envelope = LangExtractEventEnvelope(
                event_type=event_type,
                payload=event_data,
                source_service="langextract",
                routing_metadata={
                    "target_services": target_services,
                    "publisher_id": self.publisher_id,
                },
            )

            # Publish event with retry logic
            success = await self._publish_with_retry(envelope, event_type)

            if success:
                self.stats["events_published"] += 1
                logger.debug(f"Published event: {event_type}")
            else:
                self.stats["events_failed"] += 1
                logger.error(f"Failed to publish event: {event_type}")

            # Update timing statistics
            publish_time = (datetime.utcnow() - start_time).total_seconds()
            self.stats["total_publish_time"] += publish_time

        except Exception as e:
            logger.error(f"Error publishing event {event_type}: {e}")
            self.stats["events_failed"] += 1

    async def _publish_with_retry(
        self,
        envelope: LangExtractEventEnvelope,
        event_type: str,
    ) -> bool:
        """
        Publish event with retry logic.

        Args:
            envelope: Event envelope to publish
            event_type: Type of event for logging

        Returns:
            bool: True if publishing succeeded, False otherwise
        """
        max_retries = self.publishing_config["retry_attempts"]
        retry_delay = self.publishing_config["retry_delay_seconds"]

        for attempt in range(max_retries + 1):
            try:
                # Attempt to publish event
                response = await self.http_client.post(
                    f"{self.bridge_service_url}/events/publish",
                    json={
                        "event_type": event_type,
                        "payload": envelope.dict(),
                        "publisher_id": self.publisher_id,
                        "reliable_delivery": self.publishing_config[
                            "reliable_delivery"
                        ],
                    },
                )
                response.raise_for_status()

                # Success
                if attempt > 0:
                    self.stats["events_retried"] += 1
                    logger.info(
                        f"Event published after {attempt} retries: {event_type}"
                    )

                return True

            except httpx.HTTPError as e:
                if attempt < max_retries:
                    # Retry on failure
                    logger.warning(f"Event publish attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(
                        retry_delay * (2**attempt)
                    )  # Exponential backoff
                else:
                    # Final failure
                    logger.error(
                        f"Event publish failed after {max_retries} retries: {e}"
                    )
                    return False

            except Exception as e:
                logger.error(f"Unexpected error publishing event: {e}")
                return False

        return False

    async def emit_bulk_events(self, events: List[Dict[str, Any]]):
        """
        Emit multiple events in bulk for better performance.

        Args:
            events: List of event dictionaries with 'type' and 'data' keys
        """
        try:
            if not events:
                return

            logger.info(f"Publishing {len(events)} events in bulk")

            # Process events in parallel
            tasks = []
            for event_info in events:
                event_type = event_info["type"]
                event_data = event_info["data"]
                target_services = event_info.get("target_services")

                task = self._publish_event(event_type, event_data, target_services)
                tasks.append(task)

            # Wait for all events to be published
            await asyncio.gather(*tasks, return_exceptions=True)

            logger.info("Bulk event publishing completed")

        except Exception as e:
            logger.error(f"Error in bulk event publishing: {e}")

    async def notify_extraction_pipeline(
        self,
        extraction_id: str,
        document_path: str,
        pipeline_stage: str,
        stage_data: Dict[str, Any],
    ):
        """
        Notify extraction pipeline about stage completion.

        Args:
            extraction_id: Unique extraction identifier
            document_path: Document being processed
            pipeline_stage: Current pipeline stage
            stage_data: Stage-specific data
        """
        try:
            notification_event = {
                "event_id": f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "extraction_id": extraction_id,
                "document_path": document_path,
                "pipeline_stage": pipeline_stage,
                "stage_data": stage_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            await self._publish_event(
                event_type="extraction.pipeline.notification",
                event_data=notification_event,
                target_services=["intelligence"],
            )

        except Exception as e:
            logger.error(f"Failed to notify extraction pipeline: {e}")

    async def coordinate_with_intelligence_service(
        self,
        coordination_type: str,
        coordination_data: Dict[str, Any],
    ):
        """
        Coordinate with Intelligence service for advanced processing.

        Args:
            coordination_type: Type of coordination needed
            coordination_data: Coordination-specific data
        """
        try:
            coordination_request = {
                "coordination_type": coordination_type,
                "source_service": "langextract",
                "publisher_id": self.publisher_id,
                "data": coordination_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            response = await self.http_client.post(
                f"{self.intelligence_service_url}/coordinate",
                json=coordination_request,
            )
            response.raise_for_status()

            logger.debug(f"Coordination request sent: {coordination_type}")

        except httpx.HTTPError as e:
            logger.error(f"Intelligence service coordination failed: {e}")

    async def get_statistics(self) -> Dict[str, Any]:
        """Get event publishing statistics"""
        average_publish_time = self.stats["total_publish_time"] / max(
            self.stats["events_published"], 1
        )

        return {
            "publisher_id": self.publisher_id,
            "events_published": self.stats["events_published"],
            "events_failed": self.stats["events_failed"],
            "events_retried": self.stats["events_retried"],
            "success_rate": (
                self.stats["events_published"]
                / max(self.stats["events_published"] + self.stats["events_failed"], 1)
            ),
            "average_publish_time_seconds": average_publish_time,
            "routing_configuration": self.routing_config.copy(),
            "publishing_configuration": self.publishing_config.copy(),
        }

    async def update_routing_config(self, new_routing: Dict[str, List[str]]):
        """Update event routing configuration"""
        self.routing_config.update(new_routing)
        logger.info(f"Updated event routing configuration: {new_routing}")

    async def close(self):
        """Close the event emitter and cleanup resources"""
        try:
            await self.http_client.aclose()
            logger.info("Extraction event emitter closed")
        except Exception as e:
            logger.error(f"Error closing event emitter: {e}")

    async def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to required services"""
        connectivity_results = {}

        # Test Bridge service
        try:
            response = await self.http_client.get(f"{self.bridge_service_url}/health")
            connectivity_results["bridge_service"] = response.status_code == 200
        except Exception:
            connectivity_results["bridge_service"] = False

        # Test Intelligence service
        try:
            response = await self.http_client.get(
                f"{self.intelligence_service_url}/health"
            )
            connectivity_results["intelligence_service"] = response.status_code == 200
        except Exception:
            connectivity_results["intelligence_service"] = False

        return connectivity_results
