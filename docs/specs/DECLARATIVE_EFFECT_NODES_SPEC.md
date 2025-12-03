# Effect Nodes Specification

**Version**: 1.0.0
**Status**: Draft
**Created**: 2025-12-02
**Author**: OmniIntelligence Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Naming Convention](#2-naming-convention)
3. [Architecture](#3-architecture)
4. [Contract Schema Specification](#4-contract-schema-specification)
5. [Protocol Handlers](#5-protocol-handlers)
6. [Base Runtime Class](#6-base-runtime-class)
7. [Example Contracts](#7-example-contracts)
8. [File Structure](#8-file-structure)
9. [Implementation Guide](#9-implementation-guide)
10. [Testing Strategy](#10-testing-strategy)
11. [Migration Path](#11-migration-path)

---

## 1. Overview

### 1.1 Problem Statement

OmniIntelligence currently has:
- **Orchestrator nodes**: YAML workflow contracts (e.g., `document_ingestion.yaml`)
- **Reducer nodes**: YAML FSM contracts (e.g., `fsm_ingestion.yaml`)
- **Legacy effect nodes**: Python code for each adapter (e.g., `NodeQdrantVectorEffectLegacy`)

The legacy effect nodes share common patterns:
- Connection configuration (URL, auth, timeouts, pool size)
- Operation routing (switch on operation type)
- Request/response mapping
- Retry logic with exponential backoff
- Metrics collection
- Error handling and DLQ routing

### 1.2 Solution

Create a **contract-driven pattern for effect nodes** where:
- YAML contracts define connections, operations, and resilience policies
- A generic runtime (`NodeEffect`) executes the contracts
- Protocol handlers abstract HTTP, Bolt, PostgreSQL, Kafka specifics
- All effects communicate via Kafka events (consume requests, produce results)
- Only effect nodes can make HTTP/TCP calls to external systems

### 1.3 Goals

1. **Reduce boilerplate**: Eliminate repetitive Python code for each adapter
2. **Increase consistency**: Same resilience, metrics, and error handling patterns
3. **Simplify testing**: Mock at the protocol handler level
4. **Enable runtime configuration**: Change endpoints without code deployment
5. **Maintain type safety**: Generate Pydantic models from contracts

### 1.4 Non-Goals

- Replacing compute nodes (pure functions, no I/O)
- Replacing orchestrator/reducer nodes (different patterns)
- Supporting arbitrary protocols (start with HTTP, Bolt, PostgreSQL, Kafka)

---

## 2. Naming Convention

### 2.1 Overview

Contract-driven (declarative) nodes are now the **default** implementation pattern in OmniIntelligence. The naming convention reflects this:

| Node Type | Default (Contract-Driven) | Legacy (Imperative) |
|-----------|---------------------------|---------------------|
| Effect | `NodeEffect` | `NodeEffectLegacy` |
| Compute | `NodeCompute` | `NodeComputeLegacy` |
| Reducer | `NodeReducer` | `NodeReducerLegacy` |
| Orchestrator | `NodeOrchestrator` | `NodeOrchestratorLegacy` |

### 2.2 Class Naming Rules

1. **Default nodes (no suffix)**: Use YAML contracts for configuration
   - `NodeQdrantVectorEffect` - Contract-driven Qdrant effect
   - `NodeVectorizationCompute` - Contract-driven vectorization compute

2. **Legacy nodes (`Legacy` suffix)**: Imperative Python implementations
   - `NodeQdrantVectorEffectLegacy` - Old imperative Qdrant effect
   - `NodeVectorizationComputeLegacy` - Old imperative compute

### 2.3 Migration Path

When migrating from legacy to default:

1. **Rename existing imperative class**: Add `Legacy` suffix
   ```python
   # Before: NodeQdrantVectorEffect (imperative)
   # After:  NodeQdrantVectorEffectLegacy (imperative, deprecated)
   ```

2. **Create new contract-driven class**: Use original name (no suffix)
   ```python
   # New: NodeQdrantVectorEffect (contract-driven, default)
   ```

3. **Add deprecation warning** to legacy class:
   ```python
   class NodeQdrantVectorEffectLegacy(NodeEffectLegacy):
       """
       DEPRECATED: Use NodeQdrantVectorEffect (contract-driven) instead.
       This legacy imperative implementation will be removed in v2.0.0.
       """
   ```

4. **Parallel run validation**: Run both implementations to verify parity

5. **Remove legacy** after validation period (typically 2 release cycles)

### 2.4 Import Conventions

```python
# Default (contract-driven) - preferred
from omniintelligence.nodes.qdrant_vector_effect import NodeQdrantVectorEffect

# Legacy (imperative) - deprecated
from omniintelligence.nodes.qdrant_vector_effect.legacy import NodeQdrantVectorEffectLegacy
```

---

## 3. Architecture

### 3.1 Component Diagram

```
                    +---------------------------+
                    |    Kafka Event Bus        |
                    | (Request/Response Topics) |
                    +-------------+-------------+
                                  |
                    +-------------v-------------+
                    |       NodeEffect          |
                    |    (Base Runtime Class)   |
                    +-------------+-------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
+--------v--------+    +----------v----------+    +--------v--------+
|  Contract YAML  |    |  Protocol Handlers  |    |   Observability |
|  (loaded at     |    |  - HttpRestHandler  |    |   - Metrics     |
|   startup)      |    |  - BoltHandler      |    |   - Traces      |
+--------+--------+    |  - PostgresHandler  |    |   - Logs        |
         |             |  - KafkaHandler     |    +-----------------+
         |             +----------+----------+
         |                        |
         +------------------------+
                                  |
                    +-------------v-------------+
                    |   External Systems        |
                    | (Qdrant, Memgraph, etc.)  |
                    +---------------------------+
```

### 3.2 Event Flow

```
1. Kafka Consumer receives message on request topic
   e.g., dev.archon-intelligence.effect.qdrant-vector.request.v1

2. NodeEffect loads contract and routes to operation
   e.g., operation="upsert" -> uses "upsert" operation definition

3. Protocol Handler executes request
   e.g., HttpRestHandler.execute(method="POST", url="http://qdrant:6333/...")

4. Response is mapped via JSONPath expressions
   e.g., $.result.id -> output.vector_id

5. Result published to response topic
   e.g., dev.archon-intelligence.effect.qdrant-vector.response.v1

6. On failure, message routed to DLQ
   e.g., dev.archon-intelligence.effect.qdrant-vector.request.v1.dlq
```

### 3.3 ONEX Compliance

Contract-driven effect nodes maintain ONEX compliance:

| Requirement | Implementation |
|-------------|----------------|
| Suffix-based naming | `Node{Name}Effect` + contract name |
| Effect pattern | `async execute_effect()` method |
| Strong typing | Pydantic models generated from contract |
| Correlation ID | Preserved in event envelope |
| Error handling | DLQ routing with full context |

---

## 4. Contract Schema Specification

### 4.1 JSON Schema (for YAML validation)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://omniintelligence.dev/schemas/effect-contract/v1.0.0",
  "title": "Effect Contract Schema",
  "description": "Schema for effect node contracts",
  "type": "object",
  "required": ["name", "version", "protocol", "connection", "operations"],
  "properties": {
    "name": {
      "type": "string",
      "description": "Unique effect name (snake_case)",
      "pattern": "^[a-z][a-z0-9_]*$",
      "examples": ["qdrant_vector_effect", "mlx_embedding_adapter"]
    },
    "version": {
      "type": "object",
      "required": ["major", "minor", "patch"],
      "properties": {
        "major": { "type": "integer", "minimum": 0 },
        "minor": { "type": "integer", "minimum": 0 },
        "patch": { "type": "integer", "minimum": 0 }
      }
    },
    "description": {
      "type": "string",
      "description": "Human-readable description of the effect"
    },
    "protocol": {
      "$ref": "#/definitions/protocol"
    },
    "connection": {
      "$ref": "#/definitions/connection"
    },
    "authentication": {
      "$ref": "#/definitions/authentication"
    },
    "operations": {
      "type": "object",
      "additionalProperties": {
        "$ref": "#/definitions/operation"
      }
    },
    "resilience": {
      "$ref": "#/definitions/resilience"
    },
    "events": {
      "$ref": "#/definitions/events"
    },
    "observability": {
      "$ref": "#/definitions/observability"
    },
    "metadata": {
      "$ref": "#/definitions/metadata"
    }
  },
  "definitions": {
    "protocol": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["http_rest", "bolt", "postgres", "kafka"],
          "description": "Protocol handler to use"
        },
        "version": {
          "type": "string",
          "description": "Protocol version (e.g., HTTP/1.1, Bolt/4.4)"
        },
        "content_type": {
          "type": "string",
          "default": "application/json",
          "description": "Default content type for requests"
        }
      }
    },
    "connection": {
      "type": "object",
      "properties": {
        "url": {
          "type": "string",
          "description": "Connection URL or template with ${ENV_VAR} substitution",
          "examples": ["http://${QDRANT_HOST}:${QDRANT_PORT}"]
        },
        "host": {
          "type": "string",
          "description": "Host (alternative to url)"
        },
        "port": {
          "type": "integer",
          "description": "Port number"
        },
        "database": {
          "type": "string",
          "description": "Database name (for DB protocols)"
        },
        "timeout_ms": {
          "type": "integer",
          "default": 30000,
          "description": "Connection timeout in milliseconds"
        },
        "pool": {
          "type": "object",
          "properties": {
            "min_size": { "type": "integer", "default": 1 },
            "max_size": { "type": "integer", "default": 10 },
            "max_idle_time_ms": { "type": "integer", "default": 300000 }
          }
        },
        "tls": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": false },
            "verify": { "type": "boolean", "default": true },
            "ca_cert_path": { "type": "string" },
            "client_cert_path": { "type": "string" },
            "client_key_path": { "type": "string" }
          }
        }
      }
    },
    "authentication": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["none", "api_key", "basic", "bearer", "oauth2"],
          "default": "none"
        },
        "api_key": {
          "type": "object",
          "properties": {
            "header": { "type": "string", "default": "Authorization" },
            "prefix": { "type": "string", "default": "Bearer" },
            "value": { "type": "string", "description": "${ENV_VAR} substitution supported" }
          }
        },
        "basic": {
          "type": "object",
          "properties": {
            "username": { "type": "string" },
            "password": { "type": "string" }
          }
        },
        "bearer": {
          "type": "object",
          "properties": {
            "token": { "type": "string" }
          }
        },
        "oauth2": {
          "type": "object",
          "properties": {
            "token_url": { "type": "string" },
            "client_id": { "type": "string" },
            "client_secret": { "type": "string" },
            "scopes": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "operation": {
      "type": "object",
      "required": ["description"],
      "properties": {
        "description": {
          "type": "string"
        },
        "request": {
          "$ref": "#/definitions/request"
        },
        "response": {
          "$ref": "#/definitions/response"
        },
        "validation": {
          "$ref": "#/definitions/validation"
        },
        "error_handling": {
          "$ref": "#/definitions/operation_error_handling"
        }
      }
    },
    "request": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
          "description": "HTTP method (for http_rest protocol)"
        },
        "path": {
          "type": "string",
          "description": "URL path template with ${variable} substitution",
          "examples": ["/collections/${collection}/points"]
        },
        "query": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Query parameters"
        },
        "headers": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Additional headers"
        },
        "body": {
          "oneOf": [
            { "type": "object" },
            { "type": "string" }
          ],
          "description": "Request body template with ${variable} substitution"
        },
        "body_template": {
          "type": "string",
          "description": "Path to external template file"
        },
        "cypher": {
          "type": "string",
          "description": "Cypher query (for bolt protocol)"
        },
        "cypher_params": {
          "type": "object",
          "description": "Cypher query parameters mapping"
        },
        "sql": {
          "type": "string",
          "description": "SQL query (for postgres protocol)"
        },
        "sql_params": {
          "type": "array",
          "description": "SQL query parameters (positional)"
        }
      }
    },
    "response": {
      "type": "object",
      "properties": {
        "success_codes": {
          "type": "array",
          "items": { "type": "integer" },
          "default": [200, 201, 202, 204],
          "description": "HTTP status codes considered successful"
        },
        "mapping": {
          "type": "object",
          "additionalProperties": {
            "type": "string",
            "description": "JSONPath expression for extracting values"
          },
          "description": "Map response fields to output model",
          "examples": [{
            "vector_id": "$.result.id",
            "score": "$.result.score",
            "metadata": "$.result.payload"
          }]
        },
        "transform": {
          "type": "string",
          "description": "Optional transformation function name"
        }
      }
    },
    "validation": {
      "type": "object",
      "properties": {
        "required_fields": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Fields required in input"
        },
        "field_types": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Expected types for fields"
        },
        "custom_validators": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Custom validator function names"
        }
      }
    },
    "operation_error_handling": {
      "type": "object",
      "properties": {
        "retryable_errors": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Error types that should trigger retry"
        },
        "non_retryable_errors": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Error types that should not retry (immediate DLQ)"
        },
        "error_mapping": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Map error codes to error types"
        }
      }
    },
    "resilience": {
      "type": "object",
      "properties": {
        "retry": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": true },
            "max_attempts": { "type": "integer", "default": 3 },
            "initial_delay_ms": { "type": "integer", "default": 1000 },
            "max_delay_ms": { "type": "integer", "default": 30000 },
            "backoff_multiplier": { "type": "number", "default": 2.0 },
            "jitter": { "type": "boolean", "default": true }
          }
        },
        "circuit_breaker": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": true },
            "failure_threshold": { "type": "integer", "default": 5 },
            "success_threshold": { "type": "integer", "default": 2 },
            "timeout_ms": { "type": "integer", "default": 60000 },
            "half_open_max_calls": { "type": "integer", "default": 3 }
          }
        },
        "rate_limit": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": false },
            "requests_per_second": { "type": "number" },
            "burst_size": { "type": "integer" }
          }
        },
        "timeout": {
          "type": "object",
          "properties": {
            "request_ms": { "type": "integer", "default": 30000 },
            "operation_ms": { "type": "integer", "default": 120000 }
          }
        },
        "bulkhead": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": false },
            "max_concurrent": { "type": "integer", "default": 10 },
            "max_wait_ms": { "type": "integer", "default": 5000 }
          }
        }
      }
    },
    "events": {
      "type": "object",
      "properties": {
        "consume": {
          "type": "object",
          "properties": {
            "topic": {
              "type": "string",
              "description": "Kafka topic to consume from"
            },
            "group_id": {
              "type": "string",
              "description": "Consumer group ID"
            },
            "auto_offset_reset": {
              "type": "string",
              "enum": ["earliest", "latest"],
              "default": "earliest"
            },
            "enable_auto_commit": {
              "type": "boolean",
              "default": false
            },
            "batch_size": {
              "type": "integer",
              "default": 1
            }
          }
        },
        "produce": {
          "type": "object",
          "properties": {
            "success_topic": {
              "type": "string",
              "description": "Topic for successful responses"
            },
            "failure_topic": {
              "type": "string",
              "description": "Topic for failures (before DLQ)"
            },
            "dlq_topic": {
              "type": "string",
              "description": "Dead letter queue topic"
            },
            "acks": {
              "type": "string",
              "enum": ["0", "1", "all"],
              "default": "all"
            }
          }
        },
        "envelope": {
          "type": "object",
          "properties": {
            "include_metadata": { "type": "boolean", "default": true },
            "include_timing": { "type": "boolean", "default": true },
            "correlation_id_path": { "type": "string", "default": "$.correlation_id" }
          }
        }
      }
    },
    "observability": {
      "type": "object",
      "properties": {
        "metrics": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": true },
            "prefix": { "type": "string", "default": "omniintelligence_effect" },
            "labels": {
              "type": "object",
              "additionalProperties": { "type": "string" }
            },
            "histograms": {
              "type": "object",
              "properties": {
                "buckets": {
                  "type": "array",
                  "items": { "type": "number" },
                  "default": [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
                }
              }
            }
          }
        },
        "tracing": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": true },
            "service_name": { "type": "string" },
            "sample_rate": { "type": "number", "default": 1.0 }
          }
        },
        "logging": {
          "type": "object",
          "properties": {
            "level": {
              "type": "string",
              "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
              "default": "INFO"
            },
            "include_request_body": { "type": "boolean", "default": false },
            "include_response_body": { "type": "boolean", "default": false },
            "sanitize_secrets": { "type": "boolean", "default": true },
            "secret_patterns": {
              "type": "array",
              "items": { "type": "string" },
              "default": ["password", "secret", "token", "api_key", "authorization"]
            }
          }
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "author": { "type": "string" },
        "created_at": { "type": "string", "format": "date" },
        "updated_at": { "type": "string", "format": "date" },
        "tags": {
          "type": "array",
          "items": { "type": "string" }
        },
        "documentation": { "type": "string" },
        "dependencies": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

### 4.2 Template Variable Syntax

The contract supports variable substitution using `${variable}` syntax:

| Source | Syntax | Example |
|--------|--------|---------|
| Environment variable | `${ENV_VAR}` | `${QDRANT_HOST}` |
| Input field | `${input.field}` | `${input.collection}` |
| Nested input | `${input.nested.field}` | `${input.metadata.language}` |
| Context | `${context.field}` | `${context.correlation_id}` |
| Config | `${config.field}` | `${config.default_collection}` |
| Output from previous step | `${step_name.field}` | `${vectorization_result.embeddings}` |

### 4.3 JSONPath Response Mapping

Response mapping uses JSONPath expressions:

```yaml
response:
  mapping:
    # Simple path
    vector_id: "$.id"

    # Nested path
    score: "$.result.score"

    # Array access
    first_result: "$.results[0]"

    # All items
    all_scores: "$.results[*].score"

    # Conditional
    status: "$.status || 'unknown'"

    # With default
    count: "$.total_count ?? 0"
```

---

## 5. Protocol Handlers

### 5.1 Handler Interface

```python
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class ModelProtocolRequest(BaseModel):
    """Protocol-agnostic request model."""
    operation: str
    params: dict[str, Any]
    headers: dict[str, str] = {}
    timeout_ms: int = 30000
    correlation_id: str

class ModelProtocolResponse(BaseModel):
    """Protocol-agnostic response model."""
    success: bool
    status_code: int | None = None
    data: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float
    metadata: dict[str, Any] = {}

class ProtocolHandler(ABC):
    """Base class for protocol handlers."""

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize connection pool/client."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Close connections gracefully."""
        pass

    @abstractmethod
    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: dict[str, Any]
    ) -> ModelProtocolResponse:
        """Execute protocol-specific operation."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        pass
```

### 5.2 HttpRestHandler

```python
"""HTTP REST Protocol Handler."""

import aiohttp
from typing import Any
import json

class HttpRestHandler(ProtocolHandler):
    """
    Handler for HTTP REST APIs.

    Supports:
    - GET, POST, PUT, PATCH, DELETE methods
    - JSON request/response bodies
    - Header management
    - Connection pooling via aiohttp
    - TLS/SSL configuration
    """

    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        self.base_url: str = ""
        self.default_headers: dict[str, str] = {}

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize HTTP client session with connection pooling."""
        connector = aiohttp.TCPConnector(
            limit=config.get("pool", {}).get("max_size", 10),
            limit_per_host=config.get("pool", {}).get("max_size", 10),
            ttl_dns_cache=300,
            ssl=self._get_ssl_context(config.get("tls", {}))
        )

        timeout = aiohttp.ClientTimeout(
            total=config.get("timeout_ms", 30000) / 1000
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self._build_auth_headers(config.get("authentication", {}))
        )

        self.base_url = config.get("url", "")
        self.default_headers = config.get("headers", {})

    async def shutdown(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()

    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: dict[str, Any]
    ) -> ModelProtocolResponse:
        """Execute HTTP request."""
        import time
        start_time = time.perf_counter()

        try:
            req_config = operation_config.get("request", {})
            method = req_config.get("method", "GET")
            path = self._substitute_variables(
                req_config.get("path", ""),
                request.params
            )
            url = f"{self.base_url}{path}"

            # Build headers
            headers = {**self.default_headers, **request.headers}

            # Build body
            body = None
            if req_config.get("body"):
                body = self._substitute_variables(
                    req_config["body"],
                    request.params
                )
                if isinstance(body, dict):
                    body = json.dumps(body)

            # Execute request
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                data=body,
                params=req_config.get("query", {})
            ) as response:
                duration_ms = (time.perf_counter() - start_time) * 1000

                response_data = await response.json() if response.content_type == "application/json" else {}

                success_codes = operation_config.get("response", {}).get(
                    "success_codes", [200, 201, 202, 204]
                )

                return ModelProtocolResponse(
                    success=response.status in success_codes,
                    status_code=response.status,
                    data=response_data,
                    duration_ms=duration_ms,
                    metadata={"url": url, "method": method}
                )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ModelProtocolResponse(
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

    async def health_check(self) -> bool:
        """Check HTTP connectivity."""
        try:
            async with self.session.get(self.base_url) as response:
                return response.status < 500
        except Exception:
            return False

    def _substitute_variables(self, template: Any, params: dict[str, Any]) -> Any:
        """Substitute ${variable} patterns in template."""
        if isinstance(template, str):
            import re
            def replace(match):
                key = match.group(1)
                parts = key.split(".")
                value = params
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part, match.group(0))
                    else:
                        return match.group(0)
                return str(value) if not isinstance(value, (dict, list)) else json.dumps(value)
            return re.sub(r'\$\{([^}]+)\}', replace, template)
        elif isinstance(template, dict):
            return {k: self._substitute_variables(v, params) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._substitute_variables(item, params) for item in template]
        return template

    def _build_auth_headers(self, auth_config: dict[str, Any]) -> dict[str, str]:
        """Build authentication headers."""
        auth_type = auth_config.get("type", "none")
        headers = {}

        if auth_type == "api_key":
            api_key_config = auth_config.get("api_key", {})
            header = api_key_config.get("header", "Authorization")
            prefix = api_key_config.get("prefix", "Bearer")
            value = self._resolve_env_var(api_key_config.get("value", ""))
            headers[header] = f"{prefix} {value}" if prefix else value

        elif auth_type == "basic":
            import base64
            basic_config = auth_config.get("basic", {})
            username = self._resolve_env_var(basic_config.get("username", ""))
            password = self._resolve_env_var(basic_config.get("password", ""))
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        elif auth_type == "bearer":
            token = self._resolve_env_var(auth_config.get("bearer", {}).get("token", ""))
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _resolve_env_var(self, value: str) -> str:
        """Resolve ${ENV_VAR} patterns."""
        import os
        import re
        def replace(match):
            env_var = match.group(1)
            return os.getenv(env_var, "")
        return re.sub(r'\$\{([^}]+)\}', replace, value)

    def _get_ssl_context(self, tls_config: dict[str, Any]) -> Any:
        """Build SSL context from TLS config."""
        if not tls_config.get("enabled", False):
            return None

        import ssl
        ctx = ssl.create_default_context()

        if not tls_config.get("verify", True):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        if tls_config.get("ca_cert_path"):
            ctx.load_verify_locations(tls_config["ca_cert_path"])

        if tls_config.get("client_cert_path") and tls_config.get("client_key_path"):
            ctx.load_cert_chain(
                tls_config["client_cert_path"],
                tls_config["client_key_path"]
            )

        return ctx
```

### 5.3 BoltHandler

```python
"""Neo4j Bolt Protocol Handler for Memgraph/Neo4j."""

from neo4j import AsyncGraphDatabase, AsyncDriver
from typing import Any

class BoltHandler(ProtocolHandler):
    """
    Handler for Neo4j Bolt protocol (Memgraph, Neo4j).

    Supports:
    - Cypher query execution
    - Parameterized queries for security
    - Transaction management
    - Connection pooling
    """

    def __init__(self):
        self.driver: AsyncDriver | None = None
        self.database: str | None = None

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize Bolt driver with connection pooling."""
        url = config.get("url", "bolt://localhost:7687")
        auth = None

        auth_config = config.get("authentication", {})
        if auth_config.get("type") == "basic":
            auth = (
                self._resolve_env_var(auth_config.get("basic", {}).get("username", "")),
                self._resolve_env_var(auth_config.get("basic", {}).get("password", ""))
            )

        pool_config = config.get("pool", {})

        self.driver = AsyncGraphDatabase.driver(
            url,
            auth=auth,
            max_connection_pool_size=pool_config.get("max_size", 50),
            connection_timeout=config.get("timeout_ms", 30000) / 1000
        )

        self.database = config.get("database")

    async def shutdown(self) -> None:
        """Close Bolt driver."""
        if self.driver:
            await self.driver.close()

    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: dict[str, Any]
    ) -> ModelProtocolResponse:
        """Execute Cypher query."""
        import time
        start_time = time.perf_counter()

        try:
            req_config = operation_config.get("request", {})
            cypher = self._substitute_variables(
                req_config.get("cypher", ""),
                request.params
            )

            # Build Cypher parameters
            cypher_params = {}
            param_mapping = req_config.get("cypher_params", {})
            for param_name, param_source in param_mapping.items():
                cypher_params[param_name] = self._get_nested_value(
                    request.params,
                    param_source.replace("${input.", "").replace("}", "")
                )

            async with self.driver.session(database=self.database) as session:
                result = await session.run(cypher, cypher_params)
                records = await result.data()
                summary = await result.consume()

                duration_ms = (time.perf_counter() - start_time) * 1000

                return ModelProtocolResponse(
                    success=True,
                    data={
                        "records": records,
                        "counters": {
                            "nodes_created": summary.counters.nodes_created,
                            "nodes_deleted": summary.counters.nodes_deleted,
                            "relationships_created": summary.counters.relationships_created,
                            "relationships_deleted": summary.counters.relationships_deleted,
                            "properties_set": summary.counters.properties_set
                        }
                    },
                    duration_ms=duration_ms,
                    metadata={"database": self.database}
                )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ModelProtocolResponse(
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

    async def health_check(self) -> bool:
        """Check Bolt connectivity."""
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS test")
                await result.single()
                return True
        except Exception:
            return False

    def _substitute_variables(self, template: str, params: dict[str, Any]) -> str:
        """Substitute ${variable} patterns in Cypher template."""
        import re
        def replace(match):
            key = match.group(1)
            # For Cypher, we use $param syntax, not string substitution
            # This just handles structural substitution (e.g., label names)
            if key.startswith("input."):
                path = key[6:]  # Remove "input." prefix
                value = self._get_nested_value(params, path)
                return str(value) if value is not None else match.group(0)
            return match.group(0)
        return re.sub(r'\$\{([^}]+)\}', replace, template)

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _resolve_env_var(self, value: str) -> str:
        """Resolve ${ENV_VAR} patterns."""
        import os
        import re
        def replace(match):
            return os.getenv(match.group(1), "")
        return re.sub(r'\$\{([^}]+)\}', replace, value)
```

### 5.4 PostgresHandler

```python
"""PostgreSQL Protocol Handler."""

import asyncpg
from typing import Any

class PostgresHandler(ProtocolHandler):
    """
    Handler for PostgreSQL databases.

    Supports:
    - SQL query execution
    - Parameterized queries ($1, $2, etc.)
    - Connection pooling via asyncpg
    - Transaction management
    """

    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize asyncpg connection pool."""
        pool_config = config.get("pool", {})

        # Build DSN
        dsn = config.get("url")
        if not dsn:
            host = self._resolve_env_var(config.get("host", "localhost"))
            port = config.get("port", 5432)
            database = self._resolve_env_var(config.get("database", "postgres"))

            auth_config = config.get("authentication", {})
            user = ""
            password = ""
            if auth_config.get("type") == "basic":
                user = self._resolve_env_var(auth_config.get("basic", {}).get("username", ""))
                password = self._resolve_env_var(auth_config.get("basic", {}).get("password", ""))

            dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"

        self.pool = await asyncpg.create_pool(
            dsn,
            min_size=pool_config.get("min_size", 1),
            max_size=pool_config.get("max_size", 10),
            command_timeout=config.get("timeout_ms", 30000) / 1000
        )

    async def shutdown(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()

    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: dict[str, Any]
    ) -> ModelProtocolResponse:
        """Execute SQL query."""
        import time
        start_time = time.perf_counter()

        try:
            req_config = operation_config.get("request", {})
            sql = req_config.get("sql", "")

            # Build SQL parameters from mapping
            sql_params = []
            param_mapping = req_config.get("sql_params", [])
            for param_source in param_mapping:
                if param_source.startswith("${input."):
                    path = param_source[8:-1]  # Remove ${input. and }
                    value = self._get_nested_value(request.params, path)
                    sql_params.append(value)
                else:
                    sql_params.append(param_source)

            async with self.pool.acquire() as conn:
                # Determine if it's a query or execute
                sql_lower = sql.strip().lower()

                if sql_lower.startswith("select"):
                    rows = await conn.fetch(sql, *sql_params)
                    data = {"rows": [dict(row) for row in rows], "row_count": len(rows)}
                else:
                    result = await conn.execute(sql, *sql_params)
                    # Parse result like "INSERT 0 1" or "UPDATE 5"
                    parts = result.split()
                    affected = int(parts[-1]) if parts else 0
                    data = {"affected_rows": affected, "result": result}

                duration_ms = (time.perf_counter() - start_time) * 1000

                return ModelProtocolResponse(
                    success=True,
                    data=data,
                    duration_ms=duration_ms
                )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ModelProtocolResponse(
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

    async def health_check(self) -> bool:
        """Check PostgreSQL connectivity."""
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception:
            return False

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _resolve_env_var(self, value: str) -> str:
        """Resolve ${ENV_VAR} patterns."""
        import os
        import re
        def replace(match):
            return os.getenv(match.group(1), "")
        return re.sub(r'\$\{([^}]+)\}', replace, value)
```

### 5.5 KafkaHandler

```python
"""Kafka Protocol Handler for event publishing."""

from confluent_kafka import Producer, Consumer
from typing import Any
import json
import asyncio

class KafkaHandler(ProtocolHandler):
    """
    Handler for Kafka message production/consumption.

    Supports:
    - Message publishing with delivery confirmation
    - Idempotent producer
    - Batch publishing
    - Consumer group management
    """

    def __init__(self):
        self.producer: Producer | None = None
        self.config: dict[str, Any] = {}

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize Kafka producer."""
        bootstrap_servers = self._resolve_env_var(
            config.get("url", "localhost:9092")
        )

        producer_config = {
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": config.get("idempotence", True),
            "acks": config.get("acks", "all"),
            "compression.type": "lz4",
            "linger.ms": 10,
            "batch.size": 32768,
            "request.timeout.ms": config.get("timeout_ms", 30000),
            "delivery.timeout.ms": 120000,
        }

        self.producer = Producer(producer_config)
        self.config = config

    async def shutdown(self) -> None:
        """Flush and close producer."""
        if self.producer:
            self.producer.flush(timeout=10.0)

    async def execute(
        self,
        request: ModelProtocolRequest,
        operation_config: dict[str, Any]
    ) -> ModelProtocolResponse:
        """Publish message to Kafka topic."""
        import time
        start_time = time.perf_counter()

        try:
            req_config = operation_config.get("request", {})
            topic = self._substitute_variables(
                req_config.get("topic", ""),
                request.params
            )

            # Build message
            message = {
                "event_id": request.params.get("event_id", str(uuid4())),
                "event_type": request.params.get("event_type", request.operation),
                "correlation_id": request.correlation_id,
                "timestamp": time.time(),
                "payload": request.params.get("payload", {})
            }

            message_bytes = json.dumps(message, default=str).encode("utf-8")
            key = request.params.get("key", request.correlation_id)
            key_bytes = key.encode("utf-8") if isinstance(key, str) else key

            # Create delivery future
            future = asyncio.get_event_loop().create_future()

            def delivery_callback(err, msg):
                if err:
                    future.set_exception(Exception(f"Kafka delivery failed: {err}"))
                else:
                    future.set_result({
                        "partition": msg.partition(),
                        "offset": msg.offset()
                    })

            self.producer.produce(
                topic=topic,
                value=message_bytes,
                key=key_bytes,
                callback=delivery_callback
            )

            self.producer.poll(0)
            result = await future

            duration_ms = (time.perf_counter() - start_time) * 1000

            return ModelProtocolResponse(
                success=True,
                data={
                    "topic": topic,
                    "partition": result["partition"],
                    "offset": result["offset"]
                },
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ModelProtocolResponse(
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

    async def health_check(self) -> bool:
        """Check Kafka connectivity."""
        try:
            # Try to get cluster metadata
            metadata = self.producer.list_topics(timeout=5.0)
            return metadata is not None
        except Exception:
            return False

    def _substitute_variables(self, template: str, params: dict[str, Any]) -> str:
        """Substitute ${variable} patterns."""
        import re
        def replace(match):
            key = match.group(1)
            if key.startswith("input."):
                path = key[6:]
                value = self._get_nested_value(params, path)
                return str(value) if value is not None else match.group(0)
            return match.group(0)
        return re.sub(r'\$\{([^}]+)\}', replace, template)

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get nested value from dict."""
        parts = path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _resolve_env_var(self, value: str) -> str:
        """Resolve ${ENV_VAR} patterns."""
        import os
        import re
        def replace(match):
            return os.getenv(match.group(1), "")
        return re.sub(r'\$\{([^}]+)\}', replace, value)
```

### 5.6 Handler Registry

```python
"""Protocol handler registry."""

from typing import Type

class ProtocolHandlerRegistry:
    """Registry for protocol handlers."""

    _handlers: dict[str, Type[ProtocolHandler]] = {}

    @classmethod
    def register(cls, protocol_type: str, handler_class: Type[ProtocolHandler]) -> None:
        """Register a protocol handler."""
        cls._handlers[protocol_type] = handler_class

    @classmethod
    def get(cls, protocol_type: str) -> Type[ProtocolHandler]:
        """Get handler class for protocol type."""
        handler = cls._handlers.get(protocol_type)
        if not handler:
            raise ValueError(f"Unknown protocol type: {protocol_type}")
        return handler

    @classmethod
    def list_protocols(cls) -> list[str]:
        """List registered protocol types."""
        return list(cls._handlers.keys())

# Register built-in handlers
ProtocolHandlerRegistry.register("http_rest", HttpRestHandler)
ProtocolHandlerRegistry.register("bolt", BoltHandler)
ProtocolHandlerRegistry.register("postgres", PostgresHandler)
ProtocolHandlerRegistry.register("kafka", KafkaHandler)
```

---

## 6. Base Runtime Class

### 6.1 NodeEffect

```python
"""
Effect Node Runtime.

This is the base runtime class that loads YAML contracts and executes them
using the appropriate protocol handlers. This is the default implementation
for all effect nodes in OmniIntelligence.
"""

import logging
import time
import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml
from pydantic import BaseModel, Field
from jsonpath_ng import parse as jsonpath_parse

from .handlers import ProtocolHandler, ProtocolHandlerRegistry, ModelProtocolRequest
from .resilience import RetryPolicy, CircuitBreaker, RateLimiter

logger = logging.getLogger(__name__)


class ModelEffectInput(BaseModel):
    """Generic input model for effect nodes."""
    operation: str = Field(..., description="Operation to execute")
    params: dict[str, Any] = Field(default_factory=dict, description="Operation parameters")
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ModelEffectOutput(BaseModel):
    """Generic output model for effect nodes."""
    success: bool = Field(..., description="Whether operation succeeded")
    operation: str = Field(..., description="Operation that was executed")
    data: dict[str, Any] = Field(default_factory=dict, description="Response data")
    error: str | None = Field(default=None, description="Error message if failed")
    correlation_id: UUID = Field(..., description="Correlation ID")
    duration_ms: float = Field(default=0.0, description="Operation duration in ms")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Operation metadata")


class NodeEffect:
    """
    Effect Node Runtime (Default Implementation).

    This is the standard base class for all effect nodes. It uses YAML contracts
    to define behavior, replacing the legacy imperative implementations.

    This class:
    1. Loads YAML contract at initialization
    2. Validates contract against schema
    3. Initializes appropriate protocol handler
    4. Routes operations to handler based on contract
    5. Applies response mapping via JSONPath
    6. Handles resilience (retry, circuit breaker)
    7. Collects metrics and emits events

    Usage:
        >>> node = NodeEffect(
        ...     contract_path="/path/to/qdrant_vector_effect.yaml"
        ... )
        >>> await node.initialize()
        >>>
        >>> result = await node.execute_effect(ModelEffectInput(
        ...     operation="upsert",
        ...     params={"collection": "vectors", "embeddings": [...]}
        ... ))
        >>>
        >>> await node.shutdown()
    """

    def __init__(
        self,
        contract_path: str | Path,
        config_overrides: dict[str, Any] | None = None
    ):
        """
        Initialize effect node.

        Args:
            contract_path: Path to YAML contract file
            config_overrides: Optional config overrides (e.g., from environment)
        """
        self.contract_path = Path(contract_path)
        self.config_overrides = config_overrides or {}

        self.node_id = uuid4()
        self.contract: dict[str, Any] = {}
        self.handler: ProtocolHandler | None = None

        # Resilience components
        self.retry_policy: RetryPolicy | None = None
        self.circuit_breaker: CircuitBreaker | None = None
        self.rate_limiter: RateLimiter | None = None

        # Metrics
        self.metrics = {
            "operations_executed": 0,
            "operations_succeeded": 0,
            "operations_failed": 0,
            "total_duration_ms": 0.0,
            "retries_attempted": 0,
            "circuit_breaker_opens": 0,
        }

        # Operation metrics by operation name
        self.operation_metrics: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        """
        Initialize the effect node.

        This method:
        1. Loads and validates the YAML contract
        2. Resolves environment variables in config
        3. Initializes the protocol handler
        4. Sets up resilience policies
        """
        # Load contract
        self.contract = self._load_contract()

        # Validate contract (raises on invalid)
        self._validate_contract()

        # Initialize protocol handler
        protocol_type = self.contract["protocol"]["type"]
        handler_class = ProtocolHandlerRegistry.get(protocol_type)
        self.handler = handler_class()

        # Merge connection config with overrides
        connection_config = self._resolve_config(self.contract.get("connection", {}))
        connection_config["authentication"] = self._resolve_config(
            self.contract.get("authentication", {})
        )

        await self.handler.initialize(connection_config)

        # Initialize resilience
        resilience = self.contract.get("resilience", {})

        if resilience.get("retry", {}).get("enabled", True):
            self.retry_policy = RetryPolicy(
                max_attempts=resilience.get("retry", {}).get("max_attempts", 3),
                initial_delay_ms=resilience.get("retry", {}).get("initial_delay_ms", 1000),
                max_delay_ms=resilience.get("retry", {}).get("max_delay_ms", 30000),
                backoff_multiplier=resilience.get("retry", {}).get("backoff_multiplier", 2.0),
                jitter=resilience.get("retry", {}).get("jitter", True)
            )

        if resilience.get("circuit_breaker", {}).get("enabled", True):
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=resilience.get("circuit_breaker", {}).get("failure_threshold", 5),
                success_threshold=resilience.get("circuit_breaker", {}).get("success_threshold", 2),
                timeout_ms=resilience.get("circuit_breaker", {}).get("timeout_ms", 60000)
            )

        if resilience.get("rate_limit", {}).get("enabled", False):
            self.rate_limiter = RateLimiter(
                requests_per_second=resilience.get("rate_limit", {}).get("requests_per_second", 100),
                burst_size=resilience.get("rate_limit", {}).get("burst_size", 10)
            )

        logger.info(
            f"NodeEffect initialized | "
            f"node_id={self.node_id} | "
            f"contract={self.contract.get('name')} | "
            f"protocol={protocol_type}"
        )

    async def shutdown(self) -> None:
        """Shutdown the effect node gracefully."""
        if self.handler:
            await self.handler.shutdown()

        logger.info(
            f"NodeEffect shutdown | "
            f"node_id={self.node_id} | "
            f"final_metrics={self.metrics}"
        )

    async def execute_effect(self, input_data: ModelEffectInput) -> ModelEffectOutput:
        """
        Execute an effect operation.

        This method:
        1. Validates input against operation requirements
        2. Applies rate limiting if enabled
        3. Checks circuit breaker state
        4. Executes with retry policy
        5. Maps response via JSONPath
        6. Updates metrics

        Args:
            input_data: Effect input with operation and params

        Returns:
            ModelEffectOutput with result or error
        """
        start_time = time.perf_counter()
        operation = input_data.operation

        # Validate operation exists
        operations = self.contract.get("operations", {})
        if operation not in operations:
            return ModelEffectOutput(
                success=False,
                operation=operation,
                error=f"Unknown operation: {operation}. Available: {list(operations.keys())}",
                correlation_id=input_data.correlation_id
            )

        operation_config = operations[operation]

        # Validate required fields
        validation_error = self._validate_input(input_data.params, operation_config)
        if validation_error:
            return ModelEffectOutput(
                success=False,
                operation=operation,
                error=validation_error,
                correlation_id=input_data.correlation_id
            )

        # Rate limiting
        if self.rate_limiter:
            await self.rate_limiter.acquire()

        # Circuit breaker check
        if self.circuit_breaker and self.circuit_breaker.is_open():
            return ModelEffectOutput(
                success=False,
                operation=operation,
                error="Circuit breaker is open",
                correlation_id=input_data.correlation_id,
                metadata={"circuit_breaker_state": "open"}
            )

        # Build protocol request
        protocol_request = ModelProtocolRequest(
            operation=operation,
            params={
                "input": input_data.params,
                "context": input_data.context,
                "config": self._get_config_values()
            },
            correlation_id=str(input_data.correlation_id),
            timeout_ms=self.contract.get("resilience", {}).get("timeout", {}).get("request_ms", 30000)
        )

        # Execute with retry
        try:
            if self.retry_policy:
                response = await self.retry_policy.execute(
                    self.handler.execute,
                    protocol_request,
                    operation_config,
                    on_retry=lambda attempt, error: self._on_retry(attempt, error, operation)
                )
            else:
                response = await self.handler.execute(protocol_request, operation_config)

            # Map response
            mapped_data = self._map_response(response.data, operation_config)

            # Update circuit breaker
            if self.circuit_breaker:
                if response.success:
                    self.circuit_breaker.record_success()
                else:
                    self.circuit_breaker.record_failure()

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._update_metrics(operation, response.success, duration_ms)

            return ModelEffectOutput(
                success=response.success,
                operation=operation,
                data=mapped_data,
                error=response.error,
                correlation_id=input_data.correlation_id,
                duration_ms=duration_ms,
                metadata={
                    "protocol_status_code": response.status_code,
                    **response.metadata
                }
            )

        except Exception as e:
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()

            duration_ms = (time.perf_counter() - start_time) * 1000
            self._update_metrics(operation, False, duration_ms)

            logger.error(
                f"Effect execution failed | "
                f"operation={operation} | "
                f"correlation_id={input_data.correlation_id} | "
                f"error={e}",
                exc_info=True
            )

            return ModelEffectOutput(
                success=False,
                operation=operation,
                error=str(e),
                correlation_id=input_data.correlation_id,
                duration_ms=duration_ms
            )

    async def health_check(self) -> dict[str, Any]:
        """Check health of the effect node and its connection."""
        health = {
            "node_id": str(self.node_id),
            "contract": self.contract.get("name"),
            "protocol": self.contract.get("protocol", {}).get("type"),
            "status": "unhealthy",
            "handler_healthy": False,
            "circuit_breaker_state": None,
            "metrics": self.metrics
        }

        if self.handler:
            health["handler_healthy"] = await self.handler.health_check()

        if self.circuit_breaker:
            health["circuit_breaker_state"] = self.circuit_breaker.state

        health["status"] = "healthy" if health["handler_healthy"] else "unhealthy"

        return health

    def _load_contract(self) -> dict[str, Any]:
        """Load YAML contract from file."""
        with open(self.contract_path, "r") as f:
            return yaml.safe_load(f)

    def _validate_contract(self) -> None:
        """Validate contract against schema."""
        required_fields = ["name", "version", "protocol", "connection", "operations"]
        for field in required_fields:
            if field not in self.contract:
                raise ValueError(f"Contract missing required field: {field}")

        # Validate protocol type
        protocol_type = self.contract.get("protocol", {}).get("type")
        if protocol_type not in ProtocolHandlerRegistry.list_protocols():
            raise ValueError(f"Unknown protocol type: {protocol_type}")

    def _resolve_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Resolve environment variables and apply overrides."""
        import os
        import re

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                def replace(match):
                    env_var = match.group(1)
                    # Check overrides first, then environment
                    return self.config_overrides.get(env_var, os.getenv(env_var, ""))
                return re.sub(r'\$\{([^}]+)\}', replace, value)
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value

        return resolve_value(config)

    def _get_config_values(self) -> dict[str, Any]:
        """Get resolved config values for template substitution."""
        return self._resolve_config(self.contract.get("connection", {}))

    def _validate_input(
        self,
        params: dict[str, Any],
        operation_config: dict[str, Any]
    ) -> str | None:
        """Validate input against operation requirements."""
        validation = operation_config.get("validation", {})
        required_fields = validation.get("required_fields", [])

        for field in required_fields:
            if field not in params:
                return f"Missing required field: {field}"
            if params[field] is None:
                return f"Required field cannot be null: {field}"

        # Type validation
        field_types = validation.get("field_types", {})
        for field, expected_type in field_types.items():
            if field in params:
                actual_type = type(params[field]).__name__
                if actual_type != expected_type and expected_type not in ["any", "Any"]:
                    return f"Field {field} expected type {expected_type}, got {actual_type}"

        return None

    def _map_response(
        self,
        response_data: dict[str, Any] | None,
        operation_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Map response data using JSONPath expressions."""
        if not response_data:
            return {}

        mapping = operation_config.get("response", {}).get("mapping", {})
        if not mapping:
            return response_data

        result = {}
        for output_field, jsonpath_expr in mapping.items():
            try:
                # Handle simple default syntax: $.field ?? default
                if " ?? " in jsonpath_expr:
                    path, default = jsonpath_expr.split(" ?? ", 1)
                    jsonpath_expr = path.strip()
                    default_value = default.strip()
                else:
                    default_value = None

                # Parse and execute JSONPath
                jsonpath_parser = jsonpath_parse(jsonpath_expr)
                matches = jsonpath_parser.find(response_data)

                if matches:
                    if len(matches) == 1:
                        result[output_field] = matches[0].value
                    else:
                        result[output_field] = [m.value for m in matches]
                elif default_value is not None:
                    # Try to parse default as JSON, fallback to string
                    try:
                        import json
                        result[output_field] = json.loads(default_value)
                    except json.JSONDecodeError:
                        result[output_field] = default_value

            except Exception as e:
                logger.warning(
                    f"JSONPath mapping failed | field={output_field} | expr={jsonpath_expr} | error={e}"
                )

        return result

    def _on_retry(self, attempt: int, error: Exception, operation: str) -> None:
        """Callback when retry is attempted."""
        self.metrics["retries_attempted"] += 1
        logger.warning(
            f"Retrying operation | "
            f"operation={operation} | "
            f"attempt={attempt} | "
            f"error={error}"
        )

    def _update_metrics(self, operation: str, success: bool, duration_ms: float) -> None:
        """Update operation metrics."""
        self.metrics["operations_executed"] += 1
        self.metrics["total_duration_ms"] += duration_ms

        if success:
            self.metrics["operations_succeeded"] += 1
        else:
            self.metrics["operations_failed"] += 1

        # Per-operation metrics
        if operation not in self.operation_metrics:
            self.operation_metrics[operation] = {
                "executed": 0,
                "succeeded": 0,
                "failed": 0,
                "total_duration_ms": 0.0
            }

        op_metrics = self.operation_metrics[operation]
        op_metrics["executed"] += 1
        op_metrics["total_duration_ms"] += duration_ms

        if success:
            op_metrics["succeeded"] += 1
        else:
            op_metrics["failed"] += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        avg_duration = (
            self.metrics["total_duration_ms"] / self.metrics["operations_executed"]
            if self.metrics["operations_executed"] > 0
            else 0.0
        )

        return {
            **self.metrics,
            "avg_duration_ms": avg_duration,
            "success_rate": (
                self.metrics["operations_succeeded"] / self.metrics["operations_executed"]
                if self.metrics["operations_executed"] > 0
                else 0.0
            ),
            "by_operation": self.operation_metrics,
            "node_id": str(self.node_id),
            "contract": self.contract.get("name")
        }
```

### 6.2 Resilience Components

```python
"""Resilience components for effect nodes."""

import asyncio
import random
import time
from typing import Any, Callable, TypeVar
from enum import Enum

T = TypeVar("T")


class RetryPolicy:
    """Retry policy with exponential backoff and jitter."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_ms: int = 1000,
        max_delay_ms: int = 30000,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter

    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        on_retry: Callable[[int, Exception], None] | None = None,
        **kwargs
    ) -> Any:
        """Execute function with retry policy."""
        last_error = None

        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < self.max_attempts - 1:
                    delay = self._calculate_delay(attempt)

                    if on_retry:
                        on_retry(attempt + 1, e)

                    await asyncio.sleep(delay / 1000)

        raise last_error

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = self.initial_delay_ms * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay_ms)

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_ms: int = 60000
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_ms = timeout_ms

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None

    @property
    def state(self) -> str:
        return self._state.value

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._state == CircuitBreakerState.OPEN:
            # Check if timeout has elapsed
            if self._last_failure_time:
                elapsed = (time.time() - self._last_failure_time) * 1000
                if elapsed >= self.timeout_ms:
                    self._state = CircuitBreakerState.HALF_OPEN
                    return False
            return True
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._reset()
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.OPEN
            self._success_count = 0
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN

    def _reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        requests_per_second: float = 100,
        burst_size: int = 10
    ):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size

        self._tokens = burst_size
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            await self._refill()

            while self._tokens < 1:
                wait_time = (1 - self._tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                await self._refill()

            self._tokens -= 1

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(
            self.burst_size,
            self._tokens + elapsed * self.requests_per_second
        )
        self._last_update = now
```

---

## 7. Example Contracts

### 7.1 MLX Embedding Adapter

```yaml
# mlx_embedding_adapter.yaml
name: mlx_embedding_adapter
version:
  major: 1
  minor: 0
  patch: 0

description: |
  Adapter for local MLX embeddings service.
  Provides text embedding generation using MLX-optimized models
  running on Apple Silicon.

protocol:
  type: http_rest
  content_type: application/json

connection:
  url: http://${MLX_HOST:localhost}:${MLX_PORT:8001}
  timeout_ms: 60000
  pool:
    min_size: 1
    max_size: 5

authentication:
  type: none

operations:
  embed:
    description: Generate embeddings for text
    request:
      method: POST
      path: /embed
      body:
        text: ${input.text}
        model: ${input.model:all-minilm}
    response:
      success_codes: [200]
      mapping:
        embeddings: "$.embedding"
        model: "$.model"
        dimension: "$.dimension"
    validation:
      required_fields:
        - text
      field_types:
        text: str
    error_handling:
      retryable_errors:
        - ConnectionError
        - TimeoutError
      non_retryable_errors:
        - ValueError

  batch_embed:
    description: Generate embeddings for multiple texts
    request:
      method: POST
      path: /batch_embed
      body:
        texts: ${input.texts}
        model: ${input.model:all-minilm}
    response:
      success_codes: [200]
      mapping:
        embeddings: "$.embeddings"
        model: "$.model"
        dimension: "$.dimension"
    validation:
      required_fields:
        - texts
      field_types:
        texts: list

  health:
    description: Check service health
    request:
      method: GET
      path: /health
    response:
      success_codes: [200]
      mapping:
        status: "$.status"
        model_loaded: "$.model_loaded"

resilience:
  retry:
    enabled: true
    max_attempts: 3
    initial_delay_ms: 500
    max_delay_ms: 5000
    backoff_multiplier: 2.0
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    timeout_ms: 30000
  timeout:
    request_ms: 60000

events:
  consume:
    topic: dev.archon-intelligence.effect.mlx-embedding.request.v1
    group_id: mlx-embedding-adapter
  produce:
    success_topic: dev.archon-intelligence.effect.mlx-embedding.response.v1
    dlq_topic: dev.archon-intelligence.effect.mlx-embedding.request.v1.dlq

observability:
  metrics:
    enabled: true
    prefix: omniintelligence_mlx_embedding
  logging:
    level: INFO
    sanitize_secrets: true

metadata:
  author: omniintelligence
  created_at: "2025-12-02"
  tags:
    - embedding
    - mlx
    - apple-silicon
```

### 7.2 Qdrant Vector Effect

```yaml
# qdrant_vector_effect.yaml
name: qdrant_vector_effect
version:
  major: 1
  minor: 0
  patch: 0

description: |
  Effect node for vector storage operations in Qdrant.
  Supports upsert, search, delete, and collection management.

protocol:
  type: http_rest
  content_type: application/json

connection:
  url: http://${QDRANT_HOST:localhost}:${QDRANT_PORT:6333}
  timeout_ms: 30000
  pool:
    min_size: 2
    max_size: 10

authentication:
  type: api_key
  api_key:
    header: api-key
    prefix: ""
    value: ${QDRANT_API_KEY:}

operations:
  upsert:
    description: Upsert vector to collection
    request:
      method: PUT
      path: /collections/${input.collection}/points
      query:
        wait: "true"
      body:
        points:
          - id: ${input.vector_id}
            vector: ${input.embeddings}
            payload: ${input.metadata}
    response:
      success_codes: [200]
      mapping:
        operation_id: "$.result.operation_id"
        status: "$.result.status"
    validation:
      required_fields:
        - collection
        - vector_id
        - embeddings
      field_types:
        collection: str
        vector_id: str
        embeddings: list
    error_handling:
      retryable_errors:
        - ConnectionError
        - TimeoutError
      non_retryable_errors:
        - ValueError

  search:
    description: Search for similar vectors
    request:
      method: POST
      path: /collections/${input.collection}/points/search
      body:
        vector: ${input.query_vector}
        limit: ${input.top_k:10}
        score_threshold: ${input.score_threshold:0.0}
        with_payload: true
        filter: ${input.filter:null}
    response:
      success_codes: [200]
      mapping:
        results: "$.result[*]"
        total: "$.result.length()"
    validation:
      required_fields:
        - collection
        - query_vector

  delete:
    description: Delete vector by ID
    request:
      method: POST
      path: /collections/${input.collection}/points/delete
      query:
        wait: "true"
      body:
        points:
          - ${input.vector_id}
    response:
      success_codes: [200]
      mapping:
        operation_id: "$.result.operation_id"
        status: "$.result.status"
    validation:
      required_fields:
        - collection
        - vector_id

  create_collection:
    description: Create new collection
    request:
      method: PUT
      path: /collections/${input.collection}
      body:
        vectors:
          size: ${input.vector_dimension:1536}
          distance: ${input.distance_metric:Cosine}
    response:
      success_codes: [200]
      mapping:
        result: "$.result"
    validation:
      required_fields:
        - collection

  collection_info:
    description: Get collection information
    request:
      method: GET
      path: /collections/${input.collection}
    response:
      success_codes: [200]
      mapping:
        status: "$.result.status"
        vectors_count: "$.result.vectors_count"
        points_count: "$.result.points_count"
        config: "$.result.config"

resilience:
  retry:
    enabled: true
    max_attempts: 3
    initial_delay_ms: 1000
    max_delay_ms: 10000
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    timeout_ms: 60000
  timeout:
    request_ms: 30000

events:
  consume:
    topic: dev.archon-intelligence.effect.qdrant-vector.request.v1
    group_id: qdrant-vector-effect
  produce:
    success_topic: dev.archon-intelligence.effect.qdrant-vector.response.v1
    dlq_topic: dev.archon-intelligence.effect.qdrant-vector.request.v1.dlq

observability:
  metrics:
    enabled: true
    prefix: omniintelligence_qdrant
  logging:
    level: INFO

metadata:
  author: omniintelligence
  created_at: "2025-12-02"
  tags:
    - vector
    - qdrant
    - storage
```

### 7.3 Memgraph Graph Effect

```yaml
# memgraph_graph_effect.yaml
name: memgraph_graph_effect
version:
  major: 1
  minor: 0
  patch: 0

description: |
  Effect node for graph database operations in Memgraph.
  Supports entity creation, relationship management, and Cypher queries.

protocol:
  type: bolt
  version: "4.4"

connection:
  url: bolt://${MEMGRAPH_HOST:localhost}:${MEMGRAPH_PORT:7687}
  timeout_ms: 30000
  pool:
    min_size: 5
    max_size: 50

authentication:
  type: basic
  basic:
    username: ${MEMGRAPH_USER:}
    password: ${MEMGRAPH_PASSWORD:}

operations:
  create_entity:
    description: Create or update entity node
    request:
      cypher: |
        MERGE (e:${input.entity_type} {entity_id: $entity_id})
        ON CREATE SET
          e.name = $name,
          e.created_at = datetime(),
          e.metadata = $metadata
        ON MATCH SET
          e.name = $name,
          e.metadata = $metadata,
          e.updated_at = datetime()
        RETURN e.entity_id AS entity_id,
               labels(e)[0] AS label,
               CASE WHEN e.updated_at IS NULL THEN 'created' ELSE 'updated' END AS action
      cypher_params:
        entity_id: ${input.entity_id}
        name: ${input.name}
        metadata: ${input.metadata}
    response:
      mapping:
        entity_id: "$.records[0].entity_id"
        label: "$.records[0].label"
        action: "$.records[0].action"
    validation:
      required_fields:
        - entity_type
        - entity_id
        - name

  create_relationship:
    description: Create relationship between entities
    request:
      cypher: |
        MATCH (source {entity_id: $source_id})
        MATCH (target {entity_id: $target_id})
        MERGE (source)-[r:${input.relationship_type}]->(target)
        ON CREATE SET r.metadata = $metadata
        ON MATCH SET r.metadata = $metadata
        RETURN source.entity_id AS source_id,
               target.entity_id AS target_id,
               type(r) AS relationship_type
      cypher_params:
        source_id: ${input.source_id}
        target_id: ${input.target_id}
        metadata: ${input.metadata}
    response:
      mapping:
        source_id: "$.records[0].source_id"
        target_id: "$.records[0].target_id"
        relationship_type: "$.records[0].relationship_type"
    validation:
      required_fields:
        - relationship_type
        - source_id
        - target_id

  query:
    description: Execute arbitrary Cypher query
    request:
      cypher: ${input.query}
      cypher_params: ${input.params}
    response:
      mapping:
        records: "$.records"
        counters: "$.counters"
    validation:
      required_fields:
        - query

  delete_entity:
    description: Delete entity and its relationships
    request:
      cypher: |
        MATCH (e {entity_id: $entity_id})
        DETACH DELETE e
        RETURN count(e) AS deleted_count
      cypher_params:
        entity_id: ${input.entity_id}
    response:
      mapping:
        deleted_count: "$.records[0].deleted_count"
    validation:
      required_fields:
        - entity_id

resilience:
  retry:
    enabled: true
    max_attempts: 3
    initial_delay_ms: 1000
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    timeout_ms: 60000
  timeout:
    request_ms: 30000

events:
  consume:
    topic: dev.archon-intelligence.effect.memgraph-graph.request.v1
    group_id: memgraph-graph-effect
  produce:
    success_topic: dev.archon-intelligence.effect.memgraph-graph.response.v1
    dlq_topic: dev.archon-intelligence.effect.memgraph-graph.request.v1.dlq

observability:
  metrics:
    enabled: true
    prefix: omniintelligence_memgraph
  logging:
    level: INFO

metadata:
  author: omniintelligence
  created_at: "2025-12-02"
  tags:
    - graph
    - memgraph
    - cypher
```

### 7.4 PostgreSQL Pattern Effect

```yaml
# postgres_pattern_effect.yaml
name: postgres_pattern_effect
version:
  major: 1
  minor: 0
  patch: 0

description: |
  Effect node for pattern storage in PostgreSQL.
  Supports pattern CRUD, lineage tracking, and search.

protocol:
  type: postgres

connection:
  host: ${POSTGRES_HOST:localhost}
  port: ${POSTGRES_PORT:5432}
  database: ${POSTGRES_DATABASE:omniintelligence}
  timeout_ms: 30000
  pool:
    min_size: 5
    max_size: 20

authentication:
  type: basic
  basic:
    username: ${POSTGRES_USER:postgres}
    password: ${POSTGRES_PASSWORD:}

operations:
  store_pattern:
    description: Store or update a pattern
    request:
      sql: |
        INSERT INTO patterns (pattern_id, pattern_name, pattern_type, project_name, confidence_score, metadata)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        ON CONFLICT (pattern_id) DO UPDATE SET
          pattern_name = EXCLUDED.pattern_name,
          pattern_type = EXCLUDED.pattern_type,
          confidence_score = GREATEST(patterns.confidence_score, EXCLUDED.confidence_score),
          metadata = EXCLUDED.metadata,
          updated_at = NOW()
        RETURNING pattern_id, pattern_name
      sql_params:
        - ${input.pattern_id}
        - ${input.pattern_name}
        - ${input.pattern_type}
        - ${input.project_name}
        - ${input.confidence_score}
        - ${input.metadata}
    response:
      mapping:
        pattern_id: "$.rows[0].pattern_id"
        pattern_name: "$.rows[0].pattern_name"
    validation:
      required_fields:
        - pattern_id
        - pattern_name

  query_patterns:
    description: Query patterns with filters
    request:
      sql: |
        SELECT * FROM patterns
        WHERE confidence_score >= $1
        AND ($2::text IS NULL OR project_name = $2)
        AND ($3::text IS NULL OR pattern_type = $3)
        ORDER BY confidence_score DESC
        LIMIT $4 OFFSET $5
      sql_params:
        - ${input.min_confidence:0.0}
        - ${input.project_name:null}
        - ${input.pattern_type:null}
        - ${input.limit:50}
        - ${input.offset:0}
    response:
      mapping:
        patterns: "$.rows"
        count: "$.row_count"

  get_lineage:
    description: Get pattern lineage
    request:
      sql: |
        SELECT * FROM pattern_lineage
        WHERE pattern_id = $1
        ORDER BY created_at DESC
      sql_params:
        - ${input.pattern_id}
    response:
      mapping:
        lineage: "$.rows"
    validation:
      required_fields:
        - pattern_id

  search_patterns:
    description: Full-text search for patterns
    request:
      sql: |
        SELECT *,
          CASE WHEN pattern_name ILIKE $1 THEN 1.0
               WHEN pattern_name ILIKE $2 THEN 0.8
               ELSE 0.5 END as search_rank
        FROM patterns
        WHERE pattern_name ILIKE $2 OR pattern_type ILIKE $2
        ORDER BY search_rank DESC, confidence_score DESC
        LIMIT $3
      sql_params:
        - ${input.query}
        - "%${input.query}%"
        - ${input.limit:50}
    response:
      mapping:
        patterns: "$.rows"
        count: "$.row_count"
    validation:
      required_fields:
        - query

resilience:
  retry:
    enabled: true
    max_attempts: 3
    initial_delay_ms: 1000
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    timeout_ms: 60000
  timeout:
    request_ms: 30000

events:
  consume:
    topic: dev.archon-intelligence.effect.postgres-pattern.request.v1
    group_id: postgres-pattern-effect
  produce:
    success_topic: dev.archon-intelligence.effect.postgres-pattern.response.v1
    dlq_topic: dev.archon-intelligence.effect.postgres-pattern.request.v1.dlq

observability:
  metrics:
    enabled: true
    prefix: omniintelligence_postgres_pattern
  logging:
    level: INFO

metadata:
  author: omniintelligence
  created_at: "2025-12-02"
  tags:
    - pattern
    - postgres
    - storage
```

### 7.5 Kafka Event Effect

```yaml
# kafka_event_effect.yaml
name: kafka_event_effect
version:
  major: 1
  minor: 0
  patch: 0

description: |
  Effect node for publishing events to Kafka.
  Supports event publishing with delivery confirmation.

protocol:
  type: kafka

connection:
  url: ${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
  timeout_ms: 30000

authentication:
  type: none

operations:
  publish:
    description: Publish event to Kafka topic
    request:
      topic: ${input.topic}
      key: ${input.key:${input.correlation_id}}
      headers: ${input.headers:{}}
    response:
      mapping:
        topic: "$.topic"
        partition: "$.partition"
        offset: "$.offset"
    validation:
      required_fields:
        - topic
        - event_type
        - payload

  publish_batch:
    description: Publish multiple events
    request:
      topic: ${input.topic}
      messages: ${input.messages}
    response:
      mapping:
        published_count: "$.published_count"
        failed_count: "$.failed_count"
    validation:
      required_fields:
        - topic
        - messages

resilience:
  retry:
    enabled: true
    max_attempts: 3
    initial_delay_ms: 500
  circuit_breaker:
    enabled: true
    failure_threshold: 10
    timeout_ms: 60000
  timeout:
    request_ms: 30000

events:
  consume:
    topic: dev.archon-intelligence.effect.kafka-event.request.v1
    group_id: kafka-event-effect
  produce:
    success_topic: dev.archon-intelligence.effect.kafka-event.response.v1
    dlq_topic: dev.archon-intelligence.effect.kafka-event.request.v1.dlq

observability:
  metrics:
    enabled: true
    prefix: omniintelligence_kafka_event
  logging:
    level: INFO
    sanitize_secrets: true

metadata:
  author: omniintelligence
  created_at: "2025-12-02"
  tags:
    - kafka
    - event
    - messaging
```

---

## 8. File Structure

### 8.1 Directory Layout

```
src/omniintelligence/
├── nodes/
│   ├── effect_runtime/                  # Base runtime package
│   │   ├── __init__.py
│   │   ├── v1_0_0/
│   │   │   ├── __init__.py
│   │   │   ├── runtime.py               # NodeEffect (default base class)
│   │   │   ├── handlers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py              # ProtocolHandler ABC
│   │   │   │   ├── http_rest.py         # HttpRestHandler
│   │   │   │   ├── bolt.py              # BoltHandler
│   │   │   │   ├── postgres.py          # PostgresHandler
│   │   │   │   ├── kafka.py             # KafkaHandler
│   │   │   │   └── registry.py          # ProtocolHandlerRegistry
│   │   │   ├── resilience/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── retry.py             # RetryPolicy
│   │   │   │   ├── circuit_breaker.py   # CircuitBreaker
│   │   │   │   └── rate_limiter.py      # RateLimiter
│   │   │   ├── models.py                # Pydantic models
│   │   │   ├── mapping.py               # JSONPath mapping
│   │   │   └── validation.py            # Contract validation
│   │   └── contracts/
│   │       └── schema/
│   │           └── effect_contract_v1.json  # JSON Schema
│   │
│   ├── mlx_embedding_adapter/           # Effect node (uses contracts)
│   │   ├── __init__.py
│   │   └── v1_0_0/
│   │       ├── __init__.py
│   │       ├── contracts/
│   │       │   └── mlx_embedding_adapter.yaml
│   │       └── node.py                  # Thin wrapper if customization needed
│   │
│   ├── qdrant_vector_effect/            # Effect node (contract-driven default)
│   │   ├── __init__.py
│   │   └── v1_0_0/
│   │       ├── __init__.py
│   │       ├── contracts/
│   │       │   └── qdrant_vector_effect.yaml
│   │       ├── effect.py                # NodeQdrantVectorEffect (default)
│   │       └── legacy/
│   │           └── effect_legacy.py     # NodeQdrantVectorEffectLegacy (deprecated)
│   │
│   ├── memgraph_graph_effect/           # Effect node (contract-driven default)
│   │   └── v1_0_0/
│   │       ├── contracts/
│   │       │   └── memgraph_graph_effect.yaml
│   │       └── legacy/
│   │           └── effect_legacy.py     # NodeMemgraphGraphEffectLegacy (deprecated)
│   │
│   ├── postgres_pattern_effect/         # Effect node (contract-driven default)
│   │   └── v1_0_0/
│   │       └── contracts/
│   │           └── postgres_pattern_effect.yaml
│   │
│   └── kafka_event_effect/              # Effect node (contract-driven default)
│       └── v1_0_0/
│           └── contracts/
│               └── kafka_event_effect.yaml
│
├── schemas/
│   └── effect_contract_v1.json          # Shared JSON Schema
│
└── tests/
    ├── nodes/
    │   └── effect_runtime/
    │       ├── test_runtime.py
    │       ├── test_handlers/
    │       │   ├── test_http_rest.py
    │       │   ├── test_bolt.py
    │       │   ├── test_postgres.py
    │       │   └── test_kafka.py
    │       └── test_resilience/
    │           ├── test_retry.py
    │           ├── test_circuit_breaker.py
    │           └── test_rate_limiter.py
    └── integration/
        └── effects/
            ├── test_qdrant_effect.py
            └── test_memgraph_effect.py
```

### 8.2 Contract Discovery

The runtime discovers contracts via:

1. **Explicit path**: Pass contract path to `NodeEffect`
2. **Node directory**: Look for `contracts/*.yaml` in node directory
3. **Registry lookup**: Use node name to find registered contract path

```python
# Contract loader
def load_contract(node_name: str, version: str = "v1_0_0") -> Path:
    """Find contract file for an effect node."""
    base_path = Path(__file__).parent.parent / "nodes"

    # Check node-specific contracts
    node_path = base_path / node_name / version / "contracts"
    if node_path.exists():
        contracts = list(node_path.glob("*.yaml"))
        if contracts:
            return contracts[0]

    raise FileNotFoundError(f"No contract found for {node_name}/{version}")
```

### 8.3 Registering Custom Handlers

```python
# In your application startup
from omniintelligence.nodes.effect_runtime.v1_0_0.handlers import (
    ProtocolHandler,
    ProtocolHandlerRegistry
)

class CustomProtocolHandler(ProtocolHandler):
    """Custom handler for proprietary protocol."""

    async def initialize(self, config: dict) -> None:
        # Initialize connection
        pass

    async def shutdown(self) -> None:
        # Close connection
        pass

    async def execute(self, request, operation_config) -> ModelProtocolResponse:
        # Execute operation
        pass

    async def health_check(self) -> bool:
        # Check health
        pass

# Register the custom handler
ProtocolHandlerRegistry.register("custom_protocol", CustomProtocolHandler)
```

---

## 9. Implementation Guide

### 9.1 Phase 1: Core Runtime (Week 1-2)

1. **Create base package structure**
   - `effect_runtime/v1_0_0/`
   - JSON Schema for contract validation
   - Base `ProtocolHandler` ABC

2. **Implement `NodeEffect`**
   - Contract loading and validation
   - Template variable substitution
   - Operation routing
   - Basic metrics

3. **Implement `HttpRestHandler`**
   - Connection pooling with aiohttp
   - Request building with variable substitution
   - Response parsing

4. **Write unit tests**
   - Contract validation tests
   - Variable substitution tests
   - Response mapping tests

### 9.2 Phase 2: Protocol Handlers (Week 2-3)

1. **Implement `BoltHandler`**
   - Neo4j async driver integration
   - Cypher parameter building
   - Transaction support

2. **Implement `PostgresHandler`**
   - asyncpg pool integration
   - SQL parameter binding
   - Result set mapping

3. **Implement `KafkaHandler`**
   - Confluent Kafka producer
   - Delivery confirmation
   - Batch publishing

4. **Integration tests with Docker**
   - Test against real Qdrant, Memgraph, PostgreSQL
   - Verify contract correctness

### 9.3 Phase 3: Resilience (Week 3-4)

1. **Implement `RetryPolicy`**
   - Exponential backoff
   - Jitter support
   - Retry callback

2. **Implement `CircuitBreaker`**
   - State machine (closed/open/half-open)
   - Failure/success tracking
   - Timeout-based recovery

3. **Implement `RateLimiter`**
   - Token bucket algorithm
   - Async acquire with wait

4. **Integration with runtime**
   - Wire resilience into `execute_effect`
   - Add metrics for resilience events

### 9.4 Phase 4: Event Integration (Week 4-5)

1. **Kafka consumer loop**
   - Consume from request topic
   - Route to `execute_effect`
   - Publish to response/DLQ topic

2. **Event envelope handling**
   - Correlation ID extraction
   - Metadata propagation
   - Timing information

3. **DLQ routing**
   - Full context preservation
   - Error categorization
   - Retry metadata

### 9.5 Phase 5: Migration (Week 5-6)

1. **Create contracts for existing nodes**
   - `qdrant_vector_effect.yaml`
   - `memgraph_graph_effect.yaml`
   - `postgres_pattern_effect.yaml`
   - `kafka_event_effect.yaml`

2. **Parallel run validation**
   - Run legacy and contract-driven implementations in parallel
   - Compare outputs
   - Fix discrepancies

3. **Rename and deprecate legacy nodes**
   - Add `Legacy` suffix to old imperative classes
   - Add deprecation warnings
   - Update documentation
   - Update orchestrator references

### 9.6 Phase 6: New Adapters (Week 6+)

1. **MLX Embedding Adapter**
   - Create `mlx_embedding_adapter.yaml`
   - Test against local MLX service
   - Add to orchestrator workflows

2. **OpenAI Adapter (future)**
   - Create `openai_adapter.yaml`
   - Handle API key authentication
   - Rate limiting for API quotas

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/nodes/effect_runtime/test_runtime.py

import pytest
from omniintelligence.nodes.effect_runtime.v1_0_0.runtime import (
    NodeEffect,
    ModelEffectInput
)

@pytest.fixture
def sample_contract():
    return {
        "name": "test_effect",
        "version": {"major": 1, "minor": 0, "patch": 0},
        "protocol": {"type": "http_rest"},
        "connection": {"url": "http://test:8080"},
        "operations": {
            "test_op": {
                "description": "Test operation",
                "request": {
                    "method": "GET",
                    "path": "/test/${input.id}"
                },
                "response": {
                    "mapping": {
                        "result": "$.data"
                    }
                }
            }
        }
    }

def test_variable_substitution():
    node = NodeEffect.__new__(NodeEffect)
    node.contract = {}

    template = "Hello ${input.name}, your ID is ${input.id}"
    params = {"input": {"name": "World", "id": 123}}

    result = node._substitute_variables(template, params)
    assert result == "Hello World, your ID is 123"

def test_response_mapping():
    node = NodeEffect.__new__(NodeEffect)

    response_data = {
        "data": {
            "items": [1, 2, 3],
            "total": 3
        }
    }

    operation_config = {
        "response": {
            "mapping": {
                "items": "$.data.items",
                "count": "$.data.total"
            }
        }
    }

    result = node._map_response(response_data, operation_config)
    assert result["items"] == [1, 2, 3]
    assert result["count"] == 3
```

### 10.2 Handler Tests

```python
# tests/nodes/effect_runtime/test_handlers/test_http_rest.py

import pytest
import aiohttp
from unittest.mock import AsyncMock, patch

from omniintelligence.nodes.effect_runtime.v1_0_0.handlers import (
    HttpRestHandler,
    ModelProtocolRequest
)

@pytest.fixture
async def http_handler():
    handler = HttpRestHandler()
    await handler.initialize({
        "url": "http://test:8080",
        "timeout_ms": 5000
    })
    yield handler
    await handler.shutdown()

@pytest.mark.asyncio
async def test_http_get_request(http_handler):
    with patch.object(http_handler.session, 'request') as mock_request:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json = AsyncMock(return_value={"result": "success"})
        mock_request.return_value.__aenter__.return_value = mock_response

        request = ModelProtocolRequest(
            operation="get_item",
            params={"input": {"id": "123"}},
            correlation_id="test-123"
        )

        operation_config = {
            "request": {
                "method": "GET",
                "path": "/items/${input.id}"
            },
            "response": {
                "success_codes": [200]
            }
        }

        result = await http_handler.execute(request, operation_config)

        assert result.success
        assert result.data == {"result": "success"}
```

### 10.3 Integration Tests

```python
# tests/integration/effects/test_qdrant_effect.py

import pytest
from uuid import uuid4

from omniintelligence.nodes.effect_runtime.v1_0_0.runtime import (
    NodeEffect,
    ModelEffectInput
)

@pytest.fixture
async def qdrant_effect():
    node = NodeEffect(
        contract_path="src/omniintelligence/nodes/qdrant_vector_effect/v1_0_0/contracts/qdrant_vector_effect.yaml",
        config_overrides={
            "QDRANT_HOST": "localhost",
            "QDRANT_PORT": "6333"
        }
    )
    await node.initialize()
    yield node
    await node.shutdown()

@pytest.mark.integration
@pytest.mark.asyncio
async def test_qdrant_upsert_and_search(qdrant_effect):
    collection = f"test_{uuid4().hex[:8]}"
    vector_id = str(uuid4())
    embeddings = [0.1] * 1536

    # Create collection
    create_result = await qdrant_effect.execute_effect(ModelEffectInput(
        operation="create_collection",
        params={
            "collection": collection,
            "vector_dimension": 1536
        }
    ))
    assert create_result.success

    # Upsert vector
    upsert_result = await qdrant_effect.execute_effect(ModelEffectInput(
        operation="upsert",
        params={
            "collection": collection,
            "vector_id": vector_id,
            "embeddings": embeddings,
            "metadata": {"test": True}
        }
    ))
    assert upsert_result.success

    # Search
    search_result = await qdrant_effect.execute_effect(ModelEffectInput(
        operation="search",
        params={
            "collection": collection,
            "query_vector": embeddings,
            "top_k": 5
        }
    ))
    assert search_result.success
    assert len(search_result.data.get("results", [])) > 0
```

### 10.4 Contract Validation Tests

```python
# tests/nodes/effect_runtime/test_contract_validation.py

import pytest
import jsonschema
import yaml
from pathlib import Path

SCHEMA_PATH = Path("src/omniintelligence/schemas/effect_contract_v1.json")
CONTRACTS_DIR = Path("src/omniintelligence/nodes")

def get_all_contracts():
    """Find all effect contract YAML files."""
    contracts = []
    for contract_file in CONTRACTS_DIR.rglob("*_effect.yaml"):
        contracts.append(contract_file)
    return contracts

@pytest.fixture
def contract_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)

@pytest.mark.parametrize("contract_path", get_all_contracts())
def test_contract_validates_against_schema(contract_path, contract_schema):
    with open(contract_path) as f:
        contract = yaml.safe_load(f)

    # This should not raise
    jsonschema.validate(contract, contract_schema)
```

---

## 11. Migration Path

### 11.1 Compatibility Layer

During migration, provide a compatibility wrapper in the legacy module:

```python
# Compatibility wrapper for existing code (in legacy/ directory)
class NodeQdrantVectorEffectLegacy:
    """
    DEPRECATED: Use NodeQdrantVectorEffect (contract-driven) instead.

    This legacy wrapper maintains backward compatibility during migration.
    Will be removed in v2.0.0.
    """

    def __init__(self, container, config=None):
        import warnings
        warnings.warn(
            "NodeQdrantVectorEffectLegacy is deprecated. "
            "Use NodeQdrantVectorEffect (contract-driven) instead.",
            DeprecationWarning,
            stacklevel=2
        )

        # The new contract-driven implementation
        from ..effect import NodeQdrantVectorEffect
        self._effect = NodeQdrantVectorEffect(
            contract_path="qdrant_vector_effect.yaml"
        )
        self.config = config

    async def initialize(self):
        await self._effect.initialize()

    async def shutdown(self):
        await self._effect.shutdown()

    async def execute_effect(self, input_data):
        # Map old input model to new
        effect_input = ModelEffectInput(
            operation=input_data.operation,
            params={
                "collection": input_data.collection,
                "vector_id": input_data.vector_id,
                "embeddings": input_data.embeddings,
                "metadata": input_data.metadata,
                "search_params": input_data.search_params,
            },
            correlation_id=input_data.correlation_id
        )

        result = await self._effect.execute_effect(effect_input)

        # Map new output to old model
        return ModelQdrantVectorOutput(
            success=result.success,
            operation=result.operation,
            vector_id=result.data.get("vector_id"),
            results=result.data.get("results"),
            error=result.error,
            correlation_id=result.correlation_id,
            metadata=result.data
        )
```

### 11.2 Migration Checklist

For each effect node:

- [ ] Create contract YAML for the node
- [ ] Validate contract against schema
- [ ] Write integration tests for contract-driven version
- [ ] Rename old class to add `Legacy` suffix
- [ ] Create new contract-driven class with original name
- [ ] Run parallel comparison (legacy vs contract-driven)
- [ ] Add deprecation warning to legacy version
- [ ] Update orchestrator workflow references
- [ ] Update documentation
- [ ] Monitor in production (canary deployment)
- [ ] Remove legacy version after validation period (typically 2 release cycles)

### 11.3 Rollback Plan

If issues arise:

1. **Feature flag**: Use environment variable to switch between contract-driven and legacy implementations
2. **Import alias**: Temporarily alias legacy class to original name
3. **Dual-write**: Run both implementations, compare results
4. **Quick revert**: Legacy code preserved for 2 release cycles with `Legacy` suffix

---

## Appendix A: Full JSON Schema

The complete JSON Schema is available at:
`src/omniintelligence/schemas/effect_contract_v1.json`

## Appendix B: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |
| `QDRANT_API_KEY` | (empty) | Qdrant API key |
| `MEMGRAPH_HOST` | `localhost` | Memgraph server host |
| `MEMGRAPH_PORT` | `7687` | Memgraph Bolt port |
| `MEMGRAPH_USER` | (empty) | Memgraph username |
| `MEMGRAPH_PASSWORD` | (empty) | Memgraph password |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `postgres` | PostgreSQL username |
| `POSTGRES_PASSWORD` | (empty) | PostgreSQL password |
| `POSTGRES_DATABASE` | `omniintelligence` | PostgreSQL database |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka bootstrap servers |
| `MLX_HOST` | `localhost` | MLX embedding service host |
| `MLX_PORT` | `8001` | MLX embedding service port |

## Appendix C: Metrics Reference

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `omniintelligence_effect_operations_total` | Counter | `effect`, `operation`, `status` | Total operations |
| `omniintelligence_effect_operation_duration_seconds` | Histogram | `effect`, `operation` | Operation duration |
| `omniintelligence_effect_retries_total` | Counter | `effect`, `operation` | Retry attempts |
| `omniintelligence_effect_circuit_breaker_state` | Gauge | `effect` | Circuit breaker state (0=closed, 1=open, 2=half-open) |
| `omniintelligence_effect_rate_limit_wait_seconds` | Histogram | `effect` | Rate limit wait time |

---

**Document End**
