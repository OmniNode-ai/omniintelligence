# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for langextract semantic enrichment handler.

This module tests the langextract integration including:
    - Empty result creation
    - Semantic to intent boost mapping
    - Domain indicator processing
    - Concept mapping
    - Topic weight processing
    - Graceful error handling
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from omniintelligence.nodes.intent_classifier_compute.handlers import (
    LANGEXTRACT_SERVICE_URL,
    LANGEXTRACT_TIMEOUT_SECONDS,
    create_empty_langextract_result,
    enrich_with_semantics,
    map_semantic_to_intent_boost,
)


# =============================================================================
# create_empty_langextract_result Tests
# =============================================================================


class TestCreateEmptyLangextractResult:
    """Tests for create_empty_langextract_result factory function."""

    def test_creates_empty_result_without_error(self) -> None:
        """Test that empty result has all required fields."""
        result = create_empty_langextract_result()

        assert result["concepts"] == []
        assert result["themes"] == []
        assert result["domains"] == []
        assert result["patterns"] == []
        assert result["domain_indicators"] == []
        assert result["topic_weights"] == {}
        assert result["processing_time_ms"] == 0.0
        assert result["error"] is None

    def test_creates_empty_result_with_error_message(self) -> None:
        """Test that error message is included when provided."""
        error_msg = "Connection failed"
        result = create_empty_langextract_result(error=error_msg)

        assert result["error"] == error_msg
        assert result["concepts"] == []
        assert result["themes"] == []

    def test_creates_empty_result_with_none_error(self) -> None:
        """Test that None error is handled correctly."""
        result = create_empty_langextract_result(error=None)
        assert result["error"] is None

    def test_result_structure_completeness(self) -> None:
        """Test that all expected keys are present."""
        result = create_empty_langextract_result()

        expected_keys = {
            "concepts",
            "themes",
            "domains",
            "patterns",
            "domain_indicators",
            "topic_weights",
            "processing_time_ms",
            "error",
        }
        assert set(result.keys()) == expected_keys


# =============================================================================
# map_semantic_to_intent_boost Tests
# =============================================================================


class TestMapSemanticToIntentBoost:
    """Tests for map_semantic_to_intent_boost function."""

    def test_empty_result_returns_empty_boosts(self) -> None:
        """Test that empty semantic result returns no boosts."""
        empty_result = create_empty_langextract_result()
        boosts = map_semantic_to_intent_boost(empty_result)
        assert boosts == {}

    def test_domain_indicator_mapping(self) -> None:
        """Test that domain indicators map to intent boosts."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": ["api", "testing"],
            "concepts": [],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        # Should have boosts for api_design and testing
        assert "api_design" in boosts
        assert "testing" in boosts
        assert boosts["api_design"] > 0.0
        assert boosts["testing"] > 0.0

    def test_concept_mapping_by_name(self) -> None:
        """Test that concepts map to intent boosts by name."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": [],
            "concepts": [
                {"name": "api_design", "confidence": 0.9, "category": ""},
            ],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        assert "api_design" in boosts
        assert boosts["api_design"] > 0.0

    def test_concept_mapping_by_category(self) -> None:
        """Test that concepts map to intent boosts by category."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": [],
            "concepts": [
                {"name": "unknown", "confidence": 0.8, "category": "testing"},
            ],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        assert "testing" in boosts
        assert boosts["testing"] > 0.0

    def test_concept_confidence_scaling(self) -> None:
        """Test that concept confidence scales the boost."""
        high_confidence: dict[str, Any] = {
            "domain_indicators": [],
            "concepts": [
                {"name": "testing", "confidence": 1.0, "category": ""},
            ],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        low_confidence: dict[str, Any] = {
            "domain_indicators": [],
            "concepts": [
                {"name": "testing", "confidence": 0.1, "category": ""},
            ],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }

        high_boosts = map_semantic_to_intent_boost(high_confidence)
        low_boosts = map_semantic_to_intent_boost(low_confidence)

        assert high_boosts["testing"] > low_boosts["testing"]

    def test_topic_weight_mapping(self) -> None:
        """Test that topic weights map to intent boosts."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": [],
            "concepts": [],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {"api": 0.8, "testing": 0.5},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        assert "api_design" in boosts
        assert "testing" in boosts

    def test_domain_mapping(self) -> None:
        """Test that explicit domains map to intent boosts."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": [],
            "concepts": [],
            "themes": [],
            "domains": [
                {"name": "software_development", "confidence": 0.9},
            ],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        assert "code_generation" in boosts

    def test_boost_capped_at_max(self) -> None:
        """Test that boosts are capped at maximum value (0.30)."""
        # Create a result that would generate very high boosts
        semantic_result: dict[str, Any] = {
            "domain_indicators": ["api", "api", "api_design", "rest", "graphql"],
            "concepts": [
                {"name": "api", "confidence": 1.0, "category": "api_design"},
                {"name": "api", "confidence": 1.0, "category": "api_design"},
            ],
            "themes": [],
            "domains": [
                {"name": "api", "confidence": 1.0},
                {"name": "api_design", "confidence": 1.0},
            ],
            "patterns": [],
            "topic_weights": {"api": 1.0, "api_design": 1.0},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        # All boosts should be capped at 0.30
        for intent, boost in boosts.items():
            assert boost <= 0.30, f"Boost for {intent} ({boost}) exceeds max 0.30"

    def test_multiple_sources_combine(self) -> None:
        """Test that boosts from multiple sources combine."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": ["api"],  # +0.10
            "concepts": [
                {"name": "api", "confidence": 1.0, "category": ""},  # +0.05
            ],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        # Should have combined boost (0.10 + 0.05 = 0.15)
        assert "api_design" in boosts
        assert boosts["api_design"] > 0.10  # More than just domain indicator

    def test_normalized_key_matching(self) -> None:
        """Test that keys are normalized (lowercase, underscores)."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": ["API-design", "Software Development"],
            "concepts": [],
            "themes": [],
            "domains": [],
            "patterns": [],
            "topic_weights": {},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        # api-design should normalize to api_design
        # software development should normalize to software_development -> code_generation
        assert "api_design" in boosts
        assert "code_generation" in boosts

    def test_unknown_domains_ignored(self) -> None:
        """Test that unknown domains are ignored (no errors)."""
        semantic_result: dict[str, Any] = {
            "domain_indicators": ["unknown_domain", "random_thing"],
            "concepts": [
                {"name": "something_else", "confidence": 0.9, "category": "unknown"},
            ],
            "themes": [],
            "domains": [
                {"name": "not_in_mapping", "confidence": 0.8},
            ],
            "patterns": [],
            "topic_weights": {"unmapped_topic": 0.7},
            "processing_time_ms": 0.0,
            "error": None,
        }
        boosts = map_semantic_to_intent_boost(semantic_result)

        # Should return empty dict (no valid mappings)
        assert boosts == {}


# =============================================================================
# enrich_with_semantics Tests (Async)
# =============================================================================


class TestEnrichWithSemantics:
    """Tests for enrich_with_semantics async function."""

    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_result(self) -> None:
        """Test that empty content returns empty result without calling service."""
        result = await enrich_with_semantics("")
        assert result["concepts"] == []
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_whitespace_content_returns_empty_result(self) -> None:
        """Test that whitespace-only content returns empty result."""
        result = await enrich_with_semantics("   \n\t  ")
        assert result["concepts"] == []

    @pytest.mark.asyncio
    async def test_timeout_returns_empty_result_with_error(self) -> None:
        """Test that timeout returns empty result with error message."""
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("")):
            result = await enrich_with_semantics("test content")
            assert result["concepts"] == []
            assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty_result(self) -> None:
        """Test that connection error returns empty result with error message."""
        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await enrich_with_semantics("test content")
            assert result["concepts"] == []
            assert "connect" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_result(self) -> None:
        """Test that HTTP error returns empty result with error message."""
        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.HTTPError("Server error"),
        ):
            result = await enrich_with_semantics("test content")
            assert result["concepts"] == []
            assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_non_200_status_returns_empty_result(self) -> None:
        """Test that non-200 status code returns empty result."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client
            result = await enrich_with_semantics("test content")
            assert result["concepts"] == []
            assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_response_parsing(self) -> None:
        """Test that successful response is parsed correctly."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "concepts": [{"name": "api", "confidence": 0.9}],
            "themes": [{"name": "backend"}],
            "domains": [{"name": "software", "confidence": 0.8}],
            "semantic_patterns": [{"pattern_type": "test", "confidence_score": 0.85}],
            "domain_indicators": ["api", "rest"],
            "topic_weights": {"api": 0.7, "testing": 0.3},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client
            result = await enrich_with_semantics("Create a REST API")

            assert len(result["concepts"]) == 1
            assert result["concepts"][0]["name"] == "api"
            assert len(result["domain_indicators"]) == 2
            assert result["topic_weights"]["api"] == 0.7
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_min_confidence_filtering(self) -> None:
        """Test that results are filtered by min_confidence."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "concepts": [
                {"name": "high", "confidence": 0.9},
                {"name": "low", "confidence": 0.5},
            ],
            "themes": [],
            "domains": [
                {"name": "high_domain", "confidence": 0.8},
                {"name": "low_domain", "confidence": 0.3},
            ],
            "semantic_patterns": [],
            "domain_indicators": [],
            "topic_weights": {},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client
            result = await enrich_with_semantics(
                "test content",
                min_confidence=0.7,
            )

            # Only high-confidence items should be included
            assert len(result["concepts"]) == 1
            assert result["concepts"][0]["name"] == "high"
            assert len(result["domains"]) == 1
            assert result["domains"][0]["name"] == "high_domain"

    @pytest.mark.asyncio
    async def test_processing_time_recorded(self) -> None:
        """Test that processing time is recorded."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "concepts": [],
            "themes": [],
            "domains": [],
            "semantic_patterns": [],
            "domain_indicators": [],
            "topic_weights": {},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client
            result = await enrich_with_semantics("test content")
            assert result["processing_time_ms"] >= 0.0

    @pytest.mark.asyncio
    async def test_context_parameter_passed(self) -> None:
        """Test that context parameter is passed to the service."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "concepts": [],
            "themes": [],
            "domains": [],
            "semantic_patterns": [],
            "domain_indicators": [],
            "topic_weights": {},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client
            await enrich_with_semantics(
                "Create an API",
                context="api_development",
            )

            # Verify context was passed in the request
            call_args = mock_client.post.call_args
            request_json = call_args.kwargs.get("json", {})
            assert request_json.get("context") == "api_development"

    @pytest.mark.asyncio
    async def test_unexpected_exception_handled(self) -> None:
        """Test that unexpected exceptions are handled gracefully."""
        with patch(
            "httpx.AsyncClient.post",
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await enrich_with_semantics("test content")
            assert result["concepts"] == []
            assert "Unexpected" in result["error"]


# =============================================================================
# Configuration Constants Tests
# =============================================================================


class TestConfigurationConstants:
    """Tests for configuration constants."""

    def test_service_url_has_default(self) -> None:
        """Test that LANGEXTRACT_SERVICE_URL has a default value."""
        assert LANGEXTRACT_SERVICE_URL is not None
        assert isinstance(LANGEXTRACT_SERVICE_URL, str)
        assert len(LANGEXTRACT_SERVICE_URL) > 0

    def test_timeout_has_default(self) -> None:
        """Test that LANGEXTRACT_TIMEOUT_SECONDS has a reasonable default."""
        assert LANGEXTRACT_TIMEOUT_SECONDS is not None
        assert isinstance(LANGEXTRACT_TIMEOUT_SECONDS, float)
        assert LANGEXTRACT_TIMEOUT_SECONDS > 0
        # Should be a reasonable timeout (not too short, not too long)
        assert LANGEXTRACT_TIMEOUT_SECONDS <= 60.0


# =============================================================================
# Domain Mapping Coverage Tests
# =============================================================================


class TestDomainMappingCoverage:
    """Tests for domain-to-intent mapping coverage."""

    def test_api_domains_map_to_api_design(self) -> None:
        """Test that API-related domains map to api_design intent."""
        api_domains = ["api", "api_design", "rest", "graphql", "endpoint", "http"]
        for domain in api_domains:
            semantic_result: dict[str, Any] = {
                "domain_indicators": [domain],
                "concepts": [],
                "themes": [],
                "domains": [],
                "patterns": [],
                "topic_weights": {},
                "processing_time_ms": 0.0,
                "error": None,
            }
            boosts = map_semantic_to_intent_boost(semantic_result)
            assert "api_design" in boosts, f"Domain '{domain}' should map to api_design"

    def test_testing_domains_map_to_testing(self) -> None:
        """Test that testing-related domains map to testing intent."""
        testing_domains = ["testing", "test", "unit_test", "integration_test"]
        for domain in testing_domains:
            semantic_result: dict[str, Any] = {
                "domain_indicators": [domain],
                "concepts": [],
                "themes": [],
                "domains": [],
                "patterns": [],
                "topic_weights": {},
                "processing_time_ms": 0.0,
                "error": None,
            }
            boosts = map_semantic_to_intent_boost(semantic_result)
            assert "testing" in boosts, f"Domain '{domain}' should map to testing"

    def test_code_generation_domains_map_correctly(self) -> None:
        """Test that code generation domains map correctly."""
        code_domains = ["code_generation", "programming", "software_development"]
        for domain in code_domains:
            semantic_result: dict[str, Any] = {
                "domain_indicators": [domain],
                "concepts": [],
                "themes": [],
                "domains": [],
                "patterns": [],
                "topic_weights": {},
                "processing_time_ms": 0.0,
                "error": None,
            }
            boosts = map_semantic_to_intent_boost(semantic_result)
            assert "code_generation" in boosts, (
                f"Domain '{domain}' should map to code_generation"
            )

    def test_debugging_domains_map_correctly(self) -> None:
        """Test that debugging domains map correctly."""
        debug_domains = ["debugging", "troubleshooting", "error_handling", "bug_fix"]
        for domain in debug_domains:
            semantic_result: dict[str, Any] = {
                "domain_indicators": [domain],
                "concepts": [],
                "themes": [],
                "domains": [],
                "patterns": [],
                "topic_weights": {},
                "processing_time_ms": 0.0,
                "error": None,
            }
            boosts = map_semantic_to_intent_boost(semantic_result)
            assert "debugging" in boosts, f"Domain '{domain}' should map to debugging"

    def test_documentation_domains_map_correctly(self) -> None:
        """Test that documentation domains map correctly."""
        doc_domains = ["documentation", "docs", "readme", "technical_writing"]
        for domain in doc_domains:
            semantic_result: dict[str, Any] = {
                "domain_indicators": [domain],
                "concepts": [],
                "themes": [],
                "domains": [],
                "patterns": [],
                "topic_weights": {},
                "processing_time_ms": 0.0,
                "error": None,
            }
            boosts = map_semantic_to_intent_boost(semantic_result)
            assert "documentation" in boosts, (
                f"Domain '{domain}' should map to documentation"
            )
