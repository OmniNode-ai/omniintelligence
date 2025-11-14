# Haystack Adapter Effect Node

## Overview

The **Haystack Adapter Effect Node** provides a standardized ONEX interface to Haystack 2.x RAG pipelines. This adapter enables A/B testing between Haystack's RAG implementation and the custom OmniIntelligence RAG orchestration.

## Purpose

- **Feature Flag Testing**: Enable comparison between Haystack and custom RAG implementations
- **Standardized Interface**: Consistent ONEX contract-based interface regardless of RAG provider
- **Hybrid Orchestration**: Use Haystack for RAG while maintaining custom intelligence features (pattern learning, quality assessment, etc.)

## Architecture

### Node Type
- **Type**: Effect Node
- **Version**: 1.0.0
- **Base Class**: `NodeOmniAgentEffect`

### Key Features
- Document ingestion and indexing via Haystack
- Semantic search with Qdrant vector store
- RAG query with retrieval + generation
- Support for hybrid (semantic + keyword) search
- Configurable embedding and LLM models

## Operations

### 1. Index Document
Index a document into Haystack's document store.

```python
input_data = ModelHaystackAdapterInput(
    operation="index_document",
    document_content="Your document content here...",
    document_id="doc_123",
    metadata={
        "file_path": "src/main.py",
        "language": "python",
        "author": "dev@example.com",
    },
    correlation_id="corr_456",
)
```

### 2. Query (RAG)
Execute full RAG pipeline with retrieval and generation.

```python
input_data = ModelHaystackAdapterInput(
    operation="query",
    query="What are the main classes in this codebase?",
    top_k=10,
    filters={"language": "python"},
    generation_params={
        "temperature": 0.7,
        "max_tokens": 2000,
    },
    correlation_id="corr_789",
)
```

### 3. Search
Semantic search without generation (retrieval only).

```python
input_data = ModelHaystackAdapterInput(
    operation="search",
    query="authentication implementation",
    top_k=5,
    correlation_id="corr_101",
)
```

### 4. Delete Document
Remove a document from the document store.

```python
input_data = ModelHaystackAdapterInput(
    operation="delete_document",
    document_id="doc_123",
    correlation_id="corr_102",
)
```

## Configuration

### Required Configuration

```python
config = ModelHaystackAdapterConfig(
    # Qdrant configuration
    qdrant_url="http://localhost:6333",
    collection_name="haystack_documents",

    # Embedding model
    embedding_model="text-embedding-3-small",

    # LLM configuration
    llm_model="gpt-4",
    llm_temperature=0.7,
    llm_max_tokens=2000,

    # Retrieval settings
    default_top_k=10,
    similarity_threshold=0.7,

    # Feature flags
    enable_hybrid_search=True,
    enable_caching=True,
    cache_ttl_seconds=3600,
)
```

### Environment Variables

Required environment variables:
```bash
OPENAI_API_KEY=your_openai_api_key
QDRANT_URL=http://localhost:6333
```

## Integration with Intelligence Orchestrator

### Feature Flag Configuration

The orchestrator supports toggling between RAG providers:

```python
orchestrator_config = ModelOrchestratorConfig(
    # Standard config...
    max_concurrent_workflows=10,
    workflow_timeout_seconds=300,

    # RAG provider selection
    rag_provider=EnumRAGProvider.HAYSTACK,  # or CUSTOM
    enable_haystack_rag=True,
)
```

### Using Haystack RAG Workflow

```python
orchestrator_input = ModelOrchestratorInput(
    operation_type=EnumOperationType.HAYSTACK_RAG,
    entity_id="query_123",
    payload={
        "operation": "query",
        "query": "How does authentication work?",
        "top_k": 10,
    },
    correlation_id="corr_456",
)

result = await orchestrator.process(orchestrator_input)
```

## Comparison: Haystack vs Custom RAG

### Haystack RAG Workflow
**Best for:**
- Simple document Q&A
- Standard RAG use cases
- Quick prototyping
- Leveraging Haystack ecosystem

**Limitations:**
- No pattern learning
- No quality assessment
- No relationship detection
- No custom intelligence features

### Custom RAG Orchestration
**Best for:**
- Complex intelligence operations
- Pattern detection and learning
- Quality assessment
- Knowledge graph relationships
- Domain-specific customization

**Features:**
- 4-phase pattern learning
- ONEX compliance checking
- Entity extraction
- Relationship detection
- Semantic analysis

## A/B Testing Strategy

### 1. Enable Both Providers

```python
# Custom RAG for document ingestion
await orchestrator.process(ModelOrchestratorInput(
    operation_type=EnumOperationType.DOCUMENT_INGESTION,
    entity_id="doc_123",
    payload={"document_content": "..."},
    correlation_id="corr_001",
))

# Haystack RAG for querying
await orchestrator.process(ModelOrchestratorInput(
    operation_type=EnumOperationType.HAYSTACK_RAG,
    entity_id="query_123",
    payload={
        "operation": "query",
        "query": "...",
    },
    correlation_id="corr_002",
))
```

### 2. Compare Metrics

Both workflows emit metrics for comparison:
- Latency (retrieval, generation, total)
- Retrieval quality (number of documents, relevance scores)
- Answer quality (user feedback, downstream success)

### 3. Feature Flag Toggle

Use the `rag_provider` config to switch between providers:

```python
# Via environment variable
RAG_PROVIDER=HAYSTACK

# Via configuration
config.rag_provider = EnumRAGProvider.HAYSTACK
```

## Performance Characteristics

### Haystack Adapter
- **Index latency**: ~50-200ms per document
- **Query latency**: ~1-5s (retrieval + generation)
- **Search latency**: ~100-500ms (retrieval only)
- **Throughput**: ~20 queries/second
- **Memory**: ~2GB

### Comparison with Custom RAG
| Metric | Haystack | Custom |
|--------|----------|--------|
| Query Latency | 1-5s | 2-8s |
| Index Latency | 50-200ms | 100-400ms |
| Customization | Low | High |
| Intelligence Features | None | Full |
| Complexity | Low | High |

## Error Handling

The adapter implements comprehensive error handling:

### Retry Logic
- **Index failures**: 3 retries with exponential backoff
- **Query failures**: 2 retries with exponential backoff
- **Connection errors**: 5 retries with exponential backoff

### Fallback Strategies
- **Generation failure**: Falls back to retrieval-only mode
- **Connection timeout**: Returns error with partial results
- **Invalid input**: Immediate validation error

## Monitoring

### Metrics Tracked
- `workflow_duration_ms`
- `haystack_latency_ms`
- `retrieval_latency_ms`
- `generation_latency_ms`
- `documents_retrieved`
- `success_rate`
- `error_rate`

### Health Checks
- Haystack pipeline status
- Qdrant connection status
- OpenAI API availability
- Document store statistics

## Dependencies

### Required Packages
```toml
haystack-ai>=2.0.0
qdrant-haystack>=4.0.0
qdrant-client>=1.15.1
openai>=1.71.0
llama-index>=0.9.0
```

### External Services
- Qdrant vector database
- OpenAI API (or compatible embedding/LLM service)

## Development

### Running Tests
```bash
pytest src/omniintelligence/nodes/haystack_adapter_effect/
```

### Local Setup
```bash
# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Set environment variables
export OPENAI_API_KEY=your_key
export QDRANT_URL=http://localhost:6333

# Run node tests
pytest -v
```

## Migration Path

### Transitioning from Custom to Haystack
1. Enable Haystack adapter alongside custom RAG
2. Route a percentage of queries to Haystack
3. Compare metrics and quality
4. Gradually increase Haystack traffic
5. Maintain custom RAG for complex intelligence features

### Hybrid Approach (Recommended)
- **Haystack**: Simple Q&A, document retrieval
- **Custom RAG**: Pattern learning, quality assessment, relationships

## Troubleshooting

### Common Issues

**Issue**: Documents not being indexed
- Check Qdrant connection
- Verify collection exists
- Check OpenAI API key

**Issue**: Poor retrieval quality
- Adjust `similarity_threshold`
- Increase `top_k`
- Enable hybrid search
- Check document metadata filters

**Issue**: High latency
- Enable caching
- Reduce `top_k`
- Use smaller embedding model
- Check network latency to Qdrant/OpenAI

## Future Enhancements

- [ ] Support for custom embedding models (local)
- [ ] Support for custom LLMs (Ollama, local models)
- [ ] Advanced ranking strategies
- [ ] Query expansion and rewriting
- [ ] Multi-modal document support
- [ ] Streaming generation responses

## References

- [Haystack Documentation](https://docs.haystack.deepset.ai/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [ONEX Architecture Guide](../../../../docs/ONEX_ARCHITECTURE.md)
- [OmniIntelligence Migration Guide](../../../../docs/migrations/omniarchon_to_omniintelligence.md)
