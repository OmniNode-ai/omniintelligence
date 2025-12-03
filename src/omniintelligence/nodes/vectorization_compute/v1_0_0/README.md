# Vectorization Compute Node

Real implementation of embedding generation for code and documents.

## Features

- **OpenAI API Integration**: Uses `text-embedding-3-small` (or custom model) for high-quality embeddings
- **Automatic Fallback**: Falls back to TF-IDF vectorization when OpenAI API is unavailable
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Configurable**: Supports custom embedding models and dimensions
- **Batch Processing**: Efficient handling of multiple documents
- **Type-Safe**: Full Pydantic model validation for inputs and outputs

## Configuration

### Environment Variables

```bash
# OpenAI API key (optional - falls back to TF-IDF if not set)
export OPENAI_API_KEY=your-api-key-here

# Embedding model (optional - defaults to text-embedding-3-small)
export EMBEDDING_MODEL=text-embedding-3-small
```

### Configuration Model

```python
from compute import ModelVectorizationConfig

config = ModelVectorizationConfig(
    default_model="text-embedding-3-small",  # OpenAI model name
    max_batch_size=100,                      # Max items per batch
    enable_caching=True,                     # Enable result caching
    cache_ttl_seconds=3600,                  # Cache TTL in seconds
    embedding_dimension=1536,                # Output vector size
)
```

## Usage

### Basic Usage

```python
import asyncio
from compute import VectorizationCompute, ModelVectorizationInput

async def main():
    # Create node
    node = VectorizationCompute()

    # Create input
    input_data = ModelVectorizationInput(
        content="Your text content here",
        metadata={"source": "example"}
    )

    # Generate embedding
    result = await node.process(input_data)

    print(f"Success: {result.success}")
    print(f"Model: {result.model_used}")
    print(f"Dimensions: {len(result.embeddings)}")

asyncio.run(main())
```

### With Custom Configuration

```python
config = ModelVectorizationConfig(embedding_dimension=768)
node = VectorizationCompute(config=config)
```

### Batch Processing

```python
documents = ["Text 1", "Text 2", "Text 3"]
results = []

for doc in documents:
    input_data = ModelVectorizationInput(content=doc)
    result = await node.process(input_data)
    results.append(result)
```

## Input/Output Models

### Input

```python
class ModelVectorizationInput(BaseModel):
    content: str                    # Text content to vectorize
    metadata: dict[str, Any]        # Optional metadata
    model_name: str                 # OpenAI model (default: text-embedding-3-small)
    batch_mode: bool                # Batch processing flag (default: False)
```

### Output

```python
class ModelVectorizationOutput(BaseModel):
    success: bool                   # Operation success status
    embeddings: list[float]         # Generated embedding vector
    model_used: str                 # Model that generated embeddings
    metadata: dict[str, Any]        # Result metadata
```

## Embedding Methods

### 1. OpenAI API (Primary)

- Uses OpenAI's embedding API
- Requires `OPENAI_API_KEY` environment variable
- Default model: `text-embedding-3-small` (1536 dimensions)
- Automatic retry with exponential backoff
- Timeout: 30 seconds per request

### 2. TF-IDF Fallback

- Activated when OpenAI API is unavailable or fails
- Deterministic hash-based word frequency vectorization
- Normalized to unit length
- Same dimensionality as configured (default: 1536)
- No external dependencies required

## Error Handling

The node handles various error scenarios:

- **Empty Content**: Returns `success=False` with error metadata
- **OpenAI API Failure**: Automatically falls back to TF-IDF
- **Network Errors**: Retries up to 3 times with exponential backoff
- **Unexpected Errors**: Returns `success=False` with error details

## Testing

```bash
# Run tests
poetry run pytest tests/nodes/test_vectorization_compute.py -v

# Run with coverage
poetry run pytest tests/nodes/test_vectorization_compute.py --cov=src/omniintelligence/nodes/vectorization_compute
```

## Example Usage

See `example_usage.py` for comprehensive examples including:

- Basic usage
- Custom configuration
- Batch processing
- Error handling
- OpenAI API integration

Run examples:

```bash
cd src/omniintelligence/nodes/vectorization_compute/v1_0_0
poetry run python example_usage.py
```

## Performance Considerations

- **OpenAI API**: ~100-500ms per request (network latency)
- **TF-IDF Fallback**: <10ms for typical documents
- **Caching**: Configure `enable_caching=True` for repeated content
- **Batch Processing**: Process multiple documents in parallel for better throughput

## Dependencies

- `httpx`: Async HTTP client for OpenAI API
- `tenacity`: Retry logic with exponential backoff
- `pydantic`: Input/output validation
- `omnibase-core`: ONEX node framework

## Development

### Code Quality

```bash
# Linting
poetry run ruff check src/omniintelligence/nodes/vectorization_compute/

# Type checking
poetry run mypy src/omniintelligence/nodes/vectorization_compute/ --ignore-missing-imports

# Format code
poetry run black src/omniintelligence/nodes/vectorization_compute/
```

## License

Part of OmniIntelligence - ONEX Intelligence Services
