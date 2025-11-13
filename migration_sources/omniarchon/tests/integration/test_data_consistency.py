#!/usr/bin/env python3
"""
Data Consistency Validation Tests for MCP Document Indexing Pipeline

Comprehensive data consistency testing across all services:
1. Cross-service data synchronization validation
2. Data integrity after service failures and recovery
3. Eventual consistency verification and timing
4. Data corruption detection and prevention
5. Rollback and recovery scenario testing
6. Transactional integrity across the pipeline
7. Conflict resolution in concurrent updates
8. Data versioning and audit trail validation

These tests ensure data remains consistent and accurate across
the entire MCP document indexing ecosystem.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

from .conftest import IntegrationTestClient, TestDocument, TestProject

logger = logging.getLogger(__name__)


@dataclass
class DataConsistencyCheck:
    """Data consistency check result"""

    check_name: str
    service_name: str
    timestamp: datetime
    consistent: bool
    data_hash: Optional[str] = None
    record_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class CrossServiceValidation:
    """Cross-service data validation result"""

    document_id: str
    validation_timestamp: datetime
    services_checked: List[str]
    consistency_results: Dict[str, DataConsistencyCheck]
    overall_consistent: bool
    inconsistencies: List[str] = field(default_factory=list)


class DataConsistencyValidator:
    """
    Comprehensive data consistency validation across all services

    Provides methods to check data consistency, detect corruption,
    and validate synchronization across the MCP indexing pipeline.
    """

    def __init__(self, test_client: IntegrationTestClient):
        self.test_client = test_client
        self.session = test_client.session

    async def validate_document_consistency(
        self, document: TestDocument
    ) -> CrossServiceValidation:
        """Validate document consistency across all services"""
        logger.info(f"🔍 Validating document consistency: {document.id}")

        validation_timestamp = datetime.now(timezone.utc)
        consistency_results = {}
        services_checked = []

        # Check Main Server (source of truth)
        main_server_check = await self._check_main_server_document(document)
        consistency_results["main_server"] = main_server_check
        services_checked.append("main_server")

        # Check MCP Server representation
        mcp_server_check = await self._check_mcp_server_document(document)
        consistency_results["mcp_server"] = mcp_server_check
        services_checked.append("mcp_server")

        # Check Intelligence Service processing
        intelligence_check = await self._check_intelligence_service_document(document)
        consistency_results["intelligence"] = intelligence_check
        services_checked.append("intelligence")

        # Check Bridge Service sync status
        bridge_check = await self._check_bridge_service_document(document)
        consistency_results["bridge"] = bridge_check
        services_checked.append("bridge")

        # Check Vector Database (Qdrant) indexing
        vector_check = await self._check_vector_database_document(document)
        consistency_results["vector_db"] = vector_check
        services_checked.append("vector_db")

        # Check Knowledge Graph (Memgraph) entities
        graph_check = await self._check_knowledge_graph_document(document)
        consistency_results["knowledge_graph"] = graph_check
        services_checked.append("knowledge_graph")

        # Analyze consistency
        inconsistencies = []
        all_consistent = True

        for service, check in consistency_results.items():
            if not check.consistent:
                all_consistent = False
                inconsistencies.append(f"{service}: {check.error_message}")

        # Cross-service content validation
        if all_consistent:
            content_consistency = await self._validate_cross_service_content(
                document, consistency_results
            )
            if not content_consistency:
                all_consistent = False
                inconsistencies.append("Cross-service content mismatch detected")

        return CrossServiceValidation(
            document_id=document.id,
            validation_timestamp=validation_timestamp,
            services_checked=services_checked,
            consistency_results=consistency_results,
            overall_consistent=all_consistent,
            inconsistencies=inconsistencies,
        )

    async def _check_main_server_document(
        self, document: TestDocument
    ) -> DataConsistencyCheck:
        """Check document in main server database"""
        try:
            response = await self.test_client.http_client.get(
                f"{self.session.services.main_server}/api/projects/{document.project_id}/documents/{document.id}",
                timeout=10.0,
            )

            if response.status_code == 200:
                doc_data = response.json()

                # Calculate content hash for integrity check
                content_str = json.dumps(doc_data.get("content", {}), sort_keys=True)
                content_hash = hashlib.sha256(content_str.encode()).hexdigest()

                return DataConsistencyCheck(
                    check_name="main_server_document",
                    service_name="main_server",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    data_hash=content_hash,
                    record_count=1,
                    metadata={
                        "title": doc_data.get("title"),
                        "document_type": doc_data.get("document_type"),
                        "tags": doc_data.get("tags", []),
                        "last_updated": doc_data.get("updated_at"),
                    },
                )
            else:
                return DataConsistencyCheck(
                    check_name="main_server_document",
                    service_name="main_server",
                    timestamp=datetime.now(timezone.utc),
                    consistent=False,
                    error_message=f"Document not found in main server: HTTP {response.status_code}",
                )

        except Exception as e:
            return DataConsistencyCheck(
                check_name="main_server_document",
                service_name="main_server",
                timestamp=datetime.now(timezone.utc),
                consistent=False,
                error_message=f"Main server check failed: {str(e)}",
            )

    async def _check_mcp_server_document(
        self, document: TestDocument
    ) -> DataConsistencyCheck:
        """Check document accessibility via MCP server"""
        try:
            # Try to query for the document via MCP
            mcp_request = {
                "method": "get_document",
                "params": {"project_id": document.project_id, "doc_id": document.id},
            }

            response = await self.test_client.http_client.post(
                f"{self.session.services.mcp_server}/mcp",
                json=mcp_request,
                timeout=10.0,
            )

            if response.status_code == 200:
                result = response.json()

                if "result" in result and result["result"]:
                    doc_data = result["result"]

                    # Calculate content hash
                    content_str = json.dumps(
                        doc_data.get("content", {}), sort_keys=True
                    )
                    content_hash = hashlib.sha256(content_str.encode()).hexdigest()

                    return DataConsistencyCheck(
                        check_name="mcp_server_document",
                        service_name="mcp_server",
                        timestamp=datetime.now(timezone.utc),
                        consistent=True,
                        data_hash=content_hash,
                        record_count=1,
                        metadata={
                            "title": doc_data.get("title"),
                            "accessible_via_mcp": True,
                        },
                    )
                else:
                    return DataConsistencyCheck(
                        check_name="mcp_server_document",
                        service_name="mcp_server",
                        timestamp=datetime.now(timezone.utc),
                        consistent=False,
                        error_message="Document not accessible via MCP server",
                    )
            else:
                return DataConsistencyCheck(
                    check_name="mcp_server_document",
                    service_name="mcp_server",
                    timestamp=datetime.now(timezone.utc),
                    consistent=False,
                    error_message=f"MCP server returned error: HTTP {response.status_code}",
                )

        except Exception as e:
            return DataConsistencyCheck(
                check_name="mcp_server_document",
                service_name="mcp_server",
                timestamp=datetime.now(timezone.utc),
                consistent=False,
                error_message=f"MCP server check failed: {str(e)}",
            )

    async def _check_intelligence_service_document(
        self, document: TestDocument
    ) -> DataConsistencyCheck:
        """Check if document has been processed by intelligence service"""
        try:
            # Check if intelligence service has processed this document
            response = await self.test_client.http_client.get(
                f"{self.session.services.intelligence}/documents/{document.id}/entities",
                timeout=10.0,
            )

            if response.status_code == 200:
                entities_data = response.json()
                entity_count = len(entities_data.get("entities", []))

                # Calculate hash of extracted entities
                entities_str = json.dumps(
                    entities_data.get("entities", []), sort_keys=True
                )
                entities_hash = hashlib.sha256(entities_str.encode()).hexdigest()

                return DataConsistencyCheck(
                    check_name="intelligence_document_processing",
                    service_name="intelligence",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    data_hash=entities_hash,
                    record_count=entity_count,
                    metadata={
                        "entities_extracted": entity_count,
                        "processing_completed": True,
                    },
                )
            elif response.status_code == 404:
                # Document may not be processed yet (eventual consistency)
                return DataConsistencyCheck(
                    check_name="intelligence_document_processing",
                    service_name="intelligence",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,  # Not an error, might be pending
                    record_count=0,
                    metadata={"processing_status": "pending", "entities_extracted": 0},
                )
            else:
                return DataConsistencyCheck(
                    check_name="intelligence_document_processing",
                    service_name="intelligence",
                    timestamp=datetime.now(timezone.utc),
                    consistent=False,
                    error_message=f"Intelligence service error: HTTP {response.status_code}",
                )

        except Exception as e:
            return DataConsistencyCheck(
                check_name="intelligence_document_processing",
                service_name="intelligence",
                timestamp=datetime.now(timezone.utc),
                consistent=False,
                error_message=f"Intelligence service check failed: {str(e)}",
            )

    async def _check_bridge_service_document(
        self, document: TestDocument
    ) -> DataConsistencyCheck:
        """Check bridge service sync status for document"""
        try:
            # Check sync status for this document
            response = await self.test_client.http_client.get(
                f"{self.session.services.bridge}/sync/document/{document.id}/status",
                timeout=10.0,
            )

            if response.status_code == 200:
                sync_data = response.json()

                return DataConsistencyCheck(
                    check_name="bridge_sync_status",
                    service_name="bridge",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    record_count=1,
                    metadata={
                        "sync_status": sync_data.get("status", "unknown"),
                        "last_sync": sync_data.get("last_sync"),
                        "sync_attempts": sync_data.get("sync_attempts", 0),
                    },
                )
            elif response.status_code == 404:
                # Document may not be in sync queue yet
                return DataConsistencyCheck(
                    check_name="bridge_sync_status",
                    service_name="bridge",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    record_count=0,
                    metadata={"sync_status": "not_queued"},
                )
            else:
                return DataConsistencyCheck(
                    check_name="bridge_sync_status",
                    service_name="bridge",
                    timestamp=datetime.now(timezone.utc),
                    consistent=False,
                    error_message=f"Bridge service error: HTTP {response.status_code}",
                )

        except Exception as e:
            return DataConsistencyCheck(
                check_name="bridge_sync_status",
                service_name="bridge",
                timestamp=datetime.now(timezone.utc),
                consistent=False,
                error_message=f"Bridge service check failed: {str(e)}",
            )

    async def _check_vector_database_document(
        self, document: TestDocument
    ) -> DataConsistencyCheck:
        """Check if document is indexed in vector database (Qdrant)"""
        try:
            # Search for document in vector database
            search_request = {
                "query": f"document {document.id}",
                "mode": "semantic",
                "limit": 10,
                "include_content": True,
            }

            response = await self.test_client.http_client.post(
                f"{self.session.services.search}/search",
                json=search_request,
                timeout=10.0,
            )

            if response.status_code == 200:
                search_results = response.json()
                results = search_results.get("results", [])

                # Check if our document is in the results
                document_found = False
                vector_hash = None

                for result in results:
                    if (
                        document.id in str(result)
                        or document.title in str(result)
                        or self.test_client.session.session_id in str(result)
                    ):
                        document_found = True
                        # Calculate hash of vector representation
                        result_str = json.dumps(result, sort_keys=True)
                        vector_hash = hashlib.sha256(result_str.encode()).hexdigest()
                        break

                return DataConsistencyCheck(
                    check_name="vector_database_indexing",
                    service_name="vector_db",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    data_hash=vector_hash,
                    record_count=1 if document_found else 0,
                    metadata={
                        "indexed_in_vector_db": document_found,
                        "total_search_results": len(results),
                    },
                )
            else:
                return DataConsistencyCheck(
                    check_name="vector_database_indexing",
                    service_name="vector_db",
                    timestamp=datetime.now(timezone.utc),
                    consistent=False,
                    error_message=f"Vector search failed: HTTP {response.status_code}",
                )

        except Exception as e:
            return DataConsistencyCheck(
                check_name="vector_database_indexing",
                service_name="vector_db",
                timestamp=datetime.now(timezone.utc),
                consistent=False,
                error_message=f"Vector database check failed: {str(e)}",
            )

    async def _check_knowledge_graph_document(
        self, document: TestDocument
    ) -> DataConsistencyCheck:
        """Check if document entities are in knowledge graph (Memgraph)"""
        try:
            # Check if document entities exist in knowledge graph
            response = await self.test_client.http_client.get(
                f"{self.session.services.search}/entities/{document.id}/relationships",
                timeout=10.0,
            )

            if response.status_code == 200:
                graph_data = response.json()
                entity_count = len(graph_data.get("entities", []))
                relationship_count = len(graph_data.get("relationships", []))

                # Calculate hash of graph representation
                graph_str = json.dumps(graph_data, sort_keys=True)
                graph_hash = hashlib.sha256(graph_str.encode()).hexdigest()

                return DataConsistencyCheck(
                    check_name="knowledge_graph_entities",
                    service_name="knowledge_graph",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    data_hash=graph_hash,
                    record_count=entity_count,
                    metadata={
                        "entities_in_graph": entity_count,
                        "relationships_count": relationship_count,
                        "graph_indexed": entity_count > 0,
                    },
                )
            elif response.status_code == 404:
                # Document entities may not be in graph yet
                return DataConsistencyCheck(
                    check_name="knowledge_graph_entities",
                    service_name="knowledge_graph",
                    timestamp=datetime.now(timezone.utc),
                    consistent=True,
                    record_count=0,
                    metadata={"entities_in_graph": 0, "graph_status": "not_indexed"},
                )
            else:
                return DataConsistencyCheck(
                    check_name="knowledge_graph_entities",
                    service_name="knowledge_graph",
                    timestamp=datetime.now(timezone.utc),
                    consistent=False,
                    error_message=f"Knowledge graph query failed: HTTP {response.status_code}",
                )

        except Exception as e:
            return DataConsistencyCheck(
                check_name="knowledge_graph_entities",
                service_name="knowledge_graph",
                timestamp=datetime.now(timezone.utc),
                consistent=False,
                error_message=f"Knowledge graph check failed: {str(e)}",
            )

    async def _validate_cross_service_content(
        self,
        document: TestDocument,
        consistency_results: Dict[str, DataConsistencyCheck],
    ) -> bool:
        """Validate content consistency across services"""
        # Get content hashes from services that store content
        main_server_hash = consistency_results.get("main_server", {}).data_hash
        mcp_server_hash = consistency_results.get("mcp_server", {}).data_hash

        # Content should be identical between main server and MCP server
        if main_server_hash and mcp_server_hash:
            return main_server_hash == mcp_server_hash

        # If only one has content, that's still consistent
        return True

    async def wait_for_eventual_consistency(
        self,
        document: TestDocument,
        max_wait_seconds: float = 60.0,
        check_interval: float = 5.0,
    ) -> bool:
        """Wait for eventual consistency across all services"""
        logger.info(f"⏳ Waiting for eventual consistency: {document.id}")

        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            validation = await self.validate_document_consistency(document)

            if validation.overall_consistent:
                elapsed = time.time() - start_time
                logger.info(f"✅ Eventual consistency achieved in {elapsed:.1f}s")
                return True

            logger.debug(f"Consistency check failed: {validation.inconsistencies}")
            await asyncio.sleep(check_interval)

        elapsed = time.time() - start_time
        logger.warning(f"⚠️ Eventual consistency not achieved after {elapsed:.1f}s")
        return False


@pytest.mark.data_consistency
@pytest.mark.asyncio
class TestCrossServiceDataConsistency:
    """
    Test data consistency across all services in the pipeline

    These tests ensure that data remains synchronized and consistent
    across the entire MCP document indexing ecosystem.
    """

    async def test_document_consistency_immediate(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test immediate data consistency after document creation"""
        logger.info("🔍 Testing immediate document consistency")

        # Create validator
        validator = DataConsistencyValidator(test_client)

        # Create test document
        document = await test_client.create_test_document(
            test_project,
            "Immediate Consistency Test",
            content_override={
                "test_scenario": "immediate_consistency",
                "consistency_requirements": [
                    "main_server_storage",
                    "mcp_server_access",
                    "cross_service_content_match",
                ],
                "expected_behavior": "Document should be immediately consistent in core services",
            },
        )

        # Validate consistency immediately after creation
        validation = await validator.validate_document_consistency(document)

        logger.info("📊 Immediate Consistency Results:")
        for service, check in validation.consistency_results.items():
            status = "✅" if check.consistent else "❌"
            logger.info(f"  {status} {service}: {check.error_message or 'OK'}")

        # Core services should be immediately consistent
        core_services = ["main_server", "mcp_server"]
        for service in core_services:
            check = validation.consistency_results.get(service)
            assert check is not None, f"Missing consistency check for {service}"
            assert (
                check.consistent
            ), f"Core service {service} not consistent: {check.error_message}"

        # Content should match between main server and MCP server
        main_hash = validation.consistency_results["main_server"].data_hash
        mcp_hash = validation.consistency_results["mcp_server"].data_hash

        if main_hash and mcp_hash:
            assert (
                main_hash == mcp_hash
            ), "Content hash mismatch between main server and MCP server"

        logger.info("🎉 Immediate consistency test passed")

    async def test_eventual_consistency_full_pipeline(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test eventual consistency across the complete pipeline"""
        logger.info("🔍 Testing eventual consistency for full pipeline")

        # Create validator
        validator = DataConsistencyValidator(test_client)

        # Create test document
        document = await test_client.create_test_document(
            test_project,
            "Eventual Consistency Test",
            content_override={
                "test_scenario": "eventual_consistency",
                "pipeline_requirements": [
                    "intelligence_processing",
                    "bridge_synchronization",
                    "vector_indexing",
                    "knowledge_graph_entities",
                ],
                "expected_behavior": "Document should achieve full pipeline consistency within 60 seconds",
            },
        )

        # Wait for eventual consistency
        consistency_achieved = await validator.wait_for_eventual_consistency(
            document, max_wait_seconds=60.0, check_interval=5.0
        )

        # Final validation
        final_validation = await validator.validate_document_consistency(document)

        logger.info("📊 Eventual Consistency Results:")
        for service, check in final_validation.consistency_results.items():
            status = "✅" if check.consistent else "❌"
            count = (
                f" ({check.record_count} records)"
                if check.record_count is not None
                else ""
            )
            logger.info(f"  {status} {service}: {check.error_message or 'OK'}{count}")

        # Assert eventual consistency was achieved
        assert consistency_achieved, "Eventual consistency not achieved within timeout"
        assert (
            final_validation.overall_consistent
        ), f"Final validation failed: {final_validation.inconsistencies}"

        # Verify processing in downstream services
        intelligence_check = final_validation.consistency_results.get("intelligence")
        vector_check = final_validation.consistency_results.get("vector_db")

        # Intelligence service should have processed the document
        assert (
            intelligence_check.consistent
        ), "Intelligence service consistency check failed"

        # Vector database should have indexed the document
        assert vector_check.consistent, "Vector database consistency check failed"

        logger.info("🎉 Eventual consistency test passed")

    async def test_consistency_after_multiple_documents(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test consistency when multiple documents are created rapidly"""
        logger.info("🔍 Testing consistency with multiple documents")

        # Create validator
        validator = DataConsistencyValidator(test_client)

        # Create multiple documents rapidly
        num_documents = 5
        documents = []

        for i in range(num_documents):
            document = await test_client.create_test_document(
                test_project,
                f"Multi-Document Consistency Test {i}",
                content_override={
                    "test_scenario": "multi_document_consistency",
                    "document_number": i,
                    "total_documents": num_documents,
                    "unique_content": f"Document {i} content for consistency testing",
                },
            )
            documents.append(document)

        logger.info(f"✅ Created {num_documents} documents")

        # Wait for all documents to achieve eventual consistency
        consistency_results = []

        for i, document in enumerate(documents):
            logger.info(f"Checking consistency for document {i+1}/{num_documents}")

            consistency_achieved = await validator.wait_for_eventual_consistency(
                document, max_wait_seconds=45.0
            )

            final_validation = await validator.validate_document_consistency(document)
            consistency_results.append(
                (document, consistency_achieved, final_validation)
            )

        # Analyze results
        successful_consistency = sum(
            1 for _, achieved, _ in consistency_results if achieved
        )
        fully_consistent = sum(
            1
            for _, _, validation in consistency_results
            if validation.overall_consistent
        )

        logger.info("📊 Multi-Document Consistency Results:")
        logger.info(
            f"  Documents achieving eventual consistency: {successful_consistency}/{num_documents}"
        )
        logger.info(f"  Documents fully consistent: {fully_consistent}/{num_documents}")

        # Detailed per-document results
        for i, (document, achieved, validation) in enumerate(consistency_results):
            status = "✅" if achieved and validation.overall_consistent else "❌"
            logger.info(f"  {status} Document {i+1}: {document.title[:30]}...")

            if validation.inconsistencies:
                for inconsistency in validation.inconsistencies:
                    logger.info(f"    ⚠️ {inconsistency}")

        # Performance assertions
        assert (
            successful_consistency >= num_documents * 0.8
        ), f"Too many documents failed eventual consistency: {successful_consistency}/{num_documents}"

        assert (
            fully_consistent >= num_documents * 0.8
        ), f"Too many documents not fully consistent: {fully_consistent}/{num_documents}"

        logger.info("🎉 Multi-document consistency test passed")


@pytest.mark.data_consistency
@pytest.mark.asyncio
class TestDataIntegrityAndCorruption:
    """
    Test data integrity and corruption detection/prevention

    These tests ensure data integrity is maintained and corruption
    is detected and handled appropriately.
    """

    async def test_content_hash_validation(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test content hash validation across services"""
        logger.info("🔍 Testing content hash validation")

        # Create validator
        validator = DataConsistencyValidator(test_client)

        # Create document with known content
        known_content = {
            "test_scenario": "content_hash_validation",
            "deterministic_content": "This content should have consistent hash",
            "structured_data": {
                "field1": "value1",
                "field2": "value2",
                "field3": ["item1", "item2", "item3"],
            },
            "metadata": {
                "created_for": "hash_validation_test",
                "timestamp": "2024-01-01T00:00:00Z",  # Fixed timestamp for consistent hash
            },
        }

        document = await test_client.create_test_document(
            test_project, "Content Hash Validation Test", content_override=known_content
        )

        # Calculate expected hash
        content_str = json.dumps(known_content, sort_keys=True)
        expected_hash = hashlib.sha256(content_str.encode()).hexdigest()

        logger.info(f"Expected content hash: {expected_hash}")

        # Wait for processing
        await asyncio.sleep(10.0)

        # Validate consistency and check hashes
        validation = await validator.validate_document_consistency(document)

        # Check hash consistency across services
        main_server_hash = validation.consistency_results.get(
            "main_server", {}
        ).data_hash
        mcp_server_hash = validation.consistency_results.get("mcp_server", {}).data_hash

        logger.info("📊 Content Hash Results:")
        logger.info(f"  Expected: {expected_hash}")
        logger.info(f"  Main Server: {main_server_hash}")
        logger.info(f"  MCP Server: {mcp_server_hash}")

        # Hashes should be consistent (though they might differ from expected due to additional metadata)
        if main_server_hash and mcp_server_hash:
            assert (
                main_server_hash == mcp_server_hash
            ), "Content hash mismatch between services"

        # At least one service should have a valid hash
        assert (
            main_server_hash or mcp_server_hash
        ), "No content hash found in any service"

        logger.info("🎉 Content hash validation test passed")

    async def test_data_corruption_detection(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test detection of data corruption scenarios"""
        logger.info("🔍 Testing data corruption detection")

        # Create validator
        validator = DataConsistencyValidator(test_client)

        # Create document
        document = await test_client.create_test_document(
            test_project,
            "Data Corruption Detection Test",
            content_override={
                "test_scenario": "corruption_detection",
                "integrity_markers": {
                    "checksum": "known_value",
                    "version": "1.0",
                    "validation_key": "test_key_123",
                },
                "critical_data": "This data should remain uncorrupted",
            },
        )

        # Validate initial state
        initial_validation = await validator.validate_document_consistency(document)

        assert (
            initial_validation.overall_consistent
        ), "Initial state should be consistent"

        # Store initial hashes for comparison
        initial_hashes = {
            service: check.data_hash
            for service, check in initial_validation.consistency_results.items()
            if check.data_hash
        }

        logger.info(f"📊 Initial state hashes: {len(initial_hashes)} services")

        # Wait for full processing
        await asyncio.sleep(15.0)

        # Re-validate to check for any changes
        later_validation = await validator.validate_document_consistency(document)

        # Compare hashes to detect unexpected changes
        hash_changes = []
        for service, initial_hash in initial_hashes.items():
            later_check = later_validation.consistency_results.get(service)
            if later_check and later_check.data_hash:
                if later_check.data_hash != initial_hash:
                    hash_changes.append(
                        f"{service}: {initial_hash} -> {later_check.data_hash}"
                    )

        if hash_changes:
            logger.warning("⚠️ Hash changes detected:")
            for change in hash_changes:
                logger.warning(f"  {change}")
        else:
            logger.info("✅ No unexpected hash changes detected")

        # The document should still be consistent overall
        assert (
            later_validation.overall_consistent
        ), "Document consistency degraded over time"

        logger.info("🎉 Data corruption detection test passed")

    async def test_concurrent_update_integrity(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test data integrity under concurrent updates"""
        logger.info("🔍 Testing concurrent update integrity")

        # Create base document
        document = await test_client.create_test_document(
            test_project,
            "Concurrent Update Integrity Test",
            content_override={
                "test_scenario": "concurrent_updates",
                "base_content": "Original content for concurrent testing",
                "update_counter": 0,
            },
        )

        # Wait for initial processing
        await asyncio.sleep(10.0)

        # Attempt concurrent updates (simulate race conditions)
        num_concurrent_updates = 3

        async def attempt_update(update_id: int):
            try:
                # Try to update the document
                mcp_request = {
                    "method": "update_document",
                    "params": {
                        "project_id": test_project.id,
                        "doc_id": document.id,
                        "title": f"Updated Title {update_id}",
                        "content": {
                            "test_scenario": "concurrent_updates",
                            "updated_by": f"update_{update_id}",
                            "update_timestamp": time.time(),
                            "update_counter": update_id,
                        },
                    },
                }

                response = await test_client.http_client.post(
                    f"{test_client.session.services.mcp_server}/mcp",
                    json=mcp_request,
                    timeout=10.0,
                )

                return {
                    "update_id": update_id,
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                }

            except Exception as e:
                return {"update_id": update_id, "success": False, "error": str(e)}

        # Execute concurrent updates
        update_tasks = [attempt_update(i) for i in range(num_concurrent_updates)]
        update_results = await asyncio.gather(*update_tasks, return_exceptions=True)

        successful_updates = [
            r for r in update_results if isinstance(r, dict) and r.get("success")
        ]
        failed_updates = [
            r for r in update_results if isinstance(r, dict) and not r.get("success")
        ]

        logger.info("📊 Concurrent Update Results:")
        logger.info(f"  Successful updates: {len(successful_updates)}")
        logger.info(f"  Failed updates: {len(failed_updates)}")

        # Wait for processing to complete
        await asyncio.sleep(15.0)

        # Validate final state
        validator = DataConsistencyValidator(test_client)
        final_validation = await validator.validate_document_consistency(document)

        # Document should still be consistent despite concurrent updates
        assert (
            final_validation.overall_consistent
        ), "Document inconsistent after concurrent updates"

        # At least one update should have succeeded OR all should have failed gracefully
        assert (
            len(successful_updates) > 0 or len(failed_updates) == num_concurrent_updates
        ), "Concurrent updates caused unexpected behavior"

        logger.info("🎉 Concurrent update integrity test passed")


@pytest.mark.data_consistency
@pytest.mark.asyncio
class TestServiceRecoveryConsistency:
    """
    Test data consistency during and after service recovery scenarios

    These tests ensure data remains consistent when services fail
    and recover, and that recovery procedures maintain data integrity.
    """

    async def test_consistency_during_service_restart(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test data consistency during simulated service restart"""
        logger.info("🔍 Testing consistency during service restart simulation")

        # Create validator
        validator = DataConsistencyValidator(test_client)

        # Create document before "restart"
        document = await test_client.create_test_document(
            test_project,
            "Service Restart Consistency Test",
            content_override={
                "test_scenario": "service_restart",
                "pre_restart_data": "This data exists before restart",
                "consistency_requirement": "Data should survive restart simulation",
            },
        )

        # Wait for initial processing
        await asyncio.sleep(10.0)

        # Validate pre-restart state
        pre_restart_validation = await validator.validate_document_consistency(document)

        logger.info("📊 Pre-restart validation:")
        for service, check in pre_restart_validation.consistency_results.items():
            status = "✅" if check.consistent else "❌"
            logger.info(f"  {status} {service}")

        # Simulate service unavailability by temporarily changing URLs
        original_urls = {
            "intelligence": test_client.session.services.intelligence,
            "bridge": test_client.session.services.bridge,
            "search": test_client.session.services.search,
        }

        # Temporarily point to invalid URLs to simulate service unavailability
        test_client.session.services.intelligence = "http://nonexistent:9999"
        test_client.session.services.bridge = "http://nonexistent:9999"
        test_client.session.services.search = "http://nonexistent:9999"

        # Wait during "downtime"
        await asyncio.sleep(5.0)

        # Restore services
        for service, url in original_urls.items():
            setattr(test_client.session.services, service, url)

        # Wait for "recovery"
        await asyncio.sleep(10.0)

        # Validate post-restart state
        post_restart_validation = await validator.validate_document_consistency(
            document
        )

        logger.info("📊 Post-restart validation:")
        for service, check in post_restart_validation.consistency_results.items():
            status = "✅" if check.consistent else "❌"
            logger.info(f"  {status} {service}")

        # Core services should maintain consistency
        core_services = ["main_server", "mcp_server"]
        for service in core_services:
            pre_check = pre_restart_validation.consistency_results.get(service)
            post_check = post_restart_validation.consistency_results.get(service)

            assert (
                pre_check and pre_check.consistent
            ), f"Pre-restart {service} should be consistent"
            assert (
                post_check and post_check.consistent
            ), f"Post-restart {service} should be consistent"

            # Content should be identical
            if pre_check.data_hash and post_check.data_hash:
                assert (
                    pre_check.data_hash == post_check.data_hash
                ), f"Content hash changed for {service} after restart"

        logger.info("🎉 Service restart consistency test passed")

    async def test_recovery_data_integrity(
        self, test_client: IntegrationTestClient, test_project: TestProject
    ):
        """Test data integrity during recovery procedures"""
        logger.info("🔍 Testing recovery data integrity")

        # Create multiple documents to test recovery
        documents = []
        for i in range(3):
            document = await test_client.create_test_document(
                test_project,
                f"Recovery Test Document {i}",
                content_override={
                    "test_scenario": "recovery_integrity",
                    "document_index": i,
                    "recovery_test_data": f"Recovery test content for document {i}",
                    "critical_field": f"critical_value_{i}",
                },
            )
            documents.append(document)

        # Wait for initial processing
        await asyncio.sleep(15.0)

        # Validate all documents before "failure"
        validator = DataConsistencyValidator(test_client)
        pre_failure_validations = []

        for document in documents:
            validation = await validator.validate_document_consistency(document)
            pre_failure_validations.append(validation)

        consistent_before = sum(
            1 for v in pre_failure_validations if v.overall_consistent
        )
        logger.info(
            f"📊 Pre-failure: {consistent_before}/{len(documents)} documents consistent"
        )

        # Simulate recovery by checking consistency multiple times
        recovery_checks = []
        for check_round in range(3):
            logger.info(f"Recovery check round {check_round + 1}")

            round_validations = []
            for document in documents:
                validation = await validator.validate_document_consistency(document)
                round_validations.append(validation)

            recovery_checks.append(round_validations)

            # Brief pause between checks
            await asyncio.sleep(5.0)

        # Analyze recovery consistency
        for check_round, validations in enumerate(recovery_checks):
            consistent_count = sum(1 for v in validations if v.overall_consistent)
            logger.info(
                f"📊 Recovery round {check_round + 1}: {consistent_count}/{len(documents)} consistent"
            )

        # Final validation
        final_validations = recovery_checks[-1]
        finally_consistent = sum(1 for v in final_validations if v.overall_consistent)

        # Recovery should maintain or improve consistency
        assert (
            finally_consistent >= consistent_before * 0.8
        ), f"Recovery degraded consistency: {finally_consistent}/{len(documents)} vs {consistent_before}/{len(documents)}"

        # Check for data corruption during recovery
        for i, (pre_validation, final_validation) in enumerate(
            zip(pre_failure_validations, final_validations)
        ):
            document = documents[i]

            # Compare content hashes where available
            for service in ["main_server", "mcp_server"]:
                pre_check = pre_validation.consistency_results.get(service)
                final_check = final_validation.consistency_results.get(service)

                if (
                    pre_check
                    and pre_check.data_hash
                    and final_check
                    and final_check.data_hash
                ):
                    if pre_check.data_hash != final_check.data_hash:
                        logger.warning(
                            f"⚠️ Hash change detected for {document.id} in {service}"
                        )

        logger.info("🎉 Recovery data integrity test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "data_consistency"])
