"""
Memgraph (Neo4j) API Response Models

Pydantic models for validating Memgraph/Neo4j Cypher query responses.

API Documentation: https://memgraph.com/docs/
Performance: Validation overhead <2ms for typical responses
"""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# NOTE: correlation_id support enabled for tracing
class MemgraphNode(BaseModel):
    """
    Represents a node in the knowledge graph.

    Nodes can have labels, properties, and an ID.
    """

    id: Optional[Union[int, str]] = Field(
        default=None, description="Node ID (database internal ID)"
    )
    labels: List[str] = Field(
        default_factory=list, description="Node labels (e.g., ['Document', 'Code'])"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Node properties (name, description, content, etc.)",
    )

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get node property with default fallback."""
        return self.properties.get(key, default)

    def has_label(self, label: str) -> bool:
        """Check if node has specific label."""
        return label in self.labels


class MemgraphRelationship(BaseModel):
    """
    Represents a relationship between nodes in the knowledge graph.

    Relationships have a type, start/end nodes, and optional properties.
    """

    id: Optional[Union[int, str]] = Field(default=None, description="Relationship ID")
    type: str = Field(
        ..., description="Relationship type (e.g., 'DEPENDS_ON', 'RELATES_TO')"
    )
    start_node_id: Optional[Union[int, str]] = Field(
        default=None, description="Start node ID"
    )
    end_node_id: Optional[Union[int, str]] = Field(
        default=None, description="End node ID"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Relationship properties"
    )

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get relationship property with default fallback."""
        return self.properties.get(key, default)


class MemgraphRecord(BaseModel):
    """
    Single record from a Cypher query result.

    A record contains key-value pairs where values can be nodes,
    relationships, or scalar values.

    Example:
        {
            "name": "example.py",
            "description": "Example file",
            "content": "...",
            "source_path": "/path/to/example.py",
            "entity_type": "code_file",
            "labels": ["Document", "Code"]
        }
    """

    data: Dict[str, Any] = Field(
        default_factory=dict, description="Record data as key-value pairs"
    )

    @field_validator("data", mode="before")
    @classmethod
    def validate_data(cls, v: Any) -> Dict[str, Any]:
        """
        Normalize various record formats into dict.

        Handles both dict format and neo4j.Record format.
        """
        if isinstance(v, dict):
            return v
        elif hasattr(v, "data"):
            # neo4j.Record has .data() method
            return dict(v.data())
        elif hasattr(v, "__iter__") and hasattr(v, "keys"):
            # Record-like object with keys() and iteration
            return {k: v[k] for k in v.keys()}
        else:
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key with default fallback."""
        return self.data.get(key, default)

    def keys(self) -> List[str]:
        """Get all keys in record."""
        return list(self.data.keys())

    def values(self) -> List[Any]:
        """Get all values in record."""
        return list(self.data.values())

    def items(self) -> List[tuple]:
        """Get all key-value pairs."""
        return list(self.data.items())


class MemgraphQueryResponse(BaseModel):
    """
    Response model for Memgraph Cypher query execution.

    Contains list of records and optional summary statistics.

    Example:
        {
            "records": [
                {
                    "data": {
                        "name": "example.py",
                        "description": "Example file",
                        "labels": ["Document", "Code"]
                    }
                }
            ],
            "summary": {
                "query_type": "r",
                "counters": {},
                "result_available_after": 10,
                "result_consumed_after": 15
            }
        }
    """

    records: List[MemgraphRecord] = Field(
        default_factory=list, description="List of query result records"
    )
    summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Query execution summary and statistics"
    )

    @field_validator("records", mode="before")
    @classmethod
    def validate_records(cls, v: Any) -> List[Dict]:
        """
        Normalize various record formats.

        Handles:
        - List of dicts
        - List of neo4j.Record objects
        - Raw list that needs wrapping
        """
        if isinstance(v, list):
            # Normalize each item
            normalized = []
            for item in v:
                if isinstance(item, dict):
                    # Already a dict, wrap in data if needed
                    if "data" in item:
                        normalized.append(item)
                    else:
                        normalized.append({"data": item})
                elif hasattr(item, "data"):
                    # neo4j.Record object
                    normalized.append({"data": dict(item.data())})
                elif hasattr(item, "keys"):
                    # Record-like object
                    normalized.append({"data": {k: item[k] for k in item.keys()}})
                else:
                    # Unknown format, wrap as-is
                    normalized.append({"data": {"value": item}})
            return normalized
        else:
            return []

    def get_records_as_dicts(self) -> List[Dict[str, Any]]:
        """Get all records as plain dictionaries."""
        return [record.data for record in self.records]

    def get_record_count(self) -> int:
        """Get number of records returned."""
        return len(self.records)

    def is_empty(self) -> bool:
        """Check if query returned no results."""
        return len(self.records) == 0

    def get_summary_stat(self, key: str, default: Any = None) -> Any:
        """Get summary statistic by key."""
        if self.summary is None:
            return default
        return self.summary.get(key, default)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "records": [
                    {
                        "data": {
                            "name": "example.py",
                            "description": "Python example file",
                            "source_path": "/path/to/example.py",
                            "labels": ["Document", "Code"],
                        }
                    }
                ],
                "summary": {"query_type": "r", "result_available_after": 10},
            }
        }
    )


class MemgraphHealthResponse(BaseModel):
    """
    Response model for Memgraph health check.

    Simple health status validation.
    """

    status: str = Field(..., description="Health status (up, down, degraded)")
    version: Optional[str] = Field(default=None, description="Memgraph version")
    uptime_seconds: Optional[int] = Field(default=None, description="Uptime in seconds")
    storage: Optional[Dict[str, Any]] = Field(
        default=None, description="Storage statistics"
    )

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status.lower() in ["up", "healthy", "ok"]
