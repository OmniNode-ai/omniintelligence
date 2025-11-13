"""
Unit Tests for PRIntelligenceExtractor
========================================

Tests PR analysis, langextract integration, and pattern correlation.

ONEX Compliance: Yes
Migration Date: 2025-10-28
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ..pr_intelligence import PRIntelligenceExtractor


@pytest.fixture
def db_config():
    """Database configuration fixture."""
    return {
        "db_host": "localhost",
        "db_port": 5436,
        "db_name": "test_db",
        "db_user": "test_user",
        "db_password": "test_password",
    }


@pytest.fixture
def sample_pr_data():
    """Sample PR data from GitHub."""
    return {
        "number": 123,
        "title": "Add NodeStateManagerEffect pattern",
        "body": "This PR implements the NodeStateManagerEffect pattern for state management.",
        "state": "merged",
        "url": "https://github.com/owner/repo/pull/123",
        "createdAt": "2025-10-01T10:00:00Z",
        "mergedAt": "2025-10-02T14:30:00Z",
        "reviews": [
            {
                "state": "APPROVED",
                "body": "Great implementation of the Effect pattern! LGTM",
            }
        ],
        "comments": [],
        "review_comments": [
            {
                "body": "Nice use of the NodeStateManagerEffect pattern here",
            }
        ],
    }


@pytest.mark.asyncio
async def test_pr_intelligence_extractor_initialization(db_config):
    """Test PRIntelligenceExtractor initialization."""
    extractor = PRIntelligenceExtractor(**db_config)

    assert extractor.db_config["host"] == "localhost"
    assert extractor.correlation_id is not None
    assert extractor.pool is None
    assert extractor.langextract_client is None


@pytest.mark.asyncio
async def test_extract_text_content(db_config, sample_pr_data):
    """Test text content extraction from PR data."""
    extractor = PRIntelligenceExtractor(**db_config)

    contents = extractor._extract_text_content(sample_pr_data)

    assert len(contents) > 0
    assert any(mention_type == "description" for mention_type, _ in contents)
    assert any(mention_type == "review_comment" for mention_type, _ in contents)
    assert any(mention_type == "inline_comment" for mention_type, _ in contents)


@pytest.mark.asyncio
async def test_analyze_sentiment_positive(db_config):
    """Test positive sentiment analysis."""
    extractor = PRIntelligenceExtractor(**db_config)

    text = "This is an excellent implementation! Great work, looks good to me. LGTM!"
    sentiment = extractor._analyze_sentiment(text)

    assert sentiment == "positive"


@pytest.mark.asyncio
async def test_analyze_sentiment_negative(db_config):
    """Test negative sentiment analysis."""
    extractor = PRIntelligenceExtractor(**db_config)

    text = "This is broken and needs significant refactoring. The approach is wrong."
    sentiment = extractor._analyze_sentiment(text)

    assert sentiment == "negative"


@pytest.mark.asyncio
async def test_analyze_sentiment_neutral(db_config):
    """Test neutral sentiment analysis."""
    extractor = PRIntelligenceExtractor(**db_config)

    text = "Updated the documentation to reflect the changes."
    sentiment = extractor._analyze_sentiment(text)

    assert sentiment == "neutral"


@pytest.mark.asyncio
async def test_extract_context(db_config):
    """Test context extraction around pattern mentions."""
    extractor = PRIntelligenceExtractor(**db_config)

    text = "This is a long text. In the middle we have NodeStateManagerEffect pattern. More text here."
    pattern_name = "NodeStateManagerEffect"

    context = extractor._extract_context(text, pattern_name, window=50)

    assert pattern_name in context
    assert len(context) <= 100  # window * 2


@pytest.mark.asyncio
async def test_determine_pr_outcome_merged(db_config, sample_pr_data):
    """Test PR outcome determination for merged PR."""
    extractor = PRIntelligenceExtractor(**db_config)

    outcome = extractor._determine_pr_outcome(sample_pr_data)

    assert outcome == "merged"


@pytest.mark.asyncio
async def test_determine_pr_outcome_approved(db_config):
    """Test PR outcome determination for approved PR."""
    extractor = PRIntelligenceExtractor(
        db_host="localhost",
        db_port=5436,
        db_name="test",
        db_user="test",
        db_password="test",
    )

    pr_data = {
        "state": "open",
        "reviews": [{"state": "APPROVED"}],
    }

    outcome = extractor._determine_pr_outcome(pr_data)

    assert outcome == "approved"


@pytest.mark.asyncio
async def test_determine_pr_outcome_changes_requested(db_config):
    """Test PR outcome determination for changes requested."""
    extractor = PRIntelligenceExtractor(**db_config)

    pr_data = {
        "state": "open",
        "reviews": [{"state": "CHANGES_REQUESTED"}],
    }

    outcome = extractor._determine_pr_outcome(pr_data)

    assert outcome == "changes_requested"


@pytest.mark.asyncio
async def test_correlate_with_patterns(db_config):
    """Test pattern correlation with database patterns."""
    extractor = PRIntelligenceExtractor(**db_config)

    # Mock database pool
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock database response
    mock_conn.fetchrow.return_value = {
        "id": uuid.uuid4(),
        "pattern_id": "node_state_manager_effect",
        "pattern_name": "NodeStateManagerEffect",
        "pattern_type": "effect",
    }

    extractor.pool = mock_pool

    mentions = [
        {
            "pattern_name": "NodeStateManagerEffect",
            "mention_type": "description",
            "extracted_text": "Implementation of NodeStateManagerEffect",
            "full_context": "Full context here",
            "sentiment": "positive",
            "confidence_score": 0.9,
            "pr_data": {},
        }
    ]

    correlated = await extractor._correlate_with_patterns(mentions)

    assert len(correlated) == 1
    assert correlated[0]["pattern_id"] is not None
    assert correlated[0]["db_pattern_name"] == "NodeStateManagerEffect"


@pytest.mark.asyncio
async def test_correlate_with_patterns_no_match(db_config):
    """Test pattern correlation when no database match found."""
    extractor = PRIntelligenceExtractor(**db_config)

    # Mock database pool
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock no database match
    mock_conn.fetchrow.return_value = None

    extractor.pool = mock_pool

    mentions = [
        {
            "pattern_name": "UnknownPattern",
            "mention_type": "description",
            "extracted_text": "Some text",
            "full_context": "Full context",
            "sentiment": "neutral",
            "confidence_score": 0.5,
            "pr_data": {},
        }
    ]

    correlated = await extractor._correlate_with_patterns(mentions)

    assert len(correlated) == 1
    assert correlated[0]["pattern_id"] is None


@pytest.mark.asyncio
async def test_fetch_pr_data_success(db_config):
    """Test successful PR data fetching."""
    extractor = PRIntelligenceExtractor(**db_config)

    with patch("subprocess.run") as mock_run:
        # Mock gh pr view
        mock_run.return_value.stdout = json.dumps(
            {
                "title": "Test PR",
                "body": "Test body",
                "state": "open",
                "reviews": [],
                "comments": [],
                "url": "https://github.com/owner/repo/pull/1",
            }
        )
        mock_run.return_value.returncode = 0

        pr_data = await extractor._fetch_pr_data("owner/repo", 1)

    assert pr_data is not None
    assert pr_data["title"] == "Test PR"


@pytest.mark.asyncio
async def test_context_manager(db_config):
    """Test async context manager."""
    with patch("asyncpg.create_pool") as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        with patch.object(
            PRIntelligenceExtractor, "_PRIntelligenceExtractor__aenter__"
        ) as mock_enter:
            async with PRIntelligenceExtractor(**db_config) as extractor:
                # Verify connections would be established
                pass
