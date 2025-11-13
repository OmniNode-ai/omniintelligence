#!/usr/bin/env python3
"""
Test script for Bridge Intelligence Generation API

Tests the POST /api/bridge/generate-intelligence endpoint and validates:
1. OmniNode Tool Metadata Standard v0.1 compliance
2. Archon intelligence enrichment
3. LangExtract semantic analysis integration
4. QualityScorer ONEX compliance assessment
5. Pattern tracking integration (if DB available)
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict

import httpx

# Test configuration
INTELLIGENCE_SERVICE_URL = "http://localhost:8053"
BRIDGE_API_ENDPOINT = f"{INTELLIGENCE_SERVICE_URL}/api/bridge/generate-intelligence"
HEALTH_ENDPOINT = f"{INTELLIGENCE_SERVICE_URL}/api/bridge/health"
CAPABILITIES_ENDPOINT = f"{INTELLIGENCE_SERVICE_URL}/api/bridge/capabilities"


# Sample Python code for testing
SAMPLE_CODE = '''
"""
Example module for testing Bridge Intelligence Generation.

This module demonstrates various quality patterns and ONEX compliance.
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class User:
    """User entity with basic information"""
    user_id: str
    username: str
    email: str
    is_active: bool = True

    def validate_email(self) -> bool:
        """
        Validate email format.

        Returns:
            bool: True if email is valid, False otherwise
        """
        return "@" in self.email and "." in self.email


class UserService:
    """Service for managing user operations"""

    def __init__(self, db_connection: Any):
        """Initialize user service with database connection"""
        self.db = db_connection
        self.users: List[User] = []

    async def create_user(
        self,
        username: str,
        email: str,
        is_active: bool = True
    ) -> Optional[User]:
        """
        Create a new user.

        Args:
            username: User's username
            email: User's email address
            is_active: Whether user is active (default: True)

        Returns:
            Created User object or None if creation failed
        """
        try:
            user = User(
                user_id=self._generate_id(),
                username=username,
                email=email,
                is_active=is_active
            )

            if user.validate_email():
                await self.db.insert(user)
                self.users.append(user)
                return user

            return None

        except Exception as e:
            print(f"Failed to create user: {e}")
            return None

    def _generate_id(self) -> str:
        """Generate unique user ID"""
        import uuid
        return str(uuid.uuid4())
'''


def print_section(title: str):
    """Print formatted section title"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_result(label: str, value: Any, indent: int = 0):
    """Print formatted result"""
    indent_str = "  " * indent
    if isinstance(value, (dict, list)):
        print(f"{indent_str}{label}:")
        print(f"{indent_str}  {json.dumps(value, indent=2)}")
    else:
        print(f"{indent_str}{label}: {value}")


def validate_omninode_compliance(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate OmniNode Tool Metadata Standard v0.1 compliance.

    Returns dict with:
    - compliant: bool
    - missing_required: List[str]
    - validation_details: Dict[str, Any]
    """
    required_fields = [
        "metadata_version",
        "name",
        "namespace",
        "version",
        "entrypoint",
        "protocols_supported",
    ]

    missing_required = [field for field in required_fields if field not in metadata]

    validation_details = {
        "has_classification": "classification" in metadata,
        "has_trust_score": (
            "classification" in metadata
            and "trust_score" in metadata.get("classification", {})
        ),
        "has_quality_metrics": "quality_metrics" in metadata,
        "has_semantic_intelligence": "semantic_intelligence" in metadata,
        "has_pattern_intelligence": "pattern_intelligence" in metadata,
    }

    return {
        "compliant": len(missing_required) == 0,
        "missing_required": missing_required,
        "validation_details": validation_details,
    }


async def test_health_check():
    """Test Bridge Intelligence health check endpoint"""
    print_section("Testing Bridge Intelligence Health Check")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(HEALTH_ENDPOINT)

            print_result("Status Code", response.status_code)

            if response.status_code == 200:
                health_data = response.json()
                print_result("Service Status", health_data.get("status"))
                print_result("Components", health_data.get("components"), indent=1)
                print_result("Response Time (ms)", health_data.get("response_time_ms"))
                return True
            else:
                print_result("❌ Health check failed", response.text)
                return False

    except Exception as e:
        print_result("❌ Health check error", str(e))
        return False


async def test_capabilities():
    """Test Bridge Intelligence capabilities endpoint"""
    print_section("Testing Bridge Intelligence Capabilities")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(CAPABILITIES_ENDPOINT)

            if response.status_code == 200:
                capabilities = response.json()
                print_result("Protocol Version", capabilities.get("protocol_version"))
                print_result(
                    "Intelligence Sources",
                    capabilities.get("intelligence_sources"),
                    indent=1,
                )
                print_result(
                    "Supported Languages", capabilities.get("supported_languages")
                )
                print_result(
                    "Performance Targets",
                    capabilities.get("performance_targets"),
                    indent=1,
                )
                return True
            else:
                print_result("❌ Capabilities check failed", response.text)
                return False

    except Exception as e:
        print_result("❌ Capabilities check error", str(e))
        return False


async def test_generate_intelligence():
    """Test Bridge Intelligence generation with sample code"""
    print_section("Testing Bridge Intelligence Generation")

    request_payload = {
        "file_path": "/test/sample_module.py",
        "content": SAMPLE_CODE,
        "include_patterns": True,
        "include_compliance": True,
        "include_semantic": True,
        "min_confidence": 0.7,
    }

    print_result("Request Payload", request_payload, indent=1)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(BRIDGE_API_ENDPOINT, json=request_payload)

            print_result("\nResponse Status Code", response.status_code)

            if response.status_code == 200:
                result = response.json()

                # Check success status
                success = result.get("success", False)
                print_result("✅ Success", success)

                if not success:
                    print_result("❌ Error", result.get("error"))
                    return False

                # Validate metadata
                metadata = result.get("metadata")
                if not metadata:
                    print_result("❌ No metadata in response", "")
                    return False

                print_section("Generated Metadata")

                # Display required fields
                print_result("Metadata Version", metadata.get("metadata_version"))
                print_result("Name", metadata.get("name"))
                print_result("Namespace", metadata.get("namespace"))
                print_result("Version", metadata.get("version"))
                print_result("Entrypoint", metadata.get("entrypoint"))
                print_result("Protocols", metadata.get("protocols_supported"))

                # Display classification
                classification = metadata.get("classification", {})
                print_result("\nClassification")
                print_result("Maturity", classification.get("maturity"), indent=1)
                print_result(
                    "Trust Score (0-100)", classification.get("trust_score"), indent=1
                )

                # Display quality metrics
                quality = metadata.get("quality_metrics", {})
                print_result("\nQuality Metrics")
                print_result(
                    "Quality Score (0-1)", quality.get("quality_score"), indent=1
                )
                print_result(
                    "ONEX Compliance (0-1)", quality.get("onex_compliance"), indent=1
                )
                print_result(
                    "Complexity Score", quality.get("complexity_score"), indent=1
                )
                print_result(
                    "Maintainability", quality.get("maintainability_score"), indent=1
                )
                print_result(
                    "Documentation", quality.get("documentation_score"), indent=1
                )
                print_result(
                    "Temporal Relevance", quality.get("temporal_relevance"), indent=1
                )

                # Display semantic intelligence
                semantic = metadata.get("semantic_intelligence")
                if semantic:
                    print_result("\nSemantic Intelligence")
                    print_result(
                        "Concepts Count", len(semantic.get("concepts", [])), indent=1
                    )
                    print_result(
                        "Themes Count", len(semantic.get("themes", [])), indent=1
                    )
                    print_result(
                        "Domains Count", len(semantic.get("domains", [])), indent=1
                    )
                    print_result(
                        "Patterns Count", len(semantic.get("patterns", [])), indent=1
                    )

                    # Show top concepts
                    concepts = semantic.get("concepts", [])[:5]
                    if concepts:
                        print_result("Top Concepts", concepts, indent=1)

                # Display pattern intelligence
                pattern = metadata.get("pattern_intelligence")
                if pattern:
                    print_result("\nPattern Intelligence")
                    print_result(
                        "Pattern Count", pattern.get("pattern_count"), indent=1
                    )
                    print_result(
                        "Total Executions", pattern.get("total_executions"), indent=1
                    )
                    print_result(
                        "Avg Quality Score", pattern.get("avg_quality_score"), indent=1
                    )

                # Display processing metadata
                processing = result.get("processing_metadata", {})
                print_result("\nProcessing Metadata")
                print_result(
                    "Processing Time (ms)",
                    processing.get("processing_time_ms"),
                    indent=1,
                )
                print_result(
                    "Intelligence Sources", result.get("intelligence_sources"), indent=1
                )

                # Display recommendations
                recommendations = result.get("recommendations")
                if recommendations:
                    print_result("\nRecommendations", recommendations, indent=1)

                # Validate OmniNode compliance
                print_section("OmniNode Protocol Compliance Validation")
                validation = validate_omninode_compliance(metadata)

                print_result("✅ Compliant", validation["compliant"])

                if not validation["compliant"]:
                    print_result(
                        "❌ Missing Required Fields", validation["missing_required"]
                    )

                print_result(
                    "Validation Details", validation["validation_details"], indent=1
                )

                return validation["compliant"]

            else:
                print_result("❌ Generation failed", response.text)
                return False

    except Exception as e:
        print_result("❌ Generation error", str(e))
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print_section("Bridge Intelligence Generation API Tests")
    print(f"Target Service: {INTELLIGENCE_SERVICE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")

    results = {
        "health_check": False,
        "capabilities": False,
        "intelligence_generation": False,
    }

    # Test health check
    results["health_check"] = await test_health_check()

    if not results["health_check"]:
        print("\n❌ Service is not healthy. Skipping remaining tests.")
        return 1

    # Test capabilities
    results["capabilities"] = await test_capabilities()

    # Test intelligence generation
    results["intelligence_generation"] = await test_generate_intelligence()

    # Print summary
    print_section("Test Summary")
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print(f"\n{'✅ All tests passed!' if all_passed else '❌ Some tests failed'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
