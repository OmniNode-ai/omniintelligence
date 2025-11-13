"""
PR Intelligence Extractor
==========================

Extracts pattern intelligence from GitHub PR reviews and comments using langextract.

This module:
1. Fetches PR data from GitHub (description, reviews, comments)
2. Uses langextract to extract semantic concepts and pattern mentions
3. Correlates mentioned patterns with database patterns
4. Tracks PR outcomes (approved, merged, time to merge)
5. Stores intelligence in pattern_pr_intelligence table

ONEX Compliance: Yes
Migration Date: 2025-10-28
"""

import asyncio
import json
import logging
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from src.archon_services.pattern_learning.phase2_matching.client_langextract_http import (
    ClientLangextractHttp,
)

logger = logging.getLogger(__name__)


@dataclass
class PRIntelligenceMetrics:
    """Metrics for PR intelligence extraction."""

    prs_analyzed: int = 0
    patterns_found: int = 0
    mentions_extracted: int = 0
    mentions_stored: int = 0
    errors: int = 0
    processing_time_ms: float = 0.0


class PRIntelligenceExtractor:
    """
    Extract pattern intelligence from GitHub PRs using langextract.

    Workflow:
    1. Fetch PR data via GitHub CLI (gh)
    2. Extract text from description, reviews, and comments
    3. Use langextract to extract semantic concepts and keywords
    4. Match concepts/keywords to pattern names in database
    5. Analyze sentiment (positive/negative/neutral)
    6. Track PR outcome (approved, merged, time to merge)
    7. Store in pattern_pr_intelligence table

    Example:
        extractor = PRIntelligenceExtractor(db_config)
        await extractor.analyze_pr(
            repository="owner/repo",
            pr_number=123
        )
    """

    # Pattern name keywords that indicate pattern mentions
    PATTERN_KEYWORDS = [
        "pattern",
        "node",
        "effect",
        "compute",
        "reducer",
        "orchestrator",
        "onex",
        "template",
        "implementation",
        "approach",
    ]

    # Sentiment indicators
    POSITIVE_INDICATORS = [
        "good",
        "excellent",
        "great",
        "perfect",
        "nice",
        "approved",
        "lgtm",
        "looks good",
        "well done",
        "clean",
        "solid",
    ]

    NEGATIVE_INDICATORS = [
        "bad",
        "poor",
        "wrong",
        "incorrect",
        "issue",
        "problem",
        "bug",
        "broken",
        "needs work",
        "refactor",
        "change",
        "fix",
    ]

    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        langextract_base_url: str = "http://archon-langextract:8156",
        correlation_id: Optional[uuid.UUID] = None,
    ):
        """
        Initialize PR intelligence extractor.

        Args:
            db_host: Database host
            db_port: Database port
            db_name: Database name
            db_user: Database user
            db_password: Database password
            langextract_base_url: LangExtract service URL
            correlation_id: Optional correlation ID for tracing
        """
        self.db_config = {
            "host": db_host,
            "port": db_port,
            "database": db_name,
            "user": db_user,
            "password": db_password,
        }
        self.langextract_base_url = langextract_base_url
        self.correlation_id = correlation_id or uuid.uuid4()

        # Connection pool (initialized in async context)
        self.pool: Optional[asyncpg.Pool] = None
        self.langextract_client: Optional[ClientLangextractHttp] = None

        logger.info(
            f"PRIntelligenceExtractor initialized (correlation_id={self.correlation_id})"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Create database and langextract connections."""
        # Database pool
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                **self.db_config, min_size=2, max_size=10
            )
            logger.info("Database connection pool created")

        # LangExtract client
        if self.langextract_client is None:
            self.langextract_client = ClientLangextractHttp(
                base_url=self.langextract_base_url
            )
            await self.langextract_client.connect()
            logger.info("LangExtract client connected")

    async def disconnect(self):
        """Close connections."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

        if self.langextract_client:
            await self.langextract_client.close()
            self.langextract_client = None
            logger.info("LangExtract client disconnected")

    async def analyze_pr(
        self,
        repository: str,
        pr_number: int,
        min_confidence: float = 0.5,
    ) -> PRIntelligenceMetrics:
        """
        Analyze a single PR and extract pattern intelligence.

        Args:
            repository: GitHub repository (owner/repo)
            pr_number: PR number
            min_confidence: Minimum confidence for pattern mentions (0.0-1.0)

        Returns:
            PRIntelligenceMetrics with processing statistics
        """
        import time

        start_time = time.time()

        metrics = PRIntelligenceMetrics()

        try:
            # 1. Fetch PR data from GitHub
            pr_data = await self._fetch_pr_data(repository, pr_number)
            if not pr_data:
                logger.error(f"Failed to fetch PR data for {repository}#{pr_number}")
                metrics.errors += 1
                return metrics

            metrics.prs_analyzed += 1

            # 2. Extract text content
            text_contents = self._extract_text_content(pr_data)

            # 3. Analyze each text content with langextract
            all_mentions = []
            for content_type, text in text_contents:
                if not text or len(text.strip()) < 10:
                    continue

                # Use langextract for semantic analysis
                try:
                    semantic_result = await self.langextract_client.analyze_semantic(
                        content=text,
                        context="code review pattern analysis",
                        min_confidence=min_confidence,
                    )

                    # Extract pattern mentions from semantic concepts
                    mentions = self._extract_pattern_mentions(
                        semantic_result=semantic_result,
                        text=text,
                        mention_type=content_type,
                        pr_data=pr_data,
                    )

                    all_mentions.extend(mentions)
                    metrics.mentions_extracted += len(mentions)

                except Exception as e:
                    logger.error(f"Langextract analysis failed: {e}", exc_info=True)
                    metrics.errors += 1

            # 4. Correlate mentions with database patterns
            correlated_mentions = await self._correlate_with_patterns(all_mentions)
            metrics.patterns_found += len(
                set(m["pattern_id"] for m in correlated_mentions if m.get("pattern_id"))
            )

            # 5. Store in database
            stored = await self._store_mentions(correlated_mentions)
            metrics.mentions_stored += stored

            metrics.processing_time_ms = (time.time() - start_time) * 1000

            logger.info(
                f"PR analysis complete: {repository}#{pr_number}, "
                f"{metrics.mentions_extracted} mentions extracted, "
                f"{metrics.patterns_found} patterns found, "
                f"{metrics.mentions_stored} stored "
                f"({metrics.processing_time_ms:.2f}ms)"
            )

        except Exception as e:
            logger.error(
                f"Error analyzing PR {repository}#{pr_number}: {e}", exc_info=True
            )
            metrics.errors += 1

        return metrics

    async def _fetch_pr_data(
        self, repository: str, pr_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch PR data from GitHub using gh CLI.

        Args:
            repository: GitHub repository (owner/repo)
            pr_number: PR number

        Returns:
            Dictionary with PR data or None if failed
        """
        try:
            # Fetch PR details
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--repo",
                    repository,
                    "--json",
                    "title,body,state,reviews,comments,createdAt,mergedAt,url",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            pr_data = json.loads(result.stdout)

            # Enrich with review comments
            review_comments_result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repository}/pulls/{pr_number}/comments",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            pr_data["review_comments"] = json.loads(review_comments_result.stdout)

            return pr_data

        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub CLI error: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch PR data: {e}", exc_info=True)
            return None

    def _extract_text_content(self, pr_data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """
        Extract text content from PR data.

        Args:
            pr_data: PR data from GitHub

        Returns:
            List of (mention_type, text) tuples
        """
        contents = []

        # PR description
        if pr_data.get("body"):
            contents.append(("description", pr_data["body"]))

        # Reviews
        for review in pr_data.get("reviews", []):
            if review.get("body"):
                contents.append(("review_comment", review["body"]))

        # General comments
        for comment in pr_data.get("comments", []):
            if comment.get("body"):
                contents.append(("review_comment", comment["body"]))

        # Inline review comments
        for comment in pr_data.get("review_comments", []):
            if comment.get("body"):
                contents.append(("inline_comment", comment["body"]))

        return contents

    def _extract_pattern_mentions(
        self,
        semantic_result: Any,
        text: str,
        mention_type: str,
        pr_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract pattern mentions from langextract semantic analysis.

        Args:
            semantic_result: SemanticAnalysisResult from langextract
            text: Original text
            mention_type: Type of mention (description, review_comment, etc.)
            pr_data: Full PR data

        Returns:
            List of pattern mention dictionaries
        """
        mentions = []

        # Extract concepts that might be pattern names
        for concept in semantic_result.concepts:
            # Check if concept mentions pattern-related keywords
            concept_text = concept.name.lower()

            if any(keyword in concept_text for keyword in self.PATTERN_KEYWORDS):
                # Extract context around the mention
                extracted_text = self._extract_context(text, concept.name, window=200)

                # Analyze sentiment
                sentiment = self._analyze_sentiment(extracted_text)

                mention = {
                    "pattern_name": concept.name,
                    "mention_type": mention_type,
                    "extracted_text": extracted_text,
                    "full_context": text[:1000],  # Limit context size
                    "sentiment": sentiment,
                    "confidence_score": concept.confidence,
                    "pr_data": pr_data,
                }

                mentions.append(mention)

        # Also check domains and themes for pattern mentions
        for domain in getattr(semantic_result, "domains", []):
            if any(keyword in domain.name.lower() for keyword in self.PATTERN_KEYWORDS):
                extracted_text = self._extract_context(text, domain.name, window=200)
                sentiment = self._analyze_sentiment(extracted_text)

                mention = {
                    "pattern_name": domain.name,
                    "mention_type": mention_type,
                    "extracted_text": extracted_text,
                    "full_context": text[:1000],
                    "sentiment": sentiment,
                    "confidence_score": domain.confidence,
                    "pr_data": pr_data,
                }

                mentions.append(mention)

        return mentions

    def _extract_context(self, text: str, pattern_name: str, window: int = 200) -> str:
        """
        Extract context around a pattern mention.

        Args:
            text: Full text
            pattern_name: Pattern name to find
            window: Character window around the mention

        Returns:
            Extracted context string
        """
        # Find pattern name in text (case insensitive)
        match = re.search(re.escape(pattern_name), text, re.IGNORECASE)
        if not match:
            # Return first N characters if not found
            return text[:window]

        start = max(0, match.start() - window // 2)
        end = min(len(text), match.end() + window // 2)

        return text[start:end]

    def _analyze_sentiment(self, text: str) -> str:
        """
        Analyze sentiment of text (positive/negative/neutral).

        Simple keyword-based sentiment analysis.

        Args:
            text: Text to analyze

        Returns:
            "positive", "negative", or "neutral"
        """
        text_lower = text.lower()

        positive_count = sum(
            1 for indicator in self.POSITIVE_INDICATORS if indicator in text_lower
        )
        negative_count = sum(
            1 for indicator in self.NEGATIVE_INDICATORS if indicator in text_lower
        )

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    async def _correlate_with_patterns(
        self, mentions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Correlate pattern mentions with actual patterns in database.

        Fuzzy matching on pattern names.

        Args:
            mentions: List of pattern mentions

        Returns:
            Mentions with pattern_id added (if found)
        """
        if not self.pool:
            await self.connect()

        correlated = []

        async with self.pool.acquire() as conn:
            for mention in mentions:
                pattern_name = mention["pattern_name"]

                # Fuzzy search for pattern in database
                # Try exact match first
                pattern = await conn.fetchrow(
                    """
                    SELECT id, pattern_id, pattern_name, pattern_type
                    FROM pattern_lineage_nodes
                    WHERE pattern_name ILIKE $1
                    ORDER BY overall_quality DESC NULLS LAST
                    LIMIT 1
                    """,
                    f"%{pattern_name}%",
                )

                if pattern:
                    mention["pattern_id"] = pattern["id"]
                    mention["db_pattern_id"] = pattern["pattern_id"]
                    mention["db_pattern_name"] = pattern["pattern_name"]
                    mention["db_pattern_type"] = pattern["pattern_type"]
                    correlated.append(mention)
                else:
                    # No pattern found - still store but without pattern_id
                    logger.debug(f"No pattern found for mention: {pattern_name}")
                    mention["pattern_id"] = None
                    correlated.append(mention)

        return correlated

    async def _store_mentions(self, mentions: List[Dict[str, Any]]) -> int:
        """
        Store pattern mentions in database.

        Args:
            mentions: List of correlated pattern mentions

        Returns:
            Number of mentions stored
        """
        if not self.pool:
            await self.connect()

        stored = 0

        async with self.pool.acquire() as conn:
            for mention in mentions:
                # Skip mentions without pattern_id
                if not mention.get("pattern_id"):
                    continue

                pr_data = mention["pr_data"]

                # Calculate PR metrics
                pr_merged = pr_data.get("state") == "merged"
                time_to_merge_hours = None

                if pr_merged and pr_data.get("createdAt") and pr_data.get("mergedAt"):
                    created = datetime.fromisoformat(
                        pr_data["createdAt"].replace("Z", "+00:00")
                    )
                    merged = datetime.fromisoformat(
                        pr_data["mergedAt"].replace("Z", "+00:00")
                    )
                    time_to_merge_hours = (merged - created).total_seconds() / 3600

                # Determine PR outcome
                pr_outcome = self._determine_pr_outcome(pr_data)

                try:
                    await conn.execute(
                        """
                        INSERT INTO pattern_pr_intelligence (
                            pattern_id, pr_number, pr_repository, pr_url,
                            mention_type, sentiment, extracted_text, full_context,
                            pr_outcome, pr_merged, time_to_merge_hours,
                            correlation_id, confidence_score, metadata
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                        )
                        """,
                        mention["pattern_id"],
                        pr_data.get("number"),
                        (
                            mention["pr_data"]
                            .get("url", "")
                            .split("/repos/")[1]
                            .split("/pulls/")[0]
                            if "/repos/" in mention["pr_data"].get("url", "")
                            else "unknown/unknown"
                        ),
                        pr_data.get("url"),
                        mention["mention_type"],
                        mention["sentiment"],
                        mention["extracted_text"],
                        mention["full_context"],
                        pr_outcome,
                        pr_merged,
                        time_to_merge_hours,
                        self.correlation_id,
                        mention.get("confidence_score", 0.0),
                        {
                            "db_pattern_id": mention.get("db_pattern_id"),
                            "db_pattern_name": mention.get("db_pattern_name"),
                            "db_pattern_type": mention.get("db_pattern_type"),
                        },
                    )
                    stored += 1

                except Exception as e:
                    logger.error(f"Error storing mention: {e}", exc_info=True)

        return stored

    def _determine_pr_outcome(self, pr_data: Dict[str, Any]) -> str:
        """
        Determine PR outcome from PR data.

        Args:
            pr_data: PR data from GitHub

        Returns:
            PR outcome string
        """
        state = pr_data.get("state", "").lower()

        if state == "merged":
            return "merged"
        elif state == "closed":
            return "closed"

        # Check reviews
        reviews = pr_data.get("reviews", [])
        if not reviews:
            return "pending"

        # Check for approval
        approved = any(r.get("state") == "APPROVED" for r in reviews)
        changes_requested = any(r.get("state") == "CHANGES_REQUESTED" for r in reviews)

        if approved:
            return "approved"
        elif changes_requested:
            return "changes_requested"
        else:
            return "commented"
