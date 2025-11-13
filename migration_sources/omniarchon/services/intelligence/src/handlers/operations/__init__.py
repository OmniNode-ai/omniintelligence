"""
Intelligence Request Operation Handlers

Handlers for the 4 intelligence request operations defined in manifest_injector spec:
- PatternExtractionHandler: Query Qdrant for code generation patterns
- InfrastructureScanHandler: Query PostgreSQL, Kafka, Qdrant, Docker
- ModelDiscoveryHandler: Scan file system and query Memgraph
- SchemaDiscoveryHandler: Query PostgreSQL schemas

Created: 2025-10-26
Purpose: Automatic intelligence request handling for omniclaude manifest_injector
"""

from src.handlers.operations.infrastructure_scan_handler import (
    InfrastructureScanHandler,
)
from src.handlers.operations.model_discovery_handler import ModelDiscoveryHandler
from src.handlers.operations.pattern_extraction_handler import PatternExtractionHandler
from src.handlers.operations.schema_discovery_handler import SchemaDiscoveryHandler

__all__ = [
    "PatternExtractionHandler",
    "InfrastructureScanHandler",
    "ModelDiscoveryHandler",
    "SchemaDiscoveryHandler",
]
