"""
Unified Entity Type Adapter for Intelligence Service

This adapter provides backwards compatibility between the intelligence service's
existing EntityType system and the new unified EntityType system.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared_models"))

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from base_models import BaseEntity as UnifiedBaseEntity
from base_models import EntityMetadata as UnifiedEntityMetadata
from entity_types import EntityType as UnifiedEntityType
from entity_types import (
    EntityTypeMapper,
    normalize_entity_type,
)

# Import existing intelligence models
from .entity_models import (
    EntityExtractionResult,
)
from .entity_models import EntityMetadata as LegacyEntityMetadata
from .entity_models import EntityType as LegacyEntityType
from .entity_models import (
    KnowledgeEntity,
)


class EntityTypeAdapter:
    """Adapter for converting between legacy and unified entity types."""

    @staticmethod
    def legacy_to_unified(legacy_type: LegacyEntityType) -> UnifiedEntityType:
        """Convert legacy intelligence EntityType to unified EntityType."""
        # Create a mapping from legacy uppercase to unified lowercase
        mapping = {
            LegacyEntityType.FUNCTION: UnifiedEntityType.FUNCTION,
            LegacyEntityType.CLASS: UnifiedEntityType.CLASS,
            LegacyEntityType.METHOD: UnifiedEntityType.METHOD,
            LegacyEntityType.MODULE: UnifiedEntityType.MODULE,
            LegacyEntityType.INTERFACE: UnifiedEntityType.INTERFACE,
            LegacyEntityType.API_ENDPOINT: UnifiedEntityType.API_ENDPOINT,
            LegacyEntityType.SERVICE: UnifiedEntityType.SERVICE,
            LegacyEntityType.COMPONENT: UnifiedEntityType.COMPONENT,
            LegacyEntityType.CONCEPT: UnifiedEntityType.CONCEPT,
            LegacyEntityType.DOCUMENT: UnifiedEntityType.DOCUMENT,
            LegacyEntityType.CODE_EXAMPLE: UnifiedEntityType.CODE_EXAMPLE,
            LegacyEntityType.PATTERN: UnifiedEntityType.PATTERN,
            LegacyEntityType.VARIABLE: UnifiedEntityType.VARIABLE,
            LegacyEntityType.CONSTANT: UnifiedEntityType.CONSTANT,
            LegacyEntityType.CONFIG_SETTING: UnifiedEntityType.CONFIG_SETTING,
        }
        return mapping.get(legacy_type, UnifiedEntityType.ENTITY)

    @staticmethod
    def unified_to_legacy(unified_type: UnifiedEntityType) -> LegacyEntityType:
        """Convert unified EntityType to legacy intelligence EntityType."""
        return EntityTypeMapper.to_intelligence_type(unified_type)

    @staticmethod
    def knowledge_entity_to_unified(
        knowledge_entity: KnowledgeEntity,
    ) -> UnifiedBaseEntity:
        """Convert KnowledgeEntity to unified BaseEntity."""
        unified_type = EntityTypeAdapter.legacy_to_unified(knowledge_entity.entity_type)

        # Convert metadata
        unified_metadata = UnifiedEntityMetadata(
            created_at=knowledge_entity.metadata.created_at,
            updated_at=knowledge_entity.metadata.updated_at,
            created_by="intelligence-service",
            extraction_confidence=knowledge_entity.metadata.extraction_confidence,
            validation_status=knowledge_entity.metadata.validation_status,
            source_path=knowledge_entity.source_path,
            source_hash=knowledge_entity.metadata.file_hash,
            line_number=knowledge_entity.source_line_number,
            service_metadata={
                "complexity_score": knowledge_entity.metadata.complexity_score,
                "maintainability_score": knowledge_entity.metadata.maintainability_score,
                "documentation_refs": knowledge_entity.metadata.documentation_refs,
                "dependencies": knowledge_entity.metadata.dependencies,
                "review_status": knowledge_entity.metadata.review_status,
                "extraction_method": knowledge_entity.metadata.extraction_method,
            },
        )

        return UnifiedBaseEntity(
            entity_id=knowledge_entity.entity_id,
            entity_type=unified_type,
            name=knowledge_entity.name,
            description=knowledge_entity.description,
            content=None,  # KnowledgeEntity doesn't have content field
            source_id=None,  # Would need to be derived from source_path
            embedding=knowledge_entity.embedding,
            metadata=unified_metadata,
            properties=knowledge_entity.properties,
        )

    @staticmethod
    def unified_to_knowledge_entity(
        unified_entity: UnifiedBaseEntity,
    ) -> KnowledgeEntity:
        """Convert unified BaseEntity to KnowledgeEntity."""
        legacy_type = EntityTypeAdapter.unified_to_legacy(unified_entity.entity_type)

        # Convert metadata back
        legacy_metadata = LegacyEntityMetadata(
            file_hash=unified_entity.metadata.source_hash,
            extraction_method=unified_entity.metadata.service_metadata.get(
                "extraction_method", "base_extraction"
            ),
            extraction_confidence=unified_entity.metadata.extraction_confidence,
            documentation_refs=unified_entity.metadata.service_metadata.get(
                "documentation_refs", []
            ),
            validation_status=unified_entity.metadata.validation_status,
            review_status=unified_entity.metadata.service_metadata.get(
                "review_status", "unreviewed"
            ),
            complexity_score=unified_entity.metadata.service_metadata.get(
                "complexity_score"
            ),
            maintainability_score=unified_entity.metadata.service_metadata.get(
                "maintainability_score"
            ),
            dependencies=unified_entity.metadata.service_metadata.get(
                "dependencies", []
            ),
            created_at=unified_entity.metadata.created_at,
            updated_at=unified_entity.metadata.updated_at,
        )

        return KnowledgeEntity(
            entity_id=unified_entity.entity_id,
            name=unified_entity.name,
            entity_type=legacy_type,
            description=unified_entity.description,
            source_path=unified_entity.metadata.source_path or "",
            confidence_score=unified_entity.metadata.extraction_confidence,
            metadata=legacy_metadata,
            source_line_number=unified_entity.metadata.line_number,
            embedding=unified_entity.embedding,
            properties=unified_entity.properties,
        )


class SearchResultAdapter:
    """Adapter for converting entity types in search results for external services."""

    @staticmethod
    def prepare_for_search_service(
        entities: List[KnowledgeEntity],
    ) -> List[Dict[str, Any]]:
        """
        Prepare entities for indexing in the search service.

        Converts intelligence entities to search-compatible format with proper EntityType mapping.
        """
        search_documents = []

        for entity in entities:
            # Convert to unified type first, then to search type
            unified_type = EntityTypeAdapter.legacy_to_unified(entity.entity_type)
            search_type = EntityTypeMapper.to_search_type(unified_type)

            search_doc = {
                "entity_id": entity.entity_id,
                "entity_type": search_type.value,  # Use search service compatible type
                "title": entity.name,
                "content": entity.description,
                "url": None,  # Intelligence entities don't have URLs
                "metadata": {
                    "source_path": entity.source_path,
                    "entity_confidence": entity.confidence_score,
                    "extraction_method": entity.metadata.extraction_method,
                    "complexity_score": entity.metadata.complexity_score,
                    "maintainability_score": entity.metadata.maintainability_score,
                    "line_number": entity.source_line_number,
                    "unified_type": unified_type.value,  # Store original unified type
                    "intelligence_type": entity.entity_type.value,  # Store original intelligence type
                    "service": "intelligence",
                },
                "embedding": entity.embedding,
            }

            search_documents.append(search_doc)

        return search_documents

    @staticmethod
    def handle_search_response(
        search_results: List[Dict[str, Any]],
    ) -> List[KnowledgeEntity]:
        """
        Convert search results back to KnowledgeEntity format.

        This handles the reverse conversion when getting search results that contain
        intelligence entities.
        """
        entities = []

        for result in search_results:
            metadata_dict = result.get("metadata", {})

            # Try to get the original intelligence type, fall back to conversion
            if "intelligence_type" in metadata_dict:
                try:
                    legacy_type = LegacyEntityType(metadata_dict["intelligence_type"])
                except ValueError:
                    # Fallback to conversion from unified type
                    unified_type = normalize_entity_type(
                        metadata_dict.get("unified_type", "entity")
                    )
                    legacy_type = EntityTypeAdapter.unified_to_legacy(unified_type)
            else:
                # Convert from search type to intelligence type
                search_type_str = result.get("entity_type", "entity")
                unified_type = normalize_entity_type(search_type_str)
                legacy_type = EntityTypeAdapter.unified_to_legacy(unified_type)

            # Create metadata
            entity_metadata = LegacyEntityMetadata(
                extraction_confidence=metadata_dict.get("entity_confidence", 0.0),
                extraction_method=metadata_dict.get(
                    "extraction_method", "search_retrieval"
                ),
                complexity_score=metadata_dict.get("complexity_score"),
                maintainability_score=metadata_dict.get("maintainability_score"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            entity = KnowledgeEntity(
                entity_id=result["entity_id"],
                name=result.get("title", ""),
                entity_type=legacy_type,
                description=result.get("content", ""),
                source_path=metadata_dict.get("source_path", ""),
                confidence_score=metadata_dict.get("entity_confidence", 0.0),
                metadata=entity_metadata,
                source_line_number=metadata_dict.get("line_number"),
                embedding=result.get("embedding"),
                properties={},
            )

            entities.append(entity)

        return entities


class EntityExtractionResultAdapter:
    """Adapter for entity extraction results with unified types."""

    @staticmethod
    def create_compatible_result(
        entities: List[KnowledgeEntity],
        processing_time_ms: float,
        extraction_metadata: Optional[Dict[str, Any]] = None,
    ) -> EntityExtractionResult:
        """Create an EntityExtractionResult that's compatible with existing intelligence service APIs."""

        # Calculate confidence stats
        confidence_scores = [e.confidence_score for e in entities]
        if confidence_scores:
            from entity_models import ConfidenceStats

            confidence_stats = ConfidenceStats(
                mean=sum(confidence_scores) / len(confidence_scores),
                min=min(confidence_scores),
                max=max(confidence_scores),
                std=None,  # Would need numpy to calculate
            )
        else:
            from entity_models import ConfidenceStats

            confidence_stats = ConfidenceStats()

        # Add unified type information to extraction metadata
        unified_metadata = extraction_metadata or {}
        unified_metadata.update(
            {
                "unified_types_used": True,
                "entity_type_mapping": "legacy_to_unified_adapter",
                "search_compatibility": True,
                "entity_type_distribution": {},
            }
        )

        # Calculate entity type distribution using both legacy and unified types
        for entity in entities:
            unified_type = EntityTypeAdapter.legacy_to_unified(entity.entity_type)
            legacy_key = entity.entity_type.value
            unified_key = unified_type.value

            # Track both for debugging
            if (
                "legacy_distribution"
                not in unified_metadata["entity_type_distribution"]
            ):
                unified_metadata["entity_type_distribution"]["legacy_distribution"] = {}
            if (
                "unified_distribution"
                not in unified_metadata["entity_type_distribution"]
            ):
                unified_metadata["entity_type_distribution"][
                    "unified_distribution"
                ] = {}

            legacy_dist = unified_metadata["entity_type_distribution"][
                "legacy_distribution"
            ]
            unified_dist = unified_metadata["entity_type_distribution"][
                "unified_distribution"
            ]

            legacy_dist[legacy_key] = legacy_dist.get(legacy_key, 0) + 1
            unified_dist[unified_key] = unified_dist.get(unified_key, 0) + 1

        return EntityExtractionResult(
            entities=entities,
            relationships=[],  # Relationships would need separate handling
            total_count=len(entities),
            processing_time_ms=processing_time_ms,
            confidence_stats=confidence_stats,
            extraction_metadata=unified_metadata,
        )


# Utility functions for easy integration


def extract_with_unified_types(
    content: str, source_path: str, extractor_instance, **kwargs
) -> EntityExtractionResult:
    """
    Extract entities using existing intelligence service but with unified type compatibility.

    This function wraps the existing extraction logic to ensure compatibility with
    the unified entity type system.
    """
    # Call the existing extractor
    result = extractor_instance.extract_entities(content, source_path, **kwargs)

    # The result already contains KnowledgeEntity objects with legacy types
    # We don't need to convert them, but we can add metadata about unified type compatibility
    metadata_update = {
        "unified_types_compatible": True,
        "can_convert_to_search": True,
        "adapter_version": "1.0.0",
    }

    if result.extraction_metadata:
        result.extraction_metadata.update(metadata_update)
    else:
        result.extraction_metadata = metadata_update

    return result


def prepare_entities_for_external_service(
    entities: List[KnowledgeEntity], target_service: str = "search"
) -> List[Dict[str, Any]]:
    """
    Prepare intelligence entities for use in external services.

    Args:
        entities: List of KnowledgeEntity objects
        target_service: Target service name ("search", "bridge", etc.)

    Returns:
        List of dictionaries formatted for the target service
    """
    if target_service == "search":
        return SearchResultAdapter.prepare_for_search_service(entities)
    else:
        # For other services, convert to unified format
        unified_entities = [
            EntityTypeAdapter.knowledge_entity_to_unified(entity) for entity in entities
        ]
        return [entity.model_dump() for entity in unified_entities]
