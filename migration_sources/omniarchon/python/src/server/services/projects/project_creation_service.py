"""
Project Creation Service Module for Archon

This module handles the complex project creation workflow including
AI-assisted documentation generation and progress tracking.
"""

import os

# Removed direct logging import - using unified config
from datetime import datetime
from typing import Any

from server.config.logfire_config import get_logger
from server.services.projects.progress_service import progress_service
from src.server.utils import get_database_client

logger = get_logger(__name__)


class ProjectCreationService:
    """Service class for advanced project creation with AI assistance"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_database_client()
        self.progress_service = progress_service

    async def create_project_with_ai(
        self,
        progress_id: str,
        title: str,
        description: str | None = None,
        github_repo: str | None = None,
        **kwargs,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Create a project with AI-assisted documentation generation.

        Args:
            progress_id: Progress tracking identifier
            title: Project title
            description: Project description
            github_repo: GitHub repository URL
            **kwargs: Additional project data

        Returns:
            Tuple of (success, result_dict)
        """
        logger.info(
            f"🏗️ [PROJECT-CREATION] Starting create_project_with_ai for progress_id: {progress_id}, title: {title}"
        )
        try:
            # Update progress - database setup
            logger.info(
                "🏗️ [PROJECT-CREATION] About to call progress update: database_setup (30%)"
            )
            await self.progress_service.update_progress(
                progress_id,
                {
                    "percentage": 30,
                    "step": "database_setup",
                    "log": "🗄️ Setting up project database...",
                },
            )
            logger.info(
                "🏗️ [PROJECT-CREATION] Completed progress update: database_setup"
            )

            # Create basic project structure
            project_data = {
                "title": title,
                "description": description or "",
                "github_repo": github_repo,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "docs": [],  # Empty docs array to start - PRD will be added here by DocumentAgent
                "features": kwargs.get("features", {}),
                "data": kwargs.get("data", {}),
            }

            # Add any additional fields from kwargs
            for key in ["pinned"]:
                if key in kwargs:
                    project_data[key] = kwargs[key]

            # Create the project in database
            response = (
                self.supabase_client.table("archon_projects")
                .insert(project_data)
                .execute()
            )
            if not response.data:
                raise Exception("Failed to create project in database")

            project_id = response.data[0]["id"]
            logger.info(f"Created project {project_id} in database")

            # Update progress - AI processing
            logger.info(
                "🏗️ [PROJECT-CREATION] About to call progress update: processing_requirements (50%)"
            )
            await self.progress_service.update_progress(
                progress_id,
                {
                    "percentage": 50,
                    "step": "processing_requirements",
                    "log": "🧠 AI is analyzing project requirements...",
                },
            )
            logger.info(
                "🏗️ [PROJECT-CREATION] Completed progress update: processing_requirements"
            )

            # Generate AI documentation if API key is available
            ai_success = await self._generate_ai_documentation(
                progress_id, project_id, title, description, github_repo
            )

            # Final success - fetch complete project data
            final_project_response = (
                self.supabase_client.table("archon_projects")
                .select("*")
                .eq("id", project_id)
                .execute()
            )
            if final_project_response.data:
                final_project = final_project_response.data[0]

                # Prepare project data for frontend
                project_data_for_frontend = {
                    "id": final_project["id"],
                    "title": final_project["title"],
                    "description": final_project.get("description", ""),
                    "github_repo": final_project.get("github_repo"),
                    "created_at": final_project["created_at"],
                    "updated_at": final_project["updated_at"],
                    "docs": final_project.get("docs", []),  # PRD documents will be here
                    "features": final_project.get("features", []),
                    "data": final_project.get("data", []),
                    "pinned": final_project.get("pinned", False),
                    "technical_sources": [],  # Empty initially
                    "business_sources": [],  # Empty initially
                }

                await self.progress_service.update_progress(
                    progress_id,
                    {
                        "percentage": 100,
                        "step": "completed",
                        "log": f'🎉 Project "{title}" created successfully!',
                        "project_id": project_id,
                        "project": project_data_for_frontend,
                    },
                )

                return True, {
                    "project_id": project_id,
                    "project": project_data_for_frontend,
                    "ai_documentation_generated": ai_success,
                }
            else:
                # Fallback if we can't fetch the project
                await self.progress_service.update_progress(
                    progress_id,
                    {
                        "percentage": 100,
                        "step": "completed",
                        "log": f'🎉 Project "{title}" created successfully!',
                        "project_id": project_id,
                    },
                )

                return True, {
                    "project_id": project_id,
                    "ai_documentation_generated": ai_success,
                }

        except Exception as e:
            logger.error(f"🚨 [PROJECT-CREATION] Project creation failed: {e!s}")
            try:
                await self.progress_service.error_operation(progress_id, str(e))
            except Exception as progress_error:
                logger.error(
                    f"🚨 [PROJECT-CREATION] Failed to send error progress: {progress_error}"
                )
            return False, {"error": str(e)}

    async def _generate_ai_documentation(
        self,
        progress_id: str,
        project_id: str,
        title: str,
        description: str | None,
        github_repo: str | None,
    ) -> bool:
        """
        Generate AI documentation for the project.

        Returns:
            True if successful, False otherwise
        """
        try:
            api_key = os.getenv("OPENAI_API_KEY")

            if not api_key:
                await self.progress_service.update_progress(
                    progress_id,
                    {
                        "percentage": 85,
                        "step": "finalizing",
                        "log": "⚠️ OpenAI API key not configured - skipping AI documentation generation",
                    },
                )
                return False

            # Import DocumentAgent (lazy import to avoid startup issues)
            from ...agents.document_agent import DocumentAgent

            await self.progress_service.update_progress(
                progress_id,
                {
                    "percentage": 70,
                    "step": "ai_generation",
                    "log": "✨ AI is creating project documentation...",
                },
            )

            # Initialize DocumentAgent
            document_agent = DocumentAgent()

            # Generate comprehensive PRD using conversation
            prd_request = f"Create a PRD document titled '{title} - Product Requirements Document' for a project called '{title}'"
            if description:
                prd_request += f" with the following description: {description}"
            if github_repo:
                prd_request += f" (GitHub repo: {github_repo})"

            # Create a progress callback for the document agent
            async def agent_progress_callback(update_data):
                await self.progress_service.update_progress(progress_id, update_data)

            # Run the document agent to create PRD
            agent_result = await document_agent.run_conversation(
                user_message=prd_request,
                project_id=project_id,
                user_id="system",
                progress_callback=agent_progress_callback,
            )

            if agent_result.success:
                await self.progress_service.update_progress(
                    progress_id,
                    {
                        "percentage": 85,
                        "step": "finalizing",
                        "log": "📝 Successfully created project documentation",
                    },
                )
                return True
            else:
                await self.progress_service.update_progress(
                    progress_id,
                    {
                        "percentage": 85,
                        "step": "finalizing",
                        "log": f"⚠️ Project created but AI documentation generation had issues: {agent_result.message}",
                    },
                )
                return False

        except Exception as ai_error:
            logger.warning(
                f"AI generation failed, continuing with basic project: {ai_error}"
            )
            await self.progress_service.update_progress(
                progress_id,
                {
                    "percentage": 85,
                    "step": "finalizing",
                    "log": "⚠️ AI generation failed - created basic project structure",
                },
            )
            return False
