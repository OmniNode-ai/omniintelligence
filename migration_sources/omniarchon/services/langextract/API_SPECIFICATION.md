# LangExtract Service API Specification

**Service**: Archon LangExtract - Advanced Language-Aware Data Extraction  
**Version**: 1.0.0  
**Base URL**: `http://localhost:8156`  
**Protocol**: HTTP/REST with JSON  

## Overview

The LangExtract service provides advanced language-aware entity extraction and knowledge graph enhancement capabilities for the Archon platform. It supports multilingual content analysis, semantic pattern recognition, and intelligent document processing.

## Core Features

- **Language-Aware Extraction**: Automatic language detection and language-specific entity extraction
- **Multilingual Support**: Processing of multilingual documents with cross-language entity linking
- **Semantic Analysis**: Deep semantic pattern recognition and concept extraction
- **Knowledge Graph Integration**: Automatic knowledge graph updates with extracted entities
- **Event-Driven Processing**: Integration with DocumentEventBus for real-time extraction
- **Batch Processing**: High-throughput batch extraction with intelligent load balancing

## Authentication

Currently, the service operates without authentication. In production, implement service-to-service authentication using the `SERVICE_AUTH_TOKEN` environment variable.

## Base Response Format

All API responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2025-01-21T10:30:00Z",
  "version": "1.0.0"
}
```

Error responses:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "EXTRACTION_FAILED",
    "message": "Detailed error description",
    "details": { ... }
  },
  "timestamp": "2025-01-21T10:30:00Z",
  "version": "1.0.0"
}
```

## Endpoints

### Health Check

**GET** `/health`

Check service health and component status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-21T10:30:00Z",
  "components": {
    "memgraph_adapter": "healthy",
    "intelligence_client": "healthy",
    "language_extractor": "healthy",
    "document_analyzer": "healthy",
    "event_subscriber": "healthy"
  },
  "version": "1.0.0"
}
```

**Status Values:**
- `healthy` - All components operational
- `degraded` - Some components have issues
- `unhealthy` - Critical components failing

---

### Document Extraction

**POST** `/extract/document`

Extract entities and relationships from a single document with advanced language-aware processing.

**Request Body:**
```json
{
  "document_path": "/path/to/document.py",
  "extraction_options": {
    "mode": "standard",
    "target_languages": ["auto"],
    "enable_multilingual": true,
    "include_semantic_analysis": true,
    "include_relationship_extraction": true,
    "include_entity_linking": false,
    "extract_code_patterns": true,
    "extract_documentation_concepts": true,
    "min_confidence_threshold": 0.3,
    "min_quality_threshold": 0.2,
    "schema_hints": {},
    "expected_entity_types": [],
    "semantic_context": "software development",
    "domain_specific_terms": [],
    "max_entities_per_type": null,
    "enable_caching": true,
    "timeout_seconds": 300
  },
  "update_knowledge_graph": true,
  "emit_events": true,
  "document_type": "python",
  "encoding": "utf-8",
  "correlation_id": "optional-correlation-id"
}
```

**Extraction Modes:**
- `fast` - Quick extraction with basic patterns (~ 100-500ms)
- `standard` - Balanced extraction with semantic analysis (~ 500-2000ms)  
- `comprehensive` - Deep analysis with all features (~ 1000-5000ms)
- `custom` - Custom configuration based on extraction_options

**Response:**
```json
{
  "extraction_id": "ext_20250121_103045_1234",
  "document_path": "/path/to/document.py",
  "language_results": {
    "entities": [
      {
        "entity_id": "code_12345",
        "name": "UserService",
        "entity_type": "class",
        "description": "Python class: UserService",
        "confidence_score": 0.95,
        "quality_score": 0.87,
        "source_path": "/path/to/document.py",
        "language": "en",
        "content": "class UserService:\n    def __init__(self):\n        pass",
        "aliases": [],
        "tags": ["service", "user-management"],
        "categories": ["backend"],
        "semantic_embedding": [0.1, 0.2, ...],
        "semantic_concepts": ["service pattern", "user management"],
        "properties": {
          "entity_subtype": "class",
          "source_line": "class UserService:",
          "programming_language": "py"
        },
        "attributes": {},
        "metadata": {
          "extraction_method": "language_aware_code_extraction",
          "confidence_level": "very_high",
          "language_detected": "en",
          "extracted_at": "2025-01-21T10:30:45Z",
          "processing_time_ms": 15.2,
          "quality_score": 0.87,
          "completeness_score": 0.92,
          "source_line_start": 1,
          "source_line_end": 3,
          "semantic_context": {},
          "linguistic_features": {}
        }
      }
    ],
    "language_detected": "en",
    "confidence_score": 0.89,
    "language_confidence": 0.95,
    "multilingual_detected": false,
    "primary_language": "en",
    "secondary_languages": [],
    "processing_time_ms": 234.5,
    "total_tokens": 45
  },
  "structured_results": {
    "structured_entities": [],
    "data_schemas": [],
    "completeness_score": 0.85,
    "consistency_score": 0.90,
    "validity_score": 0.88,
    "detected_formats": ["python"],
    "schema_compliance": {}
  },
  "semantic_results": {
    "semantic_patterns": [
      {
        "pattern_id": "pattern_123",
        "pattern_type": "class_definition",
        "pattern_name": "Service Class Pattern",
        "description": "Service layer class following naming convention",
        "examples": ["UserService", "OrderService"],
        "frequency": 1,
        "confidence_score": 0.85,
        "significance_score": 0.75,
        "context": {},
        "properties": {},
        "related_entity_ids": ["code_12345"]
      }
    ],
    "concepts": ["service pattern", "object-oriented design"],
    "themes": ["backend development", "service architecture"],
    "semantic_density": 0.78,
    "conceptual_coherence": 0.82,
    "thematic_consistency": 0.85,
    "semantic_context": {},
    "domain_indicators": ["python", "backend"],
    "primary_topics": ["service development"],
    "topic_weights": {
      "service development": 0.85,
      "object-oriented": 0.65
    }
  },
  "analysis_result": {
    "document_type": "python_source",
    "structure_analysis": {
      "classes": 1,
      "functions": 1,
      "lines_of_code": 3
    },
    "content_summary": "Python service class definition",
    "readability_score": 0.88,
    "complexity_score": 0.25,
    "information_density": 0.65,
    "key_concepts": ["service", "initialization"],
    "main_topics": ["backend service"],
    "sentiment_analysis": null,
    "sections": [],
    "hierarchical_structure": {}
  },
  "enriched_entities": [
    // Same as language_results.entities but potentially enhanced with additional data
  ],
  "relationships": [
    {
      "relationship_id": "rel_123456789",
      "source_entity_id": "code_12345",
      "target_entity_id": "code_12346",
      "relationship_type": "contains",
      "confidence_score": 0.85,
      "strength": 0.75,
      "description": "Class contains method",
      "context": "UserService class definition",
      "semantic_weight": 0.80,
      "directionality": true,
      "properties": {},
      "evidence": ["Method defined within class"],
      "detected_in_source": "/path/to/document.py",
      "source_line_number": 2,
      "created_at": "2025-01-21T10:30:45Z"
    }
  ],
  "extraction_statistics": {
    "total_entities": 2,
    "total_relationships": 1,
    "total_patterns": 1,
    "extraction_time_seconds": 0.234,
    "processing_rate_entities_per_second": 8.5,
    "confidence_score": 0.89,
    "average_entity_confidence": 0.90,
    "average_relationship_confidence": 0.85,
    "entity_type_distribution": {
      "class": 1,
      "method": 1
    },
    "relationship_type_distribution": {
      "contains": 1
    },
    "confidence_distribution": {
      "high": 2,
      "medium": 0,
      "low": 0
    }
  },
  "status": "completed",
  "timestamp": "2025-01-21T10:30:45Z",
  "warnings": [],
  "errors": []
}
```

---

### Batch Document Extraction

**POST** `/extract/batch`

Extract entities and relationships from multiple documents in parallel with intelligent load balancing.

**Request Body:**
```json
{
  "document_paths": [
    "/path/to/document1.py",
    "/path/to/document2.md",
    "/path/to/document3.js"
  ],
  "extraction_options": {
    // Same as single document extraction
  },
  "max_concurrent_extractions": 5,
  "continue_on_error": true,
  "update_knowledge_graph": true,
  "emit_events": true,
  "batch_id": "optional-batch-id"
}
```

**Response:**
```json
[
  {
    // ExtractionResponse for document1.py
  },
  {
    // ExtractionResponse for document2.md  
  },
  {
    // ExtractionResponse for document3.js
  }
]
```

**Notes:**
- Documents are processed in parallel with configurable concurrency
- Failed extractions are excluded from results unless `continue_on_error` is true
- Background tasks for knowledge graph updates and event emission run asynchronously

---

### Semantic Analysis

**POST** `/analyze/semantic`

Perform deep semantic analysis on text content without full document extraction.

**Request Body:**
```json
{
  "content": "Text content to analyze",
  "context": "Optional semantic context",
  "language": "en"
}
```

**Query Parameters:**
- `content` (required) - Text content to analyze
- `context` (optional) - Semantic context for analysis
- `language` (optional) - Language code, defaults to auto-detection

**Response:**
```json
{
  "semantic_patterns": [
    {
      "pattern_id": "pattern_456",
      "pattern_type": "concept_definition",
      "pattern_name": "Technical Concept",
      "description": "Definition of a technical concept",
      "examples": ["API endpoint", "database schema"],
      "frequency": 2,
      "confidence_score": 0.82,
      "significance_score": 0.76
    }
  ],
  "concepts": ["API", "database", "schema"],
  "themes": ["software architecture", "data modeling"],
  "semantic_density": 0.73,
  "conceptual_coherence": 0.85,
  "thematic_consistency": 0.79,
  "semantic_context": {
    "domain": "software development",
    "complexity": "intermediate"
  },
  "domain_indicators": ["technical", "programming"],
  "primary_topics": ["API design", "data modeling"],
  "topic_weights": {
    "API design": 0.78,
    "data modeling": 0.65
  }
}
```

---

### Service Statistics

**GET** `/statistics`

Get comprehensive service statistics and performance metrics.

**Response:**
```json
{
  "service_statistics": {
    "uptime": 3600.5,
    "total_extractions": 1250,
    "average_extraction_time": 567.8
  },
  "extraction_statistics": {
    "language_extractor": {
      "extractor_type": "language_aware",
      "total_extractions": 1250,
      "successful_extractions": 1205,
      "failed_extractions": 45,
      "success_rate": 0.964,
      "total_entities_extracted": 15678,
      "average_extraction_time_ms": 567.8,
      "average_entities_per_extraction": 12.5,
      "supported_languages": [".py", ".js", ".md", ".java"],
      "supported_code_languages": ["python", "javascript"],
      "supported_doc_formats": ["markdown"]
    },
    "structured_extractor": {
      // Similar structure
    },
    "semantic_extractor": {
      // Similar structure  
    }
  },
  "knowledge_graph_statistics": {
    "total_nodes": 25430,
    "total_relationships": 18765,
    "nodes_by_type": {
      "class": 3456,
      "function": 8901,
      "concept": 5632
    },
    "last_updated": "2025-01-21T10:30:00Z"
  },
  "timestamp": "2025-01-21T10:30:00Z"
}
```

## Data Models

### Entity Types

The service supports comprehensive entity extraction across multiple domains:

**Code Entities:**
- `class` - Programming language classes
- `function` - Functions and methods
- `method` - Class methods specifically
- `variable` - Variables and properties
- `constant` - Constants and enums
- `module` - Modules and packages
- `interface` - Interfaces and protocols

**Documentation Entities:**
- `concept` - Conceptual topics
- `procedure` - Step-by-step procedures
- `requirement` - Requirements and specifications
- `specification` - Technical specifications
- `example` - Code or usage examples

**Semantic Entities:**
- `topic` - Main subject areas
- `theme` - Thematic content
- `keyword` - Important keywords
- `category` - Classification categories
- `tag` - Semantic tags

**Language-Specific Entities:**
- `phrase` - Important phrases
- `sentiment` - Sentiment expressions
- `intent` - User intents
- `entity_mention` - Named entity mentions

### Relationship Types

**Structural Relationships:**
- `contains` - Parent-child containment
- `belongs_to` - Child-parent membership
- `inherits_from` - Inheritance relationships
- `implements` - Interface implementation
- `depends_on` - Dependency relationships

**Semantic Relationships:**
- `relates_to` - General semantic relation
- `similar_to` - Similarity relationship
- `opposite_of` - Antonym relationship
- `part_of` - Part-whole relationship
- `example_of` - Example relationship

**Functional Relationships:**
- `calls` - Function/method calls
- `uses` - Usage relationships
- `defines` - Definition relationships
- `references` - Reference relationships

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `EXTRACTION_FAILED` | General extraction failure | 500 |
| `INVALID_DOCUMENT_PATH` | Document not found or inaccessible | 404 |
| `UNSUPPORTED_FORMAT` | Document format not supported | 400 |
| `TIMEOUT_ERROR` | Extraction timed out | 408 |
| `VALIDATION_ERROR` | Request validation failed | 400 |
| `SERVICE_UNAVAILABLE` | Dependent service unavailable | 503 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |

## Rate Limits

- **Document Extraction**: 100 requests/minute per client
- **Batch Extraction**: 10 requests/minute per client
- **Semantic Analysis**: 200 requests/minute per client
- **Statistics**: 60 requests/minute per client

## Performance Guidelines

### Single Document Extraction
- **Fast Mode**: < 500ms for typical documents
- **Standard Mode**: 500ms - 2s for comprehensive analysis
- **Comprehensive Mode**: 1s - 5s for deep analysis

### Batch Extraction
- **Concurrent Processing**: Up to 20 documents in parallel
- **Throughput**: ~10-50 documents/minute depending on size and complexity
- **Memory Usage**: ~100-500MB per concurrent extraction

### Optimization Tips
1. **Use Fast Mode** for real-time applications
2. **Enable Caching** for repeated analysis of similar content
3. **Batch Similar Documents** for better throughput
4. **Set Appropriate Timeouts** based on document complexity
5. **Filter Entity Types** to reduce processing time

## Integration Examples

### Python Client Example

```python
import asyncio
import httpx

class LangExtractClient:
    def __init__(self, base_url="http://localhost:8156"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def extract_document(self, document_path, options=None):
        request = {
            "document_path": document_path,
            "extraction_options": options or {},
            "update_knowledge_graph": True,
            "emit_events": True,
        }

        response = await self.client.post(
            f"{self.base_url}/extract/document",
            json=request
        )

        return response.json()

# Usage
async def main():
    client = LangExtractClient()
    result = await client.extract_document("/path/to/code.py")
    print(f"Extracted {len(result['enriched_entities'])} entities")

asyncio.run(main())
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

class LangExtractClient {
    constructor(baseUrl = 'http://localhost:8156') {
        this.baseUrl = baseUrl;
    }

    async extractDocument(documentPath, options = {}) {
        const request = {
            document_path: documentPath,
            extraction_options: options,
            update_knowledge_graph: true,
            emit_events: true,
        };

        const response = await axios.post(
            `${this.baseUrl}/extract/document`,
            request
        );

        return response.data;
    }

    async semanticAnalysis(content, context = null, language = null) {
        const params = new URLSearchParams();
        params.append('content', content);
        if (context) params.append('context', context);
        if (language) params.append('language', language);

        const response = await axios.post(
            `${this.baseUrl}/analyze/semantic?${params.toString()}`
        );

        return response.data;
    }
}

// Usage
const client = new LangExtractClient();
client.extractDocument('/path/to/document.md')
    .then(result => {
        console.log(`Extracted ${result.enriched_entities.length} entities`);
    });
```

## Event Integration

The LangExtract service integrates with the Archon DocumentEventBus for real-time processing:

### Event Subscription
The service automatically subscribes to document update events and triggers extraction for relevant files.

### Event Publication
The service publishes the following events:
- `extraction.started` - When extraction begins
- `extraction.completed` - When extraction completes successfully
- `extraction.failed` - When extraction fails
- `semantic.analysis.completed` - When semantic analysis completes
- `knowledge_graph.updated` - When knowledge graph is updated
- `batch.extraction.completed` - When batch extraction completes

## Deployment Notes

### Environment Variables
```bash
# Service Configuration
LANGEXTRACT_SERVICE_PORT=8156
LOG_LEVEL=INFO

# Database Connections
MEMGRAPH_URI=bolt://memgraph:7687
INTELLIGENCE_SERVICE_URL=http://archon-intelligence:8053
BRIDGE_SERVICE_URL=http://archon-bridge:8054

# Feature Flags
EVENT_BUS_ENABLED=true
ENABLE_MULTILINGUAL_EXTRACTION=true
ENABLE_SEMANTIC_ANALYSIS=true

# Performance Tuning
MAX_CONCURRENT_EXTRACTIONS=5
EXTRACTION_TIMEOUT_SECONDS=300
DEFAULT_EXTRACTION_MODE=standard
```

### Docker Deployment
```bash
# Build and run LangExtract service
docker build -t archon-langextract ./services/langextract
docker run -p 8156:8156 -e MEMGRAPH_URI=bolt://host:7687 archon-langextract

# Or use docker-compose
docker-compose up archon-langextract
```

### Health Monitoring
Monitor the `/health` endpoint for service health. The service reports the status of all components including database connections and dependent services.

## Support

For issues and feature requests related to the LangExtract service, please refer to the main Archon project documentation and issue tracking system.
