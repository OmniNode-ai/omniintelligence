#!/usr/bin/env python3
"""
Pattern Ingestion Script - Step 4 of Pattern Migration

Ingests extracted patterns from JSON file into pattern_lineage_nodes table
with quality scores and metadata.

Usage:
    python3 scripts/ingest_extracted_patterns.py

Input:
    /tmp/extracted_patterns.json - Patterns from Step 3 extraction

Output:
    Database records in pattern_lineage_nodes table
    Ingestion statistics report
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import asyncpg


async def ingest_patterns():
    """Ingest extracted patterns into database with quality scoring."""

    print("=" * 80)
    print("Pattern Ingestion Script - Step 4")
    print("=" * 80)
    print()

    # Load extracted patterns
    input_file = Path("/tmp/extracted_patterns.json")
    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        return

    with open(input_file, "r") as f:
        data = json.load(f)

    patterns = data.get("patterns", [])
    print(f"📊 Loaded {len(patterns)} patterns to ingest")
    print()

    # Connect to database
    print("🔌 Connecting to database...")
    try:
        conn = await asyncpg.connect(
            host="192.168.86.200",
            port=5436,
            user="postgres",
            password="omninode_remote_2024_secure",
            database="omninode_bridge",
        )
        print("✅ Database connection established")
        print()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return

    # Initialize counters
    ingested = 0
    skipped = 0
    errors = 0
    quality_scores = []
    pattern_types = {}

    # Generate base lineage ID for this ingestion batch
    batch_lineage_id = uuid.uuid4()
    batch_correlation_id = uuid.uuid4()

    print("🔄 Starting ingestion...")
    print(f"   Batch Lineage ID: {batch_lineage_id}")
    print(f"   Batch Correlation ID: {batch_correlation_id}")
    print()

    for i, pattern in enumerate(patterns, 1):
        try:
            pattern_name = pattern.get("pattern_name", "unknown")

            # Skip patterns with .py in name (likely file names, not pattern names)
            if ".py" in pattern_name:
                print(
                    f"⚠️  Skipping pattern {i}/{len(patterns)}: {pattern_name} (contains .py)"
                )
                skipped += 1
                continue

            # Generate pattern_id from pattern_name (deterministic)
            pattern_id = (
                f"pattern_{hashlib.md5(pattern_name.encode()).hexdigest()[:16]}"
            )

            # Check if pattern already exists
            exists = await conn.fetchval(
                "SELECT COUNT(*) FROM pattern_lineage_nodes WHERE pattern_id = $1",
                pattern_id,
            )

            if exists:
                print(
                    f"ℹ️  Skipping pattern {i}/{len(patterns)}: {pattern_name} (already exists)"
                )
                skipped += 1
                continue

            # Calculate quality scores from pattern data
            complexity = pattern.get("complexity", 5)
            maintainability = pattern.get("maintainability_index", 50)
            confidence = pattern.get("confidence", 0.5)

            # Normalize complexity to 0-1 scale (inverse - lower complexity is better)
            # Typical complexity range: 1-20+
            complexity_score = max(0.0, min(1.0, 1.0 - (complexity / 20.0)))

            # Normalize maintainability to 0-1 scale
            # Maintainability index typically 0-100, where higher is better
            documentation_score = max(0.0, min(1.0, maintainability / 100.0))
            maintainability_score = documentation_score  # Same value, different column

            # Use confidence as-is (already 0-1)
            confidence_score = max(0.0, min(1.0, confidence))

            # Calculate overall quality as weighted average
            overall_quality = (
                complexity_score * 0.3
                + documentation_score * 0.4
                + confidence_score * 0.3
            )

            # Prepare pattern_data (main pattern content)
            pattern_data = {
                "implementation": pattern.get("implementation", ""),
                "category": pattern.get("category", "unknown"),
                "confidence": confidence,
                "raw_complexity": complexity,
                "raw_maintainability": maintainability,
            }

            # Prepare metadata (extraction metadata)
            metadata = {
                "file_path": pattern.get("file_path", "unknown"),
                "line_range": pattern.get("line_range", [0, 0]),
                "tags": pattern.get("tags", []),
                "is_async": pattern.get("is_async", False),
                "decorators": pattern.get("decorators", []),
                "complexity_grade": pattern.get("complexity_grade", "C"),
                "docstring": pattern.get("docstring", ""),
                "ingestion_timestamp": datetime.utcnow().isoformat(),
                "extraction_source": "step3_pattern_extraction",
                "ingestion_batch": str(batch_correlation_id),
            }

            # Insert pattern
            await conn.execute(
                """
                INSERT INTO pattern_lineage_nodes (
                    pattern_id, pattern_name, pattern_type,
                    lineage_id, correlation_id,
                    pattern_data, metadata,
                    complexity_score, documentation_score, maintainability_score,
                    overall_quality, usage_count,
                    file_path, language,
                    source_system, source_user, event_type
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                """,
                pattern_id,
                pattern_name,
                pattern.get("pattern_type", "unknown"),
                batch_lineage_id,
                batch_correlation_id,
                json.dumps(pattern_data),
                json.dumps(metadata),
                complexity_score,
                documentation_score,
                maintainability_score,
                overall_quality,
                0,  # initial usage_count
                pattern.get("file_path", "unknown"),
                "python",  # assume Python for now
                "pattern_extraction_step3",
                "system",
                "pattern_ingested",
            )

            print(
                f"✅ Ingested pattern {i}/{len(patterns)}: {pattern_name} (quality: {overall_quality:.2f})"
            )
            ingested += 1
            quality_scores.append(overall_quality)

            # Track pattern types
            pattern_type = pattern.get("pattern_type", "unknown")
            pattern_types[pattern_type] = pattern_types.get(pattern_type, 0) + 1

        except Exception as e:
            print(
                f"❌ Error ingesting pattern {i}/{len(patterns)}: {pattern.get('pattern_name', 'unknown')}"
            )
            print(f"   Error: {e}")
            errors += 1

    await conn.close()

    # Calculate statistics
    print()
    print("=" * 80)
    print("INGESTION COMPLETE")
    print("=" * 80)
    print()
    print(f"✅ Successfully ingested: {ingested} patterns")
    print(f"⚠️  Skipped (duplicates/invalid): {skipped} patterns")
    print(f"❌ Errors: {errors} patterns")
    print(f"📊 Total processed: {len(patterns)} patterns")
    print()

    if quality_scores:
        avg_quality = sum(quality_scores) / len(quality_scores)
        min_quality = min(quality_scores)
        max_quality = max(quality_scores)

        print("QUALITY SCORE DISTRIBUTION")
        print("-" * 40)
        print(f"Average Quality: {avg_quality:.3f}")
        print(f"Minimum Quality: {min_quality:.3f}")
        print(f"Maximum Quality: {max_quality:.3f}")
        print()

    if pattern_types:
        print("PATTERN TYPE DISTRIBUTION")
        print("-" * 40)
        for pattern_type, count in sorted(
            pattern_types.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / ingested * 100) if ingested > 0 else 0
            print(f"{pattern_type:30s}: {count:3d} ({percentage:5.1f}%)")
        print()

    print("=" * 80)
    print(f"Ingestion completed at: {datetime.utcnow().isoformat()}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(ingest_patterns())
