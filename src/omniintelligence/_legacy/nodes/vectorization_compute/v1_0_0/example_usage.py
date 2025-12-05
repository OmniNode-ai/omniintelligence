"""
Example usage of the Vectorization Compute Node

Demonstrates how to use the vectorization node for embedding generation.
"""

import asyncio
import os

from compute import (
    ModelVectorizationConfig,
    ModelVectorizationInput,
    VectorizationCompute,
)


async def example_basic_usage() -> None:
    """Basic usage example with default configuration."""
    print("=== Basic Usage Example ===\n")

    # Create compute node
    node = VectorizationCompute()

    # Create input
    input_data = ModelVectorizationInput(
        content="This is a sample text for embedding generation.",
        metadata={"source": "example", "document_id": "doc-001"},
    )

    # Process
    result = await node.process(input_data)

    print(f"Success: {result.success}")
    print(f"Model Used: {result.model_used}")
    print(f"Embedding Dimensions: {len(result.embeddings)}")
    print(f"Metadata: {result.metadata}")
    print(f"First 5 values: {result.embeddings[:5]}\n")


async def example_with_custom_config() -> None:
    """Example with custom configuration."""
    print("=== Custom Configuration Example ===\n")

    # Create custom config
    config = ModelVectorizationConfig(
        default_model="text-embedding-3-small",
        max_batch_size=50,
        enable_caching=True,
        cache_ttl_seconds=1800,
        embedding_dimension=1536,
    )

    # Create node with config
    node = VectorizationCompute(config=config)

    # Process code content
    code_content = """
    def hello_world():
        print("Hello, World!")
        return True
    """

    input_data = ModelVectorizationInput(
        content=code_content,
        metadata={"type": "python_code", "function": "hello_world"},
    )

    result = await node.process(input_data)

    print(f"Success: {result.success}")
    print(f"Model Used: {result.model_used}")
    print(f"Embedding Dimensions: {len(result.embeddings)}")
    print(f"Method: {result.metadata.get('method')}\n")


async def example_batch_processing() -> None:
    """Example of processing multiple documents."""
    print("=== Batch Processing Example ===\n")

    node = VectorizationCompute()

    documents = [
        "Machine learning is a subset of artificial intelligence.",
        "Python is a popular programming language for data science.",
        "Neural networks are inspired by biological neurons.",
        "Deep learning requires large amounts of training data.",
    ]

    results = []
    for i, doc in enumerate(documents):
        input_data = ModelVectorizationInput(
            content=doc,
            metadata={"doc_id": f"doc-{i:03d}"},
        )
        result = await node.process(input_data)
        results.append(result)

    print(f"Processed {len(results)} documents")
    for i, result in enumerate(results):
        print(
            f"Doc {i}: {result.model_used}, "
            f"{len(result.embeddings)} dims, "
            f"success={result.success}"
        )
    print()


async def example_error_handling() -> None:
    """Example demonstrating error handling."""
    print("=== Error Handling Example ===\n")

    node = VectorizationCompute()

    # Test with empty content
    empty_input = ModelVectorizationInput(content="   ")
    result = await node.process(empty_input)

    print(f"Empty content - Success: {result.success}")
    print(f"Empty content - Error: {result.metadata.get('error')}\n")


async def example_with_openai_api() -> None:
    """Example using OpenAI API (requires OPENAI_API_KEY environment variable)."""
    print("=== OpenAI API Example ===\n")

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set - will use TF-IDF fallback")
        print("To use OpenAI API, set: export OPENAI_API_KEY=your-key-here\n")
    else:
        print("✓ OPENAI_API_KEY found - using OpenAI embeddings\n")

    node = VectorizationCompute()

    input_data = ModelVectorizationInput(
        content="Artificial intelligence is transforming software development.",
    )

    result = await node.process(input_data)

    print(f"Success: {result.success}")
    print(f"Model Used: {result.model_used}")
    print(f"Method: {result.metadata.get('method')}")
    print(f"Embedding Dimensions: {len(result.embeddings)}")

    if result.metadata.get("note"):
        print(f"Note: {result.metadata['note']}")
    print()


async def main() -> None:
    """Run all examples."""
    print("Vectorization Compute Node - Usage Examples")
    print("=" * 50 + "\n")

    await example_basic_usage()
    await example_with_custom_config()
    await example_batch_processing()
    await example_error_handling()
    await example_with_openai_api()

    print("=" * 50)
    print("✓ All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
