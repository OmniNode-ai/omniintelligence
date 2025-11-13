"""
Code Intelligence Service

Service layer for code analysis metrics aggregation from pattern and quality data.
"""

import logging
import os
from typing import Any, Dict

# Centralized configuration
from config import settings

logger = logging.getLogger(__name__)


class CodeIntelligenceService:
    """
    Service for code intelligence metrics.

    Provides methods to aggregate code analysis data from pattern_templates
    and pattern_usage_events tables.
    """

    def __init__(self, db_pool=None):
        """
        Initialize code intelligence service.

        Args:
            db_pool: Database connection pool (optional, will use env vars if not provided)
        """
        self.db_pool = db_pool
        self.logger = logging.getLogger("CodeIntelligenceService")

    def _get_db_pool(self):
        """Get or create database connection pool."""
        if self.db_pool:
            return self.db_pool

        # Import here to avoid circular dependencies
        try:
            import asyncpg
        except ImportError:
            self.logger.error(
                "asyncpg not available - install with: pip install asyncpg"
            )
            raise

        # Get database URL from centralized config
        db_url = os.getenv(
            "TRACEABILITY_DB_URL_EXTERNAL",
            settings.get_postgres_dsn(async_driver=True),
        )

        return db_url

    async def get_code_analysis(self) -> Dict[str, Any]:
        """
        Get code analysis metrics aggregated from pattern data.

        Returns:
            Dictionary with code analysis metrics:
            - files_analyzed: Total number of patterns (representing code files)
            - avg_complexity: Average cyclomatic complexity
            - code_smells: Number of low-quality patterns
            - security_issues: Number of security-related issues
        """
        self.logger.info("Computing code analysis metrics")

        try:
            import asyncpg
        except ImportError:
            self.logger.error("asyncpg not available")
            return self._get_fallback_metrics()

        db_url = self._get_db_pool()

        try:
            # Create connection for this query
            conn = await asyncpg.connect(db_url, timeout=10.0)

            try:
                # Query 1: Get total patterns and average complexity
                row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as files_analyzed,
                        COALESCE(AVG(complexity_score), 0) as avg_complexity
                    FROM pattern_templates
                    WHERE is_deprecated = FALSE
                """
                )

                files_analyzed = row["files_analyzed"] if row else 0
                avg_complexity = float(row["avg_complexity"]) if row else 0.0

                # Query 2: Count code smells (patterns with low maintainability)
                # Code smells = patterns with maintainability_score < 0.5 or quality indicators
                code_smells_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as code_smells
                    FROM pattern_templates
                    WHERE is_deprecated = FALSE
                        AND (
                            maintainability_score < 0.5
                            OR pattern_type = 'anti-pattern'
                            OR success_rate < 0.6
                        )
                """
                )

                code_smells = code_smells_row["code_smells"] if code_smells_row else 0

                # Query 3: Count security issues (patterns tagged with security concerns)
                security_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as security_issues
                    FROM pattern_templates
                    WHERE is_deprecated = FALSE
                        AND (
                            'security' = ANY(tags)
                            OR pattern_type = 'security'
                            OR category LIKE '%security%'
                        )
                """
                )

                security_issues = security_row["security_issues"] if security_row else 0

                result = {
                    "files_analyzed": files_analyzed,
                    "avg_complexity": round(avg_complexity, 1),
                    "code_smells": code_smells,
                    "security_issues": security_issues,
                }

                self.logger.info(
                    f"Code analysis metrics computed | "
                    f"files={files_analyzed} | "
                    f"complexity={avg_complexity:.1f} | "
                    f"smells={code_smells} | "
                    f"security={security_issues}"
                )

                return result

            finally:
                await conn.close()

        except Exception as e:
            self.logger.error(f"Failed to compute code analysis metrics: {e}")
            # Return fallback metrics on error
            return self._get_fallback_metrics()

    def _get_fallback_metrics(self) -> Dict[str, Any]:
        """
        Return fallback metrics when database is unavailable.

        Returns:
            Dictionary with zero/default values
        """
        self.logger.warning("Using fallback metrics (database unavailable)")
        return {
            "files_analyzed": 0,
            "avg_complexity": 0.0,
            "code_smells": 0,
            "security_issues": 0,
        }
