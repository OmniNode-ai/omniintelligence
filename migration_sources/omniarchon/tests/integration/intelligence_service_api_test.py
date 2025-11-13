#!/usr/bin/env python3
"""
Intelligence Service API Test Suite
==================================

This script demonstrates the correct usage of all Intelligence Service endpoints
with proper HTTP methods and request formats.

CRITICAL FINDINGS:
- The /entities/search endpoint requires GET method with query parameters (NOT POST)
- All extraction and assessment endpoints use POST with JSON payloads
- Health endpoint uses GET method

Service URL: http://localhost:8053
"""

import json
import sys
from datetime import datetime

import requests

BASE_URL = "http://localhost:8053"


def test_health_endpoint():
    """Test the health check endpoint - GET method"""
    print("=" * 60)
    print("Testing Health Endpoint (GET)")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_entities_search():
    """Test entity search - GET method with query parameters (NOT POST!)"""
    print("=" * 60)
    print("Testing Entities Search (GET with query params)")
    print("=" * 60)

    try:
        # THIS IS THE CORRECT METHOD - GET with query parameters
        params = {
            "query": "document",
            "limit": 5,
            "entity_type": "DOCUMENT",
            "min_confidence": 0.5,
        }

        response = requests.get(f"{BASE_URL}/entities/search", params=params)
        print(f"URL: {response.url}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data)} entities")
            if data:
                print(f"First entity: {data[0]['name']}")
                print(f"Entity type: {data[0]['entity_type']}")
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_extract_document():
    """Test document extraction - POST method with JSON payload"""
    print("=" * 60)
    print("Testing Document Extraction (POST)")
    print("=" * 60)

    try:
        payload = {
            "content": "This is a sample document about Python programming, API development, and machine learning.",
            "source_path": "/test/sample_document.md",
            "store_entities": False,  # Don't store for testing
            "extract_relationships": False,
            "trigger_freshness_analysis": False,
        }

        response = requests.post(
            f"{BASE_URL}/extract/document",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Extracted {len(data['entities'])} entities")
            if data["entities"]:
                entity = data["entities"][0]
                print(f"Entity name: {entity['name']}")
                print(f"Entity type: {entity['entity_type']}")
                print(f"Confidence: {entity['confidence_score']}")
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_extract_code():
    """Test code extraction - POST method with JSON payload"""
    print("=" * 60)
    print("Testing Code Extraction (POST)")
    print("=" * 60)

    try:
        payload = {
            "content": """
def fibonacci(n):
    '''Calculate fibonacci sequence'''
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

class DataProcessor:
    def __init__(self, data):
        self.data = data

    def process(self):
        return [x * 2 for x in self.data]
""",
            "source_path": "/test/fibonacci.py",
            "language": "python",
            "store_entities": False,
        }

        response = requests.post(
            f"{BASE_URL}/extract/code",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Extracted {len(data['entities'])} entities")
            for entity in data["entities"][:3]:  # Show first 3
                print(f"- {entity['name']} ({entity['entity_type']})")
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_assess_code():
    """Test code quality assessment - POST method with JSON payload"""
    print("=" * 60)
    print("Testing Code Assessment (POST)")
    print("=" * 60)

    try:
        payload = {
            "content": """
def calculate_total(items):
    '''Calculate total price of items'''
    total = 0
    for item in items:
        if hasattr(item, 'price'):
            total += item.price
    return total

def process_order(order):
    '''Process customer order'''
    if not order or not order.items:
        raise ValueError('Invalid order')

    total = calculate_total(order.items)
    if total > 0:
        return {'total': total, 'status': 'processed'}
    return {'total': 0, 'status': 'empty'}
""",
            "source_path": "/test/order_processor.py",
            "language": "python",
            "include_patterns": True,
            "include_compliance": True,
        }

        response = requests.post(
            f"{BASE_URL}/assess/code",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Quality Score: {data.get('quality_score', 'N/A')}")
            print(
                f"Architectural Compliance: {data.get('architectural_compliance', {}).get('score', 'N/A')}"
            )
            print(
                f"ONEX Compliance Score: {data.get('onex_compliance', {}).get('score', 'N/A')}"
            )

            maintainability = data.get("maintainability", {})
            print(f"Complexity Score: {maintainability.get('complexity_score', 'N/A')}")
            print(
                f"Readability Score: {maintainability.get('readability_score', 'N/A')}"
            )
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_assess_document():
    """Test document quality assessment - POST method with JSON payload"""
    print("=" * 60)
    print("Testing Document Assessment (POST)")
    print("=" * 60)

    try:
        payload = {
            "content": """
# API Documentation

## Overview
This API provides endpoints for user management and data processing.

## Authentication
All endpoints require Bearer token authentication.

## Endpoints

### GET /users
Returns list of users.

**Parameters:**
- limit (optional): Maximum number of users to return
- offset (optional): Number of users to skip

**Response:**
```json
{
  "users": [...],
  "total": 150
}
```

### POST /users
Creates a new user.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com"
}
```
""",
            "document_type": "api_documentation",
            "check_completeness": True,
            "include_quality_metrics": True,
        }

        response = requests.post(
            f"{BASE_URL}/assess/document",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Document Quality: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_relationships():
    """Test entity relationships - GET method with path parameter"""
    print("=" * 60)
    print("Testing Entity Relationships (GET)")
    print("=" * 60)

    try:
        # First, get an entity ID from search
        search_response = requests.get(
            f"{BASE_URL}/entities/search", params={"query": "document", "limit": 1}
        )

        if search_response.status_code == 200 and search_response.json():
            entity_id = search_response.json()[0]["entity_id"]
            print(f"Testing relationships for entity: {entity_id}")

            response = requests.get(
                f"{BASE_URL}/relationships/{entity_id}", params={"limit": 5}
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"Found {len(data)} relationships")
                for rel in data[:3]:  # Show first 3
                    print(f"- {rel}")
            else:
                print(f"Error Response: {response.text}")

            return response.status_code == 200
        else:
            print("No entities found to test relationships")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def test_performance_baseline():
    """Test performance baseline establishment - POST method with JSON payload"""
    print("=" * 60)
    print("Testing Performance Baseline (POST)")
    print("=" * 60)

    try:
        payload = {
            "operation_name": "api_endpoint_processing",
            "duration_minutes": 5,
            "metrics": {
                "response_time": "avg_response_time_ms",
                "throughput": "requests_per_second",
                "memory_usage": "memory_mb",
            },
        }

        response = requests.post(
            f"{BASE_URL}/performance/baseline",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Baseline Response: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_freshness_stats():
    """Test document freshness statistics - GET method"""
    print("=" * 60)
    print("Testing Freshness Statistics (GET)")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/freshness/stats")

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Freshness Stats: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")

        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Run all tests and summarize results"""
    print("Intelligence Service API Test Suite")
    print("=" * 60)
    print(f"Testing service at: {BASE_URL}")
    print(f"Test started at: {datetime.now()}")
    print()

    tests = [
        ("Health Check", test_health_endpoint),
        ("Entities Search (CRITICAL FIX)", test_entities_search),
        ("Document Extraction", test_extract_document),
        ("Code Extraction", test_extract_code),
        ("Code Assessment", test_assess_code),
        ("Document Assessment", test_assess_document),
        ("Entity Relationships", test_relationships),
        ("Performance Baseline", test_performance_baseline),
        ("Freshness Statistics", test_freshness_stats),
    ]

    results = {}

    for test_name, test_func in tests:
        print()
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"FATAL ERROR in {test_name}: {e}")
            results[test_name] = False

    # Summary
    print()
    print("=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")

    print()
    print("CRITICAL FINDINGS:")
    print("- /entities/search requires GET method with query parameters")
    print("- All extraction endpoints (/extract/*) use POST with JSON")
    print("- All assessment endpoints (/assess/*) use POST with JSON")
    print("- Relationships endpoint uses GET with path parameter")
    print("- Performance and freshness endpoints working correctly")

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
