#!/usr/bin/env python3
"""
Pattern Ingestion Script - Ingest all 1,102 extracted patterns to database

This script ingests real patterns extracted from the OmniClaude codebase
into the pattern_lineage_nodes table with proper quality scoring.

Usage:
    python3 ingest_all_patterns.py

Database:
    Host: 192.168.86.200:5436
    Database: omninode_bridge
    Table: pattern_lineage_nodes
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import asyncpg


async def calculate_quality_scores(pattern: Dict[str, Any]) -> Tuple[float, float]:
    """
    Calculate quality scores from pattern data.

    Args:
        pattern: Pattern dictionary with complexity and maintainability data

    Returns:
        Tuple of (complexity_score, overall_quality)
    """
    # Get raw values
    confidence = pattern.get("confidence", 0.7)
    complexity = pattern.get("complexity", 5)
    maintainability_index = pattern.get("maintainability_index", 50.0)

    # Normalize complexity to 0-1 (lower is better)
    # Assuming max complexity of 20 for real-world code
    complexity_score = max(0.0, min(1.0, 1.0 - (complexity / 20.0)))

    # Normalize maintainability index to 0-1
    # MI ranges from 0-100, higher is better
    maintainability_score = maintainability_index / 100.0

    # Calculate overall quality as weighted average
    # 40% confidence, 30% maintainability, 30% complexity
    overall_quality = (
        0.4 * confidence + 0.3 * maintainability_score + 0.3 * complexity_score
    )

    return complexity_score, overall_quality


async def ingest_all_patterns() -> Dict[str, int]:
    """
    Ingest all 1,102 patterns from extracted file to database.

    Returns:
        Dictionary with ingestion statistics
    """
    # Configuration
    input_file = "/tmp/omniclaude_patterns.json"
    db_config = {
        "host": "192.168.86.200",
        "port": 5436,
        "user": "postgres",
        "password": "omninode_remote_2024_secure",
        "database": "omninode_bridge",
    }

    print("=" * 70)
    print("Pattern Ingestion - OmniClaude Extracted Patterns")
    print("=" * 70)

    # Load patterns
    print(f"\n📂 Loading patterns from {input_file}...")
    try:
        with open(input_file, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load pattern file: {e}")
        return {"error": str(e)}

    patterns = data.get("patterns", [])
    metadata = data.get("metadata", {})

    print(f"✅ Loaded {len(patterns)} patterns")
    print(f"\nExtraction Metadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    # Connect to database
    print(f"\n🔌 Connecting to database...")
    try:
        conn = await asyncpg.connect(**db_config)
        print(
            f"✅ Connected to {db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return {"error": str(e)}

    # Statistics
    batch_id = str(uuid.uuid4())
    stats = {"total": len(patterns), "ingested": 0, "skipped": 0, "errors": 0}
    errors = []

    print(f"\n🚀 Starting ingestion (batch_id: {batch_id})...")
    print(f"Progress updates every 100 patterns...\n")

    # Process each pattern
    for i, pattern in enumerate(patterns):
        try:
            pattern_name = pattern.get("pattern_name", f"pattern_{i}")

            # Generate pattern_id from pattern_name (make it unique)
            pattern_id = f"omniclaude_{pattern_name}"

            # Check if pattern already exists (by pattern_id or pattern_name)
            exists = await conn.fetchval(
                "SELECT COUNT(*) FROM pattern_lineage_nodes WHERE pattern_id = $1 OR pattern_name = $2",
                pattern_id,
                pattern_name,
            )

            if exists > 0:
                stats["skipped"] += 1
                continue

            # Extract pattern data
            pattern_type = pattern.get("pattern_type", "function_pattern")
            category = pattern.get("category", "unknown")
            file_path = pattern.get("file_path", "")
            line_range = pattern.get("line_range", [])

            # Calculate quality scores
            complexity_score, overall_quality = await calculate_quality_scores(pattern)

            # Build pattern_data JSONB (contains implementation and core details)
            pattern_data = {
                "implementation": pattern.get("implementation", ""),
                "docstring": pattern.get("docstring", ""),
                "is_async": pattern.get("is_async", False),
                "decorators": pattern.get("decorators", []),
                "line_range": line_range,
            }

            # Build metadata JSONB (contains extraction metadata)
            pattern_metadata = {
                "batch_id": batch_id,
                "source": "omniclaude_extraction",
                "source_codebase": pattern.get("source_codebase", "omniclaude"),
                "category": category,
                "tags": pattern.get("tags", []),
                "complexity": pattern.get("complexity", 0),
                "complexity_grade": pattern.get("complexity_grade", ""),
                "maintainability_index": pattern.get("maintainability_index", 0.0),
                "confidence": pattern.get("confidence", 0.7),
                "extraction_metadata": metadata,
            }

            # Generate correlation_id and lineage_id
            correlation_id = uuid.uuid4()
            lineage_id = uuid.uuid4()

            # Insert pattern
            await conn.execute(
                """
                INSERT INTO pattern_lineage_nodes (
                    id,
                    pattern_id,
                    pattern_name,
                    pattern_type,
                    pattern_version,
                    lineage_id,
                    generation,
                    correlation_id,
                    pattern_data,
                    metadata,
                    file_path,
                    language,
                    complexity_score,
                    overall_quality,
                    usage_count,
                    created_at,
                    source_system,
                    event_type
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            """,
                uuid.uuid4(),  # id
                pattern_id,  # pattern_id
                pattern_name,  # pattern_name
                pattern_type,  # pattern_type
                "1.0.0",  # pattern_version
                lineage_id,  # lineage_id
                1,  # generation
                correlation_id,  # correlation_id
                json.dumps(pattern_data),  # pattern_data (JSONB)
                json.dumps(pattern_metadata),  # metadata (JSONB)
                file_path,  # file_path
                "python",  # language
                complexity_score,  # complexity_score
                overall_quality,  # overall_quality
                0,  # usage_count
                datetime.now(),  # created_at
                "omniclaude_extraction",  # source_system
                "pattern_extracted",  # event_type
            )

            stats["ingested"] += 1

            # Progress updates
            if (i + 1) % 100 == 0:
                progress = ((i + 1) / len(patterns)) * 100
                print(
                    f"Progress: {i + 1}/{len(patterns)} ({progress:.1f}%) - "
                    f"Ingested: {stats['ingested']}, Skipped: {stats['skipped']}"
                )

        except Exception as e:
            stats["errors"] += 1
            error_msg = (
                f"Pattern {i} ({pattern.get('pattern_name', 'unknown')}): {str(e)}"
            )
            errors.append(error_msg)

            # Log first 10 errors immediately
            if len(errors) <= 10:
                print(f"⚠️  Error: {error_msg}")

    # Close connection
    await conn.close()

    # Print results
    print("\n" + "=" * 70)
    print("INGESTION COMPLETE")
    print("=" * 70)
    print(f"\nStatistics:")
    print(f"  Total patterns:      {stats['total']}")
    print(f"  Successfully ingested: {stats['ingested']}")
    print(f"  Skipped (duplicates):  {stats['skipped']}")
    print(f"  Errors:                {stats['errors']}")
    print(f"  Success rate:          {(stats['ingested'] / stats['total'] * 100):.1f}%")
    print(f"\nBatch ID: {batch_id}")

    if errors:
        print(f"\n⚠️  First 10 errors:")
        for err in errors[:10]:
            print(f"  - {err}")

        if len(errors) > 10:
            print(f"\n  ... and {len(errors) - 10} more errors")

    return stats


async def main():
    """Main entry point"""
    stats = await ingest_all_patterns()

    if "error" in stats:
        print(f"\n❌ Ingestion failed: {stats['error']}")
        return 1

    # Success if more than 95% ingested
    success_rate = stats["ingested"] / stats["total"] if stats["total"] > 0 else 0

    if success_rate >= 0.95:
        print(f"\n✅ Ingestion successful! ({success_rate:.1%} success rate)")
        return 0
    else:
        print(
            f"\n⚠️  Ingestion completed with warnings ({success_rate:.1%} success rate)"
        )
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
