"""
Document Service Module for Archon

This module provides core business logic for document operations within projects
that can be shared between MCP tools and FastAPI endpoints.
"""

import os
import uuid

# Removed direct logging import - using unified config
from datetime import datetime
from typing import Any

import httpx
from server.config.logfire_config import get_logger
from src.server.utils import get_database_client

logger = get_logger(__name__)


class DocumentService:
    """Service class for document operations within projects"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_database_client()

    async def add_document(
        self,
        project_id: str,
        document_type: str,
        title: str,
        content: dict[str, Any] = None,
        tags: list[str] = None,
        author: str = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Add a new document to a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Get current project
            project_response = (
                self.supabase_client.table("archon_projects")
                .select("docs")
                .eq("id", project_id)
                .execute()
            )
            if not project_response.data:
                return False, {"error": f"Project with ID {project_id} not found"}

            current_docs = project_response.data[0].get("docs", [])

            # Create new document entry
            new_doc = {
                "id": str(uuid.uuid4()),
                "document_type": document_type,
                "title": title,
                "content": content or {},
                "tags": tags or [],
                "status": "draft",
                "version": "1.0",
            }

            if author:
                new_doc["author"] = author

            # Add to docs array
            updated_docs = current_docs + [new_doc]

            # Update project
            response = (
                self.supabase_client.table("archon_projects")
                .update({"docs": updated_docs})
                .eq("id", project_id)
                .execute()
            )

            if response.data:
                # Document created successfully - use resilient indexing service
                await self._queue_document_for_resilient_indexing(
                    document_id=new_doc["id"],
                    project_id=project_id,
                    title=new_doc["title"],
                    content=new_doc["content"],
                    document_type=new_doc["document_type"],
                    metadata={
                        "tags": new_doc.get("tags", []),
                        "author": new_doc.get("author"),
                        "status": new_doc["status"],
                        "version": new_doc["version"],
                        "created_at": datetime.now().isoformat(),
                    },
                )

                return True, {
                    "document": {
                        "id": new_doc["id"],
                        "project_id": project_id,
                        "document_type": new_doc["document_type"],
                        "title": new_doc["title"],
                        "content": new_doc["content"],  # Include the content field
                        "tags": new_doc.get("tags", []),
                        "author": new_doc.get("author"),
                        "status": new_doc["status"],
                        "version": new_doc["version"],
                    }
                }
            else:
                return False, {"error": "Failed to add document to project"}

        except Exception as e:
            logger.error(f"Error adding document: {e}")
            return False, {"error": f"Error adding document: {e!s}"}

    def list_documents(
        self, project_id: str, include_content: bool = False
    ) -> tuple[bool, dict[str, Any]]:
        """
        List all documents in a project's docs JSONB field.

        Args:
            project_id: The project ID
            include_content: If True, includes full document content.
                           If False (default), returns metadata only.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            response = (
                self.supabase_client.table("archon_projects")
                .select("docs")
                .eq("id", project_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Project with ID {project_id} not found"}

            docs = response.data[0].get("docs", [])

            # Format documents for response
            documents = []
            for doc in docs:
                if include_content:
                    # Return full document
                    documents.append(doc)
                else:
                    # Return metadata only
                    documents.append(
                        {
                            "id": doc.get("id"),
                            "document_type": doc.get("document_type"),
                            "title": doc.get("title"),
                            "status": doc.get("status"),
                            "version": doc.get("version"),
                            "tags": doc.get("tags", []),
                            "author": doc.get("author"),
                            "created_at": doc.get("created_at"),
                            "updated_at": doc.get("updated_at"),
                            "stats": {"content_size": len(str(doc.get("content", {})))},
                        }
                    )

            return True, {
                "project_id": project_id,
                "documents": documents,
                "total_count": len(documents),
            }

        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return False, {"error": f"Error listing documents: {e!s}"}

    def get_document(self, project_id: str, doc_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Get a specific document from a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            response = (
                self.supabase_client.table("archon_projects")
                .select("docs")
                .eq("id", project_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Project with ID {project_id} not found"}

            docs = response.data[0].get("docs", [])

            # Find the specific document
            document = None
            for doc in docs:
                if doc.get("id") == doc_id:
                    document = doc
                    break

            if document:
                return True, {"document": document}
            else:
                return False, {
                    "error": f"Document with ID {doc_id} not found in project {project_id}"
                }

        except Exception as e:
            logger.error(f"Error getting document: {e}")
            return False, {"error": f"Error getting document: {e!s}"}

    def update_document(
        self,
        project_id: str,
        doc_id: str,
        update_fields: dict[str, Any],
        create_version: bool = True,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Update a document in a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Get current project docs
            project_response = (
                self.supabase_client.table("archon_projects")
                .select("docs")
                .eq("id", project_id)
                .execute()
            )
            if not project_response.data:
                return False, {"error": f"Project with ID {project_id} not found"}

            current_docs = project_response.data[0].get("docs", [])

            # Create version snapshot if requested
            if create_version and current_docs:
                try:
                    from .versioning_service import VersioningService

                    versioning = VersioningService(self.supabase_client)

                    change_summary = self._build_change_summary(doc_id, update_fields)
                    versioning.create_version(
                        project_id=project_id,
                        field_name="docs",
                        content=current_docs,
                        change_summary=change_summary,
                        change_type="update",
                        document_id=doc_id,
                        created_by=update_fields.get("author", "system"),
                    )
                except Exception as version_error:
                    logger.warning(
                        f"Version creation failed for document {doc_id}: {version_error}"
                    )

            # Make a copy to modify
            docs = current_docs.copy()

            # Find and update the document
            updated = False
            for i, doc in enumerate(docs):
                if doc.get("id") == doc_id:
                    # Update allowed fields
                    if "title" in update_fields:
                        docs[i]["title"] = update_fields["title"]
                    if "content" in update_fields:
                        docs[i]["content"] = update_fields["content"]
                    if "status" in update_fields:
                        docs[i]["status"] = update_fields["status"]
                    if "tags" in update_fields:
                        docs[i]["tags"] = update_fields["tags"]
                    if "author" in update_fields:
                        docs[i]["author"] = update_fields["author"]
                    if "version" in update_fields:
                        docs[i]["version"] = update_fields["version"]

                    docs[i]["updated_at"] = datetime.now().isoformat()
                    updated = True
                    break

            if not updated:
                return False, {
                    "error": f"Document with ID {doc_id} not found in project {project_id}"
                }

            # Update the project
            response = (
                self.supabase_client.table("archon_projects")
                .update({"docs": docs, "updated_at": datetime.now().isoformat()})
                .eq("id", project_id)
                .execute()
            )

            if response.data:
                # Find the updated document to return
                updated_doc = None
                for doc in docs:
                    if doc.get("id") == doc_id:
                        updated_doc = doc
                        break

                return True, {"document": updated_doc}
            else:
                return False, {"error": "Failed to update document"}

        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return False, {"error": f"Error updating document: {e!s}"}

    def delete_document(
        self, project_id: str, doc_id: str
    ) -> tuple[bool, dict[str, Any]]:
        """
        Delete a document from a project's docs JSONB field.

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Get current project docs
            project_response = (
                self.supabase_client.table("archon_projects")
                .select("docs")
                .eq("id", project_id)
                .execute()
            )
            if not project_response.data:
                return False, {"error": f"Project with ID {project_id} not found"}

            docs = project_response.data[0].get("docs", [])

            # Remove the document
            original_length = len(docs)
            docs = [doc for doc in docs if doc.get("id") != doc_id]

            if len(docs) == original_length:
                return False, {
                    "error": f"Document with ID {doc_id} not found in project {project_id}"
                }

            # Update the project
            response = (
                self.supabase_client.table("archon_projects")
                .update({"docs": docs, "updated_at": datetime.now().isoformat()})
                .eq("id", project_id)
                .execute()
            )

            if response.data:
                return True, {"project_id": project_id, "doc_id": doc_id}
            else:
                return False, {"error": "Failed to delete document"}

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False, {"error": f"Error deleting document: {e!s}"}

    async def _queue_document_for_resilient_indexing(
        self,
        document_id: str,
        project_id: str,
        title: str,
        content: dict,
        document_type: str,
        metadata: dict,
    ):
        """
        Queue document for resilient indexing with retry logic and error handling.

        This ensures new documents are indexed reliably with fallback mechanisms.
        """
        try:
            # Import the resilient indexing service
            from ..indexing.resilient_indexing_service import (
                queue_document_for_indexing,
            )

            # Queue the document for processing
            success = await queue_document_for_indexing(
                document_id=document_id,
                project_id=project_id,
                title=title,
                content=content,
                document_type=document_type,
                metadata=metadata,
            )

            if success:
                logger.info(
                    f"Document queued for resilient indexing | document_id={document_id} | "
                    f"project_id={project_id}"
                )
            else:
                logger.warning(
                    f"Failed to queue document for indexing | document_id={document_id}"
                )

        except ImportError:
            # Fallback to direct HTTP call if resilient service not available
            logger.warning(
                "Resilient indexing service not available, falling back to direct call"
            )
            await self._trigger_document_indexing(
                document_id, project_id, title, content, document_type, metadata
            )
        except Exception as e:
            logger.error(
                f"Failed to queue document for resilient indexing | document_id={document_id} | "
                f"error={e!s}"
            )

    async def _trigger_document_indexing(
        self,
        document_id: str,
        project_id: str,
        title: str,
        content: dict,
        document_type: str,
        metadata: dict,
    ):
        """
        Fallback method: Trigger real-time document indexing by calling the intelligence service directly.

        This ensures new documents are immediately available in RAG queries.
        """
        try:
            # Check if auto-indexing is enabled
            auto_indexing_enabled = (
                os.getenv("AUTO_INDEXING_ENABLED", "true").lower() == "true"
            )
            if not auto_indexing_enabled:
                logger.info(f"Auto-indexing disabled, skipping document {document_id}")
                return

            intelligence_service_url = os.getenv(
                "INTELLIGENCE_SERVICE_URL", "http://archon-intelligence:8053"
            )

            # Prepare request for intelligence service
            indexing_request = {
                "document_id": document_id,
                "project_id": project_id,
                "title": title,
                "content": content,
                "document_type": document_type,
                "metadata": metadata,
            }

            logger.info(
                f"Triggering document indexing | document_id={document_id} | "
                f"project_id={project_id}"
            )

            # Call intelligence service asynchronously with timeout
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{intelligence_service_url}/process/document",
                    json=indexing_request,
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(
                        f"Document indexing triggered successfully | document_id={document_id} | "
                        f"status={result.get('status')}"
                    )
                else:
                    logger.warning(
                        f"Document indexing request failed | document_id={document_id} | "
                        f"status_code={response.status_code} | error={response.text}"
                    )

        except TimeoutError:
            logger.warning(
                f"Document indexing request timed out | document_id={document_id}"
            )
        except Exception as e:
            logger.error(
                f"Failed to trigger document indexing | document_id={document_id} | "
                f"error={e!s}"
            )

    def _build_change_summary(self, doc_id: str, update_fields: dict[str, Any]) -> str:
        """Build a human-readable change summary"""
        changes = []
        if "title" in update_fields:
            changes.append(f"title to '{update_fields['title']}'")
        if "content" in update_fields:
            changes.append("content")
        if "status" in update_fields:
            changes.append(f"status to '{update_fields['status']}'")

        if changes:
            return f"Updated document '{doc_id}': {', '.join(changes)}"
        else:
            return f"Updated document '{doc_id}'"
