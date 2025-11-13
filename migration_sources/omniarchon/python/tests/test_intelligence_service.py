#!/usr/bin/env python3
"""
Test script for Archon Intelligence Service

Tests entity extraction, storage, and retrieval functionality.
"""

import asyncio
import sys

import httpx

# Test configuration
INTELLIGENCE_SERVICE_URL = "http://localhost:8053"
SAMPLE_PYTHON_CODE = '''
"""
Example Python module for testing entity extraction
"""

class UserManager:
    """Manages user accounts and authentication"""

    def __init__(self, database_url: str):
        self.db_url = database_url
        self.users = {}

    def create_user(self, username: str, email: str) -> bool:
        """Create a new user account"""
        if username in self.users:
            return False

        self.users[username] = {
            "email": email,
            "created_at": datetime.utcnow(),
            "active": True
        }
        return True

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return token"""
        user = self.users.get(username)
        if user and user["active"]:
            # Simple token generation for demo
            return f"token_{username}_{hash(password)}"
        return None

def process_user_data(data: List[Dict]) -> Dict[str, Any]:
    """Process batch user data"""
    results = {"processed": 0, "errors": []}

    for item in data:
        try:
            if validate_user_data(item):
                results["processed"] += 1
        except ValidationError as e:
            results["errors"].append(str(e))

    return results
'''

SAMPLE_DOCUMENT = """
# API Documentation

## User Management Endpoints

### POST /users
Creates a new user account.

**Parameters:**
- `username` (string): Unique username
- `email` (string): Valid email address
- `password` (string): Strong password

**Response:**
```json
{
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "created_at": "2024-01-01T00:00:00Z"
}
```

### GET /users/{user_id}
Retrieves user information by ID.

**Response:**
```json
{
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "last_login": "2024-01-01T00:00:00Z"
}
```
"""


async def test_service_health():
    """Test service health endpoint"""
    print("🔍 Testing service health...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{INTELLIGENCE_SERVICE_URL}/health")

            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Service healthy: {health_data['status']}")
                print(f"   - Memgraph connected: {health_data['memgraph_connected']}")
                print(f"   - Service version: {health_data['service_version']}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False


async def test_code_extraction():
    """Test code entity extraction"""
    print("\n🔍 Testing code entity extraction...")

    request_data = {
        "content": SAMPLE_PYTHON_CODE,
        "source_path": "test/sample_module.py",
        "language": "python",
        "store_entities": True,
        "extract_relationships": True,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{INTELLIGENCE_SERVICE_URL}/extract/code",
                json=request_data,
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Code extraction successful:")
                print(f"   - Entities extracted: {result['total_count']}")
                print(f"   - Mean confidence: {result['confidence_stats']['mean']:.2f}")

                # Show sample entities
                for i, entity in enumerate(result["entities"][:3]):
                    print(
                        f"   - Entity {i+1}: {entity['name']} ({entity['entity_type']})"
                    )

                return result["entities"]
            else:
                print(f"❌ Code extraction failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Code extraction failed: {e}")
            return None


async def test_document_extraction():
    """Test document entity extraction"""
    print("\n🔍 Testing document entity extraction...")

    request_data = {
        "content": SAMPLE_DOCUMENT,
        "source_path": "docs/api_documentation.md",
        "store_entities": True,
        "extract_relationships": True,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{INTELLIGENCE_SERVICE_URL}/extract/document",
                json=request_data,
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Document extraction successful:")
                print(f"   - Entities extracted: {result['total_count']}")
                print(f"   - Mean confidence: {result['confidence_stats']['mean']:.2f}")

                # Show sample entities
                for i, entity in enumerate(result["entities"][:3]):
                    print(
                        f"   - Entity {i+1}: {entity['name']} ({entity['entity_type']})"
                    )

                return result["entities"]
            else:
                print(f"❌ Document extraction failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Document extraction failed: {e}")
            return None


async def test_entity_search():
    """Test entity search functionality"""
    print("\n🔍 Testing entity search...")

    search_params = {"query": "user", "limit": 5, "min_confidence": 0.5}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{INTELLIGENCE_SERVICE_URL}/entities/search",
                params=search_params,
                timeout=30.0,
            )

            if response.status_code == 200:
                entities = response.json()
                print("✅ Entity search successful:")
                print(f"   - Entities found: {len(entities)}")

                for i, entity in enumerate(entities[:3]):
                    print(
                        f"   - Result {i+1}: {entity['name']} ({entity['entity_type']}) - {entity['confidence_score']:.2f}"
                    )

                return entities
            else:
                print(f"❌ Entity search failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Entity search failed: {e}")
            return None


async def test_relationships():
    """Test relationship retrieval"""
    print("\n🔍 Testing relationship retrieval...")

    # First, get an entity ID from search
    search_params = {"query": "UserManager", "limit": 1}

    async with httpx.AsyncClient() as client:
        try:
            # Search for an entity
            response = await client.get(
                f"{INTELLIGENCE_SERVICE_URL}/entities/search",
                params=search_params,
                timeout=30.0,
            )

            if response.status_code != 200 or not response.json():
                print("⚠️ No entities found for relationship testing")
                return None

            entity = response.json()[0]
            entity_id = entity["entity_id"]

            # Get relationships for the entity
            response = await client.get(
                f"{INTELLIGENCE_SERVICE_URL}/relationships/{entity_id}", timeout=30.0
            )

            if response.status_code == 200:
                relationships = response.json()
                print("✅ Relationship retrieval successful:")
                print(f"   - Relationships found: {len(relationships)}")

                for i, rel in enumerate(relationships[:3]):
                    print(
                        f"   - Relationship {i+1}: {rel.get('relationship', {}).get('relationship_type', 'unknown')}"
                    )

                return relationships
            else:
                print(f"❌ Relationship retrieval failed: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Relationship retrieval failed: {e}")
            return None


async def main():
    """Run all intelligence service tests"""
    print("🚀 Starting Archon Intelligence Service Tests\n")

    # Test service health
    if not await test_service_health():
        print("\n❌ Service not healthy, aborting tests")
        sys.exit(1)

    # Test code extraction
    code_entities = await test_code_extraction()

    # Test document extraction
    doc_entities = await test_document_extraction()

    # Test entity search (wait a moment for storage)
    print("\n⏳ Waiting for entities to be stored...")
    await asyncio.sleep(3)

    search_entities = await test_entity_search()

    # Test relationships
    relationships = await test_relationships()

    # Summary
    print("\n" + "=" * 60)
    print("🎯 Test Results Summary")
    print("=" * 60)

    tests_passed = 0
    total_tests = 5

    if code_entities is not None:
        tests_passed += 1
        print("✅ Code extraction: PASSED")
    else:
        print("❌ Code extraction: FAILED")

    if doc_entities is not None:
        tests_passed += 1
        print("✅ Document extraction: PASSED")
    else:
        print("❌ Document extraction: FAILED")

    if search_entities is not None:
        tests_passed += 1
        print("✅ Entity search: PASSED")
    else:
        print("❌ Entity search: FAILED")

    if relationships is not None:
        tests_passed += 1
        print("✅ Relationships: PASSED")
    else:
        print("❌ Relationships: FAILED")

    print(f"\n🏆 Tests passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print("🎉 All tests passed! Intelligence service is working correctly.")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed. Check service logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
