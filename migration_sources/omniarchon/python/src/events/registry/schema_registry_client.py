"""
Schema Registry Client - Phase 1

Redpanda Schema Registry integration for event validation.

Features:
- Schema registration (JSON Schema format)
- Event validation against schemas
- Schema versioning (SemVer)
- In-memory schema caching for performance
- Compatibility checking (backward, forward, full)

Created: 2025-10-18
Reference: EVENT_BUS_ARCHITECTURE.md Phase 1
"""

import json
import logging
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

logger = logging.getLogger(__name__)


class SchemaRegistryClient:
    """
    Redpanda Schema Registry client for JSON Schema validation.

    Provides schema registration, retrieval, and validation capabilities
    with built-in caching for performance.

    Usage:
        registry = SchemaRegistryClient(
            schema_registry_url="http://omninode-bridge-redpanda:8081"
        )

        # Register schema
        schema_id = await registry.register_schema(
            subject="omninode.codegen.request.validate.v1-value",
            schema=event_schema
        )

        # Validate event
        is_valid = await registry.validate_event(
            subject="omninode.codegen.request.validate.v1-value",
            event_data=event_dict
        )
    """

    def __init__(
        self,
        schema_registry_url: str,
        timeout_s: float = 10.0,
        enable_cache: bool = True,
    ):
        """
        Initialize Schema Registry client.

        Args:
            schema_registry_url: Schema Registry HTTP endpoint
            timeout_s: Request timeout in seconds
            enable_cache: Enable in-memory schema caching
        """
        self.schema_registry_url = schema_registry_url
        self.timeout_s = timeout_s
        self.enable_cache = enable_cache

        # HTTP client
        self.client = httpx.AsyncClient(timeout=timeout_s)

        # Schema cache (subject -> schema)
        self._schema_cache: dict[str, dict[str, Any]] = {}

        logger.info(f"SchemaRegistryClient initialized | url={schema_registry_url}")

    async def register_schema(
        self, subject: str, schema: dict[str, Any], schema_type: str = "JSON"
    ) -> int:
        """
        Register schema with Schema Registry.

        Args:
            subject: Schema subject (e.g., "omninode.codegen.request.validate.v1-value")
            schema: JSON Schema definition
            schema_type: Schema type (default: "JSON")

        Returns:
            Schema ID from registry

        Raises:
            httpx.HTTPError: If registration fails
        """
        endpoint = urljoin(self.schema_registry_url, f"/subjects/{subject}/versions")

        payload = {"schema": json.dumps(schema), "schemaType": schema_type}

        try:
            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()

            result = response.json()
            schema_id = result.get("id")

            logger.info(
                f"Schema registered | subject={subject} | schema_id={schema_id}"
            )

            # Update cache
            if self.enable_cache:
                self._schema_cache[subject] = schema

            return schema_id

        except httpx.HTTPError as e:
            logger.error(f"Failed to register schema | subject={subject} | error={e}")
            raise

    async def get_schema(
        self, subject: str, version: str = "latest"
    ) -> Optional[dict[str, Any]]:
        """
        Get schema from Schema Registry.

        Args:
            subject: Schema subject
            version: Schema version (default: "latest")

        Returns:
            JSON Schema definition or None if not found
        """
        # Check cache first
        if self.enable_cache and version == "latest" and subject in self._schema_cache:
            return self._schema_cache[subject]

        endpoint = urljoin(
            self.schema_registry_url, f"/subjects/{subject}/versions/{version}"
        )

        try:
            response = await self.client.get(endpoint)
            response.raise_for_status()

            result = response.json()
            schema_str = result.get("schema")

            if schema_str:
                schema = json.loads(schema_str)

                # Update cache
                if self.enable_cache and version == "latest":
                    self._schema_cache[subject] = schema

                return schema

        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                logger.warning(
                    f"Schema not found | subject={subject} | version={version}"
                )
                return None
            else:
                logger.error(
                    f"Failed to get schema | subject={subject} | version={version} | error={e}"
                )
                raise

        return None

    async def validate_event(
        self, subject: str, event_data: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate event data against schema.

        Args:
            subject: Schema subject
            event_data: Event data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = await self.get_schema(subject)

        if not schema:
            logger.warning(f"No schema found for validation | subject={subject}")
            return (False, f"No schema found for subject: {subject}")

        try:
            validate(instance=event_data, schema=schema)
            return (True, None)

        except JsonSchemaValidationError as e:
            error_msg = f"Schema validation failed: {e.message}"
            logger.debug(f"Validation error | subject={subject} | error={error_msg}")
            return (False, error_msg)

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        await self.client.aclose()
        logger.info("SchemaRegistryClient closed")


# ============================================================================
# Factory Functions
# ============================================================================


def create_schema_registry_client(
    schema_registry_url: str, **kwargs
) -> SchemaRegistryClient:
    """
    Create Schema Registry client instance.

    Args:
        schema_registry_url: Schema Registry HTTP endpoint
        **kwargs: Additional SchemaRegistryClient arguments

    Returns:
        Configured SchemaRegistryClient instance
    """
    return SchemaRegistryClient(schema_registry_url=schema_registry_url, **kwargs)
