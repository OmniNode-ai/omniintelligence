"""
Document Type Classification Tests for Vector Routing

Tests the document type classification logic that determines which
Qdrant collection to use for indexing documents.
"""

import os
import sys

import pytest

# Add the search service to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../../services/search"))

from app import determine_collection_for_document


class TestDocumentTypeClassification:
    """Test suite for document type classification logic"""

    def test_quality_document_types_route_to_quality_vectors(self):
        """Test that quality-related document types route to quality_vectors collection"""

        quality_document_types = [
            "technical_diagnosis",
            "quality_assessment",
            "code_review",
            "execution_report",
            "quality_report",
            "compliance_check",
            "performance_analysis",
        ]

        for doc_type in quality_document_types:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "quality_vectors"
            ), f"Document type '{doc_type}' should route to quality_vectors"

    def test_quality_document_types_case_insensitive(self):
        """Test that quality document type classification is case insensitive"""

        test_cases = [
            "TECHNICAL_DIAGNOSIS",
            "Quality_Assessment",
            "CODE_REVIEW",
            "execution_report",
            "QUALITY_REPORT",
            "Compliance_Check",
            "performance_ANALYSIS",
        ]

        for doc_type in test_cases:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "quality_vectors"
            ), f"Document type '{doc_type}' should route to quality_vectors (case insensitive)"

    def test_general_document_types_route_to_archon_vectors(self):
        """Test that general document types route to archon_vectors collection"""

        general_document_types = [
            "spec",
            "design",
            "note",
            "prp",
            "api",
            "guide",
            "documentation",
            "readme",
            "tutorial",
            "wiki",
        ]

        for doc_type in general_document_types:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "archon_vectors"
            ), f"Document type '{doc_type}' should route to archon_vectors"

    def test_unknown_document_type_defaults_to_archon_vectors(self):
        """Test that unknown document types default to archon_vectors collection"""

        unknown_types = [
            "unknown_type",
            "random_document",
            "new_experimental_type",
            "",
            None,
        ]

        for doc_type in unknown_types:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "archon_vectors"
            ), f"Unknown document type '{doc_type}' should default to archon_vectors"

    def test_missing_document_type_metadata(self):
        """Test handling when document_type is missing from metadata"""

        test_cases = [
            {},  # Empty metadata
            {"title": "Some document"},  # Metadata without document_type
            {"author": "test", "created_at": "2025-01-01"},  # Other metadata fields
        ]

        for metadata in test_cases:
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "archon_vectors"
            ), "Missing document_type should default to archon_vectors"

    def test_document_type_with_extra_spaces(self):
        """Test that document types with extra spaces are handled correctly"""

        test_cases = [
            "  technical_diagnosis  ",
            " quality_assessment ",
            "code_review ",
            " execution_report",
            "  spec  ",
            " note ",
        ]

        expected_collections = [
            "quality_vectors",  # technical_diagnosis
            "quality_vectors",  # quality_assessment
            "quality_vectors",  # code_review
            "quality_vectors",  # execution_report
            "archon_vectors",  # spec
            "archon_vectors",  # note
        ]

        for doc_type, expected in zip(test_cases, expected_collections):
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == expected
            ), f"Document type '{doc_type}' should route to {expected}"

    def test_numeric_and_special_character_document_types(self):
        """Test handling of document types with numbers and special characters"""

        test_cases = [
            "quality_report_v2",
            "technical-diagnosis",
            "code_review.final",
            "performance_analysis_2024",
            "123_document",
            "document@type",
            "type_with_underscore",
        ]

        for doc_type in test_cases:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            # Should default to archon_vectors since these don't match exact quality types
            assert (
                collection == "archon_vectors"
            ), f"Document type '{doc_type}' with special chars should default to archon_vectors"

    def test_partial_matches_not_accepted(self):
        """Test that partial matches don't route to quality_vectors"""

        partial_matches = [
            "quality",  # partial match of quality_assessment
            "technical",  # partial match of technical_diagnosis
            "code",  # partial match of code_review
            "performance",  # partial match of performance_analysis
            "report",  # appears in quality_report
            "assessment",  # appears in quality_assessment
        ]

        for doc_type in partial_matches:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "archon_vectors"
            ), f"Partial match '{doc_type}' should not route to quality_vectors"

    @pytest.mark.parametrize(
        "doc_type,expected_collection",
        [
            ("technical_diagnosis", "quality_vectors"),
            ("quality_assessment", "quality_vectors"),
            ("code_review", "quality_vectors"),
            ("execution_report", "quality_vectors"),
            ("quality_report", "quality_vectors"),
            ("compliance_check", "quality_vectors"),
            ("performance_analysis", "quality_vectors"),
            ("spec", "archon_vectors"),
            ("design", "archon_vectors"),
            ("note", "archon_vectors"),
            ("prp", "archon_vectors"),
            ("api", "archon_vectors"),
            ("guide", "archon_vectors"),
            ("unknown", "archon_vectors"),
            ("", "archon_vectors"),
        ],
    )
    def test_document_type_routing_parametrized(self, doc_type, expected_collection):
        """Parametrized test for document type routing"""
        metadata = {"document_type": doc_type}
        collection = determine_collection_for_document(metadata)
        assert collection == expected_collection

    def test_metadata_with_additional_fields(self):
        """Test that routing works correctly when metadata has additional fields"""

        metadata = {
            "document_type": "technical_diagnosis",
            "title": "System Performance Analysis",
            "author": "AI Agent",
            "project_id": "test-project-123",
            "created_at": "2025-01-01T00:00:00Z",
            "tags": ["performance", "analysis", "diagnosis"],
            "version": "1.0",
        }

        collection = determine_collection_for_document(metadata)
        assert (
            collection == "quality_vectors"
        ), "Additional metadata fields should not affect routing"

    def test_all_quality_types_are_covered(self):
        """Test that all defined quality document types are properly classified"""

        # These are the exact quality types defined in the function
        expected_quality_types = {
            "technical_diagnosis",
            "quality_assessment",
            "code_review",
            "execution_report",
            "quality_report",
            "compliance_check",
            "performance_analysis",
        }

        for doc_type in expected_quality_types:
            metadata = {"document_type": doc_type}
            collection = determine_collection_for_document(metadata)
            assert (
                collection == "quality_vectors"
            ), f"Quality type '{doc_type}' must route to quality_vectors"

    def test_collection_routing_consistency(self):
        """Test that the same document type always routes to the same collection"""

        test_doc_type = "technical_diagnosis"
        metadata = {"document_type": test_doc_type}

        # Call multiple times to ensure consistency
        collections = [determine_collection_for_document(metadata) for _ in range(10)]

        # All results should be the same
        assert all(
            collection == collections[0] for collection in collections
        ), "Document type routing should be consistent across multiple calls"
        assert (
            collections[0] == "quality_vectors"
        ), "technical_diagnosis should route to quality_vectors"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
