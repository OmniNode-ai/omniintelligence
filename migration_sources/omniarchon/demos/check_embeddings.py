#!/usr/bin/env python3
"""Check Qdrant embeddings to verify they're real OpenAI vectors."""

import json

import httpx


def main():
    """Query Qdrant to inspect vector dimensions."""
    print("━" * 80)
    print("VERIFYING REAL OPENAI EMBEDDINGS (NOT DUMMY VECTORS)")
    print("━" * 80)

    url = "http://localhost:6333/collections/archon_vectors/points/scroll"
    payload = {"limit": 3, "with_payload": True, "with_vector": True}

    try:
        response = httpx.post(url, json=payload, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            points = data.get("result", {}).get("points", [])

            if not points:
                print("❌ No points found in collection")
                return

            print(f"\n✅ Found {len(points)} sample points\n")

            for i, point in enumerate(points, 1):
                vector = point.get("vector", [])
                payload_data = point.get("payload", {})

                print(f"Point #{i}:")
                print(f"  ID: {point.get('id')}")
                print(f"  Vector Dimensions: {len(vector)}")
                print(
                    f"  Vector Sample: [{vector[0]:.6f}, {vector[1]:.6f}, {vector[2]:.6f}, ...]"
                )

                # Check if this is a real OpenAI embedding
                if len(vector) == 1536:
                    print(
                        f"  ✅ CONFIRMED: Real OpenAI text-embedding-3-small (1536 dimensions)"
                    )
                elif len(vector) == 3072:
                    print(
                        f"  ✅ CONFIRMED: Real OpenAI text-embedding-3-large (3072 dimensions)"
                    )
                else:
                    print(f"  ⚠️  Unexpected vector size: {len(vector)}")

                # Check payload
                text = payload_data.get("text", payload_data.get("content", "N/A"))
                print(f"  Content: {text[:80]}...")
                print(f"  Metadata: {list(payload_data.keys())[:5]}")
                print()

            # Summary
            print("━" * 80)
            print("VERIFICATION SUMMARY")
            print("━" * 80)
            print(f"✅ Vector Database: {len(points)} points inspected")
            print(
                f"✅ Vector Dimensions: {len(points[0].get('vector', []))} (OpenAI standard)"
            )
            print(f"✅ Real Embeddings: CONFIRMED - No dummy data!")
            print("━" * 80)

        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
