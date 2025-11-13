"""
Unit tests for CredentialService - Supabase removal and graceful degradation.

Tests cover:
1. Graceful degradation when Supabase unavailable
2. Credential loading with/without Supabase
3. Encryption/decryption functionality
4. Fallback to environment variables
5. Cache behavior and invalidation
6. RAG settings cache management
"""

import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from src.server.services.credential_service import (
    CredentialItem,
    CredentialService,
    get_credential,
    initialize_credentials,
    set_credential,
)


@pytest.fixture
def credential_service():
    """Create a fresh CredentialService instance for each test."""
    service = CredentialService()
    return service


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client with proper chaining support."""
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_insert = MagicMock()
    mock_update = MagicMock()
    mock_delete = MagicMock()
    mock_upsert = MagicMock()

    # Setup method chaining for select
    mock_select.execute.return_value.data = []
    mock_select.eq.return_value = mock_select
    mock_select.order.return_value = mock_select
    mock_select.limit.return_value = mock_select
    mock_table.select.return_value = mock_select

    # Setup method chaining for insert
    mock_insert.execute.return_value.data = [{"id": "test-id"}]
    mock_table.insert.return_value = mock_insert

    # Setup method chaining for update
    mock_update.execute.return_value.data = [{"id": "test-id"}]
    mock_update.eq.return_value = mock_update
    mock_table.update.return_value = mock_update

    # Setup method chaining for delete
    mock_delete.execute.return_value.data = []
    mock_delete.eq.return_value = mock_delete
    mock_table.delete.return_value = mock_delete

    # Setup method chaining for upsert
    mock_upsert.execute.return_value.data = [{"id": "test-id"}]
    mock_table.upsert.return_value = mock_upsert

    # Make table() return the mock table
    mock_client.table.return_value = mock_table

    return mock_client


class TestCredentialServiceGracefulDegradation:
    """Test graceful degradation when Supabase is unavailable."""

    @pytest.mark.asyncio
    async def test_load_credentials_without_supabase(self, credential_service):
        """Test that service starts successfully when Supabase unavailable."""
        with patch.object(
            credential_service,
            "_get_database_client",
            side_effect=ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"),
        ):
            result = await credential_service.load_all_credentials()

            # Service should return empty dict instead of failing
            assert result == {}
            assert credential_service._cache == {}
            assert credential_service._cache_initialized is True

    @pytest.mark.asyncio
    async def test_get_credential_with_unavailable_supabase(self, credential_service):
        """Test credential retrieval when Supabase unavailable returns default."""
        with patch.object(
            credential_service,
            "_get_database_client",
            side_effect=ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"),
        ):
            # First call triggers load_all_credentials
            result = await credential_service.get_credential(
                "MISSING_KEY", default="fallback_value"
            )

            assert result == "fallback_value"
            assert credential_service._cache_initialized is True

    @pytest.mark.asyncio
    async def test_set_credential_fails_gracefully_without_supabase(
        self, credential_service
    ):
        """Test setting credential fails gracefully when Supabase unavailable."""
        with patch.object(
            credential_service,
            "_get_database_client",
            side_effect=ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"),
        ):
            result = await credential_service.set_credential("TEST_KEY", "test_value")

            assert result is False  # Should return False instead of raising

    @pytest.mark.asyncio
    async def test_get_credentials_by_category_without_supabase(
        self, credential_service
    ):
        """Test category retrieval returns empty dict when Supabase unavailable."""
        with patch.object(
            credential_service,
            "_get_database_client",
            side_effect=ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"),
        ):
            result = await credential_service.get_credentials_by_category(
                "rag_strategy"
            )

            assert result == {}


class TestCredentialServiceWithSupabase:
    """Test credential service with mocked Supabase."""

    @pytest.mark.asyncio
    async def test_load_all_credentials_success(
        self, credential_service, mock_supabase_client
    ):
        """Test successful loading of credentials from Supabase."""
        # Setup mock data
        mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = [
            {
                "key": "OPENAI_API_KEY",
                "value": None,
                "encrypted_value": "encrypted_data",
                "is_encrypted": True,
                "category": "credentials",
                "description": "OpenAI API Key",
            },
            {
                "key": "TEST_SETTING",
                "value": "test_value",
                "encrypted_value": None,
                "is_encrypted": False,
                "category": "settings",
                "description": "Test setting",
            },
        ]

        with patch.object(
            credential_service,
            "_get_database_client",
            return_value=mock_supabase_client,
        ):
            result = await credential_service.load_all_credentials()

            assert len(result) == 2
            assert "OPENAI_API_KEY" in result
            assert result["OPENAI_API_KEY"]["is_encrypted"] is True
            assert "TEST_SETTING" in result
            assert result["TEST_SETTING"] == "test_value"

    @pytest.mark.asyncio
    async def test_get_credential_with_decryption(
        self, credential_service, mock_supabase_client
    ):
        """Test retrieving encrypted credential with decryption."""
        # Pre-populate cache with encrypted credential
        credential_service._cache = {
            "ENCRYPTED_KEY": {
                "encrypted_value": "test_encrypted",
                "is_encrypted": True,
                "category": "test",
                "description": "Test",
            }
        }
        credential_service._cache_initialized = True

        with patch.object(
            credential_service, "_decrypt_value", return_value="decrypted_value"
        ):
            result = await credential_service.get_credential(
                "ENCRYPTED_KEY", decrypt=True
            )

            assert result == "decrypted_value"

    @pytest.mark.asyncio
    async def test_get_credential_without_decryption(self, credential_service):
        """Test retrieving encrypted credential without decryption."""
        # Pre-populate cache with encrypted credential
        credential_service._cache = {
            "ENCRYPTED_KEY": {
                "encrypted_value": "test_encrypted",
                "is_encrypted": True,
                "category": "test",
                "description": "Test",
            }
        }
        credential_service._cache_initialized = True

        result = await credential_service.get_credential("ENCRYPTED_KEY", decrypt=False)

        # Should return the dict with encrypted_value
        assert isinstance(result, dict)
        assert result["encrypted_value"] == "test_encrypted"

    @pytest.mark.asyncio
    async def test_set_credential_encrypted(
        self, credential_service, mock_supabase_client
    ):
        """Test setting an encrypted credential."""
        with patch.object(
            credential_service,
            "_get_database_client",
            return_value=mock_supabase_client,
        ):
            with patch.object(
                credential_service, "_encrypt_value", return_value="encrypted_test"
            ):
                result = await credential_service.set_credential(
                    "TEST_KEY",
                    "secret_value",
                    is_encrypted=True,
                    category="test",
                    description="Test credential",
                )

                assert result is True
                # Verify cache updated
                assert "TEST_KEY" in credential_service._cache
                assert credential_service._cache["TEST_KEY"]["is_encrypted"] is True

    @pytest.mark.asyncio
    async def test_delete_credential(self, credential_service, mock_supabase_client):
        """Test deleting a credential."""
        # Pre-populate cache
        credential_service._cache = {"TEST_KEY": "test_value"}

        with patch.object(
            credential_service,
            "_get_database_client",
            return_value=mock_supabase_client,
        ):
            result = await credential_service.delete_credential("TEST_KEY")

            assert result is True
            assert "TEST_KEY" not in credential_service._cache


class TestCredentialServiceEncryption:
    """Test encryption and decryption functionality."""

    def test_encrypt_value(self, credential_service):
        """Test value encryption."""
        with patch.dict(
            os.environ, {"SUPABASE_SERVICE_KEY": "test-encryption-key"}, clear=False
        ):
            encrypted = credential_service._encrypt_value("test_value")

            assert encrypted != "test_value"
            assert len(encrypted) > 0

    def test_decrypt_value(self, credential_service):
        """Test value decryption."""
        with patch.dict(
            os.environ, {"SUPABASE_SERVICE_KEY": "test-encryption-key"}, clear=False
        ):
            # Encrypt then decrypt
            encrypted = credential_service._encrypt_value("test_value")
            decrypted = credential_service._decrypt_value(encrypted)

            assert decrypted == "test_value"

    def test_encrypt_empty_value(self, credential_service):
        """Test encrypting empty string."""
        result = credential_service._encrypt_value("")
        assert result == ""

    def test_decrypt_empty_value(self, credential_service):
        """Test decrypting empty string."""
        result = credential_service._decrypt_value("")
        assert result == ""

    def test_decrypt_invalid_value_fails(self, credential_service):
        """Test decryption failure with invalid encrypted data."""
        with patch.dict(
            os.environ, {"SUPABASE_SERVICE_KEY": "test-encryption-key"}, clear=False
        ):
            with pytest.raises(Exception):
                credential_service._decrypt_value("invalid_encrypted_data")


class TestCredentialServiceCache:
    """Test credential caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self, credential_service):
        """Test cache is properly initialized."""
        assert credential_service._cache_initialized is False
        assert credential_service._cache == {}

        # After loading credentials, cache should be initialized
        with patch.object(
            credential_service,
            "_get_database_client",
            side_effect=ValueError("No Supabase"),
        ):
            await credential_service.load_all_credentials()

        assert credential_service._cache_initialized is True

    @pytest.mark.asyncio
    async def test_rag_settings_cache(self, credential_service, mock_supabase_client):
        """Test RAG settings caching with TTL."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "key": "LLM_PROVIDER",
                "value": "openai",
                "encrypted_value": None,
                "is_encrypted": False,
                "category": "rag_strategy",
                "description": "LLM Provider",
            }
        ]

        with patch.object(
            credential_service,
            "_get_database_client",
            return_value=mock_supabase_client,
        ):
            # First call - should query database
            result1 = await credential_service.get_credentials_by_category(
                "rag_strategy"
            )
            assert result1 == {"LLM_PROVIDER": "openai"}
            assert credential_service._rag_settings_cache is not None

            # Second call - should use cache
            result2 = await credential_service.get_credentials_by_category(
                "rag_strategy"
            )
            assert result2 == {"LLM_PROVIDER": "openai"}

            # Verify only one database call was made (cache hit on second call)
            assert (
                mock_supabase_client.table.return_value.select.return_value.eq.call_count
                == 1
            )

    @pytest.mark.asyncio
    async def test_rag_cache_invalidation_on_set(
        self, credential_service, mock_supabase_client
    ):
        """Test RAG cache invalidation when setting rag_strategy credential."""
        # Pre-populate RAG cache
        credential_service._rag_settings_cache = {"OLD_KEY": "old_value"}
        credential_service._rag_cache_timestamp = 123456789

        with patch.object(
            credential_service,
            "_get_database_client",
            return_value=mock_supabase_client,
        ):
            # Set a rag_strategy credential
            await credential_service.set_credential(
                "NEW_KEY", "new_value", category="rag_strategy"
            )

            # Cache should be invalidated
            assert credential_service._rag_settings_cache is None
            assert credential_service._rag_cache_timestamp is None


class TestCredentialServiceProviderManagement:
    """Test provider configuration management."""

    @pytest.mark.asyncio
    async def test_get_active_provider_openai(
        self, credential_service, mock_supabase_client
    ):
        """Test getting active OpenAI provider configuration."""
        # Mock RAG settings
        credential_service._cache = {
            "LLM_PROVIDER": "openai",
            "MODEL_CHOICE": "gpt-4",
            "EMBEDDING_MODEL": "text-embedding-3-small",
            "OPENAI_API_KEY": "test-api-key",
        }
        credential_service._cache_initialized = True

        with patch.object(
            credential_service, "get_credentials_by_category"
        ) as mock_get_category:
            mock_get_category.return_value = {
                "LLM_PROVIDER": "openai",
                "MODEL_CHOICE": "gpt-4",
                "EMBEDDING_MODEL": "text-embedding-3-small",
            }

            with patch.object(
                credential_service, "_get_provider_api_key"
            ) as mock_get_key:
                mock_get_key.return_value = "test-api-key"

                result = await credential_service.get_active_provider()

                assert result["provider"] == "openai"
                assert result["api_key"] == "test-api-key"
                assert result["chat_model"] == "gpt-4"
                assert result["embedding_model"] == "text-embedding-3-small"
                assert result["base_url"] is None  # OpenAI uses default

    @pytest.mark.asyncio
    async def test_get_active_provider_ollama(
        self, credential_service, mock_supabase_client
    ):
        """Test getting active Ollama provider configuration."""
        credential_service._cache = {
            "LLM_PROVIDER": "ollama",
            "LLM_BASE_URL": "http://192.168.86.200:11434/v1",
        }
        credential_service._cache_initialized = True

        with patch.object(
            credential_service, "get_credentials_by_category"
        ) as mock_get_category:
            mock_get_category.return_value = {
                "LLM_PROVIDER": "ollama",
                "LLM_BASE_URL": "http://192.168.86.200:11434/v1",
            }

            with patch.object(
                credential_service, "_get_provider_api_key"
            ) as mock_get_key:
                mock_get_key.return_value = "ollama"

                result = await credential_service.get_active_provider()

                assert result["provider"] == "ollama"
                assert result["api_key"] == "ollama"
                assert result["base_url"] == "http://192.168.86.200:11434/v1"

    @pytest.mark.asyncio
    async def test_get_active_provider_fallback_to_env(
        self, credential_service, mock_supabase_client
    ):
        """Test fallback to environment variables when database unavailable."""
        with patch.object(
            credential_service,
            "get_credentials_by_category",
            side_effect=Exception("Database unavailable"),
        ):
            with patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "openai",
                    "OPENAI_API_KEY": "env-api-key",
                    "MODEL_CHOICE": "gpt-3.5-turbo",
                },
                clear=False,
            ):
                result = await credential_service.get_active_provider()

                assert result["provider"] == "openai"
                assert result["api_key"] == "env-api-key"
                assert result["chat_model"] == "gpt-3.5-turbo"


class TestCredentialServiceGlobalFunctions:
    """Test global convenience functions."""

    @pytest.mark.asyncio
    async def test_get_credential_global_function(self, credential_service):
        """Test global get_credential function."""
        with patch(
            "src.server.services.credential_service.credential_service.get_credential"
        ) as mock_get:
            mock_get.return_value = "test_value"

            result = await get_credential("TEST_KEY")

            assert result == "test_value"
            mock_get.assert_called_once_with("TEST_KEY", None)

    @pytest.mark.asyncio
    async def test_set_credential_global_function(self, credential_service):
        """Test global set_credential function."""
        with patch(
            "src.server.services.credential_service.credential_service.set_credential"
        ) as mock_set:
            mock_set.return_value = True

            result = await set_credential("TEST_KEY", "test_value")

            assert result is True
            mock_set.assert_called_once_with(
                "TEST_KEY", "test_value", False, None, None
            )

    @pytest.mark.asyncio
    async def test_initialize_credentials(self, credential_service):
        """Test credential initialization sets environment variables."""
        mock_credentials = {
            "OPENAI_API_KEY": "test-key",
            "HOST": "localhost",
            "PORT": "8181",
        }

        with patch(
            "src.server.services.credential_service.credential_service.load_all_credentials"
        ) as mock_load:
            mock_load.return_value = mock_credentials

            with patch(
                "src.server.services.credential_service.credential_service.get_credential"
            ) as mock_get:
                mock_get.side_effect = lambda key, **kwargs: mock_credentials.get(key)

                await initialize_credentials()

                # Verify credentials loaded
                mock_load.assert_called_once()


class TestCredentialServiceEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_list_all_credentials_with_decryption_error(
        self, credential_service, mock_supabase_client
    ):
        """Test list_all_credentials handles decryption errors gracefully."""
        mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = [
            {
                "key": "BROKEN_KEY",
                "value": None,
                "encrypted_value": "corrupted_data",
                "is_encrypted": True,
                "category": "test",
                "description": "Broken credential",
            }
        ]

        with patch.object(
            credential_service,
            "_get_database_client",
            return_value=mock_supabase_client,
        ):
            with patch.object(
                credential_service,
                "_decrypt_value",
                side_effect=Exception("Decryption failed"),
            ):
                result = await credential_service.list_all_credentials()

                assert len(result) == 1
                assert result[0].key == "BROKEN_KEY"
                assert result[0].value == "[DECRYPTION ERROR]"

    def test_get_config_as_env_dict_uninitialized(self, credential_service):
        """Test get_config_as_env_dict returns empty when uninitialized."""
        result = credential_service.get_config_as_env_dict()

        assert result == {}

    def test_get_config_as_env_dict_skips_encrypted(self, credential_service):
        """Test get_config_as_env_dict skips encrypted values."""
        credential_service._cache = {
            "PLAIN_KEY": "plain_value",
            "ENCRYPTED_KEY": {
                "encrypted_value": "encrypted",
                "is_encrypted": True,
                "category": "test",
            },
        }
        credential_service._cache_initialized = True

        result = credential_service.get_config_as_env_dict()

        assert "PLAIN_KEY" in result
        assert result["PLAIN_KEY"] == "plain_value"
        assert "ENCRYPTED_KEY" not in result

    @pytest.mark.asyncio
    async def test_get_credential_decryption_failure_returns_default(
        self, credential_service
    ):
        """Test get_credential returns default when decryption fails."""
        credential_service._cache = {
            "BAD_KEY": {
                "encrypted_value": "corrupted",
                "is_encrypted": True,
                "category": "test",
            }
        }
        credential_service._cache_initialized = True

        with patch.object(
            credential_service,
            "_decrypt_value",
            side_effect=Exception("Decryption failed"),
        ):
            result = await credential_service.get_credential(
                "BAD_KEY", default="fallback"
            )

            assert result == "fallback"
