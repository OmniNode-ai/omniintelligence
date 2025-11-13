"""
Intelligence Document Writer Module

Handles write operations for intelligence documents stored in archon_projects.docs JSONB field.
Focused on document updates, correlation data insertion, and database write operations.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IntelligenceDocumentWriter:
    """Handles write operations for intelligence documents."""

    def __init__(self, database_client):
        """Initialize the writer with database client."""
        self.client = database_client

    def update_document_correlations(
        self, document_id: str, correlation_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update correlation data for a specific intelligence document.

        Args:
            document_id: UUID of the intelligence document to update
            correlation_data: Dictionary containing correlation analysis data

        Returns:
            Dict with success status and details
        """
        try:
            logger.info(f"🔄 Updating correlations for document {document_id}")

            # Find which project contains this document
            project_info = self._find_document_location(document_id)
            if not project_info:
                return {
                    "success": False,
                    "error": f"Document {document_id} not found in any project",
                    "document_id": document_id,
                }

            # Update the document with new correlation data
            return self._update_document_in_project(
                project_info["project_id"],
                project_info["document_index"],
                document_id,
                correlation_data,
            )

        except Exception as e:
            logger.error(f"❌ Error updating document correlations: {e}")
            return {"success": False, "error": str(e), "document_id": document_id}

    def _find_document_location(self, document_id: str) -> Optional[dict[str, Any]]:
        """Find which project contains a specific intelligence document."""
        try:
            result = self.client.table("archon_projects").select("id,docs").execute()

            for project in result.data:
                docs = project.get("docs", [])
                for index, doc in enumerate(docs):
                    if doc.get("id") == document_id:
                        return {"project_id": project["id"], "document_index": index}
            return None

        except Exception as e:
            logger.error(f"Error finding document {document_id}: {e}")
            return None

    def _update_document_in_project(
        self,
        project_id: str,
        doc_index: int,
        document_id: str,
        correlation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a specific document within a project's docs array."""
        try:
            # Get current project docs
            project_result = (
                self.client.table("archon_projects")
                .select("docs")
                .eq("id", project_id)
                .execute()
            )
            if not project_result.data:
                return {
                    "success": False,
                    "error": f"Project {project_id} not found",
                    "document_id": document_id,
                }

            current_docs = project_result.data[0]["docs"]

            # Update the specific document
            if doc_index < len(current_docs):
                document = current_docs[doc_index]

                if "content" not in document:
                    document["content"] = {}

                document["content"]["correlation_analysis"] = correlation_data

                # Update the database
                update_result = (
                    self.client.table("archon_projects")
                    .update({"docs": current_docs})
                    .eq("id", project_id)
                    .execute()
                )

                if update_result.data:
                    logger.info(
                        f"✅ Successfully updated correlations for document {document_id}"
                    )
                    return {
                        "success": True,
                        "document_id": document_id,
                        "project_id": project_id,
                        "correlations_updated": {
                            "temporal": len(
                                correlation_data.get("temporal_correlations", [])
                            ),
                            "semantic": len(
                                correlation_data.get("semantic_correlations", [])
                            ),
                            "breaking": len(
                                correlation_data.get("breaking_changes", [])
                            ),
                        },
                    }

                return {
                    "success": False,
                    "error": "Database update failed",
                    "document_id": document_id,
                }

            return {
                "success": False,
                "error": f"Document index {doc_index} out of range",
                "document_id": document_id,
            }

        except Exception as e:
            logger.error(f"Error updating document in project: {e}")
            return {"success": False, "error": str(e), "document_id": document_id}


def create_intelligence_document_writer(database_client) -> IntelligenceDocumentWriter:
    """Factory function to create document writer instance."""
    return IntelligenceDocumentWriter(database_client)
