"""
Qdrant Collection Schemas

Defines Qdrant vector database collection configurations for file location search.
Provides schema definitions, payload structures, and helper methods for collection management.

ONEX Pattern: Compute (Configuration and schema definitions)
Performance: Collection creation <1s, payload validation <5ms
"""

import os
from typing import Any, Dict, List, Optional

from qdrant_client.models import Distance, VectorParams


class QdrantSchemas:
    """
    Qdrant collection schemas for file location search.

    Collections:
    - archon_vectors: Main collection for file metadata and semantic search

    Vector Configuration:
    - Size: Configurable via EMBEDDING_DIMENSIONS env var (default: 1536)
    - Distance: Cosine similarity
    """

    # Collection names
    FILE_LOCATIONS_COLLECTION = "archon_vectors"

    # Vector configuration - read from environment
    EMBEDDING_SIZE = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    DISTANCE_METRIC = Distance.COSINE

    @staticmethod
    def get_file_locations_config() -> Dict[str, Any]:
        """
        Get configuration for archon_vectors collection.

        Returns:
            Collection configuration dictionary with vectors_config

        Example:
            >>> config = QdrantSchemas.get_file_locations_config()
            >>> # Use with Qdrant client to create collection
            >>> client.create_collection(
            ...     collection_name=config["collection_name"],
            ...     vectors_config=config["vectors_config"]
            ... )
        """
        return {
            "collection_name": QdrantSchemas.FILE_LOCATIONS_COLLECTION,
            "vectors_config": VectorParams(
                size=QdrantSchemas.EMBEDDING_SIZE,
                distance=QdrantSchemas.DISTANCE_METRIC,
            ),
        }

    @staticmethod
    def get_payload_schema() -> Dict[str, str]:
        """
        Get payload schema for archon_vectors collection.

        This defines the metadata fields stored with each vector point.
        All fields are indexed for filtering and querying.

        Returns:
            Payload schema dictionary mapping field names to types

        Payload Fields:
            - absolute_path: Full file path (keyword index)
            - relative_path: Path relative to project root (keyword index)
            - file_hash: BLAKE3 hash of file content (keyword index)
            - project_name: Project identifier (keyword index)
            - project_root: Project root directory (keyword index)
            - file_type: File extension (keyword index)
            - quality_score: Code quality score 0.0-1.0 (float index)
            - onex_compliance: ONEX compliance score 0.0-1.0 (float index)
            - onex_type: ONEX node type (keyword index)
            - concepts: Semantic concepts (keyword[] index)
            - themes: High-level themes (keyword[] index)
            - domains: Domain classification (keyword[] index)
            - pattern_types: Pattern classifications (keyword[] index)
            - indexed_at: Indexing timestamp (datetime index)
            - last_modified: File modification time (datetime index)

        Example:
            >>> schema = QdrantSchemas.get_payload_schema()
            >>> print(schema["quality_score"])  # "float"
        """
        return {
            # Path identifiers
            "absolute_path": "keyword",
            "relative_path": "keyword",
            "file_hash": "keyword",
            # Project information
            "project_name": "keyword",
            "project_root": "keyword",
            "file_type": "keyword",
            # Quality metrics
            "quality_score": "float",
            "onex_compliance": "float",
            "onex_type": "keyword",
            # Semantic metadata
            "concepts": "keyword[]",
            "themes": "keyword[]",
            "domains": "keyword[]",
            "pattern_types": "keyword[]",
            # Timestamps
            "indexed_at": "datetime",
            "last_modified": "datetime",
        }

    @staticmethod
    def get_example_payload() -> Dict[str, Any]:
        """
        Get example payload for documentation and testing.

        Returns:
            Example payload dictionary with all fields populated

        Example:
            >>> payload = QdrantSchemas.get_example_payload()
            >>> print(payload["absolute_path"])
        """
        return {
            "absolute_path": "/Volumes/PRO-G40/Code/omniarchon/src/services/auth/jwt_handler.py",
            "relative_path": "src/services/auth/jwt_handler.py",
            "file_hash": "blake3_abc123def456",
            "project_name": "omniarchon",
            "project_root": "/Volumes/PRO-G40/Code/omniarchon",
            "file_type": ".py",
            "quality_score": 0.87,
            "onex_compliance": 0.92,
            "onex_type": "effect",
            "concepts": ["authentication", "JWT", "token", "security"],
            "themes": ["security", "api"],
            "domains": ["backend.auth"],
            "pattern_types": ["effect"],
            "indexed_at": "2025-10-24T12:00:00Z",
            "last_modified": "2025-10-23T15:30:00Z",
        }

    @staticmethod
    def get_filter_examples() -> Dict[str, Dict[str, Any]]:
        """
        Get example Qdrant filters for common query patterns.

        Returns:
            Dictionary of named filter examples

        Examples:
            >>> filters = QdrantSchemas.get_filter_examples()
            >>> project_filter = filters["filter_by_project"]
        """
        return {
            "filter_by_project": {
                "must": [
                    {
                        "key": "project_name",
                        "match": {"value": "omniarchon"},
                    }
                ]
            },
            "filter_by_quality": {
                "must": [
                    {
                        "key": "quality_score",
                        "range": {"gte": 0.7},
                    }
                ]
            },
            "filter_by_file_type": {
                "must": [
                    {
                        "key": "file_type",
                        "match": {"value": ".py"},
                    }
                ]
            },
            "filter_by_onex_type": {
                "must": [
                    {
                        "key": "onex_type",
                        "match": {"value": "effect"},
                    }
                ]
            },
            "filter_by_concept": {
                "must": [
                    {
                        "key": "concepts",
                        "match": {"value": "authentication"},
                    }
                ]
            },
            "composite_filter": {
                "must": [
                    {
                        "key": "project_name",
                        "match": {"value": "omniarchon"},
                    },
                    {
                        "key": "quality_score",
                        "range": {"gte": 0.8},
                    },
                    {
                        "key": "file_type",
                        "match": {"value": ".py"},
                    },
                ]
            },
        }

    @staticmethod
    def validate_payload(payload: Dict[str, Any]) -> bool:
        """
        Validate payload structure against schema.

        Args:
            payload: Payload dictionary to validate

        Returns:
            True if payload is valid, False otherwise

        Example:
            >>> payload = {"absolute_path": "/path/to/file.py", ...}
            >>> is_valid = QdrantSchemas.validate_payload(payload)
        """
        schema = QdrantSchemas.get_payload_schema()
        required_fields = [
            "absolute_path",
            "relative_path",
            "file_hash",
            "project_name",
            "project_root",
            "file_type",
        ]

        # Check required fields
        for field in required_fields:
            if field not in payload:
                return False

        # Type validation
        if not isinstance(payload.get("quality_score", 0.0), (int, float)):
            return False
        if not isinstance(payload.get("onex_compliance", 0.0), (int, float)):
            return False
        if not isinstance(payload.get("concepts", []), list):
            return False
        if not isinstance(payload.get("themes", []), list):
            return False

        return True


__all__ = ["QdrantSchemas"]
