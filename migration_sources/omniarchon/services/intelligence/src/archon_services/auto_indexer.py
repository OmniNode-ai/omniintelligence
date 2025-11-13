"""
Auto-Indexing Service

Automatic project indexing service for zero-configuration operation.
Monitors projects and triggers indexing automatically.

Features:
- Startup auto-index for configured projects
- Optional file watching for change detection
- Optional scheduled re-indexing
- Automatic INDEX_PROJECT_REQUESTED event publishing
- Configurable via environment variables

ONEX Pattern: Orchestrator (coordinates multiple services and workflows)
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class AutoIndexerService:
    """
    Automatic project indexing service.

    Handles:
    - Startup auto-index for configured projects
    - Optional file change monitoring
    - Optional scheduled re-indexing
    - Automatic event publishing to Kafka

    Configuration (Environment Variables):
    - AUTO_INDEXING_ENABLED: Enable/disable auto-indexing (default: true)
    - AUTO_INDEX_PROJECTS: Comma-separated list of project paths to auto-index
    - AUTO_INDEX_WORKSPACE: Workspace directory to scan for projects (alternative)
    - AUTO_INDEX_ON_STARTUP: Index projects on service startup (default: true)
    - AUTO_INDEX_WATCH_CHANGES: Watch for file changes and re-index (default: false)
    - AUTO_INDEX_SCHEDULE_HOURS: Re-index every N hours (default: 0 = disabled)
    - AUTO_INDEX_INCLUDE_TESTS: Include test files in indexing (default: true)
    - AUTO_INDEX_FORCE_REINDEX: Force re-index even if already indexed (default: false)

    Usage:
        # In app.py startup
        auto_indexer = AutoIndexerService(event_router=kafka_consumer.router)
        await auto_indexer.start()

        # In app.py shutdown
        await auto_indexer.shutdown()
    """

    def __init__(self, event_router=None):
        """
        Initialize AutoIndexerService.

        Args:
            event_router: KafkaEventRouter instance for publishing events
        """
        self.event_router = event_router

        # Configuration
        self.enabled = os.getenv("AUTO_INDEXING_ENABLED", "true").lower() == "true"
        self.index_on_startup = (
            os.getenv("AUTO_INDEX_ON_STARTUP", "true").lower() == "true"
        )
        self.watch_changes = (
            os.getenv("AUTO_INDEX_WATCH_CHANGES", "false").lower() == "true"
        )
        self.schedule_hours = int(os.getenv("AUTO_INDEX_SCHEDULE_HOURS", "0"))
        self.include_tests = (
            os.getenv("AUTO_INDEX_INCLUDE_TESTS", "true").lower() == "true"
        )
        self.force_reindex = (
            os.getenv("AUTO_INDEX_FORCE_REINDEX", "false").lower() == "true"
        )

        # Project configuration
        self.projects = self._load_project_config()

        # Background tasks
        self._tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

        # Metrics
        self.metrics = {
            "projects_indexed": 0,
            "index_requests_sent": 0,
            "index_failures": 0,
            "last_index_time": None,
            "startup_index_complete": False,
        }

        logger.info(
            f"AutoIndexerService initialized: "
            f"enabled={self.enabled}, "
            f"projects={len(self.projects)}, "
            f"startup={self.index_on_startup}, "
            f"watch={self.watch_changes}, "
            f"schedule_hours={self.schedule_hours}"
        )

    def _load_project_config(self) -> List[Dict[str, str]]:
        """
        Load project configuration from environment.

        Returns:
            List of project configs with path and name
        """
        projects = []

        # Option 1: Explicit project list (AUTO_INDEX_PROJECTS)
        project_paths = os.getenv("AUTO_INDEX_PROJECTS", "")
        if project_paths:
            for path in project_paths.split(","):
                path = path.strip()
                if path:
                    project_name = Path(path).name
                    projects.append(
                        {
                            "path": path,
                            "name": project_name,
                        }
                    )
            logger.info(f"Loaded {len(projects)} projects from AUTO_INDEX_PROJECTS")

        # Option 2: Workspace scanning (AUTO_INDEX_WORKSPACE)
        workspace = os.getenv("AUTO_INDEX_WORKSPACE", "")
        if workspace and not projects:
            workspace_path = Path(workspace)
            if workspace_path.exists() and workspace_path.is_dir():
                discovered = self._discover_projects_in_workspace(workspace_path)
                projects.extend(discovered)
                logger.info(
                    f"Discovered {len(discovered)} projects in workspace: {workspace}"
                )
            else:
                logger.warning(
                    f"Workspace path does not exist or is not a directory: {workspace}"
                )

        # Option 3: Default - index current omniarchon project
        if not projects:
            # Default to omniarchon project itself (portable mount path in Docker)
            default_path = "/workspace/omniarchon"
            if Path(default_path).exists():
                projects.append(
                    {
                        "path": default_path,
                        "name": "omniarchon",
                    }
                )
                logger.info(f"Using default project: {default_path}")

        return projects

    def _discover_projects_in_workspace(
        self, workspace_path: Path
    ) -> List[Dict[str, str]]:
        """
        Discover projects in a workspace directory.

        Projects are detected by presence of:
        - .git directory
        - pyproject.toml, package.json, Cargo.toml, go.mod, etc.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            List of discovered project configs
        """
        projects = []

        try:
            # Only scan first level of workspace (not recursive)
            for item in workspace_path.iterdir():
                if not item.is_dir():
                    continue

                # Skip hidden directories
                if item.name.startswith("."):
                    continue

                # Check for project indicators
                is_project = (
                    (item / ".git").exists()
                    or (item / "pyproject.toml").exists()
                    or (item / "package.json").exists()
                    or (item / "Cargo.toml").exists()
                    or (item / "go.mod").exists()
                    or (item / "pom.xml").exists()
                    or (item / "build.gradle").exists()
                )

                if is_project:
                    projects.append(
                        {
                            "path": str(item.absolute()),
                            "name": item.name,
                        }
                    )
                    logger.debug(f"Discovered project: {item.name}")

        except Exception as e:
            logger.error(f"Failed to discover projects in workspace: {e}")

        return projects

    async def start(self):
        """
        Start auto-indexing service.

        Starts background tasks:
        - Startup indexing (if enabled)
        - Scheduled re-indexing (if configured)
        - File change watching (if enabled)
        """
        if not self.enabled:
            logger.info("Auto-indexing disabled (AUTO_INDEXING_ENABLED=false)")
            return

        if not self.event_router:
            logger.warning(
                "AutoIndexerService started without event_router - "
                "events will NOT be published! Pass event_router to enable."
            )

        logger.info("Starting AutoIndexerService...")

        # Startup indexing
        if self.index_on_startup:
            task = asyncio.create_task(self._startup_index())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        # Scheduled re-indexing
        if self.schedule_hours > 0:
            task = asyncio.create_task(self._scheduled_reindex())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        # File change watching (future enhancement - requires watchdog library)
        if self.watch_changes:
            logger.warning(
                "File change watching requested but not yet implemented. "
                "Install 'watchdog' library and implement _watch_for_changes()."
            )
            # task = asyncio.create_task(self._watch_for_changes())
            # self._tasks.add(task)
            # task.add_done_callback(self._tasks.discard)

        logger.info(
            f"AutoIndexerService started successfully " f"(tasks={len(self._tasks)})"
        )

    async def shutdown(self):
        """
        Shutdown auto-indexing service.

        Cancels all background tasks and waits for completion.
        Cleans up event router if available.
        """
        logger.info("Shutting down AutoIndexerService...")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Shutdown event router if available
        if self.event_router and hasattr(self.event_router, "shutdown"):
            try:
                logger.info("Shutting down AutoIndexer event router...")
                await self.event_router.shutdown()
                logger.info("Event router shutdown complete")
            except Exception as e:
                logger.error(f"Failed to shutdown event router: {e}")

        logger.info("AutoIndexerService shutdown complete")

    async def _startup_index(self):
        """
        Index all configured projects on startup.

        Publishes INDEX_PROJECT_REQUESTED events for each project.
        """
        try:
            logger.info(
                f"Starting startup indexing for {len(self.projects)} projects..."
            )

            for project in self.projects:
                if self._shutdown_event.is_set():
                    logger.info("Startup indexing cancelled due to shutdown")
                    return

                try:
                    await self._index_project(
                        project_path=project["path"],
                        project_name=project["name"],
                        force_reindex=self.force_reindex,
                    )

                    self.metrics["projects_indexed"] += 1

                    # Small delay between projects to avoid overwhelming services
                    await asyncio.sleep(1.0)

                except Exception as e:
                    logger.error(
                        f"Failed to index project {project['name']}: {e}", exc_info=True
                    )
                    self.metrics["index_failures"] += 1

            self.metrics["startup_index_complete"] = True
            self.metrics["last_index_time"] = datetime.now()

            logger.info(
                f"✅ Startup indexing complete: "
                f"{self.metrics['projects_indexed']} projects indexed, "
                f"{self.metrics['index_failures']} failures"
            )

        except Exception as e:
            logger.error(f"Startup indexing failed: {e}", exc_info=True)

    async def _scheduled_reindex(self):
        """
        Re-index all projects on a schedule.

        Runs in background, re-indexing every N hours as configured.
        """
        try:
            logger.info(
                f"Scheduled re-indexing enabled (every {self.schedule_hours} hours)"
            )

            interval_seconds = self.schedule_hours * 3600

            while not self._shutdown_event.is_set():
                # Wait for interval or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=interval_seconds
                    )
                    # Shutdown event triggered
                    break
                except asyncio.TimeoutError:
                    # Interval elapsed, proceed with re-indexing
                    pass

                logger.info("Starting scheduled re-indexing...")

                for project in self.projects:
                    if self._shutdown_event.is_set():
                        logger.info("Scheduled re-indexing cancelled due to shutdown")
                        return

                    try:
                        await self._index_project(
                            project_path=project["path"],
                            project_name=project["name"],
                            force_reindex=True,  # Always force for scheduled re-index
                        )

                        # Small delay between projects
                        await asyncio.sleep(1.0)

                    except Exception as e:
                        logger.error(
                            f"Scheduled re-index failed for {project['name']}: {e}",
                            exc_info=True,
                        )

                self.metrics["last_index_time"] = datetime.now()
                logger.info("✅ Scheduled re-indexing complete")

        except Exception as e:
            logger.error(f"Scheduled re-indexing task failed: {e}", exc_info=True)

    async def _index_project(
        self,
        project_path: str,
        project_name: str,
        force_reindex: bool = False,
    ):
        """
        Index a single project by publishing INDEX_PROJECT_REQUESTED event.

        Args:
            project_path: Absolute path to project
            project_name: Project name for identification
            force_reindex: Force re-indexing even if already indexed
        """
        try:
            logger.info(
                f"Indexing project: {project_name} "
                f"(path={project_path}, force={force_reindex})"
            )

            # Generate correlation ID
            correlation_id = uuid4()

            # Create event payload
            from events.models.tree_stamping_events import (
                create_index_project_requested,
            )

            event_envelope = create_index_project_requested(
                project_path=project_path,
                project_name=project_name,
                include_tests=self.include_tests,
                force_reindex=force_reindex,
                correlation_id=correlation_id,
            )

            # Publish event
            if self.event_router:
                topic = "dev.archon-intelligence.tree.index-project-requested.v1"
                await self.event_router.publish(
                    topic=topic,
                    event=event_envelope,
                    key=str(correlation_id),
                )

                self.metrics["index_requests_sent"] += 1

                logger.info(
                    f"📤 Published INDEX_PROJECT_REQUESTED: "
                    f"{project_name} (correlation_id={correlation_id})"
                )
            else:
                logger.warning(
                    f"⚠️  Event router not available - cannot publish event for {project_name}. "
                    f"Event would be sent to topic: dev.archon-intelligence.tree.index-project-requested.v1"
                )

        except Exception as e:
            logger.error(
                f"Failed to publish index request for {project_name}: {e}",
                exc_info=True,
            )
            raise

    def get_metrics(self) -> Dict:
        """
        Get auto-indexer metrics.

        Returns:
            Metrics dictionary
        """
        return {
            **self.metrics,
            "enabled": self.enabled,
            "projects_configured": len(self.projects),
            "active_tasks": len(self._tasks),
            "last_index_time_iso": (
                self.metrics["last_index_time"].isoformat()
                if self.metrics["last_index_time"]
                else None
            ),
        }

    def get_project_list(self) -> List[Dict[str, str]]:
        """
        Get list of configured projects.

        Returns:
            List of project configs
        """
        return self.projects.copy()
