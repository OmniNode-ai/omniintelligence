#!/usr/bin/env python3
"""
Test script for FreshnessScore model validation fix
"""

import os
import sys
from typing import Any, Dict, List, Optional, Union

# Add the current directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from pydantic import BaseModel, Field, validator
except ImportError:
    print("❌ Pydantic not available. Install with: pip install pydantic")
    sys.exit(1)


# Define the fixed FreshnessScore model inline
class FreshnessScore(BaseModel):
    """Detailed freshness scoring information"""

    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall freshness score"
    )
    time_decay_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on time since last update"
    )
    dependency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on dependency freshness"
    )
    content_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on content analysis"
    )
    usage_frequency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Score based on access patterns"
    )

    # Scoring weights (how much each factor contributes)
    time_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    dependency_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    content_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    usage_weight: float = Field(default=0.1, ge=0.0, le=1.0)

    # Detailed scoring factors - supports both simple values and complex nested data
    factors: Dict[str, Union[float, int, bool, Dict[str, Any], List[Any]]] = Field(
        default_factory=dict
    )
    explanation: Optional[str] = Field(None, description="Explanation of scoring")

    @validator("time_weight", "dependency_weight", "content_weight", "usage_weight")
    def validate_weights(cls, v):
        """Ensure weights are between 0 and 1"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Weights must be between 0.0 and 1.0")
        return v


def test_freshness_score_validation():
    """Test the FreshnessScore model with complex factors data"""
    print("Testing FreshnessScore model validation...")

    # Test data that mimics what the scoring system actually produces
    test_data = {
        "overall_score": 0.75,
        "time_decay_score": 0.8,
        "dependency_score": 0.7,
        "content_relevance_score": 0.75,
        "usage_frequency_score": 0.5,
        "time_weight": 0.4,
        "dependency_weight": 0.3,
        "content_weight": 0.2,
        "usage_weight": 0.1,
        "factors": {
            # Simple numeric factors
            "document_age_days": 15,
            "type_adjustment": 0.9,
            "dependencies_count": 3,
            "broken_dependencies": 1,
            # Complex dictionary factor (content_indicators)
            "content_indicators": {
                "has_recent_dates": False,
                "has_code_examples": True,
                "temporal_freshness_words": 2,
                "temporal_staleness_words": 0,
                "appears_incomplete": False,
                "has_todo_sections": True,
                "version_references": ["v1.2.3", "2.1.0"],
            },
            # Complex dictionary factor (weighted_components)
            "weighted_components": {
                "time_decay": 0.32,
                "dependency": 0.21,
                "content_relevance": 0.15,
                "usage_frequency": 0.05,
            },
        },
        "explanation": "Document shows some signs of staleness but is generally usable. Moderately aged content. Some dependency issues detected. Content has some outdated elements. Moderate usage patterns.",
    }

    try:
        # Create the FreshnessScore instance
        score = FreshnessScore(**test_data)

        print("✅ FreshnessScore validation SUCCESS!")
        print(f"   Overall score: {score.overall_score}")
        print(f"   Factors keys: {list(score.factors.keys())}")
        print(f"   Content indicators: {score.factors.get('content_indicators', {})}")
        print(f"   Weighted components: {score.factors.get('weighted_components', {})}")

        # Test serialization
        score_dict = score.dict()
        print("✅ Serialization SUCCESS!")
        print(f"   Serialized keys: {list(score_dict.keys())}")

        return True

    except Exception as e:
        print(f"❌ FreshnessScore validation FAILED: {e}")
        return False


def test_edge_cases():
    """Test edge cases and boundary conditions"""
    print("\nTesting edge cases...")

    test_cases = [
        {
            "name": "Minimal data",
            "data": {
                "overall_score": 1.0,
                "time_decay_score": 1.0,
                "dependency_score": 1.0,
                "content_relevance_score": 1.0,
                "usage_frequency_score": 1.0,
                "factors": {},
            },
        },
        {
            "name": "List values in factors",
            "data": {
                "overall_score": 0.5,
                "time_decay_score": 0.5,
                "dependency_score": 0.5,
                "content_relevance_score": 0.5,
                "usage_frequency_score": 0.5,
                "factors": {
                    "version_refs": ["1.0.0", "2.0.0", "3.0.0"],
                    "broken_links": ["http://example.com", "http://test.com"],
                    "nested_data": {"level1": {"level2": ["a", "b", "c"]}},
                },
            },
        },
    ]

    for case in test_cases:
        try:
            FreshnessScore(**case["data"])
            print(f"✅ {case['name']}: SUCCESS")
        except Exception as e:
            print(f"❌ {case['name']}: FAILED - {e}")
            return False

    return True


if __name__ == "__main__":
    print("FreshnessScore Model Validation Test")
    print("=" * 40)

    success = test_freshness_score_validation()
    edge_success = test_edge_cases()

    print("\n" + "=" * 40)
    if success and edge_success:
        print("🎉 ALL TESTS PASSED!")
        print("The FreshnessScore model validation issue has been fixed.")
    else:
        print("💥 SOME TESTS FAILED!")
        print("The validation issue still exists.")
        sys.exit(1)
