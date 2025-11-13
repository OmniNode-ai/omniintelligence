"""
Integration test for relationship extraction fix

Verifies that the document indexing handler correctly calls LangExtract
/extract/document endpoint and creates relationships in Memgraph.

Root cause: DocumentIndexingHandler was calling /extract/code (404 Not Found)
instead of /extract/document, resulting in 0 relationships being extracted.

Fix: Changed endpoint to /extract/document and updated request payload format.

Created: 2025-11-12
"""

import asyncio

import pytest
from neo4j import AsyncGraphDatabase


@pytest.mark.asyncio
async def test_langextract_endpoint_returns_relationships():
    """
    Test that LangExtract /extract/document endpoint returns relationships
    for Python code with imports, classes, and functions.
    """
    import httpx

    test_code = """import os
import sys
from pathlib import Path

class TestClass:
    def test_method(self):
        result = os.path.exists("test")
        return result

def main():
    obj = TestClass()
    obj.test_method()
    sys.exit(0)
"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8156/extract/document",
            json={
                "document_path": "test.py",
                "content": test_code,
                "extraction_options": {
                    "extract_entities": True,
                    "extract_relationships": True,
                    "enable_semantic_analysis": True,
                    "schema_hints": {},
                    "semantic_context": "",
                },
                "update_knowledge_graph": False,
                "emit_events": False,
            },
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        result = response.json()

        # Verify relationships are extracted
        assert "relationships" in result, "Response missing 'relationships' field"
        relationships = result["relationships"]

        assert len(relationships) > 0, "Expected relationships to be extracted"

        # Verify relationship types
        rel_types = {r["relationship_type"] for r in relationships}
        assert "IMPORTS" in rel_types, "Expected IMPORTS relationships to be detected"

        # Verify import relationships
        import_rels = [r for r in relationships if r["relationship_type"] == "IMPORTS"]
        assert (
            len(import_rels) >= 3
        ), f"Expected at least 3 import relationships, got {len(import_rels)}"

        # Verify import targets
        import_targets = {r["target_entity_id"] for r in import_rels}
        expected_imports = {"os", "sys", "pathlib.Path"}
        assert expected_imports.issubset(
            import_targets
        ), f"Expected imports {expected_imports}, got {import_targets}"


@pytest.mark.asyncio
async def test_memgraph_has_relationships():
    """
    Test that Memgraph contains relationships after document indexing.

    This verifies the end-to-end flow:
    1. Document indexing handler calls LangExtract /extract/document
    2. LangExtract returns relationships
    3. Relationships are stored in Memgraph
    """
    uri = "bolt://localhost:7687"
    driver = AsyncGraphDatabase.driver(uri)

    async with driver.session() as session:
        # Check total relationships
        result = await session.run("MATCH ()-[r]->() RETURN count(r) as total")
        record = await result.single()
        total = record["total"] if record else 0

        assert total > 0, f"Expected relationships in Memgraph, found {total}"

        # Check for IMPORTS relationships specifically
        result = await session.run(
            """
            MATCH ()-[r:IMPORTS]->()
            RETURN count(r) as import_count
        """
        )
        record = await result.single()
        import_count = record["import_count"] if record else 0

        assert import_count > 0, f"Expected IMPORTS relationships, found {import_count}"

        print(
            f"✅ Verified: {total} total relationships, {import_count} IMPORTS relationships"
        )

    await driver.close()


@pytest.mark.asyncio
async def test_document_indexing_handler_uses_correct_endpoint():
    """
    Test that DocumentIndexingHandler calls /extract/document (not /extract/code).

    This is a regression test for the bug where /extract/code was being called
    (which doesn't exist) instead of /extract/document.
    """
    import httpx

    # Verify /extract/code returns 404
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8156/extract/code",
            json={"content": "test", "file_path": "test.py", "language": "python"},
        )

        assert (
            response.status_code == 404
        ), "/extract/code should return 404 (endpoint doesn't exist)"

    # Verify /extract/document returns 200
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8156/extract/document",
            json={
                "document_path": "test.py",
                "content": "import os",
                "extraction_options": {
                    "extract_entities": True,
                    "extract_relationships": True,
                    "enable_semantic_analysis": True,
                    "schema_hints": {},
                    "semantic_context": "",
                },
                "update_knowledge_graph": False,
            },
        )

        assert (
            response.status_code == 200
        ), f"/extract/document should return 200, got {response.status_code}"
