"""
Pattern Extraction Handler

Handles PATTERN_EXTRACTION operation requests by querying Qdrant vector database
for code generation patterns.

Created: 2025-10-26
Purpose: Provide code generation patterns to omniclaude manifest_injector
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from src.events.models.intelligence_adapter_events import ModelPatternExtractionPayload

logger = logging.getLogger(__name__)


class PatternExtractionHandler:
    """
    Handle PATTERN_EXTRACTION operations.

    Query Qdrant vector database for code generation patterns and return
    structured results for manifest_injector.

    Performance Target: <1500ms query timeout
    """

    # Configuration
    DEFAULT_COLLECTION = "code_generation_patterns"  # Pattern learning collection
    ACTUAL_COLLECTION = (
        "code_generation_patterns"  # Actual Qdrant collection with code patterns
    )
    DEFAULT_LIMIT = 10
    TIMEOUT_MS = 1500  # Per spec: 1500ms query timeout

    # Collection mapping: legacy collection names -> actual collection + pattern_type filter
    COLLECTION_MAPPING = {
        "execution_patterns": ("code_generation_patterns", None),  # Code gen patterns
        "code_patterns": ("code_generation_patterns", None),  # Code gen patterns
        "code_generation_patterns": ("code_generation_patterns", None),  # Direct access
        "archon_vectors": (
            "archon_vectors",
            None,
        ),  # AST/mypy stub data (different use case)
    }

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        qdrant_collection: Optional[str] = None,
    ):
        """
        Initialize Pattern Extraction handler.

        Args:
            qdrant_url: Qdrant URL (default: from environment or http://qdrant:6333)
            qdrant_collection: Collection name (default: execution_patterns)
        """
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.collection_name = qdrant_collection or self.DEFAULT_COLLECTION
        self._client: Optional[AsyncQdrantClient] = None

    async def _get_client(self) -> AsyncQdrantClient:
        """Get or create Qdrant client."""
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self.qdrant_url,
                timeout=self.TIMEOUT_MS / 1000,  # Convert to seconds
            )
        return self._client

    async def execute(
        self,
        source_path: str,
        options: Dict[str, Any],
    ) -> ModelPatternExtractionPayload:
        """
        Execute PATTERN_EXTRACTION operation.

        Args:
            source_path: Pattern filter (e.g., "node_*_*.py")
            options: Operation options (include_patterns, pattern_types, collection_name, etc.)

        Returns:
            ModelPatternExtractionPayload with pattern results

        Raises:
            Exception: If query fails or times out
        """
        start_time = time.perf_counter()

        try:
            # Extract options
            include_patterns = options.get("include_patterns", True)
            pattern_types = options.get("pattern_types", [])
            limit = options.get("limit", self.DEFAULT_LIMIT)
            # Allow override of collection name per-request
            requested_collection = options.get("collection_name", self.collection_name)

            # Map legacy collection names to actual collection + pattern_type filter
            actual_collection, pattern_type_filter = self.COLLECTION_MAPPING.get(
                requested_collection, (requested_collection, None)
            )

            logger.info(
                f"Executing PATTERN_EXTRACTION | requested_collection={requested_collection} | "
                f"actual_collection={actual_collection} | pattern_type_filter={pattern_type_filter} | "
                f"source_path={source_path} | pattern_types={pattern_types} | limit={limit}"
            )

            # Query Qdrant for patterns
            client = await self._get_client()

            # Check if collection exists
            collections = await client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if actual_collection not in collection_names:
                logger.warning(
                    f"Collection '{actual_collection}' not found. "
                    f"Available: {collection_names}. Returning empty results."
                )
                return ModelPatternExtractionPayload(
                    patterns=[],
                    query_time_ms=(time.perf_counter() - start_time) * 1000,
                    total_count=0,
                )

            # Build query filter based on options
            filter_conditions = []

            # Add pattern_type filter from collection mapping
            if pattern_type_filter:
                filter_conditions.append(
                    models.FieldCondition(
                        key="pattern_type",
                        match=models.MatchValue(value=pattern_type_filter),
                    )
                )

            # Add node_types filter if specified
            if pattern_types:
                # Filter by node types if specified (using "node_type" field from ONEX patterns)
                filter_conditions.append(
                    models.Filter(
                        should=[
                            models.FieldCondition(
                                key="node_type",
                                match=models.MatchValue(value=pt),
                            )
                            for pt in pattern_types
                        ]
                    )
                )

            # Combine filters with AND logic
            # CRITICAL: Filter out test patterns with synthetic placeholder data
            # Test patterns have source_context.domain="domain_0" or "test_*"
            # and source_context.service_name="service_0" or similar test placeholders
            # These are created during development/testing and should not appear in production
            test_pattern_exclusions = [
                models.FieldCondition(
                    key="source_context.domain",
                    match=models.MatchValue(value="domain_0"),
                ),
                models.FieldCondition(
                    key="source_context.domain",
                    match=models.MatchText(text="test"),  # Catches test_1, test_2, etc.
                ),
                models.FieldCondition(
                    key="source_context.service_name",
                    match=models.MatchValue(value="service_0"),
                ),
            ]

            query_filter = None
            if filter_conditions:
                # Combine must conditions with must_not exclusions
                query_filter = models.Filter(
                    must=filter_conditions,
                    must_not=test_pattern_exclusions,
                )
            else:
                # Only test exclusions (no other filters)
                query_filter = models.Filter(must_not=test_pattern_exclusions)

            # Scroll through collection to get patterns
            # Note: Using scroll instead of search since we want all matching patterns
            patterns_raw, _ = await client.scroll(
                collection_name=actual_collection,
                scroll_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,  # Don't need vectors in results
            )

            # Transform Qdrant points to pattern objects
            patterns = []
            for point in patterns_raw:
                payload = point.payload or {}

                pattern = {
                    "name": payload.get("pattern_name", "Unknown Pattern"),
                    "file_path": payload.get("file_path", source_path),
                    "description": payload.get("description", ""),
                    "node_types": payload.get("node_types", []),
                    "confidence": payload.get("confidence", 0.5),
                    "use_cases": payload.get("use_cases", []),
                    "metadata": {
                        "complexity": payload.get("complexity", "unknown"),
                        "last_updated": payload.get(
                            "timestamp", "2025-10-26T00:00:00Z"
                        ),
                        "pattern_id": str(point.id),
                    },
                }
                patterns.append(pattern)

            query_time_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                f"PATTERN_EXTRACTION completed | patterns_found={len(patterns)} | "
                f"query_time_ms={query_time_ms:.2f}"
            )

            return ModelPatternExtractionPayload(
                patterns=patterns,
                query_time_ms=query_time_ms,
                total_count=len(patterns),
            )

        except Exception as e:
            query_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"PATTERN_EXTRACTION failed | error={e} | query_time_ms={query_time_ms:.2f}",
                exc_info=True,
            )
            raise

    async def cleanup(self):
        """Cleanup resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
