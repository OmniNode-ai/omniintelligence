"""Integration test configuration for RAG pipeline tests.

This configuration allows real database connections for integration testing
while maintaining safety guards to prevent production data access.
"""

import os
from unittest.mock import patch

import pytest

# Set integration test environment
os.environ["TESTING"] = "true"
os.environ["REAL_INTEGRATION_TESTS"] = "true"
# Override any existing database credentials to use local Supabase
os.environ["SUPABASE_URL"] = "http://localhost:54321"
os.environ["SUPABASE_SERVICE_KEY"] = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
    "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
)
# Set required port environment variables for ServiceDiscovery
os.environ.setdefault("ARCHON_SERVER_PORT", "8181")
os.environ.setdefault("ARCHON_AGENTS_PORT", "8052")


async def create_mock_embedding_batch_result(texts, **kwargs):
    """Create a mock EmbeddingBatchResult with dummy embeddings for homelab testing."""
    from src.server.services.embeddings.embedding_service import EmbeddingBatchResult

    result = EmbeddingBatchResult()

    # Create dummy 1536-dimensional embeddings (OpenAI's text-embedding-3-small size)
    for i, text in enumerate(texts):
        # Generate deterministic dummy embedding based on text hash for reproducibility
        text_hash = hash(text) % 1000  # Keep it reasonable
        dummy_embedding = [float(text_hash + j) / 1536 for j in range(1536)]
        result.add_success(dummy_embedding, text)

    return result


@pytest.fixture(autouse=True, scope="session")
def integration_test_environment():
    """Set up integration test environment without database mocking."""
    print(
        "\n🔬 Integration test environment - homelab mode with local Supabase and mock embeddings"
    )

    # Verify we're in safe test environment
    if os.getenv("TESTING") != "true":
        raise OSError("TESTING environment must be 'true' for integration tests")

    # Check database URL is safe (not production)
    supabase_url = os.getenv("SUPABASE_URL", "")
    if "prod" in supabase_url.lower() and "test" not in supabase_url.lower():
        raise OSError(f"Database URL appears to be production: {supabase_url}")

    # Mock embedding service for homelab testing - no external API dependencies!
    with patch(
        "src.server.services.embeddings.embedding_service.create_embeddings_batch"
    ) as mock_embeddings:
        # Configure the async mock to return dummy embeddings
        mock_embeddings.side_effect = create_mock_embedding_batch_result

        print("🏠 Homelab mode: Mocking OpenAI embeddings with local dummy vectors")

        yield

    print("\n✅ Integration test environment teardown complete")
