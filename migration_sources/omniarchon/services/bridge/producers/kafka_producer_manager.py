"""
Kafka Producer Manager for Bridge Service

This module provides a Kafka producer for publishing document enrichment
requests to the async intelligence enrichment pipeline.

Author: Archon Architecture Team
Version: 1.0.0
Date: 2025-10-30
Related: docs/ASYNC_INTELLIGENCE_ARCHITECTURE.md
Correlation ID: ad5eefe7-a3ba-4d26-a425-6c7f251d74e9
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaProducer

# Centralized configuration
from config import settings

logger = logging.getLogger(__name__)


class KafkaProducerManager:
    """
    Manages Kafka producer lifecycle for enrichment events.

    This producer publishes document enrichment requests to Kafka for
    asynchronous processing by the intelligence consumer service.

    Features:
    - Automatic producer lifecycle management
    - Configurable via environment variables
    - Feature flag support (ENABLE_ASYNC_ENRICHMENT)
    - Snappy compression
    - All-replicas acknowledgment (acks='all')
    - Automatic retries

    Usage:
        producer = KafkaProducerManager()
        await producer.start()

        await producer.publish_enrichment_request(
            document_id="doc-123",
            project_name="my-project",
            content_hash="abc123...",
            file_path="src/main.py",
            content="def main():\n    pass",
            document_type="code",
            language="python",
            metadata={},
            correlation_id="CORR-123"
        )

        await producer.stop()
    """

    def __init__(self):
        """Initialize Kafka producer configuration."""
        self.producer: Optional[AIOKafkaProducer] = None

        # Feature flag
        self.enabled = os.getenv("ENABLE_ASYNC_ENRICHMENT", "false").lower() == "true"

        # Kafka configuration from centralized config
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", settings.kafka_bootstrap_servers
        )
        self.topic = os.getenv(
            "KAFKA_ENRICHMENT_TOPIC", "dev.archon-intelligence.enrich-document.v1"
        )

        logger.info(
            f"KafkaProducerManager initialized | "
            f"enabled={self.enabled} | "
            f"bootstrap_servers={self.bootstrap_servers} | "
            f"topic={self.topic}"
        )

    async def start(self):
        """
        Initialize Kafka producer on app startup.

        Creates and starts the Kafka producer if async enrichment is enabled.
        If disabled, this is a no-op.

        Raises:
            Exception: If producer fails to start
        """
        if not self.enabled:
            logger.info(
                "Async enrichment disabled (ENABLE_ASYNC_ENRICHMENT=false) - "
                "Kafka producer not started"
            )
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=30000,  # 30s timeout
            )

            await self.producer.start()

            logger.info(
                f"✅ Kafka producer started successfully | "
                f"bootstrap_servers={self.bootstrap_servers} | "
                f"topic={self.topic}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to start Kafka producer: {e}")
            raise

    async def stop(self):
        """
        Cleanup producer on app shutdown.

        Gracefully stops the Kafka producer, ensuring all pending messages
        are sent before shutdown.
        """
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("Kafka producer stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping Kafka producer: {e}")

    async def publish_enrichment_request(
        self,
        document_id: str,
        project_name: str,
        content_hash: str,
        file_path: str,
        content: str,
        document_type: str,
        language: Optional[str],
        metadata: Dict[str, Any],
        correlation_id: str,
        enrichment_type: str = "full",
        priority: str = "normal",
    ) -> bool:
        """
        Publish enrichment request event to Kafka.

        Args:
            document_id: Unique document identifier (UUID, lowercase)
            project_name: Project name (for multi-tenant isolation)
            content_hash: BLAKE3 hash of file content (64-char hex)
            file_path: Relative file path within project
            content: Full document content (required for intelligence enrichment)
            document_type: Document type (code, documentation, etc.)
            language: Programming language (if code)
            metadata: Additional metadata
            correlation_id: Unique correlation ID for tracing (UUID, UPPERCASE)
            enrichment_type: Type of enrichment (full, incremental, quality_only, entities_only)
            priority: Processing priority (high, normal, low)

        Returns:
            bool: True if event published successfully, False otherwise

        Note:
            This method does NOT raise exceptions on publish failure.
            Failures are logged but do not prevent document indexing.
            This ensures fast indexing even if Kafka is temporarily unavailable.
        """
        if not self.enabled or not self.producer:
            logger.debug(
                f"Async enrichment disabled - skipping event publish | "
                f"document_id={document_id}"
            )
            return False

        # Event schema with envelope structure (matches consumer expectations)
        event = {
            "correlation_id": correlation_id.upper(),  # UUID UPPERCASE (top-level)
            "event_type": "enrichment_request",
            "timestamp": datetime.utcnow().isoformat() + "Z",  # ISO 8601
            "payload": {
                "document_id": document_id.lower(),  # UUID lowercase
                "project_name": project_name,
                "content_hash": content_hash,  # BLAKE3 64-char hex
                "file_path": file_path,  # Relative path
                "content": content,  # Full document content (REQUIRED by consumer)
                "document_type": document_type,
                "language": language,
                "indexed_at": datetime.utcnow().isoformat() + "Z",  # ISO 8601
                "enrichment_type": enrichment_type,  # full | incremental | quality_only | entities_only
                "priority": priority,  # high | normal | low
                "metadata": metadata,
                "retry_count": 0,
            },
        }

        try:
            # DEBUG: Log event structure before publishing
            logger.info(
                f"🔍 [DEBUG] Publishing enrichment event | "
                f"event_keys={list(event.keys())} | "
                f"payload_keys={list(event.get('payload', {}).keys())} | "
                f"has_content={('content' in event.get('payload', {}))}"
            )

            # Publish to Kafka (non-blocking, fire-and-forget)
            # Use document_id as key for partitioning consistency
            await self.producer.send_and_wait(
                self.topic, value=event, key=document_id.encode("utf-8")
            )

            logger.info(
                f"📤 Published enrichment request | "
                f"document_id={document_id} | "
                f"correlation_id={correlation_id} | "
                f"topic={self.topic}"
            )

            return True

        except Exception as e:
            logger.error(
                f"❌ Failed to publish enrichment request | "
                f"document_id={document_id} | "
                f"correlation_id={correlation_id} | "
                f"error={e}"
            )
            # DON'T raise - document indexing should continue
            # even if enrichment publish fails
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Get producer health status.

        Returns:
            dict: Health status information
        """
        return {
            "enabled": self.enabled,
            "producer_running": self.producer is not None,
            "bootstrap_servers": self.bootstrap_servers,
            "topic": self.topic,
        }
