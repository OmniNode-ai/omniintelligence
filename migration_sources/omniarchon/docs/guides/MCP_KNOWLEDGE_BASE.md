# MCP Document Indexing Pipeline - Knowledge Base

**Version**: 1.0.0
**Last Updated**: 2024-12-22
**Status**: Comprehensive Reference

## Overview

This knowledge base consolidates all critical information, best practices, lessons learned, and searchable patterns for the MCP document indexing pipeline. It serves as the definitive reference for development, operations, troubleshooting, and optimization.

## 🔍 Quick Search Index

### Critical Issues
- [Embedding Dimension Mismatch](#embedding-dimension-mismatch) - Primary vectorization failure cause
- [Qdrant Configuration](#qdrant-configuration-patterns) - Vector database setup
- [Service Dependencies](#service-dependency-patterns) - Inter-service communication

### Best Practices
- [Vector Pipeline Optimization](#vector-pipeline-best-practices) - Performance guidelines
- [Error Handling Patterns](#error-handling-best-practices) - Robust error management
- [Monitoring Strategies](#monitoring-best-practices) - Health and performance tracking

### Development Patterns
- [Async Implementation](#async-development-patterns) - Concurrent processing
- [Testing Strategies](#testing-best-practices) - Quality assurance
- [Security Patterns](#security-best-practices) - Safe development

---

## 🚨 Critical Knowledge - Priority 1

### Embedding Dimension Mismatch

**Issue**: Most critical architectural flaw identified in investigation

**Root Cause**:
```python
# services/search/engines/qdrant_adapter.py
embedding_dim: int = 1536  # Expects OpenAI standard dimensions

# services/search/engines/vector_search.py
embedding_model: str = "rjmalagon/gte-qwen2-1.5b-instruct-embed-f16:latest"
# Produces unknown dimensions (likely != 1536)
```

**Impact**: Complete vectorization pipeline failure, no document indexing

**Fix Pattern**:
```python
# Phase 1: Add dimension validation
def validate_embedding_dimensions(embedding: List[float], expected_dim: int) -> bool:
    if len(embedding) != expected_dim:
        logger.error(f"Dimension mismatch: got {len(embedding)}, expected {expected_dim}")
        return False
    return True

# Phase 2: Dynamic dimension detection
async def detect_model_dimensions(self) -> int:
    test_embedding = await self.generate_embeddings(["test"])
    return len(test_embedding[0])

# Phase 3: Auto-configuration
embedding_dim = await vector_engine.detect_model_dimensions()
qdrant_adapter = QdrantAdapter(embedding_dim=embedding_dim)
```

**Lesson Learned**: Always validate dimensional compatibility between embedding models and vector databases during initialization.

### Service Startup Dependencies

**Critical Pattern**: Services must start in specific order

**Correct Startup Sequence**:
1. **Memgraph** (knowledge graph)
2. **Qdrant** (vector database)
3. **Intelligence Service** (8053) - entity extraction
4. **Search Service** (8055) - vectorization
5. **Bridge Service** (8054) - data synchronization
6. **Main Server** (8181) - API coordination

**Failure Pattern**: Starting services out of order causes cascade failures

**Best Practice**:
```yaml
# docker-compose.yml dependency pattern
services:
  search-service:
    depends_on:
      memgraph:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8055/health"]
```

---

## 📊 Performance Knowledge

### Vector Pipeline Best Practices

**High-Performance Patterns**:

```python
# 1. Batch Processing Pattern
async def batch_vectorize_documents(documents: List[Dict], batch_size: int = 50):
    """Process documents in batches for optimal performance"""
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        embeddings = await vector_engine.generate_embeddings([doc['content'] for doc in batch])
        await qdrant_adapter.batch_index_vectors(embeddings, batch)

# 2. Async Concurrent Processing
async def concurrent_document_processing(documents: List[Dict]):
    """Process multiple documents concurrently"""
    tasks = [process_single_document(doc) for doc in documents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]

# 3. Memory-Efficient Streaming
async def stream_large_documents(document_path: str, chunk_size: int = 1000):
    """Stream large documents in chunks"""
    async with aiofiles.open(document_path, 'r') as file:
        chunk = await file.read(chunk_size)
        while chunk:
            yield chunk
            chunk = await file.read(chunk_size)
```

**Performance Targets**:
- Document vectorization: < 500ms per document
- Batch processing: 100+ documents/minute
- Search response: < 100ms for similarity queries
- Memory usage: < 2GB per service under normal load

### Qdrant Configuration Patterns

**Optimal Configuration**:
```python
# High-performance Qdrant setup
qdrant_config = {
    "vectors": {
        "size": embedding_dimensions,  # CRITICAL: Must match model
        "distance": "Cosine",  # Best for semantic similarity
        "hnsw_config": {
            "m": 16,  # Connectivity factor
            "ef_construct": 200,  # Index construction quality
            "full_scan_threshold": 10000  # Fallback threshold
        }
    },
    "optimizers_config": {
        "deleted_threshold": 0.2,
        "vacuum_min_vector_number": 1000,
        "default_segment_number": 2
    }
}

# Memory optimization
QDRANT_MEMORY_LIMITS = {
    "max_segment_size": 100_000,  # Vectors per segment
    "memmap_threshold": 50_000,   # Memory mapping threshold
    "indexing_threshold": 20_000  # Indexing threshold
}
```

**Collection Management Pattern**:
```python
async def create_optimized_collection(collection_name: str, vector_size: int):
    """Create collection with optimal settings"""
    await qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        hnsw_config=HnswConfigDiff(
            m=16,
            ef_construct=200,
            full_scan_threshold=10000,
            max_indexing_threads=4
        ),
        quantization_config=ScalarQuantization(
            type=ScalarType.INT8,
            quantile=0.99,
            always_ram=True
        )
    )
```

---

## 🛡️ Error Handling Best Practices

### Robust Error Patterns

**Comprehensive Error Handling**:
```python
import asyncio
from typing import Optional, Dict, Any
import logging
from enum import Enum

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class PipelineError(Exception):
    def __init__(self, message: str, severity: ErrorSeverity, context: Dict[str, Any]):
        self.message = message
        self.severity = severity
        self.context = context
        super().__init__(message)

async def robust_vectorization_with_retry(
    document: Dict[str, Any],
    max_retries: int = 3,
    backoff_factor: float = 2.0
) -> Optional[Dict[str, Any]]:
    """Vectorize document with exponential backoff retry"""

    for attempt in range(max_retries):
        try:
            # Validate input
            if not document.get('content'):
                raise PipelineError(
                    "Document content is empty",
                    ErrorSeverity.MEDIUM,
                    {"document_id": document.get('id'), "attempt": attempt}
                )

            # Generate embedding
            embedding = await vector_engine.generate_embeddings([document['content']])

            # Validate embedding
            if not embedding or len(embedding[0]) == 0:
                raise PipelineError(
                    "Empty embedding generated",
                    ErrorSeverity.HIGH,
                    {"document_id": document.get('id'), "content_length": len(document['content'])}
                )

            # Index vector
            result = await qdrant_adapter.index_vectors([(document['id'], embedding[0], document)])

            logger.info(f"Successfully vectorized document {document['id']} on attempt {attempt + 1}")
            return result

        except PipelineError as e:
            logger.error(f"Pipeline error: {e.message}", extra=e.context)
            if e.severity == ErrorSeverity.CRITICAL:
                raise  # Don't retry critical errors

        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")

        if attempt < max_retries - 1:
            wait_time = backoff_factor ** attempt
            logger.info(f"Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)

    logger.error(f"Failed to vectorize document {document.get('id')} after {max_retries} attempts")
    return None

# Circuit breaker pattern for service failures
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time < self.timeout:
                raise Exception("Circuit breaker is OPEN")
            else:
                self.state = "HALF_OPEN"

        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"

            raise e
```

### Service Health Patterns

**Comprehensive Health Checking**:
```python
async def comprehensive_health_check() -> Dict[str, Any]:
    """Check health of all pipeline components"""
    health_status = {
        "overall": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check Qdrant connection
    try:
        collections = await qdrant_client.get_collections()
        health_status["services"]["qdrant"] = {
            "status": "healthy",
            "collections_count": len(collections.collections),
            "response_time_ms": measure_response_time()
        }
    except Exception as e:
        health_status["services"]["qdrant"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall"] = "degraded"

    # Check embedding model
    try:
        test_embedding = await vector_engine.generate_embeddings(["health check"])
        health_status["services"]["embedding_model"] = {
            "status": "healthy",
            "model": vector_engine.embedding_model,
            "dimension": len(test_embedding[0]),
            "response_time_ms": measure_response_time()
        }
    except Exception as e:
        health_status["services"]["embedding_model"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall"] = "unhealthy"

    return health_status
```

---

## 🔧 Development Best Practices

### Async Development Patterns

**High-Performance Async Patterns**:
```python
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# 1. Async Context Managers for Resource Management
@asynccontextmanager
async def managed_qdrant_connection() -> AsyncGenerator[QdrantClient, None]:
    """Properly manage Qdrant connections"""
    client = None
    try:
        client = QdrantClient(url="http://qdrant:6333")
        await client.get_collections()  # Verify connection
        yield client
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        raise
    finally:
        if client:
            await client.close()

# 2. Connection Pooling Pattern
class QdrantConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections = asyncio.Queue(maxsize=max_connections)
        self.initialized = False

    async def initialize(self):
        """Initialize connection pool"""
        for _ in range(self.max_connections):
            client = QdrantClient(url="http://qdrant:6333")
            await self.connections.put(client)
        self.initialized = True

    @asynccontextmanager
    async def get_connection(self):
        """Get connection from pool"""
        if not self.initialized:
            await self.initialize()

        client = await self.connections.get()
        try:
            yield client
        finally:
            await self.connections.put(client)

# 3. Async Batch Processing
async def process_documents_efficiently(documents: List[Dict]) -> List[Dict]:
    """Process documents with optimal concurrency"""
    semaphore = asyncio.Semaphore(10)  # Limit concurrent operations

    async def process_single_doc(doc: Dict) -> Dict:
        async with semaphore:
            try:
                return await vectorize_document(doc)
            except Exception as e:
                logger.error(f"Failed to process doc {doc.get('id')}: {e}")
                return {"id": doc.get("id"), "error": str(e)}

    tasks = [process_single_doc(doc) for doc in documents]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter successful results
    successful = [r for r in results if not isinstance(r, Exception) and "error" not in r]
    failed = [r for r in results if isinstance(r, Exception) or "error" in r]

    logger.info(f"Processed {len(successful)} documents successfully, {len(failed)} failed")
    return successful
```

### Testing Best Practices

**Comprehensive Testing Strategy**:
```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

# 1. Integration Testing with Real Services
@pytest.mark.asyncio
async def test_document_vectorization_integration():
    """Test complete vectorization pipeline"""
    # Setup test document
    test_doc = {
        "id": "test-doc-123",
        "content": "This is a test document for vectorization",
        "metadata": {"source": "test", "type": "text"}
    }

    # Test vectorization
    result = await vectorize_document(test_doc)

    # Assertions
    assert result is not None
    assert "embedding" in result
    assert len(result["embedding"]) > 0
    assert result["id"] == test_doc["id"]

    # Verify in Qdrant
    async with managed_qdrant_connection() as client:
        points = await client.scroll(
            collection_name="test_collection",
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="id", match=models.MatchValue(value="test-doc-123"))]
            )
        )
        assert len(points[0]) == 1

# 2. Property-Based Testing
@given(
    content=st.text(min_size=10, max_size=1000),
    doc_id=st.text(min_size=1, max_size=50)
)
@pytest.mark.asyncio
async def test_vectorization_properties(content: str, doc_id: str):
    """Test vectorization with various inputs"""
    test_doc = {"id": doc_id, "content": content}

    with patch('vector_engine.generate_embeddings') as mock_embeddings:
        mock_embeddings.return_value = [[0.1] * 1536]  # Mock embedding

        result = await vectorize_document(test_doc)

        # Properties that should always hold
        assert result["id"] == doc_id
        assert len(result["embedding"]) == 1536
        mock_embeddings.assert_called_once_with([content])

# 3. Performance Testing
@pytest.mark.asyncio
async def test_batch_processing_performance():
    """Test batch processing performance requirements"""
    import time

    # Create test documents
    test_docs = [
        {"id": f"doc-{i}", "content": f"Test content {i}" * 10}
        for i in range(100)
    ]

    start_time = time.time()
    results = await process_documents_efficiently(test_docs)
    end_time = time.time()

    # Performance assertions
    processing_time = end_time - start_time
    assert processing_time < 60.0  # Should process 100 docs in under 60 seconds
    assert len(results) >= 95  # At least 95% success rate

    # Calculate throughput
    throughput = len(results) / processing_time
    assert throughput >= 1.5  # At least 1.5 documents per second

# 4. Error Simulation Testing
@pytest.mark.asyncio
async def test_error_handling_resilience():
    """Test system resilience to various errors"""

    # Test embedding service failure
    with patch('vector_engine.generate_embeddings', side_effect=Exception("Embedding failed")):
        result = await robust_vectorization_with_retry({"id": "test", "content": "test"})
        assert result is None  # Should handle gracefully

    # Test Qdrant connection failure
    with patch('qdrant_adapter.index_vectors', side_effect=ConnectionError("Qdrant unavailable")):
        result = await robust_vectorization_with_retry({"id": "test", "content": "test"})
        assert result is None  # Should handle gracefully

# 5. Load Testing
@pytest.mark.asyncio
@pytest.mark.load_test
async def test_concurrent_load():
    """Test system under concurrent load"""
    concurrent_tasks = 50

    tasks = [
        vectorize_document({"id": f"load-test-{i}", "content": f"Load test content {i}"})
        for i in range(concurrent_tasks)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check success rate under load
    successful = [r for r in results if not isinstance(r, Exception)]
    success_rate = len(successful) / len(results)

    assert success_rate >= 0.9  # 90% success rate under load
```

---

## 🔍 Monitoring Best Practices

### Comprehensive Monitoring Strategy

**Key Metrics to Track**:
```python
import time
import psutil
from prometheus_client import Counter, Histogram, Gauge
from functools import wraps

# Define metrics
VECTORIZATION_REQUESTS = Counter('vectorization_requests_total', 'Total vectorization requests')
VECTORIZATION_DURATION = Histogram('vectorization_duration_seconds', 'Vectorization duration')
VECTORIZATION_ERRORS = Counter('vectorization_errors_total', 'Vectorization errors', ['error_type'])
ACTIVE_CONNECTIONS = Gauge('active_qdrant_connections', 'Active Qdrant connections')
MEMORY_USAGE = Gauge('memory_usage_bytes', 'Memory usage in bytes')
DOCUMENT_QUEUE_SIZE = Gauge('document_queue_size', 'Documents waiting for processing')

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        VECTORIZATION_REQUESTS.inc()

        try:
            result = await func(*args, **kwargs)
            VECTORIZATION_DURATION.observe(time.time() - start_time)
            return result
        except Exception as e:
            VECTORIZATION_ERRORS.labels(error_type=type(e).__name__).inc()
            raise
    return wrapper

# System resource monitoring
async def update_system_metrics():
    """Update system resource metrics"""
    while True:
        # Memory usage
        memory = psutil.virtual_memory()
        MEMORY_USAGE.set(memory.used)

        # Active connections (mock - replace with actual Qdrant connection count)
        # ACTIVE_CONNECTIONS.set(qdrant_pool.active_connections)

        await asyncio.sleep(30)  # Update every 30 seconds

# Health check endpoint with detailed metrics
async def detailed_health_check():
    """Comprehensive health check with metrics"""
    return {
        "status": "healthy",
        "metrics": {
            "memory_usage_mb": psutil.virtual_memory().used / 1024 / 1024,
            "cpu_percent": psutil.cpu_percent(),
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "active_connections": 0,  # Replace with actual count
            "queue_size": 0,  # Replace with actual queue size
            "last_error": None,  # Track last error
            "uptime_seconds": time.time() - start_time
        },
        "dependencies": {
            "qdrant": await check_qdrant_health(),
            "ollama": await check_ollama_health(),
            "memgraph": await check_memgraph_health()
        }
    }
```

### Alerting Patterns

**Critical Alert Conditions**:
```python
# Alert thresholds
ALERT_THRESHOLDS = {
    "error_rate": 0.05,          # 5% error rate
    "response_time_p95": 2.0,    # 2 second 95th percentile
    "memory_usage": 0.85,        # 85% memory usage
    "disk_usage": 0.90,          # 90% disk usage
    "queue_size": 1000,          # 1000 documents in queue
    "failed_health_checks": 3    # 3 consecutive failed health checks
}

async def check_alert_conditions():
    """Check if any alert conditions are met"""
    alerts = []

    # Error rate check
    error_rate = calculate_error_rate()
    if error_rate > ALERT_THRESHOLDS["error_rate"]:
        alerts.append({
            "severity": "high",
            "message": f"High error rate: {error_rate:.2%}",
            "metric": "error_rate",
            "value": error_rate
        })

    # Memory usage check
    memory_percent = psutil.virtual_memory().percent / 100
    if memory_percent > ALERT_THRESHOLDS["memory_usage"]:
        alerts.append({
            "severity": "medium",
            "message": f"High memory usage: {memory_percent:.1%}",
            "metric": "memory_usage",
            "value": memory_percent
        })

    return alerts
```

---

## 🔐 Security Best Practices

### Security Patterns

**Input Validation & Sanitization**:
```python
import re
from typing import Dict, Any
from html import escape
import bleach

def validate_document_input(document: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize document input"""

    # Required fields validation
    required_fields = ['id', 'content']
    for field in required_fields:
        if field not in document:
            raise ValueError(f"Missing required field: {field}")

    # ID validation (alphanumeric, dashes, underscores only)
    if not re.match(r'^[a-zA-Z0-9_-]+$', document['id']):
        raise ValueError("Document ID contains invalid characters")

    # Content length validation
    if len(document['content']) > 100000:  # 100KB limit
        raise ValueError("Document content too large")

    # Content sanitization
    sanitized_content = bleach.clean(
        document['content'],
        tags=['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
        strip=True
    )

    return {
        **document,
        'content': sanitized_content,
        'id': escape(document['id'])
    }

# Rate limiting pattern
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]

        # Check if under limit
        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            return True

        return False

# Authentication middleware
async def authenticate_request(request):
    """Authenticate API requests"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = auth_header[7:]  # Remove 'Bearer ' prefix
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return extract_user_from_token(token)
```

### Data Protection Patterns

**Sensitive Data Handling**:
```python
import hashlib
from cryptography.fernet import Fernet
import os

class DataProtector:
    def __init__(self):
        self.encryption_key = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
        self.cipher_suite = Fernet(self.encryption_key)

    def hash_document_id(self, doc_id: str) -> str:
        """Hash document ID for privacy"""
        return hashlib.sha256(doc_id.encode()).hexdigest()[:16]

    def encrypt_sensitive_content(self, content: str) -> str:
        """Encrypt sensitive content"""
        return self.cipher_suite.encrypt(content.encode()).decode()

    def decrypt_sensitive_content(self, encrypted_content: str) -> str:
        """Decrypt sensitive content"""
        return self.cipher_suite.decrypt(encrypted_content.encode()).decode()

    def scrub_pii_from_logs(self, log_message: str) -> str:
        """Remove PII from log messages"""
        # Remove email addresses
        log_message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', log_message)

        # Remove phone numbers
        log_message = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]', log_message)

        # Remove credit card numbers
        log_message = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD]', log_message)

        return log_message
```

---

## 📚 Common Patterns Library

### Document Processing Patterns

**Text Preprocessing Pipeline**:
```python
import re
from typing import List, Dict
import nltk
from textstat import flesch_reading_ease

class DocumentProcessor:
    def __init__(self):
        # Download required NLTK data
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
        except:
            pass

    def preprocess_text(self, text: str) -> str:
        """Comprehensive text preprocessing"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:-]', '', text)

        # Normalize quotes
        text = re.sub(r'["""]', '"', text)
        text = re.sub(r'[''']', "'", text)

        return text

    def extract_metadata(self, text: str) -> Dict[str, Any]:
        """Extract useful metadata from text"""
        return {
            'character_count': len(text),
            'word_count': len(text.split()),
            'sentence_count': len(nltk.sent_tokenize(text)),
            'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
            'reading_ease': flesch_reading_ease(text),
            'language': 'en',  # Simple assumption
            'has_code': bool(re.search(r'```|`[^`]+`|\bclass\b|\bdef\b|\bfunction\b', text))
        }

    def chunk_document(self, text: str, max_chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """Split document into overlapping chunks"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), max_chunk_size - overlap):
            chunk_words = words[i:i + max_chunk_size]
            chunks.append(' '.join(chunk_words))

            if i + max_chunk_size >= len(words):
                break

        return chunks
```

### Search Optimization Patterns

**Advanced Query Processing**:
```python
from typing import List, Dict, Optional
import re

class QueryOptimizer:
    def __init__(self):
        self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

    def optimize_search_query(self, query: str) -> Dict[str, Any]:
        """Optimize search query for better results"""

        # Extract quoted phrases
        quoted_phrases = re.findall(r'"([^"]*)"', query)
        query_without_quotes = re.sub(r'"[^"]*"', '', query)

        # Extract individual terms
        terms = [term.lower().strip() for term in query_without_quotes.split() if term.strip()]

        # Remove stop words
        meaningful_terms = [term for term in terms if term not in self.stop_words and len(term) > 2]

        # Identify potential technical terms
        technical_terms = [term for term in meaningful_terms if self._is_technical_term(term)]

        return {
            'original_query': query,
            'quoted_phrases': quoted_phrases,
            'meaningful_terms': meaningful_terms,
            'technical_terms': technical_terms,
            'optimized_query': self._build_optimized_query(quoted_phrases, meaningful_terms, technical_terms)
        }

    def _is_technical_term(self, term: str) -> bool:
        """Identify technical terms that should be weighted higher"""
        technical_patterns = [
            r'.*api.*', r'.*config.*', r'.*auth.*', r'.*db.*', r'.*sql.*',
            r'.*http.*', r'.*json.*', r'.*xml.*', r'.*rest.*', r'.*graph.*'
        ]
        return any(re.match(pattern, term, re.IGNORECASE) for pattern in technical_patterns)

    def _build_optimized_query(self, phrases: List[str], terms: List[str], technical_terms: List[str]) -> str:
        """Build optimized query string"""
        parts = []

        # Quoted phrases (highest priority)
        for phrase in phrases:
            parts.append(f'"{phrase}"')

        # Technical terms (high priority)
        for term in technical_terms:
            parts.append(f'{term}^2.0')  # Boost technical terms

        # Other meaningful terms
        regular_terms = [term for term in terms if term not in technical_terms]
        parts.extend(regular_terms)

        return ' '.join(parts)
```

---

## 🎯 Troubleshooting Quick Reference

### Common Issues Lookup Table

| Issue | Symptoms | Quick Fix | Root Cause |
|-------|----------|-----------|------------|
| **Dimension Mismatch** | `ValueError: vector dimension mismatch` | Check embedding model dimensions | Model/Qdrant config mismatch |
| **Empty Embeddings** | Documents not searchable | Verify Ollama model running | Embedding service failure |
| **Service Timeout** | 500 errors, no response | Check service health endpoints | Dependency service down |
| **Memory Error** | OOM errors, slow response | Reduce batch size | Insufficient resources |
| **Auth Failure** | 401 unauthorized | Check API tokens | Invalid credentials |
| **Connection Error** | Cannot connect to Qdrant | Verify Qdrant container | Network/port issues |

### Emergency Commands

```bash
# Quick health check all services
curl -s http://localhost:8053/health | jq .  # Intelligence
curl -s http://localhost:8055/health | jq .  # Search
curl -s http://localhost:8054/health | jq .  # Bridge

# Check Qdrant collections
curl -s http://localhost:6333/collections | jq .

# Test embedding generation
curl -X POST http://localhost:8055/vectorize/test \
  -H "Content-Type: application/json" \
  -d '{"content": "test document"}'

# View service logs
docker compose logs -f intelligence-service
docker compose logs -f search-service
docker compose logs -f bridge-service

# Restart specific service
docker compose restart search-service

# Full system restart
docker compose down && docker compose up -d
```

---

## 📈 Performance Optimization Checklists

### Pre-Production Checklist

**System Configuration**:
- [ ] Embedding model dimensions match Qdrant configuration
- [ ] Qdrant HNSW parameters optimized for dataset size
- [ ] Connection pooling implemented for all services
- [ ] Resource limits set appropriately
- [ ] Health checks configured with proper timeouts
- [ ] Error handling and retry logic implemented
- [ ] Monitoring and alerting configured
- [ ] Security authentication enabled
- [ ] Rate limiting configured
- [ ] Data backup strategy in place

**Performance Validation**:
- [ ] Document vectorization < 500ms per document
- [ ] Batch processing > 100 docs/minute
- [ ] Search queries < 100ms response time
- [ ] Memory usage stable under load
- [ ] CPU usage < 80% under normal load
- [ ] Error rate < 1% under normal conditions
- [ ] 95th percentile response time < 2 seconds
- [ ] System recovers gracefully from failures

### Production Monitoring Checklist

**Daily Checks**:
- [ ] All services healthy and responding
- [ ] Error rates within acceptable limits
- [ ] Response times meeting SLA requirements
- [ ] Resource usage trending normally
- [ ] No critical alerts triggered
- [ ] Backup verification successful
- [ ] Security logs reviewed

**Weekly Reviews**:
- [ ] Performance trend analysis
- [ ] Capacity planning review
- [ ] Security audit logs
- [ ] System optimization opportunities
- [ ] Dependency updates available
- [ ] Documentation updates needed

---

## 🧠 Lessons Learned & Best Practices Summary

### Critical Lessons

1. **Always Validate Dimensions**: The most critical issue was embedding dimension mismatch - always validate model output dimensions match storage expectations.

2. **Service Dependencies Matter**: Proper startup ordering and health checks prevent cascade failures.

3. **Error Handling is Essential**: Robust error handling with retry logic and circuit breakers prevents system instability.

4. **Monitor Everything**: Comprehensive monitoring catches issues before they become critical.

5. **Security from Start**: Input validation, authentication, and rate limiting should be built in from the beginning.

### Golden Rules

1. **Fail Fast, Fail Explicitly**: Detect problems early and provide clear error messages.
2. **Graceful Degradation**: System should continue operating even when components fail.
3. **Idempotent Operations**: Operations should be safe to retry.
4. **Resource Management**: Always clean up connections and resources properly.
5. **Documentation as Code**: Keep documentation synchronized with implementation.

### Anti-Patterns to Avoid

1. **Silent Failures**: Never ignore exceptions or errors without proper handling.
2. **Hard-coded Configuration**: Always use environment variables or configuration files.
3. **Blocking Operations**: Use async patterns for all I/O operations.
4. **Missing Validation**: Always validate inputs and intermediate results.
5. **Tight Coupling**: Services should be loosely coupled with clear interfaces.

---

**End of Knowledge Base**

*This knowledge base serves as the definitive reference for MCP document indexing pipeline development, operations, and optimization. It should be updated regularly as new patterns and lessons are discovered.*

**Version History**:
- v1.0.0 (2024-12-22): Initial comprehensive knowledge base with investigation findings
