#!/usr/bin/env python3
"""
Test script for /api/pattern-learning/hybrid/score endpoint

Demonstrates the hybrid scoring API that combines:
- Keyword matching (pattern keywords vs context keywords)
- Semantic similarity (pattern relevance to user prompt)
- Quality score (pattern quality from metadata)
- Success rate (historical pattern success rate)

Performance target: <50ms per request
"""

import json
import time
from typing import Any, Dict

import requests


def test_hybrid_score(
    pattern: Dict[str, Any],
    context: Dict[str, Any],
    weights: Dict[str, float] = None,
    base_url: str = "http://localhost:8053",
) -> Dict[str, Any]:
    """
    Test the hybrid score endpoint

    Args:
        pattern: Pattern data with keywords and metadata
        context: User context with keywords and task info
        weights: Optional custom weights for scoring dimensions
        base_url: Base URL of the intelligence service

    Returns:
        API response with hybrid score and breakdown
    """
    url = f"{base_url}/api/pattern-learning/hybrid/score"

    payload = {"pattern": pattern, "context": context}

    if weights:
        payload["weights"] = weights

    start = time.time()
    response = requests.post(url, json=payload)
    elapsed_ms = (time.time() - start) * 1000

    response.raise_for_status()
    result = response.json()

    print(f"\n{'='*60}")
    print(f"Hybrid Score: {result['data']['hybrid_score']:.4f}")
    print(f"Confidence: {result['data']['confidence']:.4f}")
    print(f"\nBreakdown:")
    for key, value in result["data"]["breakdown"].items():
        print(f"  {key}: {value:.4f}")
    print(f"\nMetadata:")
    print(
        f"  Processing time: {result['data']['metadata']['processing_time_ms']:.2f}ms"
    )
    print(f"  Request time: {elapsed_ms:.2f}ms")
    print(f"  Keyword matches: {result['data']['metadata']['keyword_matches']}")
    print(
        f"  Weights used: {json.dumps(result['data']['metadata']['weights_used'], indent=4)}"
    )
    print(f"{'='*60}\n")

    return result


def main():
    """Run test scenarios"""

    print("Testing Hybrid Score API")
    print("=" * 60)

    # Test 1: Full request with all parameters
    print("\n✅ Test 1: Full request with custom weights")
    test_hybrid_score(
        pattern={
            "keywords": ["fastapi", "async", "api", "rest"],
            "metadata": {
                "quality_score": 0.85,
                "success_rate": 0.90,
                "confidence_score": 0.88,
                "semantic_score": 0.82,
            },
        },
        context={
            "keywords": ["fastapi", "rest", "endpoint"],
            "task_type": "api_development",
            "complexity": "moderate",
        },
        weights={
            "keyword": 0.25,
            "semantic": 0.35,
            "quality": 0.20,
            "success_rate": 0.20,
        },
    )

    # Test 2: Default weights
    print("\n✅ Test 2: Using default weights")
    test_hybrid_score(
        pattern={
            "keywords": ["fastapi", "async"],
            "metadata": {"quality_score": 0.85, "success_rate": 0.90},
        },
        context={"keywords": ["fastapi", "endpoint"]},
    )

    # Test 3: Missing metadata (should use defaults)
    print("\n✅ Test 3: Missing metadata (defaults to 0.5)")
    test_hybrid_score(
        pattern={"keywords": ["python", "django"], "metadata": {}},
        context={"keywords": ["fastapi", "rest"]},
    )

    # Test 4: Perfect match
    print("\n✅ Test 4: Perfect keyword match")
    test_hybrid_score(
        pattern={
            "keywords": ["fastapi", "rest", "async"],
            "metadata": {
                "quality_score": 0.95,
                "success_rate": 0.98,
                "semantic_score": 0.92,
            },
        },
        context={"keywords": ["fastapi", "rest", "async"]},
    )

    # Test 5: Custom weights (not summing to 1.0 - will be normalized)
    print("\n✅ Test 5: Custom weights with normalization")
    test_hybrid_score(
        pattern={
            "keywords": ["fastapi"],
            "metadata": {
                "quality_score": 0.9,
                "success_rate": 0.95,
                "semantic_score": 0.88,
            },
        },
        context={"keywords": ["fastapi"]},
        weights={
            "keyword": 1.0,
            "semantic": 2.0,  # Higher weight on semantic
            "quality": 1.0,
            "success_rate": 1.0,
        },
    )

    print("\n✅ All tests completed successfully!")


if __name__ == "__main__":
    main()
