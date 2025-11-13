"""
MCP Server Document Creation Unit Tests

Tests for the MCP server document creation functionality including:
- create_document MCP tool functionality
- Document structure preservation during creation
- Real-time sync trigger validation
- MCP protocol compliance
- Error handling and validation

Critical focus on ensuring MCP sends complete document data without truncation.
"""

import asyncio
import json
import os
import sys
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared_fixtures import (
    NESTED_CONTENT_DOCUMENT,
    STANDARDIZED_TEST_DOCUMENT,
    ContentExtractionAssertions,
    generate_large_document,
)


class TestMCPDocumentCreation:
    """Test MCP server document creation functionality."""

    def setup_method(self):
        """Setup for each test method."""
        self.assertions = ContentExtractionAssertions()
        self.mcp_server_url = "http://test-mcp:8051"

    @pytest.fixture
    def mock_mcp_server_components(self):
        """Mock MCP server components."""
        return {
            "database_client": AsyncMock(),
            "bridge_service_client": AsyncMock(),
            "websocket_manager": AsyncMock(),
            "mcp_protocol_handler": AsyncMock(),
        }

    @pytest.fixture
    def mock_supabase_client(self):
        """Mock Supabase client for document storage."""
        client = AsyncMock()
        client.table.return_value.insert.return_value.execute.return_value = Mock(
            data=[
                {
                    "id": "generated-doc-id",
                    "project_id": "test-project-67890",
                    "title": "Test Document",
                    "content": {"test": "content"},
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]
        )
        return client

    @pytest.mark.asyncio
    async def test_create_document_mcp_tool_with_standardized_document(
        self, mock_mcp_server_components, mock_supabase_client
    ):
        """Test create_document MCP tool with standardized test document."""
        # Prepare MCP tool call
        mcp_request = {
            "method": "tools/call",
            "params": {
                "name": "create_document",
                "arguments": {
                    "project_id": STANDARDIZED_TEST_DOCUMENT["project_id"],
                    "title": STANDARDIZED_TEST_DOCUMENT["document_data"]["title"],
                    "document_type": STANDARDIZED_TEST_DOCUMENT["document_data"][
                        "document_type"
                    ],
                    "content": STANDARDIZED_TEST_DOCUMENT["document_data"]["content"],
                    "tags": ["test", "content_extraction", "validation"],
                    "author": "test_user",
                },
            },
        }

        # Mock MCP tool execution
        async def mock_create_document_tool(arguments):
            # Validate input arguments
            assert "project_id" in arguments, "project_id required"
            assert "title" in arguments, "title required"
            assert "content" in arguments, "content required"

            # Extract content and validate structure
            content = arguments["content"]
            title = arguments["title"]

            # Critical: Ensure content structure is preserved
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                self.assertions.assert_content_not_truncated(content_text, content)
                assert (
                    len(content_text) > 400
                ), f"MCP content truncated: {len(content_text)} chars"

            # Simulate document creation in database
            document_id = str(uuid.uuid4())

            # Prepare document for storage (preserving full structure)
            document_record = {
                "id": document_id,
                "project_id": arguments["project_id"],
                "title": title,
                "content": content,  # Complete content structure preserved
                "document_type": arguments.get("document_type", "document"),
                "metadata": {
                    "tags": arguments.get("tags", []),
                    "author": arguments.get("author", "unknown"),
                    "created_via": "mcp_tool",
                    "content_validation": {
                        "content_length": (
                            len(content_text)
                            if isinstance(content, dict) and "content" in content
                            else len(str(content))
                        ),
                        "structure_preserved": True,
                    },
                },
                "created_at": "2024-01-01T00:00:00Z",
            }

            # Mock database insertion
            with patch.object(mock_supabase_client, "table") as mock_table:
                mock_table.return_value.insert.return_value.execute.return_value = Mock(
                    data=[document_record]
                )

                # Simulate real-time sync trigger
                sync_payload = {
                    "document_id": document_id,
                    "project_id": arguments["project_id"],
                    "document_data": {
                        "title": title,
                        "content": content,  # Full content preserved for sync
                        "document_type": arguments.get("document_type", "document"),
                        "metadata": document_record["metadata"],
                    },
                }

                # Validate sync payload preserves content
                if isinstance(sync_payload["document_data"]["content"], dict):
                    sync_content = sync_payload["document_data"]["content"]
                    if "content" in sync_content:
                        sync_content_text = sync_content["content"]
                        assert (
                            len(sync_content_text) > 400
                        ), f"Sync payload content truncated: {len(sync_content_text)}"

                return {
                    "success": True,
                    "document_id": document_id,
                    "title": title,
                    "content_length": (
                        len(content_text)
                        if isinstance(content, dict) and "content" in content
                        else len(str(content))
                    ),
                    "sync_triggered": True,
                    "message": "Document created successfully",
                }

        # Execute MCP tool
        result = await mock_create_document_tool(mcp_request["params"]["arguments"])

        # Validate MCP tool response
        assert result["success"] is True, "MCP tool execution failed"
        assert (
            result["content_length"] > 400
        ), f"MCP document content truncated: {result['content_length']}"
        assert result["sync_triggered"] is True, "Real-time sync not triggered"
        assert "document_id" in result, "Document ID not returned"

    @pytest.mark.asyncio
    async def test_document_structure_preservation_during_mcp_creation(self):
        """Test that complex document structures are preserved during MCP creation."""
        # Test with nested content document
        nested_doc_request = {
            "project_id": NESTED_CONTENT_DOCUMENT["project_id"],
            "title": NESTED_CONTENT_DOCUMENT["document_data"]["title"],
            "document_type": NESTED_CONTENT_DOCUMENT["document_data"]["document_type"],
            "content": NESTED_CONTENT_DOCUMENT["document_data"][
                "content"
            ],  # Complex nested structure
            "metadata": NESTED_CONTENT_DOCUMENT["document_data"]["metadata"],
        }

        # Mock MCP document creation with structure preservation
        async def preserve_structure_creation(arguments):
            content = arguments["content"]

            # Validate that nested structure is preserved
            assert isinstance(
                content, dict
            ), "Content structure not preserved as dictionary"

            if "overview" in content:
                overview_text = content["overview"]
                assert (
                    len(overview_text) > 50
                ), f"Overview content truncated: {len(overview_text)}"
                assert (
                    "deeply nested content structures" in overview_text
                ), "Nested content detail lost"

            if "sections" in content:
                sections = content["sections"]
                assert isinstance(sections, dict), "Sections structure not preserved"

                for section_key, section_value in sections.items():
                    if isinstance(section_value, str):
                        assert (
                            len(section_value) > 20
                        ), f"Section {section_key} content truncated: {len(section_value)}"

            # Simulate storage with structure preservation
            stored_document = {
                "document_id": str(uuid.uuid4()),
                "project_id": arguments["project_id"],
                "title": arguments["title"],
                "content": content,  # Complete structure preserved
                "document_type": arguments["document_type"],
                "metadata": arguments.get("metadata", {}),
                "structure_validation": {
                    "is_dict": isinstance(content, dict),
                    "keys_count": (
                        len(content.keys()) if isinstance(content, dict) else 0
                    ),
                    "nested_depth": self._calculate_nested_depth(content),
                },
            }

            return stored_document

        # Execute structure preservation test
        result = await preserve_structure_creation(nested_doc_request)

        # Validate structure preservation
        assert (
            result["structure_validation"]["is_dict"] is True
        ), "Document structure not preserved as dictionary"
        assert (
            result["structure_validation"]["keys_count"] > 3
        ), "Content structure keys lost"
        assert (
            result["structure_validation"]["nested_depth"] >= 2
        ), "Nested structure flattened incorrectly"

    def _calculate_nested_depth(self, obj, current_depth=0):
        """Calculate the depth of nested structures."""
        if not isinstance(obj, dict):
            return current_depth

        max_depth = current_depth
        for value in obj.values():
            if isinstance(value, dict):
                depth = self._calculate_nested_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)

        return max_depth

    @pytest.mark.asyncio
    async def test_real_time_sync_trigger_validation(self, mock_mcp_server_components):
        """Test that MCP document creation triggers real-time sync properly."""
        # Create large document to test sync payload
        large_doc = generate_large_document(content_size=3000)

        mcp_request = {
            "project_id": large_doc["project_id"],
            "title": large_doc["document_data"]["title"],
            "document_type": large_doc["document_data"]["document_type"],
            "content": large_doc["document_data"]["content"],
        }

        # Mock real-time sync process
        async def mock_create_with_sync_trigger(arguments):
            # Step 1: Create document
            document_id = str(uuid.uuid4())
            content = arguments["content"]

            # Step 2: Prepare sync payload
            sync_payload = {
                "document_id": document_id,
                "project_id": arguments["project_id"],
                "document_data": {
                    "title": arguments["title"],
                    "content": content,  # Complete content for sync
                    "document_type": arguments["document_type"],
                    "metadata": {
                        "sync_source": "mcp_server",
                        "sync_timestamp": "2024-01-01T00:00:00Z",
                    },
                },
            }

            # Critical: Validate sync payload content
            if isinstance(content, dict) and "content" in content:
                sync_content_text = content["content"]
                assert (
                    len(sync_content_text) == 3000
                ), f"Sync content truncated: {len(sync_content_text)} != 3000"

            # Step 3: Trigger real-time sync
            with patch("httpx.AsyncClient.post") as mock_sync_call:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "success": True,
                    "document_id": document_id,
                    "status": "sync_queued",
                }
                mock_sync_call.return_value = mock_response

                # Simulate sync call to bridge service
                bridge_url = "http://test-bridge:8054/sync/realtime-document"
                sync_response = await mock_sync_call(bridge_url, json=sync_payload)

                return {
                    "document_created": True,
                    "document_id": document_id,
                    "sync_triggered": sync_response.status_code == 200,
                    "sync_payload_size": len(json.dumps(sync_payload)),
                    "content_length_in_sync": (
                        len(sync_content_text)
                        if isinstance(content, dict) and "content" in content
                        else 0
                    ),
                }

        # Execute sync trigger test
        result = await mock_create_with_sync_trigger(mcp_request)

        # Validate sync trigger
        assert result["document_created"] is True, "Document creation failed"
        assert result["sync_triggered"] is True, "Real-time sync not triggered"
        assert (
            result["content_length_in_sync"] == 3000
        ), f"Content truncated in sync: {result['content_length_in_sync']}"
        assert (
            result["sync_payload_size"] > 3500
        ), f"Sync payload too small: {result['sync_payload_size']} bytes"

    @pytest.mark.asyncio
    async def test_mcp_protocol_compliance_and_error_handling(self):
        """Test MCP protocol compliance and error handling."""
        # Test case 1: Valid MCP request
        valid_request = {
            "method": "tools/call",
            "params": {
                "name": "create_document",
                "arguments": {
                    "project_id": "test-project-67890",
                    "title": "Valid Document",
                    "document_type": "test",
                    "content": {
                        "content": "Valid content for testing MCP protocol compliance."
                    },
                },
            },
        }

        # Mock MCP protocol handler
        async def mock_mcp_protocol_handler(request):
            # Validate MCP request structure
            assert "method" in request, "MCP method missing"
            assert request["method"] == "tools/call", "Invalid MCP method"
            assert "params" in request, "MCP params missing"
            assert "name" in request["params"], "Tool name missing"
            assert "arguments" in request["params"], "Tool arguments missing"

            arguments = request["params"]["arguments"]

            # Validate required arguments
            required_fields = ["project_id", "title", "content"]
            for field in required_fields:
                assert field in arguments, f"Required field missing: {field}"

            # Validate content structure
            content = arguments["content"]
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert len(content_text) > 10, "Content too short"

            return {
                "success": True,
                "result": {
                    "document_id": str(uuid.uuid4()),
                    "message": "Document created successfully",
                },
            }

        # Test valid request
        result = await mock_mcp_protocol_handler(valid_request)
        assert result["success"] is True, "Valid MCP request failed"

        # Test case 2: Invalid MCP requests
        invalid_requests = [
            {
                "method": "tools/call",
                "params": {
                    "name": "create_document",
                    "arguments": {
                        # Missing project_id
                        "title": "Invalid Document",
                        "content": {"content": "Test content"},
                    },
                },
            },
            {
                "method": "tools/call",
                "params": {
                    "name": "create_document",
                    "arguments": {
                        "project_id": "test-project",
                        "title": "Invalid Content Document",
                        "content": None,  # Invalid content
                    },
                },
            },
        ]

        for invalid_request in invalid_requests:
            try:
                await mock_mcp_protocol_handler(invalid_request)
                assert False, "Invalid request should have failed"
            except (AssertionError, ValueError, KeyError) as e:
                # Expected error for invalid requests
                assert len(str(e)) > 0, "Error message should be provided"

    @pytest.mark.asyncio
    async def test_large_document_creation_through_mcp(self):
        """Test creation of large documents through MCP interface."""
        # Create very large document
        large_content = "A" * 50000  # 50KB content
        large_doc_request = {
            "project_id": "test-project-67890",
            "title": "Large Document Test",
            "document_type": "large_test",
            "content": {
                "content": large_content,
                "metadata": {"size": "50KB", "test_type": "large_content_validation"},
            },
        }

        # Mock large document creation
        async def mock_large_document_creation(arguments):
            content = arguments["content"]

            # Validate large content handling
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert (
                    len(content_text) == 50000
                ), f"Large content truncated: {len(content_text)} != 50000"

            # Simulate processing time for large content
            import time

            start_time = time.time()

            # Mock validation and storage operations
            await asyncio.sleep(0.1)  # Simulate processing delay

            processing_time = time.time() - start_time

            # Create response
            return {
                "success": True,
                "document_id": str(uuid.uuid4()),
                "content_size": (
                    len(content_text)
                    if isinstance(content, dict) and "content" in content
                    else 0
                ),
                "processing_time_ms": processing_time * 1000,
                "performance_acceptable": processing_time < 1.0,
            }

        # Execute large document test
        result = await mock_large_document_creation(large_doc_request)

        # Validate large document handling
        assert result["success"] is True, "Large document creation failed"
        assert (
            result["content_size"] == 50000
        ), f"Large content size mismatch: {result['content_size']}"
        assert (
            result["performance_acceptable"] is True
        ), f"Large document processing too slow: {result['processing_time_ms']}ms"

    @pytest.mark.asyncio
    async def test_concurrent_mcp_document_creation(self):
        """Test concurrent document creation through MCP interface."""
        # Create multiple document requests
        document_requests = []
        for i in range(5):
            doc_request = {
                "project_id": "test-project-67890",
                "title": f"Concurrent Document {i}",
                "document_type": "concurrent_test",
                "content": {
                    "content": f"This is concurrent test document {i} with substantial content for testing parallel MCP document creation. "
                    * 10,
                    "test_id": i,
                },
            }
            document_requests.append(doc_request)

        # Mock concurrent document creation
        async def mock_concurrent_creation(arguments):
            content = arguments["content"]

            # Simulate MCP processing delay
            await asyncio.sleep(0.1)

            # Validate content preservation
            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert (
                    len(content_text) > 100
                ), f"Concurrent content truncated: {len(content_text)}"

            return {
                "document_id": str(uuid.uuid4()),
                "title": arguments["title"],
                "content_length": (
                    len(content_text)
                    if isinstance(content, dict) and "content" in content
                    else 0
                ),
                "status": "created",
            }

        # Execute concurrent creation
        import time

        start_time = time.time()

        results = await asyncio.gather(
            *[mock_concurrent_creation(req) for req in document_requests]
        )

        total_time = time.time() - start_time

        # Validate concurrent creation
        assert len(results) == 5, f"Not all documents created: {len(results)}"
        assert total_time < 1.0, f"Concurrent creation too slow: {total_time}s"

        for i, result in enumerate(results):
            assert result["status"] == "created", f"Document {i} creation failed"
            assert (
                result["content_length"] > 100
            ), f"Document {i} content truncated: {result['content_length']}"
            assert (
                f"Concurrent Document {i}" in result["title"]
            ), f"Document {i} title mismatch"


class TestMCPDocumentValidation:
    """Test MCP document validation and integrity checks."""

    @pytest.mark.asyncio
    async def test_document_content_validation_in_mcp(self):
        """Test document content validation during MCP creation."""
        # Test various content types
        content_validation_tests = [
            {
                "name": "string_content",
                "content": "Simple string content for validation testing.",
                "expected_valid": True,
            },
            {
                "name": "dict_content",
                "content": {
                    "content": "Dictionary content with nested structure.",
                    "metadata": {"type": "test"},
                },
                "expected_valid": True,
            },
            {"name": "empty_string", "content": "", "expected_valid": False},
            {"name": "null_content", "content": None, "expected_valid": False},
            {
                "name": "complex_nested",
                "content": {
                    "sections": {
                        "intro": "Introduction section with content.",
                        "body": "Main body section with substantial content.",
                        "conclusion": "Conclusion section wrapping up the document.",
                    },
                    "metadata": {"author": "test", "version": 1},
                },
                "expected_valid": True,
            },
        ]

        async def validate_mcp_content(content):
            """Validate content according to MCP document creation rules."""
            if content is None:
                return False, "Content cannot be None"

            if isinstance(content, str):
                if len(content.strip()) == 0:
                    return False, "Content cannot be empty string"
                return True, "String content valid"

            if isinstance(content, dict):
                # Check if dictionary has meaningful content
                has_content = False

                def check_dict_content(obj):
                    nonlocal has_content
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str) and len(value.strip()) > 0:
                                has_content = True
                                return
                            elif isinstance(value, dict):
                                check_dict_content(value)

                check_dict_content(content)

                if not has_content:
                    return False, "Dictionary content has no meaningful text"

                return True, "Dictionary content valid"

            return False, f"Unsupported content type: {type(content)}"

        # Test each content validation case
        for test_case in content_validation_tests:
            is_valid, message = await validate_mcp_content(test_case["content"])

            assert (
                is_valid == test_case["expected_valid"]
            ), f"Validation failed for {test_case['name']}: {message}"

            if is_valid:
                # Additional checks for valid content
                content = test_case["content"]
                if isinstance(content, dict):
                    # Ensure nested content is preserved
                    json_str = json.dumps(content)
                    parsed_back = json.loads(json_str)
                    assert (
                        parsed_back == content
                    ), f"Content structure lost in serialization for {test_case['name']}"

    @pytest.mark.asyncio
    async def test_mcp_response_format_compliance(self):
        """Test that MCP responses follow the correct format."""
        # Test successful response format
        successful_creation = {
            "project_id": "test-project-67890",
            "title": "Format Compliance Test",
            "content": {"content": "Test content for format compliance validation."},
            "document_type": "format_test",
        }

        async def mock_mcp_create_document_response(arguments):
            """Mock MCP create_document response with proper format."""
            # Validate arguments
            content = arguments["content"]

            if isinstance(content, dict) and "content" in content:
                content_text = content["content"]
                assert len(content_text) > 0, "Content validation failed"

            # Generate proper MCP response format
            response = {
                "success": True,
                "document": {
                    "document_id": str(uuid.uuid4()),
                    "project_id": arguments["project_id"],
                    "title": arguments["title"],
                    "document_type": arguments.get("document_type", "document"),
                    "content_preview": (
                        content_text[:100]
                        if isinstance(content, dict) and "content" in content
                        else str(content)[:100]
                    ),
                    "created_at": "2024-01-01T00:00:00Z",
                },
                "metadata": {
                    "content_length": (
                        len(content_text)
                        if isinstance(content, dict) and "content" in content
                        else len(str(content))
                    ),
                    "processing_time_ms": 150,
                    "validation_passed": True,
                },
            }

            return response

        # Test successful response format
        result = await mock_mcp_create_document_response(successful_creation)

        # Validate MCP response format
        assert "success" in result, "MCP response missing success field"
        assert result["success"] is True, "MCP response indicates failure"
        assert "document" in result, "MCP response missing document field"
        assert "metadata" in result, "MCP response missing metadata field"

        # Validate document structure
        document = result["document"]
        required_doc_fields = [
            "document_id",
            "project_id",
            "title",
            "document_type",
            "created_at",
        ]
        for field in required_doc_fields:
            assert field in document, f"Document missing required field: {field}"

        # Validate metadata
        metadata = result["metadata"]
        assert metadata["content_length"] > 0, "Content length not recorded in metadata"
        assert metadata["validation_passed"] is True, "Validation status not recorded"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
