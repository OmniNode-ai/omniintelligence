"""
RAG Integration Test Configuration

Test configuration and environment setup for RAG integration tests.
Ensures proper test environment configuration and safety checks.
"""

import os

import pytest


def setup_test_environment() -> dict[str, str]:
    """
    Set up test environment variables for RAG integration tests.
    Returns the environment configuration used.
    """
    test_env = {
        # CRITICAL: Mark as testing environment
        "TESTING": "true",
        # Use test database (NEVER production!)
        "SUPABASE_URL": os.getenv("SUPABASE_TEST_URL", "http://test.supabase.co"),
        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_TEST_KEY", "test_service_key"),
        # Use test API keys (can be dummy values for some tests)
        "OPENAI_API_KEY": os.getenv("OPENAI_TEST_KEY", "test_openai_key"),
        # RAG strategy settings for testing
        "USE_HYBRID_SEARCH": "true",  # Enable for integration testing
        "USE_RERANKING": "false",  # Disable to avoid external API calls
        "USE_AGENTIC_RAG": "true",  # Enable for code example testing
        # Test-specific settings
        "DOCUMENT_STORAGE_BATCH_SIZE": "10",
        "DELETE_BATCH_SIZE": "25",
        "ENABLE_PARALLEL_BATCHES": "false",  # Simpler for testing
        # Disable external services that aren't needed for core testing
        "LOGFIRE_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
    }

    # Apply test environment
    os.environ.update(test_env)

    return test_env


class TestEnvironmentValidator:
    """Validates test environment setup"""

    @staticmethod
    def validate_configuration() -> bool:
        """
        Validate that test configuration is properly set up.
        Returns True if valid, raises exception if invalid.
        """
        # Check critical safety variables
        if os.getenv("TESTING") != "true":
            raise OSError("TESTING environment variable must be 'true'")

        # Validate database URL is for testing
        supabase_url = os.getenv("SUPABASE_URL", "")
        if not supabase_url or (
            "prod" in supabase_url.lower() and "test" not in supabase_url.lower()
        ):
            raise OSError(f"Invalid test database URL: {supabase_url}")

        # Check required variables exist
        required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise OSError(f"Missing required environment variables: {missing_vars}")

        return True

    @staticmethod
    def print_test_config() -> None:
        """Print test configuration for debugging"""
        print("\n🔧 RAG Test Configuration:")
        print(f"  TESTING: {os.getenv('TESTING')}")
        print(f"  SUPABASE_URL: {os.getenv('SUPABASE_URL', '')[:50]}...")
        print(f"  USE_HYBRID_SEARCH: {os.getenv('USE_HYBRID_SEARCH')}")
        print(f"  USE_AGENTIC_RAG: {os.getenv('USE_AGENTIC_RAG')}")
        print(f"  USE_RERANKING: {os.getenv('USE_RERANKING')}")


# Pytest configuration for RAG tests
@pytest.fixture(scope="session", autouse=True)
def setup_rag_test_environment():
    """Session-wide setup for RAG integration tests"""
    print("\n🚀 Setting up RAG test environment...")

    # Set up test environment
    test_env = setup_test_environment()

    # Validate configuration
    TestEnvironmentValidator.validate_configuration()
    TestEnvironmentValidator.print_test_config()

    yield test_env

    print("\n✅ RAG test environment teardown complete")


@pytest.fixture
def test_settings():
    """Provide test-specific settings"""
    return {
        "batch_size": 5,
        "test_document_count": 3,
        "performance_timeout": 30.0,
        "cleanup_batch_size": 50,
    }


# Test markers for different test categories
pytest.mark.integration = pytest.mark.slowtest = pytest.mark.slow  # Integration tests
pytest.mark.performance = pytest.mark.performance  # Performance benchmarks
pytest.mark.safety = pytest.mark.safety  # Safety and guard tests
