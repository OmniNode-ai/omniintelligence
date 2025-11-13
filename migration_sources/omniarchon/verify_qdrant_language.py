#!/usr/bin/env python3
"""Verify language field in Qdrant vectors."""

import json

import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "archon_vectors"


def main():
    """Main verification function."""
    print("=" * 60)
    print("Qdrant Language Field Verification")
    print("=" * 60)

    # Get collection info
    response = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    if response.status_code == 200:
        data = response.json()
        result = data.get("result", {})
        print(f"\n✅ Collection: {COLLECTION_NAME}")
        print(f"Total vectors: {result.get('vectors_count', 'N/A')}")
        print(f"Indexed vectors: {result.get('indexed_vectors_count', 'N/A')}")
        print(f"Status: {result.get('status', 'N/A')}")
    else:
        print(f"❌ Failed to get collection info: {response.status_code}")
        return

    # Sample recent vectors
    print(f"\n{'='*60}")
    print("Sampling Recent Vectors (limit 100)")
    print("=" * 60)

    scroll_request = {"limit": 100, "with_payload": True, "with_vector": False}

    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll", json=scroll_request
    )

    if response.status_code == 200:
        data = response.json()
        points = data.get("result", {}).get("points", [])

        print(f"Points sampled: {len(points)}")

        # Count points with language field
        with_lang = [p for p in points if "language" in p.get("payload", {})]
        print(
            f"Points with language field: {len(with_lang)}/{len(points)} ({len(with_lang)/len(points)*100:.1f}%)"
        )

        # Show language distribution
        if with_lang:
            lang_counts = {}
            for p in with_lang:
                lang = p.get("payload", {}).get("language", "unknown")
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            print(f"\nLanguage Distribution in Sample:")
            for lang, count in sorted(
                lang_counts.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {lang}: {count}")

            print(f"\nSample Points with Language (first 10):")
            for i, p in enumerate(with_lang[:10], 1):
                payload = p.get("payload", {})
                file_path = payload.get("file_path", "N/A")
                language = payload.get("language", "N/A")
                # Truncate long paths
                if len(file_path) > 60:
                    file_path = "..." + file_path[-57:]
                print(f"  {i}. {file_path}")
                print(f"     Language: {language}")
    else:
        print(f"❌ Failed to scroll points: {response.status_code}")

    # Check for Python files specifically
    print(f"\n{'='*60}")
    print("Python Files in Qdrant")
    print("=" * 60)

    filter_request = {
        "limit": 100,
        "with_payload": True,
        "with_vector": False,
        "filter": {"must": [{"key": "language", "match": {"value": "python"}}]},
    }

    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll", json=filter_request
    )

    if response.status_code == 200:
        data = response.json()
        points = data.get("result", {}).get("points", [])
        print(f"Python files found: {len(points)}")

        if points:
            print("\nSample Python files (first 10):")
            for i, p in enumerate(points[:10], 1):
                payload = p.get("payload", {})
                file_path = payload.get("file_path", "N/A")
                if len(file_path) > 70:
                    file_path = "..." + file_path[-67:]
                print(f"  {i}. {file_path}")
    else:
        print(f"❌ Failed to filter Python files: {response.status_code}")

    # Check for other languages
    print(f"\n{'='*60}")
    print("Checking Other Languages")
    print("=" * 60)

    for lang in ["markdown", "yaml", "shell", "json", "sql", "toml"]:
        filter_request = {
            "limit": 10,
            "with_payload": False,
            "with_vector": False,
            "filter": {"must": [{"key": "language", "match": {"value": lang}}]},
        }

        response = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/scroll",
            json=filter_request,
        )

        if response.status_code == 200:
            data = response.json()
            points = data.get("result", {}).get("points", [])
            print(f"{lang.capitalize()}: {len(points)} files")
        else:
            print(f"{lang.capitalize()}: Error")


if __name__ == "__main__":
    main()
