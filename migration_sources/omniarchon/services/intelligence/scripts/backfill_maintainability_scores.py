#!/usr/bin/env python3
"""
Backfill Maintainability Scores for Pattern Lineage Nodes

Purpose: Calculate maintainability_score for all patterns in pattern_lineage_nodes
         that currently have NULL maintainability_score.

Formula: maintainability_score = (coupling_score * 0.5) + (cohesion_score * 0.5)

Migration Date: 2025-10-29
ONEX Compliance: Yes
"""

import ast
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg
from radon.complexity import cc_visit
from radon.metrics import mi_visit


class MaintainabilityScorer:
    """Calculate maintainability scores using coupling and cohesion analysis."""

    def calculate_maintainability_score(self, tree: ast.AST, code: str) -> float:
        """
        Calculate maintainability score based on coupling and cohesion.

        Scoring:
        - Low coupling (few dependencies): +0.5
        - High cohesion (single responsibility): +0.5

        Args:
            tree: AST of the code
            code: Source code string

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Check coupling (number of imports)
        coupling_score = self._calculate_coupling_score(tree)
        score += coupling_score * 0.5

        # Check cohesion (single responsibility indicator)
        cohesion_score = self._calculate_cohesion_score(tree, code)
        score += cohesion_score * 0.5

        return score

    def _calculate_coupling_score(self, tree: ast.AST) -> float:
        """
        Calculate coupling score based on number of imports.

        Low coupling (0-5 imports): 1.0
        Medium coupling (6-10 imports): 0.6
        High coupling (10+ imports): 0.3
        """
        import_count = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_count += 1

        if import_count <= 5:
            return 1.0
        elif import_count <= 10:
            return 0.6
        else:
            return 0.3

    def _calculate_cohesion_score(self, tree: ast.AST, code: str) -> float:
        """
        Calculate cohesion score using maintainability index.

        Uses radon's maintainability index (0-100):
        - MI >= 20: High cohesion (1.0)
        - MI 10-20: Medium cohesion (0.6)
        - MI < 10: Low cohesion (0.3)
        """
        try:
            # Calculate maintainability index using radon
            mi_results = mi_visit(code, multi=True)

            if not mi_results:
                return 0.5  # Neutral score

            # Get average MI across all functions/classes
            avg_mi = sum(result.mi for result in mi_results) / len(mi_results)

            # Map MI to cohesion score
            if avg_mi >= 20:
                return 1.0
            elif avg_mi >= 10:
                return 0.6
            else:
                return 0.3

        except Exception:
            # Fallback: use complexity as proxy
            try:
                complexity_results = cc_visit(code)
                if complexity_results:
                    avg_complexity = sum(
                        r.complexity for r in complexity_results
                    ) / len(complexity_results)

                    if avg_complexity <= 5:
                        return 1.0
                    elif avg_complexity <= 10:
                        return 0.6
                    else:
                        return 0.3
            except Exception:
                pass

            return 0.5  # Default neutral score


async def extract_code_from_pattern(pattern: Dict[str, Any]) -> Optional[str]:
    """
    Extract source code from pattern_data.

    Args:
        pattern: Pattern record with pattern_data

    Returns:
        Source code string or None
    """
    pattern_data = pattern.get("pattern_data")

    if not pattern_data:
        return None

    # Parse pattern_data if it's a JSON string (asyncpg returns JSONB as string)
    if isinstance(pattern_data, str):
        try:
            pattern_data = json.loads(pattern_data)
        except json.JSONDecodeError:
            return None

    # Try to get code from pattern_data['implementation']
    if isinstance(pattern_data, dict):
        if "implementation" in pattern_data and pattern_data["implementation"]:
            return pattern_data["implementation"]

        # Try to get code from pattern_data['code']
        if "code" in pattern_data and pattern_data["code"]:
            return pattern_data["code"]

        # Try to get code from pattern_data['source_code']
        if "source_code" in pattern_data and pattern_data["source_code"]:
            return pattern_data["source_code"]

    return None


async def backfill_maintainability_scores(
    host: str = "192.168.86.200",
    port: int = 5436,
    user: str = "postgres",
    password: str = "omninode_remote_2024_secure",
    database: str = "omninode_bridge",
    batch_size: int = 100,
    dry_run: bool = False,
):
    """
    Backfill maintainability scores for all patterns.

    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        database: Database name
        batch_size: Number of patterns to process before committing
        dry_run: If True, don't actually update the database
    """
    print("=" * 80)
    print("Maintainability Score Backfill Script")
    print("=" * 80)
    print(f"Database: {host}:{port}/{database}")
    print(f"Batch Size: {batch_size}")
    print(f"Dry Run: {dry_run}")
    print("=" * 80)
    print()

    # Connect to database
    print("Connecting to database...")
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=database
    )
    print("✅ Connected to database")
    print()

    # Fetch patterns without maintainability_score
    print("Fetching patterns without maintainability_score...")
    patterns = await conn.fetch(
        """
        SELECT id, pattern_name, pattern_data
        FROM pattern_lineage_nodes
        WHERE overall_quality IS NOT NULL
          AND maintainability_score IS NULL
        ORDER BY created_at
    """
    )

    total_patterns = len(patterns)
    print(f"✅ Found {total_patterns} patterns to process")
    print()

    if total_patterns == 0:
        print("No patterns to process. Exiting.")
        await conn.close()
        return

    # Initialize scorer
    scorer = MaintainabilityScorer()

    # Process patterns
    updated = 0
    skipped = 0
    errors = 0

    score_distribution = {}  # Track score distribution for reporting

    print("Processing patterns...")
    print("-" * 80)

    for i, pattern in enumerate(patterns):
        try:
            # Extract code
            code = await extract_code_from_pattern(pattern)

            if not code:
                print(
                    f"⚠ [{i+1}/{total_patterns}] {pattern['pattern_name']}: No code found"
                )
                skipped += 1
                continue

            # Parse code to AST
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                print(
                    f"⚠ [{i+1}/{total_patterns}] {pattern['pattern_name']}: Syntax error - {e}"
                )
                skipped += 1
                continue

            # Calculate maintainability score
            score = scorer.calculate_maintainability_score(tree, code)

            # Round to 4 decimal places
            score = round(score, 4)

            # Track distribution
            score_bucket = round(score, 1)
            score_distribution[score_bucket] = (
                score_distribution.get(score_bucket, 0) + 1
            )

            # Update database (unless dry run)
            if not dry_run:
                await conn.execute(
                    """
                    UPDATE pattern_lineage_nodes
                    SET maintainability_score = $1
                    WHERE id = $2
                """,
                    score,
                    pattern["id"],
                )

            updated += 1

            # Progress reporting
            if (i + 1) % batch_size == 0:
                print(
                    f"✅ Progress: {i + 1}/{total_patterns} ({updated} updated, {skipped} skipped, {errors} errors)"
                )
            elif updated <= 10:  # Show first 10 updates
                print(
                    f"✅ [{i+1}/{total_patterns}] {pattern['pattern_name']}: score = {score:.4f}"
                )

        except Exception as e:
            print(f"❌ [{i+1}/{total_patterns}] {pattern['pattern_name']}: Error - {e}")
            errors += 1

    await conn.close()

    # Final report
    print()
    print("=" * 80)
    print("Backfill Complete!")
    print("=" * 80)
    print(f"Total Patterns: {total_patterns}")
    print(f"✅ Updated: {updated}")
    print(f"⚠ Skipped: {skipped}")
    print(f"❌ Errors: {errors}")
    print()

    if updated > 0:
        print("Score Distribution:")
        print("-" * 40)
        for score_bucket in sorted(score_distribution.keys()):
            count = score_distribution[score_bucket]
            pct = (count / updated) * 100
            bar = "█" * int(pct / 2)
            print(f"  {score_bucket:.1f}: {count:4d} ({pct:5.1f}%) {bar}")
        print()

    if dry_run:
        print("⚠️  DRY RUN MODE - No changes were made to the database")

    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill maintainability scores for patterns"
    )
    parser.add_argument("--host", default="192.168.86.200", help="Database host")
    parser.add_argument("--port", type=int, default=5436, help="Database port")
    parser.add_argument("--user", default="postgres", help="Database user")
    parser.add_argument(
        "--password", default="omninode_remote_2024_secure", help="Database password"
    )
    parser.add_argument("--database", default="omninode_bridge", help="Database name")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Batch size for progress reporting"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually update the database"
    )

    args = parser.parse_args()

    asyncio.run(
        backfill_maintainability_scores(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    )
