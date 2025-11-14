"""
Shared utilities for omniintelligence.

Common utility functions used across all nodes.
"""

import hashlib
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone


def generate_entity_id(prefix: str, *components: str) -> str:
    """
    Generate a deterministic entity ID from components.

    Args:
        prefix: ID prefix (e.g., 'doc', 'ent', 'wf')
        components: Components to hash for uniqueness

    Returns:
        Generated entity ID
    """
    combined = ":".join(str(c) for c in components)
    hash_value = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"{prefix}_{hash_value}"


def generate_workflow_id(operation_type: str, entity_id: str) -> str:
    """Generate a workflow ID."""
    timestamp = datetime.utcnow().timestamp()
    return generate_entity_id("wf", operation_type, entity_id, timestamp)


def compute_content_hash(content: str) -> str:
    """
    Compute SHA-256 hash of content.

    Args:
        content: Content to hash

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(content.encode()).hexdigest()


def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def serialize_for_cache(obj: Any) -> str:
    """
    Serialize object for caching.

    Args:
        obj: Object to serialize

    Returns:
        JSON string
    """
    if hasattr(obj, "model_dump"):
        # Pydantic model
        return obj.model_dump_json()
    return json.dumps(obj, default=str)


def deserialize_from_cache(data: str, model_class: Optional[type] = None) -> Any:
    """
    Deserialize object from cache.

    Args:
        data: JSON string
        model_class: Optional Pydantic model class

    Returns:
        Deserialized object
    """
    if model_class:
        return model_class.model_validate_json(data)
    return json.loads(data)


def build_cache_key(*components: str) -> str:
    """
    Build a cache key from components.

    Args:
        components: Key components

    Returns:
        Cache key string
    """
    return ":".join(str(c) for c in components)


def extract_metadata_fields(
    metadata: Dict[str, Any],
    fields: list[str],
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract specific fields from metadata with defaults.

    Args:
        metadata: Source metadata dictionary
        fields: Fields to extract
        defaults: Default values for missing fields

    Returns:
        Dictionary with extracted fields
    """
    defaults = defaults or {}
    return {
        field: metadata.get(field, defaults.get(field))
        for field in fields
    }


def merge_metadata(
    base: Dict[str, Any],
    update: Dict[str, Any],
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Merge metadata dictionaries.

    Args:
        base: Base metadata
        update: Updates to apply
        overwrite: Whether to overwrite existing keys

    Returns:
        Merged metadata
    """
    result = base.copy()
    for key, value in update.items():
        if overwrite or key not in result:
            result[key] = value
    return result


def truncate_string(s: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length.

    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to append if truncated

    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def format_duration_ms(start_time: datetime, end_time: Optional[datetime] = None) -> float:
    """
    Calculate duration in milliseconds.

    Args:
        start_time: Start timestamp
        end_time: End timestamp (defaults to now)

    Returns:
        Duration in milliseconds
    """
    end = end_time or utc_now()
    delta = end - start_time
    return delta.total_seconds() * 1000


def parse_topic_name(topic: str, prefix: str = "dev.archon-intelligence") -> Dict[str, str]:
    """
    Parse Kafka topic name into components.

    Expected format: {prefix}.{domain}.{action}.{version}

    Args:
        topic: Topic name
        prefix: Expected prefix

    Returns:
        Dictionary with domain, action, version
    """
    if not topic.startswith(prefix):
        raise ValueError(f"Topic does not start with expected prefix: {prefix}")

    remainder = topic[len(prefix)+1:]  # +1 for the dot
    parts = remainder.split(".")

    if len(parts) < 3:
        raise ValueError(f"Invalid topic format: {topic}")

    return {
        "domain": parts[0],
        "action": parts[1],
        "version": parts[2],
    }


def build_topic_name(
    domain: str,
    action: str,
    version: str = "v1",
    prefix: str = "dev.archon-intelligence",
) -> str:
    """
    Build Kafka topic name.

    Args:
        domain: Topic domain (e.g., 'enrichment', 'pattern')
        action: Topic action (e.g., 'requested', 'completed')
        version: Topic version
        prefix: Topic prefix

    Returns:
        Full topic name
    """
    return f"{prefix}.{domain}.{action}.{version}"


__all__ = [
    "generate_entity_id",
    "generate_workflow_id",
    "compute_content_hash",
    "utc_now",
    "serialize_for_cache",
    "deserialize_from_cache",
    "build_cache_key",
    "extract_metadata_fields",
    "merge_metadata",
    "truncate_string",
    "format_duration_ms",
    "parse_topic_name",
    "build_topic_name",
]
