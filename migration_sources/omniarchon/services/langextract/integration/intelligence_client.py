"""
Intelligence Service Client for LangExtract Service

Client for integrating with the existing Intelligence service to coordinate
entity extraction, knowledge graph updates, and semantic analysis.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from models.extraction_models import (
    EnhancedEntity,
    EnhancedRelationship,
    ExtractionResponse,
)

logger = logging.getLogger(__name__)


class IntelligenceServiceClient:
    """
    Client for communicating with the Archon Intelligence service.

    Provides methods for coordinating extraction tasks, updating knowledge graph,
    and leveraging existing intelligence capabilities.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8053",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize Intelligence service client.

        Args:
            base_url: Base URL of Intelligence service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Configure HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

        # Service coordination settings
        self.coordination_config = {
            "service_name": "langextract",
            "coordination_version": "1.0.0",
            "priority": "normal",
            "timeout_seconds": timeout,
        }

        # Statistics tracking
        self.stats = {
            "requests_sent": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "coordination_requests": 0,
            "knowledge_graph_updates": 0,
            "semantic_analysis_requests": 0,
        }

    async def health_check(self) -> bool:
        """Check if Intelligence service is healthy"""
        try:
            response = await self.http_client.get(f"{self.base_url}/health")
            self.stats["requests_sent"] += 1

            if response.status_code == 200:
                self.stats["requests_successful"] += 1
                return True
            else:
                self.stats["requests_failed"] += 1
                return False

        except Exception as e:
            logger.error(f"Intelligence service health check failed: {e}")
            self.stats["requests_failed"] += 1
            return False

    async def coordinate_extraction(
        self,
        extraction_request: Dict[str, Any],
        coordination_type: str = "entity_extraction",
    ) -> Optional[Dict[str, Any]]:
        """
        Coordinate extraction task with Intelligence service.

        Args:
            extraction_request: Extraction request details
            coordination_type: Type of coordination needed

        Returns:
            Coordination response or None if failed
        """
        try:
            coordination_payload = {
                "coordination_type": coordination_type,
                "source_service": "langextract",
                "request_data": extraction_request,
                "coordination_config": self.coordination_config,
                "timestamp": datetime.utcnow().isoformat(),
            }

            response = await self._make_request(
                "POST",
                "/coordinate",
                json=coordination_payload,
            )

            if response:
                self.stats["coordination_requests"] += 1
                logger.debug(f"Extraction coordination successful: {coordination_type}")
                return response

            return None

        except Exception as e:
            logger.error(f"Extraction coordination failed: {e}")
            return None

    async def enhance_entities_with_intelligence(
        self,
        entities: List[EnhancedEntity],
        enhancement_options: Optional[Dict[str, Any]] = None,
    ) -> List[EnhancedEntity]:
        """
        Enhance entities using Intelligence service capabilities.

        Args:
            entities: List of entities to enhance
            enhancement_options: Enhancement configuration options

        Returns:
            List of enhanced entities
        """
        try:
            if not entities:
                return entities

            # Prepare entities for Intelligence service format
            entity_data = [
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "entity_type": entity.entity_type.value,
                    "description": entity.description,
                    "confidence_score": entity.confidence_score,
                    "source_path": entity.source_path,
                    "properties": entity.properties,
                    "content": entity.content,
                }
                for entity in entities
            ]

            enhancement_request = {
                "entities": entity_data,
                "enhancement_options": enhancement_options or {},
                "source_service": "langextract",
            }

            response = await self._make_request(
                "POST",
                "/enhance/entities",
                json=enhancement_request,
            )

            if response and response.get("enhanced_entities"):
                enhanced_entities = []

                for i, enhanced_data in enumerate(response["enhanced_entities"]):
                    # Update original entity with enhanced data
                    if i < len(entities):
                        original_entity = entities[i]

                        # Update with enhanced information
                        if "semantic_embedding" in enhanced_data:
                            original_entity.semantic_embedding = enhanced_data[
                                "semantic_embedding"
                            ]

                        if "semantic_concepts" in enhanced_data:
                            original_entity.semantic_concepts = enhanced_data[
                                "semantic_concepts"
                            ]

                        if "quality_score" in enhanced_data:
                            original_entity.quality_score = enhanced_data[
                                "quality_score"
                            ]

                        if "enhanced_properties" in enhanced_data:
                            original_entity.properties.update(
                                enhanced_data["enhanced_properties"]
                            )

                        enhanced_entities.append(original_entity)

                logger.debug(
                    f"Enhanced {len(enhanced_entities)} entities with Intelligence service"
                )
                return enhanced_entities

            # Return original entities if enhancement failed
            return entities

        except Exception as e:
            logger.error(f"Entity enhancement failed: {e}")
            return entities

    async def update_knowledge_graph_bulk(
        self,
        entities: List[EnhancedEntity],
        relationships: List[EnhancedRelationship],
        update_options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update knowledge graph with entities and relationships in bulk.

        Args:
            entities: List of entities to add/update
            relationships: List of relationships to add/update
            update_options: Update configuration options

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Prepare entities for knowledge graph format
            entity_data = []
            for entity in entities:
                kg_entity = {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "entity_type": entity.entity_type.value,
                    "description": entity.description,
                    "confidence_score": entity.confidence_score,
                    "source_path": entity.source_path,
                    "properties": entity.properties,
                    "metadata": {
                        "extraction_method": entity.metadata.extraction_method,
                        "language_detected": (
                            entity.language.value if entity.language else "en"
                        ),
                        "created_at": datetime.utcnow().isoformat(),
                    },
                }
                entity_data.append(kg_entity)

            # Prepare relationships for knowledge graph format
            relationship_data = []
            for rel in relationships:
                kg_relationship = {
                    "relationship_id": rel.relationship_id,
                    "source_entity_id": rel.source_entity_id,
                    "target_entity_id": rel.target_entity_id,
                    "relationship_type": rel.relationship_type.value,
                    "confidence_score": rel.confidence_score,
                    "description": rel.description,
                    "properties": rel.properties,
                    "metadata": {
                        "created_at": rel.created_at.isoformat(),
                        "detected_in_source": rel.detected_in_source,
                    },
                }
                relationship_data.append(kg_relationship)

            # Prepare bulk update request
            bulk_update_request = {
                "entities": entity_data,
                "relationships": relationship_data,
                "update_options": update_options
                or {
                    "mode": "upsert",
                    "validate_before_update": True,
                    "create_missing_entities": True,
                },
                "source_service": "langextract",
                "batch_id": f"langextract_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            }

            response = await self._make_request(
                "POST",
                "/knowledge-graph/bulk-update",
                json=bulk_update_request,
            )

            if response and response.get("success"):
                self.stats["knowledge_graph_updates"] += 1
                logger.info(
                    f"Knowledge graph bulk update successful: {len(entities)} entities, {len(relationships)} relationships"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Knowledge graph bulk update failed: {e}")
            return False

    async def request_semantic_analysis(
        self,
        content: str,
        analysis_type: str = "comprehensive",
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Request semantic analysis from Intelligence service.

        Args:
            content: Content to analyze
            analysis_type: Type of analysis to perform
            context: Additional context for analysis

        Returns:
            Semantic analysis results or None if failed
        """
        try:
            analysis_request = {
                "content": content,
                "analysis_type": analysis_type,
                "context": context,
                "source_service": "langextract",
                "analysis_options": {
                    "include_concepts": True,
                    "include_themes": True,
                    "include_sentiment": True,
                    "include_entities": True,
                },
            }

            response = await self._make_request(
                "POST",
                "/analyze/semantic",
                json=analysis_request,
            )

            if response:
                self.stats["semantic_analysis_requests"] += 1
                logger.debug(f"Semantic analysis successful: {analysis_type}")
                return response

            return None

        except Exception as e:
            logger.error(f"Semantic analysis request failed: {e}")
            return None

    async def get_entity_suggestions(
        self,
        partial_entity: Dict[str, Any],
        suggestion_count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get entity suggestions from Intelligence service.

        Args:
            partial_entity: Partial entity data for suggestions
            suggestion_count: Number of suggestions to return

        Returns:
            List of entity suggestions
        """
        try:
            suggestion_request = {
                "partial_entity": partial_entity,
                "suggestion_count": suggestion_count,
                "suggestion_types": [
                    "similar_entities",
                    "entity_enhancements",
                    "related_concepts",
                ],
                "source_service": "langextract",
            }

            response = await self._make_request(
                "POST",
                "/suggest/entities",
                json=suggestion_request,
            )

            return response.get("suggestions", []) if response else []

        except Exception as e:
            logger.error(f"Entity suggestions request failed: {e}")
            return []

    async def validate_extraction_quality(
        self,
        extraction_result: ExtractionResponse,
    ) -> Dict[str, Any]:
        """
        Validate extraction quality using Intelligence service.

        Args:
            extraction_result: Extraction result to validate

        Returns:
            Quality validation results
        """
        try:
            validation_request = {
                "extraction_id": extraction_result.extraction_id,
                "document_path": extraction_result.document_path,
                "entity_count": len(extraction_result.enriched_entities),
                "relationship_count": len(extraction_result.relationships),
                "extraction_confidence": extraction_result.extraction_statistics.confidence_score,
                "language_results": {
                    "language_detected": extraction_result.language_results.language_detected.value,
                    "confidence_score": extraction_result.language_results.confidence_score,
                    "multilingual_detected": extraction_result.language_results.multilingual_detected,
                },
                "source_service": "langextract",
            }

            response = await self._make_request(
                "POST",
                "/validate/extraction",
                json=validation_request,
            )

            return response or {
                "validation_score": 0.5,
                "validation_notes": ["Validation failed"],
            }

        except Exception as e:
            logger.error(f"Extraction quality validation failed: {e}")
            return {
                "validation_score": 0.0,
                "validation_notes": [f"Validation error: {str(e)}"],
            }

    async def sync_with_intelligence_models(self) -> bool:
        """
        Synchronize with Intelligence service data models and schemas.

        Returns:
            True if synchronization successful, False otherwise
        """
        try:
            sync_request = {
                "source_service": "langextract",
                "sync_types": [
                    "entity_schemas",
                    "relationship_schemas",
                    "extraction_patterns",
                ],
                "service_version": "1.0.0",
            }

            response = await self._make_request(
                "POST",
                "/sync/models",
                json=sync_request,
            )

            if response and response.get("sync_successful"):
                logger.info("Intelligence service model synchronization successful")
                return True

            return False

        except Exception as e:
            logger.error(f"Intelligence service model synchronization failed: {e}")
            return False

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to Intelligence service with retry logic.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Response data or None if failed
        """
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries + 1):
            try:
                self.stats["requests_sent"] += 1

                response = await self.http_client.request(method, url, **kwargs)

                if response.status_code == 200:
                    self.stats["requests_successful"] += 1
                    return response.json()
                else:
                    logger.warning(
                        f"Intelligence service request failed: {response.status_code} {response.text}"
                    )

            except Exception as e:
                if attempt < self.max_retries:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"Request attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All request attempts failed: {e}")
                    self.stats["requests_failed"] += 1

        return None

    async def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics"""
        total_requests = (
            self.stats["requests_successful"] + self.stats["requests_failed"]
        )
        success_rate = self.stats["requests_successful"] / max(total_requests, 1)

        return {
            "client_name": "intelligence_service_client",
            "base_url": self.base_url,
            "total_requests": total_requests,
            "successful_requests": self.stats["requests_successful"],
            "failed_requests": self.stats["requests_failed"],
            "success_rate": success_rate,
            "coordination_requests": self.stats["coordination_requests"],
            "knowledge_graph_updates": self.stats["knowledge_graph_updates"],
            "semantic_analysis_requests": self.stats["semantic_analysis_requests"],
            "configuration": self.coordination_config,
        }

    async def close(self):
        """Close the HTTP client"""
        try:
            await self.http_client.aclose()
            logger.info("Intelligence service client closed")
        except Exception as e:
            logger.error(f"Error closing Intelligence service client: {e}")
