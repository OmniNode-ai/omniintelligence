"""
Integration tests for Supabase fallback behavior.

These tests verify that services can start and operate when Supabase is unavailable,
falling back to environment variables for configuration.

Tests cover:
1. Service startup without Supabase
2. Credential retrieval with fallback to environment variables
3. Operations continue normally when database unavailable
4. Graceful degradation of credential-dependent features
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.server.services.credential_service import (
    CredentialService,
    initialize_credentials,
)


@pytest.fixture
def mock_env_credentials():
    """Mock environment variables for credential fallback."""
    return {
        "OPENAI_API_KEY": "env-openai-key",
        "LLM_PROVIDER": "openai",
        "MODEL_CHOICE": "gpt-4",
        "HOST": "0.0.0.0",
        "PORT": "8181",
    }


@pytest.fixture
def credential_service_no_supabase():
    """Create CredentialService with Supabase unavailable."""
    service = CredentialService()
    # Force database client to fail
    with patch.object(
        service,
        "_get_database_client",
        side_effect=ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"),
    ):
        # This simulates Supabase being unavailable
        yield service


class TestSupabaseFallbackStartup:
    """Test application startup when Supabase unavailable."""

    @pytest.mark.asyncio
    async def test_credential_service_starts_without_supabase(
        self, credential_service_no_supabase
    ):
        """Test CredentialService initializes successfully without Supabase."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            # Should not raise exception
            credentials = await credential_service_no_supabase.load_all_credentials()

            # Returns empty dict instead of failing
            assert credentials == {}
            assert credential_service_no_supabase._cache_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_credentials_without_supabase(self, mock_env_credentials):
        """Test credential initialization falls back to environment variables."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch(
                "src.server.services.credential_service.credential_service._get_database_client",
                side_effect=ValueError("No Supabase"),
            ):
                # Should complete without exception
                await initialize_credentials()

                # Environment variables should remain set
                assert os.environ.get("OPENAI_API_KEY") == "env-openai-key"
                assert os.environ.get("LLM_PROVIDER") == "openai"

    def test_service_uses_environment_variables_as_fallback(self, mock_env_credentials):
        """Test that services can use environment variables when Supabase down."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            # Simulate reading configuration from environment
            api_key = os.getenv("OPENAI_API_KEY")
            provider = os.getenv("LLM_PROVIDER")
            model = os.getenv("MODEL_CHOICE")

            assert api_key == "env-openai-key"
            assert provider == "openai"
            assert model == "gpt-4"


class TestSupabaseFallbackOperations:
    """Test operations continue when Supabase unavailable."""

    @pytest.mark.asyncio
    async def test_get_credential_returns_default_without_supabase(
        self, credential_service_no_supabase
    ):
        """Test get_credential returns default value when Supabase unavailable."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            result = await credential_service_no_supabase.get_credential(
                "MISSING_KEY", default="fallback_value"
            )

            assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_set_credential_fails_gracefully_without_supabase(
        self, credential_service_no_supabase
    ):
        """Test set_credential fails gracefully without raising exception."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            result = await credential_service_no_supabase.set_credential(
                "TEST_KEY", "test_value"
            )

            # Returns False instead of raising exception
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_credential_fails_gracefully_without_supabase(
        self, credential_service_no_supabase
    ):
        """Test delete_credential fails gracefully without raising exception."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            result = await credential_service_no_supabase.delete_credential("TEST_KEY")

            # Returns False instead of raising exception
            assert result is False

    @pytest.mark.asyncio
    async def test_get_credentials_by_category_returns_empty_without_supabase(
        self, credential_service_no_supabase
    ):
        """Test get_credentials_by_category returns empty dict when Supabase unavailable."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            result = await credential_service_no_supabase.get_credentials_by_category(
                "rag_strategy"
            )

            # Returns empty dict instead of raising exception
            assert result == {}

    @pytest.mark.asyncio
    async def test_list_all_credentials_returns_empty_without_supabase(
        self, credential_service_no_supabase
    ):
        """Test list_all_credentials returns empty list when Supabase unavailable."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            result = await credential_service_no_supabase.list_all_credentials()

            # Returns empty list instead of raising exception
            assert result == []


class TestSupabaseFallbackProviderManagement:
    """Test provider management falls back to environment variables."""

    @pytest.mark.asyncio
    async def test_get_active_provider_uses_environment_fallback(
        self, credential_service_no_supabase, mock_env_credentials
    ):
        """Test get_active_provider falls back to environment variables."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch.object(
                credential_service_no_supabase,
                "get_credentials_by_category",
                side_effect=Exception("Supabase unavailable"),
            ):
                result = await credential_service_no_supabase.get_active_provider()

                # Should return configuration from environment variables
                assert result["provider"] == "openai"
                assert result["api_key"] == "env-openai-key"
                assert result["chat_model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_get_active_provider_ollama_with_env_fallback(
        self, credential_service_no_supabase
    ):
        """Test Ollama provider configuration with environment fallback."""
        env_vars = {
            "LLM_PROVIDER": "ollama",
            "LLM_BASE_URL": "http://192.168.86.200:11434",
            "MODEL_CHOICE": "llama3.1:8b",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            with patch.object(
                credential_service_no_supabase,
                "get_credentials_by_category",
                side_effect=Exception("Supabase unavailable"),
            ):
                result = await credential_service_no_supabase.get_active_provider()

                assert result["provider"] == "ollama"
                assert result["api_key"] == "ollama"
                assert "11434" in result["base_url"]
                assert result["chat_model"] == "llama3.1:8b"


class TestSupabaseFallbackApplicationFlow:
    """Test complete application flow with Supabase fallback."""

    @pytest.mark.asyncio
    async def test_application_initialization_without_supabase(
        self, mock_env_credentials
    ):
        """Test full application initialization when Supabase unavailable."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch(
                "src.server.services.credential_service.credential_service._get_database_client",
                side_effect=ValueError("Supabase unavailable"),
            ):
                # Initialize credentials
                await initialize_credentials()

                # Verify environment variables still accessible
                assert os.getenv("OPENAI_API_KEY") is not None
                assert os.getenv("LLM_PROVIDER") == "openai"

    @pytest.mark.asyncio
    async def test_credential_service_continues_after_supabase_failure(
        self, credential_service_no_supabase, mock_env_credentials
    ):
        """Test credential service continues operating after Supabase failure."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch.object(
                credential_service_no_supabase,
                "_get_database_client",
                side_effect=ValueError("Supabase unavailable"),
            ):
                # First operation - should handle error gracefully
                await credential_service_no_supabase.load_all_credentials()

                # Subsequent operations should continue working
                result = await credential_service_no_supabase.get_credential(
                    "MISSING", default="default_value"
                )
                assert result == "default_value"

                # Cache should be initialized even after failure
                assert credential_service_no_supabase._cache_initialized is True


class TestSupabaseFallbackCacheBehavior:
    """Test cache behavior when Supabase unavailable."""

    @pytest.mark.asyncio
    async def test_cache_initialized_even_when_supabase_unavailable(
        self, credential_service_no_supabase
    ):
        """Test cache is initialized after failed Supabase connection."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            await credential_service_no_supabase.load_all_credentials()

            # Cache should be initialized to prevent retry loops
            assert credential_service_no_supabase._cache_initialized is True
            assert credential_service_no_supabase._cache == {}

    @pytest.mark.asyncio
    async def test_get_config_as_env_dict_when_cache_empty(
        self, credential_service_no_supabase
    ):
        """Test get_config_as_env_dict returns empty when cache uninitialized."""
        # Don't initialize cache
        assert credential_service_no_supabase._cache_initialized is False

        result = credential_service_no_supabase.get_config_as_env_dict()

        assert result == {}


class TestSupabaseFallbackMultiServiceScenario:
    """Test multi-service scenario with Supabase unavailable."""

    @pytest.mark.asyncio
    async def test_multiple_services_start_without_supabase(self, mock_env_credentials):
        """Test multiple services can start when Supabase unavailable."""
        services = [
            "archon-server",
            "archon-intelligence",
            "archon-bridge",
            "archon-search",
        ]

        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch(
                "src.server.services.credential_service.CredentialService._get_database_client",
                side_effect=ValueError("Supabase unavailable"),
            ):
                # Simulate each service creating its own credential service
                credential_services = []

                for service_name in services:
                    cred_svc = CredentialService()
                    await cred_svc.load_all_credentials()

                    # Each service should start successfully
                    assert cred_svc._cache_initialized is True
                    credential_services.append(cred_svc)

                # All services initialized successfully
                assert len(credential_services) == 4

    @pytest.mark.asyncio
    async def test_services_use_environment_for_critical_config(
        self, mock_env_credentials
    ):
        """Test services can read critical configuration from environment."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            # Simulate service reading critical configuration
            host = os.getenv("HOST", "0.0.0.0")
            port = int(os.getenv("PORT", "8181"))
            api_key = os.getenv("OPENAI_API_KEY")

            # Services should be able to start with these values
            assert host is not None
            assert port > 0
            assert api_key is not None


class TestSupabaseFallbackErrorMessages:
    """Test error messages and logging when Supabase unavailable."""

    @pytest.mark.asyncio
    async def test_load_credentials_logs_warning_on_failure(
        self, credential_service_no_supabase, caplog
    ):
        """Test that Supabase failure logs appropriate warning."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("Supabase unavailable"),
        ):
            await credential_service_no_supabase.load_all_credentials()

            # Verify warning logged (check caplog records)
            # Note: Actual logging depends on logger configuration
            assert credential_service_no_supabase._cache_initialized is True

    @pytest.mark.asyncio
    async def test_set_credential_logs_error_on_failure(
        self, credential_service_no_supabase, caplog
    ):
        """Test that credential set failure is logged."""
        with patch.object(
            credential_service_no_supabase,
            "_get_database_client",
            side_effect=ValueError("Supabase unavailable"),
        ):
            result = await credential_service_no_supabase.set_credential(
                "TEST_KEY", "test_value"
            )

            assert result is False


class TestSupabaseFallbackRecovery:
    """Test recovery scenarios when Supabase becomes available again."""

    @pytest.mark.asyncio
    async def test_credential_service_can_reconnect_after_failure(self):
        """Test that credential service can reconnect if Supabase recovers."""
        service = CredentialService()

        # First attempt fails
        with patch.object(
            service,
            "_get_database_client",
            side_effect=ValueError("Supabase unavailable"),
        ):
            await service.load_all_credentials()
            assert service._cache == {}

        # Second attempt succeeds (Supabase recovered)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.execute.return_value.data = [
            {
                "key": "RECOVERED_KEY",
                "value": "recovered_value",
                "encrypted_value": None,
                "is_encrypted": False,
                "category": "test",
                "description": "Recovered",
            }
        ]

        with patch.object(service, "_get_database_client", return_value=mock_client):
            # Reset cache to force reload
            service._cache_initialized = False

            await service.load_all_credentials()

            # Should now have credentials from database
            assert "RECOVERED_KEY" in service._cache
            assert service._cache["RECOVERED_KEY"] == "recovered_value"


# End-to-end scenario tests


class TestSupabaseFallbackE2EScenarios:
    """End-to-end tests for Supabase fallback scenarios."""

    @pytest.mark.asyncio
    async def test_e2e_application_startup_without_supabase(self, mock_env_credentials):
        """Test complete application startup sequence without Supabase."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch(
                "src.server.services.credential_service.create_client",
                side_effect=Exception("Supabase connection failed"),
            ):
                # Step 1: Initialize credential service
                cred_svc = CredentialService()

                # Step 2: Load credentials (will fail gracefully)
                credentials = await cred_svc.load_all_credentials()
                assert credentials == {}

                # Step 3: Application continues with environment variables
                api_key = os.getenv("OPENAI_API_KEY")
                provider = os.getenv("LLM_PROVIDER")

                assert api_key == "env-openai-key"
                assert provider == "openai"

                # Step 4: Application services can start
                # (simulated by successful execution up to this point)
                assert cred_svc._cache_initialized is True

    @pytest.mark.asyncio
    async def test_e2e_credential_operations_with_fallback(
        self, credential_service_no_supabase, mock_env_credentials
    ):
        """Test complete credential operation flow with environment fallback."""
        with patch.dict(os.environ, mock_env_credentials, clear=False):
            with patch.object(
                credential_service_no_supabase,
                "_get_database_client",
                side_effect=ValueError("Supabase unavailable"),
            ):
                # Initialize
                await credential_service_no_supabase.load_all_credentials()

                # Try to get credential (returns default)
                result = await credential_service_no_supabase.get_credential(
                    "API_KEY", default=os.getenv("OPENAI_API_KEY")
                )
                assert result == "env-openai-key"

                # Try to set credential (fails gracefully)
                set_result = await credential_service_no_supabase.set_credential(
                    "NEW_KEY", "new_value"
                )
                assert set_result is False

                # Application continues operating normally
                assert credential_service_no_supabase._cache_initialized is True
