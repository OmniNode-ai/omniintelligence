"""
Schema Registry - Phase 1

Schema registry integration for event validation:
- Redpanda Schema Registry client
- JSON Schema validation
- Schema versioning (SemVer)
- Schema caching for performance
"""

from src.events.registry.schema_registry_client import SchemaRegistryClient

__all__ = ["SchemaRegistryClient"]
