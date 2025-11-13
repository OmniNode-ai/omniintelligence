"""
Intelligence Data Access Module

Pure data access layer for intelligence operations. This module provides:
- Raw data fetching operations
- Framework-agnostic data structures
- Testable data access patterns
- Clean separation from API/UI concerns

This module can be used by:
- API routes
- WebSocket handlers
- Test suites
- Background services
- CLI tools

All functions return raw data structures without HTTP-specific formatting.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Data structures for intelligence data
@dataclass
class DiffAnalysisData:
    """Raw diff analysis data structure."""

    total_changes: int
    added_lines: int
    removed_lines: int
    modified_files: list[str]


@dataclass
class TemporalCorrelationData:
    """Raw temporal correlation data structure."""

    repository: str
    commit_sha: str
    time_diff_hours: float
    correlation_strength: float


@dataclass
class SemanticCorrelationData:
    """Raw semantic correlation data structure."""

    repository: str
    commit_sha: str
    semantic_similarity: float
    common_keywords: list[str]
    file_information: Optional[dict[str, Any]] = None


@dataclass
class BreakingChangeData:
    """Raw breaking change data structure."""

    type: str
    severity: str
    description: str
    files_affected: list[str]


@dataclass
class SecurityAnalysisData:
    """Raw security analysis data structure."""

    patterns_detected: list[str]
    risk_level: str
    secure_patterns: int


@dataclass
class IntelligenceDocumentData:
    """Raw intelligence document data structure."""

    id: str
    created_at: str
    repository: str
    commit_sha: str
    author: str
    change_type: str
    diff_analysis: Optional[DiffAnalysisData]
    temporal_correlations: list[TemporalCorrelationData]
    semantic_correlations: list[SemanticCorrelationData]
    breaking_changes: list[BreakingChangeData]
    security_analysis: Optional[SecurityAnalysisData]
    raw_content: dict[str, Any]  # Original content for debugging/validation


@dataclass
class IntelligenceStatsData:
    """Raw intelligence statistics data structure."""

    total_changes: int
    total_correlations: int
    average_correlation_strength: float
    breaking_changes: int
    repositories_active: int
    correlation_strengths: list[float]  # Raw data for further analysis
    repositories_list: list[str]


@dataclass
class QueryParameters:
    """Query parameters for data access operations."""

    repository: Optional[str] = None
    time_range: str = "24h"
    limit: int = 50
    offset: int = 0


class TimeRange(Enum):
    """Supported time ranges."""

    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWENTY_FOUR_HOURS = "24h"
    SEVENTY_TWO_HOURS = "72h"
    SEVEN_DAYS = "7d"


class IntelligenceDataAccess:
    """
    Pure data access class for intelligence operations.

    This class provides raw data access without any framework dependencies
    or HTTP-specific formatting. All methods return plain data structures
    that can be consumed by any layer.
    """

    def __init__(self, database_client):
        """
        Initialize with a database client.

        Args:
            database_client: Database client instance (Supabase, etc.)
        """
        self.client = database_client

    def parse_time_range(self, time_range: str) -> int:
        """
        Parse time range string to hours.

        Args:
            time_range: Time range string (1h, 6h, 24h, 72h, 7d)

        Returns:
            Hours as integer
        """
        time_map = {
            "1h": 1,
            "6h": 6,
            "24h": 24,
            "72h": 72,
            "7d": 168,  # 7 days * 24 hours
        }

        return time_map.get(time_range, 24)  # Default to 24h

    def extract_intelligence_documents_from_projects(
        self,
        projects: list[dict[str, Any]],
        cutoff_time: datetime,
        repository_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Extract intelligence documents from project data.

        Args:
            projects: List of project dictionaries
            cutoff_time: Cutoff datetime for filtering
            repository_filter: Optional repository filter

        Returns:
            List of intelligence documents with metadata
        """
        intelligence_documents = []

        for project in projects:
            docs = project.get("docs", [])
            if not docs:
                continue

            for doc in docs:
                # Check if document has intelligence-related tags
                tags = doc.get("tags", [])
                has_intelligence_tags = any(
                    tag in tags
                    for tag in [
                        "intelligence",
                        "intelligence-initialization",
                        "pre-push",
                        "rag-indexing",
                        "intelligence-update",
                        "quality-assessment",
                    ]
                )

                if not has_intelligence_tags:
                    continue

                # Extract repository info from document content - handle MCP format
                content = doc.get("content", {})
                content_metadata = content.get("metadata", {})
                doc_repository = content_metadata.get("repository")

                # Fallback to old format
                if not doc_repository:
                    repo_info = content.get("repository_info", {})
                    doc_repository = repo_info.get(
                        "repository", project.get("title", "unknown")
                    )

                # Apply repository filter if specified
                if repository_filter and repository_filter != "all":
                    if doc_repository != repository_filter:
                        continue

                # Apply document-level time filtering
                doc_timestamp = (
                    doc.get("created_at")
                    or content_metadata.get("timestamp")
                    or content.get("update_timestamp")  # MCP format
                    or content.get("initialization_date")
                    or project["updated_at"]  # fallback to project update time
                )

                if doc_timestamp and isinstance(doc_timestamp, str):
                    try:
                        # Parse timestamp and check if it's within time range
                        doc_time = datetime.fromisoformat(
                            doc_timestamp.replace("Z", "+00:00")
                        )
                        if doc_time < cutoff_time:
                            continue  # Skip documents older than cutoff
                    except (ValueError, TypeError):
                        # If timestamp parsing fails, use project timestamp as fallback
                        try:
                            project_time = datetime.fromisoformat(project["updated_at"])
                            if project_time < cutoff_time:
                                continue
                        except (ValueError, TypeError):
                            # Skip if we can't parse any timestamp
                            continue

                # Add project metadata to document
                doc_created_at = doc.get("created_at") or project["created_at"]
                # For intelligence documents, prefer the intelligence timestamp
                if content_metadata.get("timestamp"):
                    doc_created_at = content_metadata["timestamp"]

                doc_with_metadata = {
                    **doc,
                    "project_id": project["id"],
                    "project_title": project["title"],
                    "created_at": doc_created_at,
                    "updated_at": doc.get("updated_at") or project["updated_at"],
                }
                intelligence_documents.append(doc_with_metadata)

        return intelligence_documents

    def parse_diff_analysis(
        self, content: dict[str, Any]
    ) -> Optional[DiffAnalysisData]:
        """
        Parse diff analysis data from document content.

        Args:
            content: Document content dictionary

        Returns:
            DiffAnalysisData or None if not found
        """
        try:
            # Parse diff analysis from git hook intelligence documents
            if "diff_analysis" in content:
                diff_data = content["diff_analysis"]
                return DiffAnalysisData(
                    total_changes=diff_data.get("total_changes", 0),
                    added_lines=diff_data.get("added_lines", 0),
                    removed_lines=diff_data.get("removed_lines", 0),
                    modified_files=diff_data.get("modified_files", []),
                )

            # Parse diff analysis from project documents with file change info or MCP format
            elif (
                "changed_files" in content
                or "repository_info" in content
                or "code_changes_analysis" in content
            ):
                # Handle MCP format first
                if "code_changes_analysis" in content:
                    code_analysis = content["code_changes_analysis"]
                    changed_files = code_analysis.get("changed_files", [])
                    total_changes = len(changed_files)
                # Handle project documents with repository_info
                elif (
                    "repository_info" in content
                    and "files_changed" in content["repository_info"]
                ):
                    changed_files = content.get("changed_files", [])
                    total_changes = content["repository_info"]["files_changed"]
                # Handle direct changed_files
                else:
                    changed_files = content.get("changed_files", [])
                    total_changes = len(changed_files)

                return DiffAnalysisData(
                    total_changes=total_changes,
                    added_lines=0,  # Not available in project docs
                    removed_lines=0,  # Not available in project docs
                    modified_files=changed_files,
                )

            return None

        except Exception as e:
            logger.error(f"Error parsing diff analysis: {e}")
            return None

    def parse_correlations(self, content: dict[str, Any]) -> tuple[
        list[TemporalCorrelationData],
        list[SemanticCorrelationData],
        list[BreakingChangeData],
    ]:
        """
        Parse correlation data from document content.

        Args:
            content: Document content dictionary

        Returns:
            Tuple of (temporal_correlations, semantic_correlations, breaking_changes)
        """
        temporal_correlations = []
        semantic_correlations = []
        breaking_changes = []

        try:
            # Parse correlation analysis - support both old and new v3.0 formats and MCP format
            corr_data = None
            if "correlation_analysis" in content:
                corr_data = content["correlation_analysis"]
            elif "cross_repository_correlation" in content:
                # v3.0 hook format and MCP format
                corr_data = content["cross_repository_correlation"]

            if not corr_data:
                return temporal_correlations, semantic_correlations, breaking_changes

            # Parse temporal correlations
            for tc in corr_data.get("temporal_correlations", []):
                # Handle both old format (time_diff_hours) and new format (time_window)
                time_diff = tc.get("time_diff_hours", 0.0)
                if time_diff == 0.0 and "time_window" in tc:
                    # Convert time window string to hours
                    time_window = tc.get("time_window", "24h")
                    if time_window.endswith("h"):
                        time_diff = float(time_window[:-1])
                    elif time_window.endswith("d"):
                        time_diff = float(time_window[:-1]) * 24

                # Handle correlation strength (string or float)
                strength = tc.get("correlation_strength", 0.0)
                if isinstance(strength, str):
                    strength_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
                    strength = strength_map.get(strength, 0.0)

                temporal_correlations.append(
                    TemporalCorrelationData(
                        repository=tc.get("repository", ""),
                        commit_sha=tc.get("commit_sha", tc.get("commit", "")),
                        time_diff_hours=time_diff,
                        correlation_strength=strength,
                    )
                )

            # Parse semantic correlations
            for sc in corr_data.get("semantic_correlations", []):
                # Handle semantic similarity (may not exist in v3.0 format)
                semantic_sim = sc.get("semantic_similarity", 0.0)
                if semantic_sim == 0.0 and "correlation_strength" in sc:
                    strength = sc.get("correlation_strength", 0.0)
                    if isinstance(strength, str):
                        strength_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
                        semantic_sim = strength_map.get(strength, 0.0)

                # Extract keywords from v3.0 format
                keywords = sc.get("common_keywords", [])
                if not keywords and "shared_keywords" in sc:
                    keywords = sc.get("shared_keywords", "").split()

                semantic_correlations.append(
                    SemanticCorrelationData(
                        repository=sc.get("repository", ""),
                        commit_sha=sc.get("commit_sha", sc.get("commit", "")),
                        semantic_similarity=semantic_sim,
                        common_keywords=keywords,
                        file_information=sc.get("file_information"),
                    )
                )

            # Parse breaking changes
            for bc in corr_data.get("breaking_changes", []):
                breaking_changes.append(
                    BreakingChangeData(
                        type=bc.get("type", ""),
                        severity=bc.get("severity", ""),
                        description=bc.get("description", ""),
                        files_affected=bc.get("files_affected", []),
                    )
                )

        except Exception as e:
            logger.error(f"Error parsing correlations: {e}")

        return temporal_correlations, semantic_correlations, breaking_changes

    def parse_security_analysis(
        self, content: dict[str, Any]
    ) -> Optional[SecurityAnalysisData]:
        """
        Parse security analysis data from document content.

        Args:
            content: Document content dictionary

        Returns:
            SecurityAnalysisData or None if not found
        """
        try:
            # Parse security analysis from git hook intelligence documents
            if "security_analysis" in content:
                sec_data = content["security_analysis"]
                return SecurityAnalysisData(
                    patterns_detected=sec_data.get("patterns_detected", []),
                    risk_level=sec_data.get("risk_level", "UNKNOWN"),
                    secure_patterns=sec_data.get("secure_patterns", 0),
                )

            # Parse security patterns from project documents with quality metrics
            elif "quality_baseline" in content or "code_quality_metrics" in content:
                quality_data = content.get("quality_baseline", {})
                code_metrics = quality_data.get("code_quality_metrics", {})

                patterns_detected = []
                risk_level = "LOW"
                secure_patterns = 0

                if code_metrics:
                    if code_metrics.get("anti_patterns_found", 0) == 0:
                        patterns_detected.append("No anti-patterns detected")
                        secure_patterns += 1
                    if code_metrics.get("architectural_compliance") == "High":
                        patterns_detected.append("High architectural compliance")
                        secure_patterns += 1
                    if code_metrics.get("type_safety") == "Strong":
                        patterns_detected.append("Strong type safety")
                        secure_patterns += 1

                return SecurityAnalysisData(
                    patterns_detected=patterns_detected,
                    risk_level=risk_level,
                    secure_patterns=secure_patterns,
                )

            return None

        except Exception as e:
            logger.error(f"Error parsing security analysis: {e}")
            return None

    def parse_document_metadata(self, doc: dict[str, Any]) -> tuple[str, str, str, str]:
        """
        Parse document metadata to extract repository, commit, author, and change type.

        Args:
            doc: Document dictionary

        Returns:
            Tuple of (repository, commit_sha, author, change_type)
        """
        metadata = doc.get("metadata", {})
        content = doc.get("content", {})
        doc_type = doc.get("document_type", "unknown")

        # Handle different document types
        if doc_type == "intelligence":
            # Git hook intelligence documents - check content.metadata first, then fallback
            content_metadata = content.get("metadata", {})
            repository_info = content.get("repository_info", {})
            repository = (
                content_metadata.get("repository")
                or repository_info.get("repository")  # Legacy format
                or metadata.get("repository")
                or "unknown"
            )
            commit_sha = (
                content_metadata.get("commit")
                or repository_info.get("commit")  # Legacy format
                or metadata.get("commit_sha")
                or metadata.get("commit")
                or "unknown"
            )
            author = (
                content_metadata.get("author")
                or metadata.get("author")
                or doc.get("author")
                or "unknown"
            )
            change_type = (
                content_metadata.get("change_type")
                or metadata.get("change_type")
                or content.get("analysis_type")
                or "unknown"
            )
        else:
            # Project documents with intelligence tags
            repository = content.get("repository_info", {}).get(
                "repository"
            ) or metadata.get("repository", "unknown")
            commit_sha = content.get("repository_info", {}).get("commit", "unknown")
            author = doc.get("author", "unknown")
            change_type = content.get(
                "update_type", doc.get("document_type", "unknown")
            )

        return repository, commit_sha, author, change_type

    def get_raw_documents(self, params: QueryParameters) -> dict[str, Any]:
        """
        Get raw intelligence documents from database.

        Args:
            params: Query parameters

        Returns:
            Dictionary with documents and metadata
        """
        try:
            # Parse time range
            time_hours = self.parse_time_range(params.time_range)
            cutoff_time = datetime.now(UTC) - timedelta(hours=time_hours)

            # Build query to get all projects (we'll filter documents by time later)
            query = self.client.table("archon_projects").select(
                "id,title,created_at,updated_at,docs"
            )
            query = query.order("updated_at", desc=True)
            result = query.execute()

            if not result.data:
                return {
                    "documents": [],
                    "total_count": 0,
                    "success": True,
                    "error": None,
                }

            # Extract intelligence documents from project docs
            intelligence_documents = self.extract_intelligence_documents_from_projects(
                result.data, cutoff_time, params.repository
            )

            # Sort by created_at descending
            intelligence_documents.sort(
                key=lambda x: x.get("created_at", ""), reverse=True
            )

            # Apply pagination
            start_idx = params.offset
            end_idx = params.offset + params.limit
            paginated_docs = intelligence_documents[start_idx:end_idx]

            return {
                "documents": paginated_docs,
                "total_count": len(intelligence_documents),
                "success": True,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error fetching raw intelligence documents: {e}")
            return {
                "documents": [],
                "total_count": 0,
                "success": False,
                "error": str(e),
            }

    def get_parsed_documents(
        self, params: QueryParameters
    ) -> list[IntelligenceDocumentData]:
        """
        Get parsed intelligence documents with structured data.

        Args:
            params: Query parameters

        Returns:
            List of IntelligenceDocumentData objects
        """
        try:
            # Get raw documents
            raw_result = self.get_raw_documents(params)

            if not raw_result["success"]:
                return []

            documents = []

            for doc in raw_result["documents"]:
                try:
                    # Parse document metadata
                    (
                        repository,
                        commit_sha,
                        author,
                        change_type,
                    ) = self.parse_document_metadata(doc)

                    # Parse intelligence data from content
                    content = doc.get("content", {})

                    diff_analysis = self.parse_diff_analysis(content)
                    (
                        temporal_correlations,
                        semantic_correlations,
                        breaking_changes,
                    ) = self.parse_correlations(content)
                    security_analysis = self.parse_security_analysis(content)

                    # Create structured document data
                    document_data = IntelligenceDocumentData(
                        id=doc["id"],
                        created_at=doc["created_at"],
                        repository=repository,
                        commit_sha=commit_sha,
                        author=author,
                        change_type=change_type,
                        diff_analysis=diff_analysis,
                        temporal_correlations=temporal_correlations,
                        semantic_correlations=semantic_correlations,
                        breaking_changes=breaking_changes,
                        security_analysis=security_analysis,
                        raw_content=content,  # Include raw content for debugging
                    )

                    documents.append(document_data)

                except Exception as e:
                    logger.error(
                        f"Error parsing intelligence document {doc.get('id', 'unknown')}: {e}"
                    )
                    continue

            return documents

        except Exception as e:
            logger.error(f"Error getting parsed intelligence documents: {e}")
            return []

    def calculate_statistics(self, params: QueryParameters) -> IntelligenceStatsData:
        """
        Calculate intelligence statistics from parsed documents.

        Args:
            params: Query parameters (repository and time_range are used)

        Returns:
            IntelligenceStatsData with all metrics
        """
        try:
            # Get parsed documents for statistics (use large limit)
            stats_params = QueryParameters(
                repository=params.repository,
                time_range=params.time_range,
                limit=10000,  # Large limit for accurate stats
                offset=0,
            )

            documents = self.get_parsed_documents(stats_params)

            if not documents:
                return IntelligenceStatsData(
                    total_changes=0,
                    total_correlations=0,
                    average_correlation_strength=0.0,
                    breaking_changes=0,
                    repositories_active=0,
                    correlation_strengths=[],
                    repositories_list=[],
                )

            # Calculate statistics
            total_changes = len(documents)
            total_correlations = 0
            correlation_strengths = []
            breaking_changes = 0
            repositories = set()

            for doc in documents:
                repositories.add(doc.repository)

                # Access correlations directly from IntelligenceDocumentData attributes
                # The data structure has temporal_correlations, semantic_correlations, breaking_changes as direct attributes

                # Count temporal correlations
                total_correlations += len(doc.temporal_correlations)
                correlation_strengths.extend(
                    [c.correlation_strength for c in doc.temporal_correlations]
                )

                # Count semantic correlations (enhanced correlation data)
                total_correlations += len(doc.semantic_correlations)
                correlation_strengths.extend(
                    [c.semantic_similarity for c in doc.semantic_correlations]
                )

                # Count breaking changes
                breaking_changes += len(doc.breaking_changes)

            # Calculate average correlation strength
            avg_correlation = (
                sum(correlation_strengths) / len(correlation_strengths)
                if correlation_strengths
                else 0.0
            )

            return IntelligenceStatsData(
                total_changes=total_changes,
                total_correlations=total_correlations,
                average_correlation_strength=avg_correlation,
                breaking_changes=breaking_changes,
                repositories_active=len(repositories),
                correlation_strengths=correlation_strengths,
                repositories_list=sorted(repositories),
            )

        except Exception as e:
            logger.error(f"Error calculating intelligence statistics: {e}")
            return IntelligenceStatsData(
                total_changes=0,
                total_correlations=0,
                average_correlation_strength=0.0,
                breaking_changes=0,
                repositories_active=0,
                correlation_strengths=[],
                repositories_list=[],
            )

    def get_active_repositories(self) -> list[str]:
        """
        Get list of repositories that have generated intelligence data.

        Returns:
            List of repository names
        """
        try:
            # Get projects and extract repositories from intelligence documents
            result = (
                self.client.table("archon_projects").select("id,title,docs").execute()
            )

            repositories = set()
            for project in result.data:
                docs = project.get("docs", [])
                for doc in docs:
                    # Check if document has intelligence-related tags
                    tags = doc.get("tags", [])
                    has_intelligence_tags = any(
                        tag in tags
                        for tag in [
                            "intelligence",
                            "intelligence-initialization",
                            "pre-push",
                            "rag-indexing",
                            "intelligence-update",
                            "quality-assessment",
                        ]
                    )

                    if has_intelligence_tags:
                        # Extract repository from document content - handle MCP format
                        content = doc.get("content", {})
                        content_metadata = content.get("metadata", {})
                        repository = content_metadata.get("repository")

                        # Fallback to old format
                        if not repository:
                            repo_info = content.get("repository_info", {})
                            repository = repo_info.get(
                                "repository", project.get("title", "unknown")
                            )
                        repositories.add(repository)

            return sorted(repositories)

        except Exception as e:
            logger.error(f"Error fetching repositories: {e}")
            return []

    # WRITE OPERATIONS FOR INTELLIGENCE DOCUMENTS

    def update_intelligence_document_correlations(
        self, document_id: str, correlation_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update correlation data for a specific intelligence document stored in archon_projects.docs JSONB field.

        Args:
            document_id: UUID of the intelligence document to update
            correlation_data: Dictionary containing correlation analysis data with structure:
                {
                    "temporal_correlations": [...],
                    "semantic_correlations": [...],
                    "breaking_changes": [...]
                }

        Returns:
            Dict with success status and details
        """
        try:
            logger.info(f"🔄 Updating correlations for document {document_id}")

            # Find which project contains this document
            project_info = self.find_document_in_project_docs(document_id)
            if not project_info:
                return {
                    "success": False,
                    "error": f"Document {document_id} not found in any project",
                    "document_id": document_id,
                }

            project_id = project_info["project_id"]
            doc_index = project_info["document_index"]

            # Get the current project docs
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

            # Update the specific document's correlation data
            if doc_index < len(current_docs):
                document = current_docs[doc_index]

                # Merge correlation data into the document content
                if "content" not in document:
                    document["content"] = {}

                # Update correlation_analysis in the content
                document["content"]["correlation_analysis"] = correlation_data

                # Update the entire docs array in the database
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
                else:
                    return {
                        "success": False,
                        "error": "Database update failed",
                        "document_id": document_id,
                    }
            else:
                return {
                    "success": False,
                    "error": f"Document index {doc_index} out of range",
                    "document_id": document_id,
                }

        except Exception as e:
            logger.error(f"❌ Error updating document correlations: {e}")
            return {"success": False, "error": str(e), "document_id": document_id}

    def find_document_in_project_docs(
        self, document_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Find which project contains a specific intelligence document and its index.

        Args:
            document_id: UUID of the document to find

        Returns:
            Dict with project_id and document_index, or None if not found
        """
        try:
            # Query all projects with their docs
            result = self.client.table("archon_projects").select("id,docs").execute()

            for project in result.data:
                docs = project.get("docs", [])
                for index, doc in enumerate(docs):
                    if doc.get("id") == document_id:
                        return {
                            "project_id": project["id"],
                            "document_index": index,
                            "document": doc,
                        }

            return None

        except Exception as e:
            logger.error(f"Error finding document {document_id}: {e}")
            return None

    def merge_correlation_data(
        self, existing_data: dict[str, Any], new_correlations: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Merge new correlation data with existing correlation data.

        Args:
            existing_data: Existing correlation analysis data
            new_correlations: New correlation data to merge

        Returns:
            Merged correlation data
        """
        # Start with existing data or empty structure
        merged = {
            "temporal_correlations": existing_data.get("temporal_correlations", []),
            "semantic_correlations": existing_data.get("semantic_correlations", []),
            "breaking_changes": existing_data.get("breaking_changes", []),
        }

        # Add new correlations (avoiding duplicates based on repository + commit)
        for new_temporal in new_correlations.get("temporal_correlations", []):
            existing_temporal = [
                tc
                for tc in merged["temporal_correlations"]
                if tc.get("repository") == new_temporal.get("repository")
                and tc.get("commit_sha") == new_temporal.get("commit_sha")
            ]
            if not existing_temporal:
                merged["temporal_correlations"].append(new_temporal)

        for new_semantic in new_correlations.get("semantic_correlations", []):
            existing_semantic = [
                sc
                for sc in merged["semantic_correlations"]
                if sc.get("repository") == new_semantic.get("repository")
                and sc.get("commit_sha") == new_semantic.get("commit_sha")
            ]
            if not existing_semantic:
                merged["semantic_correlations"].append(new_semantic)

        for new_breaking in new_correlations.get("breaking_changes", []):
            # For breaking changes, check by type and description to avoid duplicates
            existing_breaking = [
                bc
                for bc in merged["breaking_changes"]
                if bc.get("type") == new_breaking.get("type")
                and bc.get("description") == new_breaking.get("description")
            ]
            if not existing_breaking:
                merged["breaking_changes"].append(new_breaking)

        return merged


# Factory function to create data access instance
def create_intelligence_data_access(database_client) -> IntelligenceDataAccess:
    """
    Create an intelligence data access instance.

    Args:
        database_client: Database client instance

    Returns:
        IntelligenceDataAccess instance
    """
    return IntelligenceDataAccess(database_client)
