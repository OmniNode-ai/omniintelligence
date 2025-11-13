#!/usr/bin/env python3
"""
Backfill Documentation Scores for Pattern Lineage Nodes

Purpose: Calculate documentation_score for all patterns in pattern_lineage_nodes
         that currently have NULL documentation_score.

Formula: documentation_score = (docstring_present * 0.5) + (type_hints_present * 0.5)

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


class DocumentationScorer:
    """Calculate documentation scores using docstring and type hint analysis."""

    def calculate_documentation_score(self, tree: ast.AST) -> float:
        """
        Calculate documentation score based on docstrings and type hints.

        Scoring:
        - Has docstring (module, class, or function): +0.5
        - Has type hints (return type or parameter annotations): +0.5

        Args:
            tree: AST of the code

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Check for docstring (0.5 points)
        if self._has_docstring(tree):
            score += 0.5

        # Check for type hints (0.5 points)
        if self._has_type_hints(tree):
            score += 0.5

        return score

    def _has_docstring(self, tree: ast.AST) -> bool:
        """
        Check if code has any docstring (module, class, or function level).

        Returns:
            True if any docstring found, False otherwise
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring and len(docstring.strip()) > 0:
                    return True
        return False

    def _has_type_hints(self, tree: ast.AST) -> bool:
        """
        Check if code has any type hints (return annotations or parameter annotations).

        Returns:
            True if any type hints found, False otherwise
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check return type hint
                if node.returns is not None:
                    return True

                # Check parameter type hints
                for arg in node.args.args:
                    if arg.annotation is not None:
                        return True

                # Check kwonly args
                for arg in node.args.kwonlyargs:
                    if arg.annotation is not None:
                        return True

                # Check vararg and kwarg
                if node.args.vararg and node.args.vararg.annotation:
                    return True
                if node.args.kwarg and node.args.kwarg.annotation:
                    return True

        return False


async def extract_code_from_pattern(pattern: Dict[str, Any]) -> Optional[str]:
    """
    Extract source code from pattern data or file.

    Args:
        pattern: Pattern record with pattern_data and file_path

    Returns:
        Source code string or None
    """
    # First try pattern_data for implementation
    pattern_data = pattern.get("pattern_data")

    if pattern_data:
        # Parse JSON if pattern_data is a string
        if isinstance(pattern_data, str):
            try:
                pattern_data = json.loads(pattern_data)
            except json.JSONDecodeError:
                pass

        # Try to get code from pattern_data['implementation']
        if isinstance(pattern_data, dict):
            if "implementation" in pattern_data and pattern_data["implementation"]:
                return pattern_data["implementation"]

            # Try to get code from pattern_data['code']
            if "code" in pattern_data and pattern_data["code"]:
                return pattern_data["code"]

    # Try to read from file_path column
    file_path_str = pattern.get("file_path")
    if file_path_str:
        try:
            file_path = Path(file_path_str)
            if file_path.exists() and file_path.is_file():
                return file_path.read_text()
        except Exception:
            pass

    return None


async def backfill_documentation_scores(
    host: str = "192.168.86.200",
    port: int = 5436,
    user: str = "postgres",
    password: str = "omninode_remote_2024_secure",
    database: str = "omninode_bridge",
    batch_size: int = 100,
    dry_run: bool = False,
):
    """
    Backfill documentation scores for all patterns.

    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        database: Database name
        batch_size: Number of patterns to process before reporting progress
        dry_run: If True, don't actually update the database
    """
    print("=" * 80)
    print("Documentation Score Backfill Script")
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

    # Fetch patterns without documentation_score
    print("Fetching patterns without documentation_score...")
    patterns = await conn.fetch(
        """
        SELECT id, pattern_name, pattern_data, file_path
        FROM pattern_lineage_nodes
        WHERE overall_quality IS NOT NULL
          AND documentation_score IS NULL
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
    scorer = DocumentationScorer()

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

            # Calculate documentation score
            score = scorer.calculate_documentation_score(tree)

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
                    SET documentation_score = $1
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
        description="Backfill documentation scores for patterns"
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
        backfill_documentation_scores(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    )
