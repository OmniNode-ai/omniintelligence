"""
Integration Test: Background Task Status Tracking

Tests the end-to-end error propagation and status tracking for document processing background tasks.

Created: 2025-11-12
Purpose: Verify that background task failures are tracked and can be queried via API
"""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

BASE_URL = "http://localhost:8053"
TEST_DOCUMENT_ID = f"test-doc-{int(datetime.now(timezone.utc).timestamp())}"
TEST_PROJECT_ID = "test-project"


@pytest.mark.asyncio
async def test_successful_document_processing_status():
    """Test that successful document processing is tracked correctly."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Submit document for processing
        process_request = {
            "document_id": TEST_DOCUMENT_ID,
            "project_id": TEST_PROJECT_ID,
            "title": "Test Document",
            "content": "This is a test document content for status tracking.",
            "document_type": "test",
            "metadata": {"test": True},
        }

        response = await client.post(
            f"{BASE_URL}/process/document", json=process_request
        )
        assert response.status_code == 200, f"Process request failed: {response.text}"

        process_result = response.json()
        assert process_result["success"] is True
        assert process_result["status"] == "processing_queued"
        assert "status_url" in process_result

        status_url = process_result["status_url"]
        print(f"✅ Document processing queued | status_url={status_url}")

        # Step 2: Poll status endpoint until completion (max 30 seconds)
        for attempt in range(30):
            await asyncio.sleep(1)

            status_response = await client.get(f"{BASE_URL}{status_url}")
            assert status_response.status_code in [
                200,
                404,
            ], f"Status check failed: {status_response.text}"

            if status_response.status_code == 404:
                print(f"⏳ Status not yet available (attempt {attempt + 1}/30)")
                continue

            status_data = status_response.json()
            print(f"📊 Status: {status_data['status']} (attempt {attempt + 1}/30)")

            if status_data["status"] in ["success", "failed"]:
                print(f"\n✅ Final Status: {status_data}")

                # Assertions for successful completion
                assert (
                    status_data["status"] == "success"
                ), f"Task failed: {status_data.get('error_message')}"
                assert status_data["entities_extracted"] is not None
                assert status_data["vector_indexed"] is not None
                assert "pipeline_steps" in status_data
                assert status_data["started_at"] is not None
                assert status_data["completed_at"] is not None

                return

        pytest.fail("Task did not complete within 30 seconds")


@pytest.mark.asyncio
async def test_failed_document_processing_status():
    """Test that failed document processing is tracked correctly."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Submit invalid document to trigger failure
        # (missing required fields)
        process_request = {
            "document_id": f"fail-test-{int(datetime.now(timezone.utc).timestamp())}",
            # Missing project_id to trigger failure
            "title": "",
            "content": "",
            "document_type": "test",
            "metadata": {},
        }

        response = await client.post(
            f"{BASE_URL}/process/document", json=process_request
        )

        # Should fail immediately (400) or queue and fail in background
        if response.status_code == 400:
            print("✅ Request rejected immediately (expected)")
            return

        assert response.status_code == 200, f"Process request failed: {response.text}"

        process_result = response.json()
        document_id = process_result["document_id"]
        status_url = process_result["status_url"]

        print(
            f"⏳ Document processing queued (expected to fail) | status_url={status_url}"
        )

        # Step 2: Poll status endpoint until completion or failure
        for attempt in range(30):
            await asyncio.sleep(1)

            status_response = await client.get(f"{BASE_URL}{status_url}")
            if status_response.status_code == 404:
                print(f"⏳ Status not yet available (attempt {attempt + 1}/30)")
                continue

            assert (
                status_response.status_code == 200
            ), f"Status check failed: {status_response.text}"

            status_data = status_response.json()
            print(f"📊 Status: {status_data['status']} (attempt {attempt + 1}/30)")

            if status_data["status"] in ["success", "failed"]:
                print(f"\n❌ Final Status: {status_data}")

                # Assertions for failure tracking
                assert status_data["status"] == "failed", "Task should have failed"
                assert status_data["error_message"] is not None
                assert "error_details" in status_data
                assert status_data["started_at"] is not None
                assert status_data["completed_at"] is not None

                return

        pytest.fail("Task did not complete or fail within 30 seconds")


@pytest.mark.asyncio
async def test_status_endpoint_not_found():
    """Test that status endpoint returns 404 for unknown document_id."""

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{BASE_URL}/process/document/nonexistent-doc-id/status"
        )
        assert response.status_code == 404

        error_data = response.json()
        assert "detail" in error_data
        assert "No status found" in error_data["detail"]

        print("✅ Status endpoint correctly returns 404 for unknown document_id")


if __name__ == "__main__":
    # Run tests manually
    print("🧪 Running Background Task Status Tracking Integration Tests\n")

    print("=" * 80)
    print("Test 1: Successful Document Processing Status")
    print("=" * 80)
    asyncio.run(test_successful_document_processing_status())

    print("\n" + "=" * 80)
    print("Test 2: Failed Document Processing Status")
    print("=" * 80)
    asyncio.run(test_failed_document_processing_status())

    print("\n" + "=" * 80)
    print("Test 3: Status Endpoint Not Found")
    print("=" * 80)
    asyncio.run(test_status_endpoint_not_found())

    print("\n✅ All tests passed!")
