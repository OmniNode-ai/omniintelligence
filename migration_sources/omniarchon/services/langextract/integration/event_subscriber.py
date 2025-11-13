"""
Document Event Subscriber for LangExtract Service

Subscribes to DocumentEventBus to receive document update notifications
and trigger automatic extraction workflows.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class DocumentEventSubscriber:
    """
    Subscriber for document update events from DocumentEventBus.

    Integrates with the existing Intelligence service event system to
    automatically trigger extraction when documents are updated.
    """

    def __init__(
        self,
        callback: Callable[[Dict[str, Any]], None],
        bridge_service_url: str = "http://localhost:8054",
        intelligence_service_url: str = "http://localhost:8053",
        subscription_id: Optional[str] = None,
    ):
        """
        Initialize document event subscriber.

        Args:
            callback: Function to call when document events are received
            bridge_service_url: URL of the Bridge service for event subscription
            intelligence_service_url: URL of Intelligence service for coordination
            subscription_id: Optional subscription identifier
        """
        self.callback = callback
        self.bridge_service_url = bridge_service_url
        self.intelligence_service_url = intelligence_service_url
        self.subscription_id = (
            subscription_id or f"langextract_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Connection management
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.is_subscribed = False
        self.subscription_task: Optional[asyncio.Task] = None

        # Event filtering
        self.event_filters = {
            "event_types": [
                "DOCUMENT_CREATED",
                "DOCUMENT_UPDATED",
                "DOCUMENT_BATCH_UPDATED",
                "FRESHNESS_ANALYSIS_COMPLETED",
            ],
            "document_extensions": [
                ".py",
                ".js",
                ".ts",
                ".java",
                ".cpp",
                ".c",
                ".go",
                ".rs",
                ".md",
                ".rst",
                ".txt",
                ".json",
                ".yaml",
                ".yml",
                ".xml",
                ".html",
                ".tex",
                ".pdf",
            ],
            "min_file_size": 100,  # Minimum file size in bytes
            "max_file_size": 10 * 1024 * 1024,  # Maximum file size (10MB)
        }

        # Processing state
        self.active_extractions = set()
        self.extraction_queue = asyncio.Queue()
        self.stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_filtered": 0,
            "extraction_triggered": 0,
            "errors": 0,
        }

    async def start(self):
        """Start the event subscription"""
        try:
            logger.info(f"Starting document event subscription: {self.subscription_id}")

            # Register subscription with Bridge service (optional)
            try:
                await self._register_subscription()

                # Start event polling task only if registration succeeded
                self.subscription_task = asyncio.create_task(self._event_polling_loop())

                # Start extraction processing task
                asyncio.create_task(self._process_extraction_queue())

                self.is_subscribed = True
                logger.info("Document event subscription started successfully")

            except Exception as e:
                logger.warning(
                    f"Event subscription registration failed "
                    f"(service will continue without events): {e}"
                )
                logger.info(
                    "LangExtract service starting without event subscription - "
                    "this is optional functionality"
                )
                self.is_subscribed = False

        except Exception as e:
            logger.warning(
                f"Failed to start event subscription (continuing without it): {e}"
            )
            self.is_subscribed = False
            # Don't raise - let the service continue without event subscription

    async def stop(self):
        """Stop the event subscription"""
        try:
            logger.info("Stopping document event subscription")

            self.is_subscribed = False

            # Cancel subscription task
            if self.subscription_task:
                self.subscription_task.cancel()
                try:
                    await self.subscription_task
                except asyncio.CancelledError:
                    pass

            # Unregister subscription
            await self._unregister_subscription()

            # Close HTTP client
            await self.http_client.aclose()

            logger.info("Document event subscription stopped")

        except Exception as e:
            logger.error(f"Error stopping event subscription: {e}")

    async def _register_subscription(self):
        """Register subscription with Bridge service"""
        subscription_config = {
            "subscription_id": self.subscription_id,
            "service_name": "langextract",
            "event_types": self.event_filters["event_types"],
            "filters": {
                "document_extensions": self.event_filters["document_extensions"],
                "file_size_range": {
                    "min": self.event_filters["min_file_size"],
                    "max": self.event_filters["max_file_size"],
                },
            },
            "callback_config": {
                "delivery_mode": "polling",  # Use polling instead of webhook
                "polling_interval_seconds": 5,
                "batch_size": 10,
            },
        }

        try:
            response = await self.http_client.post(
                f"{self.bridge_service_url}/events/subscribe",
                json=subscription_config,
            )
            response.raise_for_status()

            logger.info(f"Registered event subscription: {self.subscription_id}")

        except httpx.HTTPError as e:
            logger.error(f"Failed to register subscription: {e}")
            raise

    async def _unregister_subscription(self):
        """Unregister subscription from Bridge service"""
        try:
            response = await self.http_client.delete(
                f"{self.bridge_service_url}/events/subscribe/{self.subscription_id}"
            )
            response.raise_for_status()

            logger.info(f"Unregistered event subscription: {self.subscription_id}")

        except httpx.HTTPError as e:
            logger.warning(f"Failed to unregister subscription: {e}")

    async def _event_polling_loop(self):
        """Main event polling loop"""
        while self.is_subscribed:
            try:
                # Poll for events from Bridge service
                events = await self._poll_events()

                if events:
                    logger.debug(f"Received {len(events)} document events")

                    for event in events:
                        await self._handle_event(event)

                # Wait before next poll
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event polling loop: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(10)  # Wait longer on error

    async def _poll_events(self) -> list:
        """Poll for events from Bridge service"""
        try:
            response = await self.http_client.get(
                f"{self.bridge_service_url}/events/poll/{self.subscription_id}",
                params={"limit": 10, "timeout": 30},
            )
            response.raise_for_status()

            data = response.json()
            return data.get("events", [])

        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                # Subscription not found, try to re-register
                logger.warning("Subscription not found, attempting to re-register")
                await self._register_subscription()
                return []
            else:
                logger.error(f"Failed to poll events: {e}")
                return []

    async def _handle_event(self, event: Dict[str, Any]):
        """Handle individual document event"""
        try:
            self.stats["events_received"] += 1

            # Extract event information
            event_type = event.get("event_type")
            document_path = event.get("document_path")
            event_id = event.get("event_id")

            logger.debug(
                f"Processing event {event_id}: {event_type} for {document_path}"
            )

            # Apply event filters
            if not self._should_process_event(event):
                self.stats["events_filtered"] += 1
                logger.debug(f"Event filtered out: {event_id}")
                return

            # Check if already processing this document
            if document_path in self.active_extractions:
                logger.debug(f"Already processing {document_path}, skipping")
                return

            # Add to extraction queue
            await self.extraction_queue.put(event)
            self.stats["extraction_triggered"] += 1

            logger.debug(f"Event queued for processing: {event_id}")

        except Exception as e:
            logger.error(f"Error handling event: {e}")
            self.stats["errors"] += 1

    def _should_process_event(self, event: Dict[str, Any]) -> bool:
        """Determine if event should trigger extraction"""
        document_path = event.get("document_path", "")
        event_type = event.get("event_type", "")

        # Check event type
        if event_type not in self.event_filters["event_types"]:
            return False

        # Check file extension
        file_extension = (
            "." + document_path.split(".")[-1] if "." in document_path else ""
        )
        if file_extension not in self.event_filters["document_extensions"]:
            return False

        # Check file size if available
        file_size = event.get("file_size")
        if file_size is not None:
            if (
                file_size < self.event_filters["min_file_size"]
                or file_size > self.event_filters["max_file_size"]
            ):
                return False

        # Additional filtering logic can be added here

        return True

    async def _process_extraction_queue(self):
        """Process queued extraction requests"""
        while True:
            try:
                # Wait for event from queue
                event = await self.extraction_queue.get()

                document_path = event.get("document_path")
                if document_path:
                    # Mark as active
                    self.active_extractions.add(document_path)

                    try:
                        # Call the registered callback
                        await self.callback(event)
                        self.stats["events_processed"] += 1

                    except Exception as e:
                        logger.error(
                            f"Error in extraction callback for {document_path}: {e}"
                        )
                        self.stats["errors"] += 1

                    finally:
                        # Remove from active extractions
                        self.active_extractions.discard(document_path)

                # Mark task as done
                self.extraction_queue.task_done()

            except Exception as e:
                logger.error(f"Error in extraction queue processing: {e}")
                await asyncio.sleep(1)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get subscription statistics"""
        return {
            "subscription_id": self.subscription_id,
            "is_subscribed": self.is_subscribed,
            "active_extractions": len(self.active_extractions),
            "queue_size": self.extraction_queue.qsize(),
            "statistics": self.stats.copy(),
            "event_filters": self.event_filters.copy(),
        }

    async def update_filters(self, new_filters: Dict[str, Any]):
        """Update event filtering configuration"""
        try:
            # Update local filters
            self.event_filters.update(new_filters)

            # Update subscription with Bridge service
            await self._update_subscription_filters()

            logger.info(f"Updated event filters: {new_filters}")

        except Exception as e:
            logger.error(f"Failed to update filters: {e}")
            raise

    async def _update_subscription_filters(self):
        """Update subscription filters with Bridge service"""
        filter_config = {
            "document_extensions": self.event_filters["document_extensions"],
            "file_size_range": {
                "min": self.event_filters["min_file_size"],
                "max": self.event_filters["max_file_size"],
            },
        }

        try:
            base_url = f"{self.bridge_service_url}/events/subscribe"
            url = f"{base_url}/{self.subscription_id}/filters"
            response = await self.http_client.put(url, json=filter_config)
            response.raise_for_status()

        except httpx.HTTPError as e:
            logger.error(f"Failed to update subscription filters: {e}")
            raise

    async def force_process_document(self, document_path: str):
        """Force processing of a specific document"""
        try:
            # Create a synthetic event
            synthetic_event = {
                "event_id": f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "event_type": "DOCUMENT_UPDATED",
                "document_path": document_path,
                "timestamp": datetime.utcnow().isoformat(),
                "manual_trigger": True,
            }

            # Add to processing queue
            await self.extraction_queue.put(synthetic_event)

            logger.info(f"Manually triggered extraction for: {document_path}")

        except Exception as e:
            logger.error(f"Failed to force process document {document_path}: {e}")
            raise


class DocumentEventFilter:
    """Helper class for advanced event filtering"""

    @staticmethod
    def create_language_filter(languages: list) -> Dict[str, Any]:
        """Create filter for specific programming languages"""
        language_extensions = {
            "python": [".py", ".pyx", ".pyi"],
            "javascript": [".js", ".jsx", ".mjs"],
            "typescript": [".ts", ".tsx"],
            "java": [".java"],
            "cpp": [".cpp", ".cxx", ".cc", ".hpp", ".h"],
            "go": [".go"],
            "rust": [".rs"],
            "markdown": [".md", ".markdown"],
        }

        extensions = []
        for lang in languages:
            extensions.extend(language_extensions.get(lang, []))

        return {"document_extensions": extensions}

    @staticmethod
    def create_size_filter(min_kb: int = 1, max_mb: int = 10) -> Dict[str, Any]:
        """Create filter for file size range"""
        return {
            "min_file_size": min_kb * 1024,
            "max_file_size": max_mb * 1024 * 1024,
        }

    @staticmethod
    def create_project_filter(project_patterns: list) -> Dict[str, Any]:
        """Create filter for specific project patterns"""
        return {
            "path_patterns": project_patterns,
            "exclude_patterns": [
                "*/node_modules/*",
                "*/venv/*",
                "*/.git/*",
                "*/dist/*",
                "*/build/*",
            ],
        }
