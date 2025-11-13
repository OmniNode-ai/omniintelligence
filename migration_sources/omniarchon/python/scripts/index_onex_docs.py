#!/usr/bin/env python3
"""
Index ONEX Documentation to RAG System

This script uploads ONEX documentation files to the Archon RAG system
via the /api/documents/upload endpoint, making them available in rag_search results.

Usage:
    python scripts/index_onex_docs.py [--dry-run] [--api-url http://localhost:8181]
"""

import argparse
import asyncio
import glob
import json
import os
import sys

import aiohttp

# ONEX documentation files to index
ONEX_DOCS_DIR = "/Volumes/PRO-G40/Code/omniarchon/docs/onex"
API_BASE_URL = "http://localhost:8181"


async def upload_document(
    session: aiohttp.ClientSession,
    file_path: str,
    api_url: str,
    tags: list[str],
    knowledge_type: str = "technical",
    dry_run: bool = False,
) -> dict:
    """
    Upload a single document to the RAG system.

    Args:
        session: aiohttp client session
        file_path: Path to the markdown file
        api_url: Base API URL
        tags: Tags for the document
        knowledge_type: Type of knowledge
        dry_run: If True, don't actually upload

    Returns:
        Result dict with success status and details
    """
    file_name = os.path.basename(file_path)

    if dry_run:
        return {
            "success": True,
            "file": file_name,
            "message": "DRY RUN - Would upload file",
            "dry_run": True,
        }

    try:
        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Prepare multipart form data
        data = aiohttp.FormData()
        data.add_field(
            "file", file_content, filename=file_name, content_type="text/markdown"
        )
        data.add_field("tags", json.dumps(tags))
        data.add_field("knowledge_type", knowledge_type)

        # Upload to API
        upload_url = f"{api_url}/api/documents/upload"
        async with session.post(upload_url, data=data) as response:
            if response.status == 200:
                result = await response.json()
                progress_id = result.get("progressId")

                # Wait for completion (poll progress)
                if progress_id:
                    await asyncio.sleep(2)  # Initial delay for processing to start

                return {
                    "success": True,
                    "file": file_name,
                    "progress_id": progress_id,
                    "message": "Upload started successfully",
                }
            else:
                error_text = await response.text()
                return {
                    "success": False,
                    "file": file_name,
                    "error": f"HTTP {response.status}: {error_text}",
                }

    except Exception as e:
        return {"success": False, "file": file_name, "error": str(e)}


def get_onex_files() -> list[dict[str, any]]:
    """
    Get list of ONEX documentation files to index.

    Returns:
        List of dicts with file_path and tags for each file
    """
    files = []

    # Primary documentation files (high priority)
    primary_docs = [
        {
            "file": f"{ONEX_DOCS_DIR}/ONEX_GUIDE.md",
            "tags": ["onex", "documentation", "architecture", "guide", "primary"],
            "description": "Comprehensive ONEX implementation guide",
        },
        {
            "file": f"{ONEX_DOCS_DIR}/ONEX_QUICK_REFERENCE.md",
            "tags": ["onex", "documentation", "reference", "quick-start", "primary"],
            "description": "ONEX quick reference guide",
        },
        {
            "file": f"{ONEX_DOCS_DIR}/examples/QUICKSTART.md",
            "tags": ["onex", "examples", "quickstart", "tutorial", "primary"],
            "description": "ONEX quickstart examples",
        },
    ]

    # Additional documentation files
    additional_docs = [
        {
            "file": f"{ONEX_DOCS_DIR}/SHARED_RESOURCE_VERSIONING.md",
            "tags": ["onex", "documentation", "versioning", "resources"],
            "description": "Shared resource versioning guide",
        },
        {
            "file": f"{ONEX_DOCS_DIR}/examples/README.md",
            "tags": ["onex", "examples", "readme"],
            "description": "Examples README",
        },
        {
            "file": f"{ONEX_DOCS_DIR}/examples/INDEX.md",
            "tags": ["onex", "examples", "index"],
            "description": "Examples index",
        },
        {
            "file": f"{ONEX_DOCS_DIR}/examples/MANIFEST_TYPES.md",
            "tags": ["onex", "examples", "manifest", "types"],
            "description": "Manifest types reference",
        },
        {
            "file": f"{ONEX_DOCS_DIR}/examples/COMPLETE_REFERENCE_SUMMARY.md",
            "tags": ["onex", "examples", "reference", "summary"],
            "description": "Complete reference summary",
        },
    ]

    # Archive documentation (lower priority, optional)
    archive_docs = []
    archive_pattern = f"{ONEX_DOCS_DIR}/archive/*.md"
    for archive_file in glob.glob(archive_pattern):
        archive_docs.append(
            {
                "file": archive_file,
                "tags": ["onex", "documentation", "archive"],
                "description": f"Archive: {os.path.basename(archive_file)}",
            }
        )

    # Combine all files
    all_docs = primary_docs + additional_docs + archive_docs

    # Filter to only existing files
    for doc in all_docs:
        if os.path.exists(doc["file"]):
            files.append(doc)
        else:
            print(f"⚠️  Warning: File not found: {doc['file']}")

    return files


async def index_onex_documentation(
    api_url: str = API_BASE_URL, dry_run: bool = False, include_archive: bool = False
):
    """
    Main function to index all ONEX documentation.

    Args:
        api_url: Base API URL
        dry_run: If True, don't actually upload
        include_archive: If True, include archive docs
    """
    print("🚀 ONEX Documentation Indexing")
    print("=" * 60)
    print(f"API URL: {api_url}")
    print(f"Docs Directory: {ONEX_DOCS_DIR}")
    print(f"Dry Run: {dry_run}")
    print(f"Include Archive: {include_archive}")
    print()

    # Get list of files
    files_to_index = get_onex_files()

    # Filter out archive if not included
    if not include_archive:
        files_to_index = [f for f in files_to_index if "archive" not in f["tags"]]

    print(f"📄 Found {len(files_to_index)} files to index:")
    for i, doc in enumerate(files_to_index, 1):
        status = "✓" if os.path.exists(doc["file"]) else "✗"
        print(f"  {i}. {status} {os.path.basename(doc['file'])}")
        print(f"     Tags: {', '.join(doc['tags'])}")
    print()

    if dry_run:
        print("🔍 DRY RUN MODE - No files will be uploaded")
        print()
        return

    # Confirm before proceeding
    if not dry_run:
        response = input("Proceed with upload? [y/N]: ")
        if response.lower() != "y":
            print("❌ Cancelled by user")
            return
        print()

    # Upload files
    results = []
    async with aiohttp.ClientSession() as session:
        for i, doc in enumerate(files_to_index, 1):
            print(
                f"📤 [{i}/{len(files_to_index)}] Uploading: {os.path.basename(doc['file'])}"
            )

            result = await upload_document(
                session=session,
                file_path=doc["file"],
                api_url=api_url,
                tags=doc["tags"],
                knowledge_type="technical",
                dry_run=dry_run,
            )

            results.append(result)

            if result["success"]:
                print(f"   ✅ {result['message']}")
                if "progress_id" in result:
                    print(f"   📊 Progress ID: {result['progress_id']}")
            else:
                print(f"   ❌ Error: {result['error']}")

            # Wait between uploads to avoid overwhelming the system
            if i < len(files_to_index):
                await asyncio.sleep(3)
            print()

    # Summary
    print("=" * 60)
    print("📊 INDEXING SUMMARY")
    print("=" * 60)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")

    if failed > 0:
        print("\n❌ Failed uploads:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['file']}: {r['error']}")

    print()
    if successful > 0:
        print("🎉 ONEX documentation has been indexed to the RAG system!")
        print("   Run a test query to verify:")
        print(f"   curl -X POST {api_url}/api/rag/query \\")
        print("        -H 'Content-Type: application/json' \\")
        print(
            '        -d \'{"query": "ONEX architecture patterns", "match_count": 5}\''
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Index ONEX documentation to Archon RAG system"
    )
    parser.add_argument(
        "--api-url",
        default=API_BASE_URL,
        help=f"API base URL (default: {API_BASE_URL})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Include archived documentation files",
    )

    args = parser.parse_args()

    # Check if API is accessible
    if not args.dry_run:
        try:
            import requests

            response = requests.get(f"{args.api_url}/api/health", timeout=5)
            if response.status_code != 200:
                print(f"❌ Error: API at {args.api_url} is not responding correctly")
                print(f"   Status: {response.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Error: Cannot connect to API at {args.api_url}")
            print(f"   Error: {e}")
            print("\n💡 Tip: Make sure Archon services are running:")
            print("   docker compose up -d")
            sys.exit(1)

    # Run indexing
    asyncio.run(
        index_onex_documentation(
            api_url=args.api_url,
            dry_run=args.dry_run,
            include_archive=args.include_archive,
        )
    )


if __name__ == "__main__":
    main()
