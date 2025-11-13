#!/usr/bin/env python3
"""
Identify files in Batch 161 that caused MessageSizeTooLargeError during omniclaude ingestion.

This script replicates the file discovery logic from bulk_ingest_repository.py
to identify the exact 25 files in batch 161.
"""

import sys
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.file_discovery import (
    DEFAULT_EXCLUDE_PATTERNS,
    DEFAULT_SUPPORTED_EXTENSIONS,
    FileDiscovery,
)


def main():
    # Configuration
    project_path = Path("/Volumes/PRO-G40/Code/omniclaude")
    batch_size = 25
    batch_index = 161

    # Calculate file range for batch 161
    start_index = batch_index * batch_size
    end_index = start_index + batch_size - 1

    print(f"=" * 80)
    print(f"IDENTIFYING BATCH 161 FILES")
    print(f"=" * 80)
    print(f"Project: {project_path}")
    print(f"Batch size: {batch_size}")
    print(f"Batch index: {batch_index}")
    print(f"File range: {start_index} to {end_index} (inclusive)")
    print(f"=" * 80)
    print()

    # Initialize file discovery with same defaults as bulk_ingest_repository.py
    file_discovery = FileDiscovery(
        supported_extensions=DEFAULT_SUPPORTED_EXTENSIONS,
        exclude_patterns=DEFAULT_EXCLUDE_PATTERNS,
        max_file_size=5 * 1024 * 1024,  # 5MB default
        follow_symlinks=False,
    )

    # Discover files
    print("🔍 Discovering files...")
    discovered_files, stats = file_discovery.discover(project_path)

    print(f"✅ Discovery complete:")
    print(f"   Total files found: {stats.filtered_files}")
    print(f"   Excluded files: {stats.excluded_files}")
    print(f"   Oversized files: {stats.oversized_files}")
    print(f"   Discovery time: {stats.discovery_duration_ms:.0f}ms")
    print()

    # Calculate total batches
    total_batches = (len(discovered_files) + batch_size - 1) // batch_size
    print(f"📦 Total batches: {total_batches} (batch 0 to {total_batches - 1})")
    print()

    # Check if batch 161 exists
    if batch_index >= total_batches:
        print(f"❌ ERROR: Batch {batch_index} does not exist!")
        print(f"   Total batches: {total_batches}")
        print(f"   Last batch: {total_batches - 1}")
        return 1

    # Extract batch 161 files
    batch_files = discovered_files[start_index : end_index + 1]

    print(f"=" * 80)
    print(f"BATCH 161 FILES ({len(batch_files)} files)")
    print(f"=" * 80)
    print()

    total_size = 0
    for i, file_info in enumerate(batch_files, start=start_index):
        size_kb = file_info.size_bytes / 1024
        size_mb = size_kb / 1024
        total_size += file_info.size_bytes

        # Highlight large files
        size_indicator = ""
        if size_mb >= 1.0:
            size_indicator = " 🔴 LARGE"
        elif size_kb >= 100:
            size_indicator = " 🟡"

        print(
            f"[{i:4d}] {size_kb:8.1f} KB | {file_info.language:12s} | {file_info.relative_path}{size_indicator}"
        )

    print()
    print(f"=" * 80)
    print(f"SUMMARY")
    print(f"=" * 80)
    print(f"Total files in batch: {len(batch_files)}")
    print(f"Total size: {total_size / 1024:.1f} KB ({total_size / 1024 / 1024:.2f} MB)")
    print(f"Average file size: {(total_size / len(batch_files)) / 1024:.1f} KB")
    print()

    # Find largest files in batch
    sorted_by_size = sorted(batch_files, key=lambda f: f.size_bytes, reverse=True)
    print(f"TOP 10 LARGEST FILES IN BATCH 161:")
    print(f"-" * 80)
    for i, file_info in enumerate(sorted_by_size[:10], 1):
        size_mb = file_info.size_bytes / 1024 / 1024
        print(
            f"{i:2d}. {size_mb:6.2f} MB | {file_info.language:12s} | {file_info.relative_path}"
        )
    print()

    # Language breakdown for batch
    from collections import Counter

    language_counts = Counter(f.language for f in batch_files)
    print(f"LANGUAGE BREAKDOWN:")
    print(f"-" * 80)
    for language, count in language_counts.most_common():
        print(f"{language:15s}: {count:3d} files")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
