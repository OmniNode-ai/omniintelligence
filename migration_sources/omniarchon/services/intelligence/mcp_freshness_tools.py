"""
MCP Tools for Archon Document Freshness System

Tools for external access to document freshness monitoring and refresh capabilities
through the MCP (Model Context Protocol) interface.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from freshness import DataRefreshWorker, DocumentFreshnessMonitor, FreshnessDatabase
from freshness.models import RefreshRequest

logger = logging.getLogger(__name__)


class ArchonFreshnessTools:
    """
    MCP tools for document freshness operations.

    This class provides external access to the Archon document freshness system
    through standardized tool interfaces that can be called from MCP clients.
    """

    def __init__(self, bridge_service_url: str):
        """Initialize freshness tools with bridge service connection"""
        self.bridge_service_url = bridge_service_url
        self.monitor = DocumentFreshnessMonitor()
        self.database = FreshnessDatabase(bridge_service_url)
        self.worker = None
        self._initialized = False

    async def initialize(self):
        """Initialize the freshness system components"""
        if not self._initialized:
            await self.database.initialize()
            self.worker = DataRefreshWorker(self.database, self.monitor)
            self._initialized = True
            logger.info("Archon freshness tools initialized")

    async def analyze_document_freshness(
        self,
        path: str,
        recursive: bool = True,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_files: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Analyze document freshness for a path (file or directory).

        Args:
            path: Path to analyze (file or directory)
            recursive: Whether to analyze subdirectories
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude
            max_files: Maximum number of files to analyze

        Returns:
            Dictionary with freshness analysis results
        """
        if not self._initialized:
            await self.initialize()

        try:
            path_obj = Path(path)

            if not path_obj.exists():
                return {"success": False, "error": f"Path does not exist: {path}"}

            if path_obj.is_file():
                # Analyze single document
                document_analysis = await self.monitor.analyze_document(
                    file_path=path, include_dependencies=True
                )

                # Store in database
                await self.database.store_document_freshness(document_analysis)

                return {
                    "success": True,
                    "type": "single_document",
                    "document": {
                        "path": document_analysis.file_path,
                        "type": document_analysis.classification.document_type.value,
                        "freshness_level": document_analysis.freshness_level.value,
                        "freshness_score": document_analysis.freshness_score.overall_score,
                        "age_days": document_analysis.age_days,
                        "dependencies": len(document_analysis.dependencies),
                        "broken_dependencies": document_analysis.broken_dependencies_count,
                        "needs_refresh": document_analysis.needs_refresh,
                        "refresh_priority": document_analysis.refresh_priority.value,
                        "estimated_refresh_effort_minutes": document_analysis.estimated_refresh_effort_minutes,
                    },
                }
            else:
                # Analyze directory
                analysis = await self.monitor.analyze_directory(
                    directory_path=path,
                    recursive=recursive,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                    max_files=max_files,
                )

                # Store analysis in database
                await self.database.store_analysis(analysis)

                return {
                    "success": True,
                    "type": "directory_analysis",
                    "analysis_id": analysis.analysis_id,
                    "summary": {
                        "total_documents": analysis.total_documents,
                        "analyzed_documents": analysis.analyzed_documents,
                        "average_freshness_score": analysis.average_freshness_score,
                        "stale_documents": analysis.stale_documents_count,
                        "critical_documents": analysis.critical_documents_count,
                        "total_dependencies": analysis.total_dependencies,
                        "broken_dependencies": analysis.broken_dependencies,
                        "health_score": analysis.health_score,
                        "staleness_percentage": analysis.staleness_percentage,
                    },
                    "freshness_distribution": analysis.freshness_distribution,
                    "recommendations": analysis.recommendations,
                    "priority_actions": analysis.priority_actions,
                    "refresh_strategies_count": len(analysis.refresh_strategies),
                    "analysis_time_seconds": analysis.analysis_time_seconds,
                }

        except Exception as e:
            logger.error(f"Document freshness analysis failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_stale_documents(
        self,
        limit: Optional[int] = 50,
        freshness_levels: Optional[List[str]] = None,
        priority_filter: Optional[str] = None,
        document_types: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get stale documents with filtering options.

        Args:
            limit: Maximum number of documents to return
            freshness_levels: List of freshness levels to include (STALE, OUTDATED, CRITICAL)
            priority_filter: Priority filter (LOW, MEDIUM, HIGH, CRITICAL)
            document_types: List of document types to include
            max_age_days: Maximum age in days

        Returns:
            Dictionary with stale documents information
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Convert string parameters to enums
            from freshness.models import FreshnessLevel, RefreshPriority

            levels = None
            if freshness_levels:
                levels = [FreshnessLevel(level) for level in freshness_levels]

            priority = None
            if priority_filter:
                priority = RefreshPriority(priority_filter)

            stale_docs = await self.database.get_stale_documents(
                limit=limit,
                freshness_levels=levels,
                priority_filter=priority,
                document_types=document_types,
                max_age_days=max_age_days,
            )

            return {
                "success": True,
                "stale_documents": stale_docs,
                "count": len(stale_docs),
                "filters_applied": {
                    "freshness_levels": freshness_levels,
                    "priority_filter": priority_filter,
                    "document_types": document_types,
                    "max_age_days": max_age_days,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get stale documents: {e}")
            return {"success": False, "error": str(e)}

    async def refresh_documents(
        self,
        document_paths: List[str],
        refresh_mode: str = "safe",
        backup_enabled: bool = True,
        dry_run: bool = False,
        max_age_days: Optional[int] = None,
        min_freshness_score: Optional[float] = None,
        priority_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Refresh stale documents with comprehensive processing.

        Args:
            document_paths: List of document paths to refresh
            refresh_mode: Refresh mode (safe, aggressive, force)
            backup_enabled: Whether to create backups
            dry_run: Whether to perform a dry run
            max_age_days: Only refresh documents older than this
            min_freshness_score: Only refresh documents below this score
            priority_filter: Only refresh documents with this priority

        Returns:
            Dictionary with refresh operation results
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Create refresh request
            from freshness.models import RefreshPriority

            priority = None
            if priority_filter:
                priority = RefreshPriority(priority_filter)

            request = RefreshRequest(
                document_paths=document_paths,
                refresh_mode=refresh_mode,
                backup_enabled=backup_enabled,
                dry_run=dry_run,
                max_age_days=max_age_days,
                min_freshness_score=min_freshness_score,
                priority_filter=priority,
            )

            # Execute refresh
            result = await self.worker.refresh_documents(request)

            return {
                "success": True,
                "refresh_id": result.refresh_id,
                "summary": {
                    "requested_documents": len(result.requested_documents),
                    "processed_documents": len(result.processed_documents),
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                    "skipped_count": len(result.skipped_documents),
                    "success_rate": result.success_rate,
                    "total_time_seconds": result.total_time_seconds,
                    "average_time_per_document": result.average_time_per_document,
                },
                "processed_documents": result.processed_documents,
                "failed_documents": result.failed_documents,
                "skipped_documents": result.skipped_documents,
                "warnings": result.warnings,
                "errors": result.errors[:10],  # Limit errors for response size
                "freshness_improvement": result.freshness_improvement,
                "dependencies_fixed": result.dependencies_fixed,
                "backup_locations": result.backup_locations,
            }

        except Exception as e:
            logger.error(f"Document refresh failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_freshness_stats(
        self, base_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive freshness statistics.

        Args:
            base_path: Optional base path to filter statistics

        Returns:
            Dictionary with freshness statistics
        """
        if not self._initialized:
            await self.initialize()

        try:
            stats = await self.database.get_freshness_stats(base_path=base_path)

            return {
                "success": True,
                "statistics": {
                    "total_documents": stats.total_documents,
                    "fresh_count": stats.fresh_count,
                    "stale_count": stats.stale_count,
                    "outdated_count": stats.outdated_count,
                    "critical_count": stats.critical_count,
                    "average_age_days": stats.average_age_days,
                    "average_freshness_score": stats.average_freshness_score,
                    "recently_updated_count": stats.recently_updated_count,
                    "never_updated_count": stats.never_updated_count,
                },
                "type_distribution": stats.type_distribution,
                "health_indicators": {
                    "freshness_percentage": (
                        stats.fresh_count / max(stats.total_documents, 1)
                    )
                    * 100,
                    "staleness_percentage": (
                        (
                            stats.stale_count
                            + stats.outdated_count
                            + stats.critical_count
                        )
                        / max(stats.total_documents, 1)
                    )
                    * 100,
                    "critical_percentage": (
                        stats.critical_count / max(stats.total_documents, 1)
                    )
                    * 100,
                    "recent_activity_percentage": (
                        stats.recently_updated_count / max(stats.total_documents, 1)
                    )
                    * 100,
                },
                "base_path": base_path,
                "last_updated": stats.last_updated.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get freshness statistics: {e}")
            return {"success": False, "error": str(e)}

    async def get_document_freshness(self, document_path: str) -> Dict[str, Any]:
        """
        Get freshness information for a specific document.

        Args:
            document_path: Path to the document

        Returns:
            Dictionary with document freshness information
        """
        if not self._initialized:
            await self.initialize()

        try:
            document_info = await self.database.get_document_by_path(document_path)

            if not document_info:
                return {
                    "success": False,
                    "error": f"Document not found: {document_path}",
                }

            return {"success": True, "document": document_info}

        except Exception as e:
            logger.error(f"Failed to get document freshness: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, Any]:
        """
        Clean up old freshness data.

        Args:
            days_to_keep: Number of days to keep data for

        Returns:
            Dictionary with cleanup results
        """
        if not self._initialized:
            await self.initialize()

        try:
            if days_to_keep < 7:
                return {"success": False, "error": "days_to_keep must be at least 7"}

            # Clean up database records
            deleted_db_count = await self.database.cleanup_old_data(
                days_to_keep=days_to_keep
            )

            # Clean up backup files
            deleted_backup_count = await self.worker.cleanup_old_backups(
                days_to_keep=days_to_keep
            )

            return {
                "success": True,
                "cleanup_results": {
                    "deleted_database_records": deleted_db_count,
                    "deleted_backup_directories": deleted_backup_count,
                    "days_kept": days_to_keep,
                },
            }

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {"success": False, "error": str(e)}


# Example usage functions for MCP integration
async def create_freshness_tools(bridge_service_url: str) -> ArchonFreshnessTools:
    """Create and initialize freshness tools"""
    tools = ArchonFreshnessTools(bridge_service_url)
    await tools.initialize()
    return tools


def get_available_tools() -> List[Dict[str, Any]]:
    """Get list of available freshness tools with descriptions"""
    return [
        {
            "name": "analyze_document_freshness",
            "description": "Analyze document freshness for files or directories",
            "parameters": {
                "path": "Path to analyze (required)",
                "recursive": "Analyze subdirectories (default: true)",
                "include_patterns": "File patterns to include (optional)",
                "exclude_patterns": "File patterns to exclude (optional)",
                "max_files": "Maximum files to analyze (optional)",
            },
        },
        {
            "name": "get_stale_documents",
            "description": "Get list of stale documents with filtering",
            "parameters": {
                "limit": "Maximum documents to return (default: 50)",
                "freshness_levels": "Freshness levels to include (optional)",
                "priority_filter": "Priority filter (optional)",
                "document_types": "Document types to include (optional)",
                "max_age_days": "Maximum age in days (optional)",
            },
        },
        {
            "name": "refresh_documents",
            "description": "Refresh stale documents with batch processing",
            "parameters": {
                "document_paths": "List of document paths to refresh (required)",
                "refresh_mode": "Refresh mode: safe, aggressive, force (default: safe)",
                "backup_enabled": "Create backups (default: true)",
                "dry_run": "Perform dry run (default: false)",
            },
        },
        {
            "name": "get_freshness_stats",
            "description": "Get comprehensive freshness statistics",
            "parameters": {"base_path": "Base path to filter statistics (optional)"},
        },
        {
            "name": "get_document_freshness",
            "description": "Get freshness info for specific document",
            "parameters": {"document_path": "Path to document (required)"},
        },
        {
            "name": "cleanup_old_data",
            "description": "Clean up old freshness data and backups",
            "parameters": {
                "days_to_keep": "Days of data to keep (default: 90, minimum: 7)"
            },
        },
    ]
