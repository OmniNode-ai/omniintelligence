"""
Projects Services Package

This package contains all services related to project management,
including project CRUD operations, task management, document management,
versioning, progress tracking, source linking, and AI-assisted project creation.
"""

from server.services.projects.document_service import DocumentService
from server.services.projects.progress_service import ProgressService, progress_service
from server.services.projects.project_creation_service import ProjectCreationService
from server.services.projects.project_service import ProjectService
from server.services.projects.source_linking_service import SourceLinkingService
from server.services.projects.task_service import TaskService
from server.services.projects.versioning_service import VersioningService

__all__ = [
    "ProjectService",
    "TaskService",
    "DocumentService",
    "VersioningService",
    "ProgressService",
    "progress_service",
    "ProjectCreationService",
    "SourceLinkingService",
]
