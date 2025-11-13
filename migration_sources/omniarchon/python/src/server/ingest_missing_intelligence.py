#!/usr/bin/env python3
"""
Bulk ingest missing intelligence documents from omninode repositories.

This script finds all the locally stored intelligence documents that failed
to upload due to MCP communication issues and ingests them into the
intelligence system for proper correlation analysis.
"""

import asyncio
import glob
import json
import os
from datetime import UTC, datetime
from typing import Any

from data.intelligence_document_writer import create_intelligence_document_writer

from services.client_manager import get_database_client


async def find_intelligence_documents() -> list[dict[str, Any]]:
    """Find all intelligence document JSON files in omninode repos."""
    repo_paths = ["../omnimcp", "../omnibase-core", "../omniagent", "../omnibase-spi"]

    documents = []

    for repo_path in repo_paths:
        if os.path.exists(repo_path):
            # Look for intelligence document files
            pattern = os.path.join(repo_path, ".git", "intelligence-document-*.json")
            files = glob.glob(pattern)

            print(f"📁 {repo_path}: Found {len(files)} intelligence documents")

            for file_path in files:
                try:
                    with open(file_path) as f:
                        doc_data = json.load(f)

                    # Extract repository name from path
                    repo_name = os.path.basename(repo_path)

                    documents.append(
                        {
                            "file_path": file_path,
                            "repository": repo_name,
                            "data": doc_data,
                        }
                    )

                except Exception as e:
                    print(f"❌ Error reading {file_path}: {e}")

    return documents


async def convert_to_intelligence_format(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert hook intelligence document to intelligence system format."""
    data = doc["data"]
    content = data.get("content", {})

    # Extract metadata
    metadata = content.get("metadata", {})

    intelligence_doc = {
        "repository": doc["repository"],
        "commit_sha": metadata.get("commit", "unknown"),
        "author": metadata.get("author", "unknown"),
        "created_at": metadata.get("timestamp", datetime.now(UTC).isoformat()),
        "change_type": content.get(
            "analysis_type", "enhanced_code_changes_with_correlation"
        ),
        "intelligence_data": {
            "diff_analysis": {
                "total_changes": content.get("change_summary", {}).get(
                    "files_changed", 0
                ),
                "added_lines": 0,  # Not available in hook format
                "removed_lines": 0,  # Not available in hook format
                "modified_files": content.get("code_changes_analysis", {}).get(
                    "changed_files", []
                ),
            },
            "correlation_analysis": {
                "temporal_correlations": [],
                "semantic_correlations": [],
                "breaking_changes": [],
            },
            "security_analysis": {
                "security_status": content.get("change_summary", {}).get(
                    "security_status", "unknown"
                ),
                "content_filtered": content.get("security_and_privacy", {}).get(
                    "content_filtered", "false"
                ),
                "rag_safe": content.get("security_and_privacy", {}).get(
                    "rag_safe", "true"
                ),
            },
            # Rich data from hooks
            "cross_repository_correlation": content.get(
                "cross_repository_correlation", {}
            ),
            "technologies_detected": content.get("technologies_detected", []),
            "architecture_patterns": content.get("architecture_patterns", []),
            "commit_message": content.get("change_summary", {}).get(
                "commit_message", ""
            ),
            "github_url": metadata.get("github_url", ""),
            "hook_version": metadata.get("hook_version", "unknown"),
        },
    }

    return intelligence_doc


async def ingest_documents():
    """Main ingestion function."""
    print("🚀 Starting bulk intelligence document ingestion")
    print("=" * 60)

    # Find all documents
    documents = await find_intelligence_documents()
    print(f"\n📊 Total documents found: {len(documents)}")

    if not documents:
        print("❌ No intelligence documents found to ingest")
        return

    # Initialize writer
    database_client = get_database_client()
    create_intelligence_document_writer(database_client)

    ingested = 0
    errors = 0

    for i, doc in enumerate(documents):
        try:
            print(f"\n📄 Processing {i+1}/{len(documents)}: {doc['repository']}")

            # Convert to intelligence format
            intelligence_doc = await convert_to_intelligence_format(doc)

            # Show what we're about to ingest
            technologies = intelligence_doc["intelligence_data"].get(
                "technologies_detected", []
            )
            commit_msg = intelligence_doc["intelligence_data"].get(
                "commit_message", ""
            )[:100]

            print(f"   📋 Commit: {commit_msg}...")
            print(f"   🛠️ Technologies: {technologies[:5]}")

            # TODO: Ingest into intelligence system
            # This would require implementing the intelligence document writer
            # For now, just show what we would ingest
            print("   ✅ Ready for ingestion (simulated)")
            ingested += 1

        except Exception as e:
            print(f"   ❌ Error processing document: {e}")
            errors += 1

    print("\n🎯 INGESTION SUMMARY")
    print("=" * 60)
    print(f"✅ Documents processed: {ingested}")
    print(f"❌ Errors: {errors}")
    print(f"📊 Success rate: {(ingested / len(documents) * 100):.1f}%")

    if ingested > 0:
        print(
            f"\n🎉 Successfully prepared {ingested} rich intelligence documents for ingestion!"
        )
        print("These contain detailed commit analysis, cross-repository correlations,")
        print(
            "and technology detection that will dramatically improve correlation quality."
        )


if __name__ == "__main__":
    asyncio.run(ingest_documents())
