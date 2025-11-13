#!/usr/bin/env python3
"""
Claude Code Repository Crawler Subagent

A specialized Claude Code subagent for intelligent repository crawling and analysis
with integration into the Archon intelligence services ecosystem.

This agent is designed to be invoked through Claude Code's Task tool system
and provides comprehensive repository analysis, code quality assessment,
and intelligence service integration.

Version: 1.0.0
Author: Archon Intelligence Services
"""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

# Import utility modules
from agents.utils.file_discovery import FileDiscoveryEngine
from agents.utils.intelligence_processor import IntelligenceProcessor
from agents.utils.repository_analyzer import RepositoryAnalyzer


class ClaudeCodeRepositoryCrawler:
    """
    Claude Code subagent for repository crawling with intelligence integration.

    Designed for integration with Claude Code's Task tool system and optimized
    for interactive development workflows.
    """

    def __init__(
        self,
        intelligence_service_url: str = "http://localhost:8053",
        archon_mcp_url: str = "http://localhost:8051",
    ):
        self.intelligence_service_url = intelligence_service_url
        self.archon_mcp_url = archon_mcp_url

        # Claude Code optimized processing limits
        self.processing_limits = {
            "max_files": 50,  # Reasonable limit for Claude Code sessions
            "max_file_size": 5 * 1024 * 1024,  # 5MB per file
            "timeout": 20.0,  # Shorter timeout for interactive use
            "concurrent_limit": 3,  # Conservative concurrent requests
        }

        # File type configurations optimized for development workflows
        self.supported_extensions = {
            # Code files (high priority)
            ".py": {"type": "code", "language": "python", "priority": 0.9},
            ".js": {"type": "code", "language": "javascript", "priority": 0.9},
            ".ts": {"type": "code", "language": "typescript", "priority": 0.9},
            ".tsx": {"type": "code", "language": "typescript", "priority": 0.9},
            ".jsx": {"type": "code", "language": "javascript", "priority": 0.9},
            ".java": {"type": "code", "language": "java", "priority": 0.8},
            ".go": {"type": "code", "language": "go", "priority": 0.8},
            ".rs": {"type": "code", "language": "rust", "priority": 0.8},
            ".cpp": {"type": "code", "language": "cpp", "priority": 0.8},
            ".c": {"type": "code", "language": "c", "priority": 0.8},
            ".h": {"type": "code", "language": "c", "priority": 0.7},
            # Documentation (very high priority)
            ".md": {"type": "documentation", "language": "markdown", "priority": 1.0},
            ".rst": {
                "type": "documentation",
                "language": "restructuredtext",
                "priority": 0.9,
            },
            ".txt": {"type": "documentation", "language": "text", "priority": 0.6},
            ".adoc": {"type": "documentation", "language": "asciidoc", "priority": 0.8},
            # Configuration (medium priority)
            ".json": {"type": "configuration", "language": "json", "priority": 0.7},
            ".yaml": {"type": "configuration", "language": "yaml", "priority": 0.7},
            ".yml": {"type": "configuration", "language": "yaml", "priority": 0.7},
            ".toml": {"type": "configuration", "language": "toml", "priority": 0.7},
            ".ini": {"type": "configuration", "language": "ini", "priority": 0.6},
            ".env": {"type": "configuration", "language": "env", "priority": 0.6},
        }

        # High-value file patterns
        self.high_value_patterns = {
            "README": 1.0,
            "readme": 1.0,
            "CHANGELOG": 0.9,
            "changelog": 0.9,
            "package.json": 0.9,
            "pyproject.toml": 0.9,
            "Cargo.toml": 0.9,
            "pom.xml": 0.9,
            "Dockerfile": 0.8,
            "docker-compose": 0.8,
            "main": 0.8,
            "index": 0.8,
            "app": 0.8,
            "config": 0.7,
            "settings": 0.7,
        }

        # Exclude patterns for Claude Code workflows
        self.exclude_patterns = {
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            "env",
            ".pytest_cache",
            "coverage",
            "dist",
            "build",
            "target",
            ".idea",
            ".vscode",
            "vendor",
            "bower_components",
            ".next",
            "out",
            "bin",
            "obj",
            "tmp",
            "temp",
            "cache",
            "logs",
            ".DS_Store",
            "Thumbs.db",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".tox",
            ".coverage",
            ".nyc_output",
            "junit.xml",
        }

        # Initialize utility engines
        self.file_discovery = FileDiscoveryEngine(
            supported_extensions=self.supported_extensions,
            high_value_patterns=self.high_value_patterns,
            exclude_patterns=self.exclude_patterns,
            max_file_size=self.processing_limits["max_file_size"],
        )

        self.intelligence_processor = IntelligenceProcessor(
            intelligence_service_url=self.intelligence_service_url,
            timeout=self.processing_limits["timeout"],
            concurrent_limit=self.processing_limits["concurrent_limit"],
        )

        self.repository_analyzer = RepositoryAnalyzer()

        # Processing statistics
        self.stats = {
            "start_time": None,
            "end_time": None,
            "files_discovered": 0,
            "files_processed": 0,
            "intelligence_calls": 0,
            "errors": 0,
            "warnings": 0,
        }

        # Configuration flags
        self.verbose = False
        self.dry_run = False

    async def _find_or_create_archon_project(
        self, repo_context: dict[str, Any], task_config: dict[str, Any]
    ) -> str | None:
        """
        Find existing Archon project or create new one based on repository context.

        Args:
            repo_context: Repository context information
            task_config: Task configuration

        Returns:
            Project ID if found or created, None if operation failed
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.processing_limits["timeout"]
            ) as client:
                # Check for existing projects
                existing_project = await self._search_existing_projects(
                    client, repo_context
                )

                if existing_project:
                    if self.verbose:
                        print(
                            f"🔗 Found existing Archon project: {existing_project['title']}"
                        )
                    return existing_project["id"]

                # Create new project if none found and auto-creation enabled
                if task_config.get("create_project_if_missing", True):
                    new_project = await self._create_archon_project(
                        client, repo_context, task_config
                    )
                    if new_project:
                        if self.verbose:
                            print(
                                f"📝 Created new Archon project: {new_project['title']}"
                            )
                        return new_project["id"]

                return None

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Archon project management failed: {e}")
            return None

    async def _search_existing_projects(
        self, client: httpx.AsyncClient, repo_context: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Search for existing Archon projects that match the repository.

        Args:
            client: HTTP client instance
            repo_context: Repository context information

        Returns:
            Matching project data or None if no match found
        """
        try:
            # Get all projects from Archon
            response = await client.get(
                f"{self.archon_mcp_url.replace('8051', '8181')}/api/projects"
            )

            if response.status_code != 200:
                if self.verbose:
                    print(f"⚠️ Failed to fetch Archon projects: {response.status_code}")
                return None

            projects = response.json()
            repo_name = repo_context.get("name", "").lower()
            git_remote = repo_context.get("git_info", {}).get("remote", "").lower()

            # Search for matches using multiple criteria
            for project in projects:
                project_title = project.get("title", "").lower()
                project_desc = project.get("description", "").lower()
                project_github = project.get("github_repo", "").lower()

                # Exact name match (highest priority)
                if repo_name and repo_name == project_title:
                    return project

                # GitHub repository match (high priority)
                if git_remote and project_github and git_remote in project_github:
                    return project

                # Repository name in project title (medium priority)
                if repo_name and repo_name in project_title:
                    return project

                # Repository name in project description (lower priority)
                if repo_name and len(repo_name) > 3 and repo_name in project_desc:
                    return project

            return None

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Project search failed: {e}")
            return None

    async def _create_archon_project(
        self,
        client: httpx.AsyncClient,
        repo_context: dict[str, Any],
        task_config: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Create a new Archon project based on repository context.

        Args:
            client: HTTP client instance
            repo_context: Repository context information
            task_config: Task configuration

        Returns:
            Created project data or None if creation failed
        """
        try:
            # Prepare project data
            repo_name = repo_context.get("name", "Unknown Repository")
            git_info = repo_context.get("git_info", {})
            tech_stack = repo_context.get("technology_stack", [])

            project_data = {
                "title": repo_name,
                "description": self._generate_project_description(
                    repo_context, tech_stack
                ),
                "github_repo": (
                    git_info.get("remote")
                    if git_info.get("remote", "").startswith("http")
                    else None
                ),
            }

            # Create project via Archon API
            response = await client.post(
                f"{self.archon_mcp_url.replace('8051', '8181')}/api/projects",
                json=project_data,
            )

            if response.status_code == 201:
                created_project = response.json()
                return created_project
            else:
                if self.verbose:
                    print(f"⚠️ Failed to create Archon project: {response.status_code}")
                return None

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Project creation failed: {e}")
            return None

    def _generate_project_description(
        self, repo_context: dict[str, Any], tech_stack: list[str]
    ) -> str:
        """Generate a project description based on repository context."""
        description_parts = [f"Repository: {repo_context.get('name', 'Unknown')}"]

        if tech_stack:
            description_parts.append(f"Technology Stack: {', '.join(tech_stack)}")

        git_info = repo_context.get("git_info", {})
        if git_info.get("branch"):
            description_parts.append(f"Current Branch: {git_info['branch']}")

        files_count = repo_context.get("files_count", 0)
        if files_count > 0:
            description_parts.append(f"Repository Size: {files_count} files")

        description_parts.append("Auto-created by Claude Code Repository Crawler")

        return " | ".join(description_parts)

    async def _update_archon_project_with_results(
        self, project_id: str, results: dict[str, Any]
    ) -> bool:
        """
        Update Archon project with analysis results.

        Args:
            project_id: Archon project ID
            results: Analysis results to add to project

        Returns:
            True if update successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.processing_limits["timeout"]
            ) as client:
                # Prepare update data based on analysis results
                insights = results.get("repository_insights", {})

                update_data = {
                    "analysis_results": {
                        "last_crawl_timestamp": datetime.now(UTC).isoformat(),
                        "files_analyzed": self.stats["files_processed"],
                        "intelligence_coverage": f"{(self.stats['intelligence_calls'] / max(self.stats['files_processed'], 1) * 100):.1f}%",
                        "technology_analysis": insights.get("technology_analysis", {}),
                        "quality_summary": insights.get("quality_analysis", {}),
                        "documentation_summary": insights.get(
                            "documentation_analysis", {}
                        ),
                    }
                }

                # Update project via Archon API
                response = await client.put(
                    f"{self.archon_mcp_url.replace('8051', '8181')}/api/projects/{project_id}",
                    json=update_data,
                )

                if response.status_code == 200:
                    if self.verbose:
                        print(
                            f"📊 Updated Archon project {project_id} with analysis results"
                        )
                    return True
                else:
                    if self.verbose:
                        print(
                            f"⚠️ Failed to update Archon project: {response.status_code}"
                        )
                    return False

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Project update failed: {e}")
            return False

    async def execute_task(self, task_prompt: str, **kwargs) -> dict[str, Any]:
        """
        Main entry point for Claude Code Task integration.

        This method is called by Claude Code's Task tool system.

        Args:
            task_prompt: The task description from Claude Code
            **kwargs: Additional parameters from the Task call

        Returns:
            Comprehensive task execution results
        """
        self.stats["start_time"] = time.time()

        try:
            # Parse task parameters
            task_config = await self._parse_task_prompt(task_prompt, **kwargs)

            print("🚀 Claude Code Repository Crawler - Task Execution Started")
            print(f"📋 Task: {task_config.get('description', 'Repository Analysis')}")
            print(f"📁 Repository: {task_config.get('repo_path', 'Current Directory')}")

            # Execute the comprehensive analysis
            results = await self._execute_comprehensive_analysis(task_config)

            self.stats["end_time"] = time.time()
            processing_time = self.stats["end_time"] - self.stats["start_time"]

            # Generate Claude Code-friendly output
            output = await self._format_claude_code_output(results, task_config)

            print(f"✅ Task completed successfully in {processing_time:.2f}s")
            print(
                f"📊 Processed {self.stats['files_processed']} files with {self.stats['intelligence_calls']} intelligence calls"
            )

            return {
                "success": True,
                "task_results": output,
                "processing_stats": self.stats,
                "recommendations": results.get("recommendations", []),
            }

        except Exception as e:
            self.stats["end_time"] = time.time()
            error_msg = f"Task execution failed: {e!s}"
            print(f"❌ {error_msg}")

            return {
                "success": False,
                "error": error_msg,
                "processing_stats": self.stats,
                "partial_results": getattr(self, "_partial_results", None),
            }

    async def _parse_task_prompt(self, task_prompt: str, **kwargs) -> dict[str, Any]:
        """Parse task prompt and extract configuration parameters."""
        config = {
            "repo_path": kwargs.get("repo_path", "."),
            "description": "Repository Analysis",
            "focus": "comprehensive",  # comprehensive, quality, documentation, architecture
            "max_files": kwargs.get("max_files", self.processing_limits["max_files"]),
            "include_intelligence": kwargs.get("include_intelligence", True),
            "generate_reports": kwargs.get("generate_reports", True),
            "update_archon": kwargs.get("update_archon", False),
            "dry_run": kwargs.get("dry_run", False),
        }

        # Ensure instance state tracks the current request only
        self.dry_run = config["dry_run"]

        # Parse prompt for specific instructions
        prompt_lower = task_prompt.lower()

        if "quality" in prompt_lower or "compliance" in prompt_lower:
            config["focus"] = "quality"
        elif "documentation" in prompt_lower or "docs" in prompt_lower:
            config["focus"] = "documentation"
        elif "architecture" in prompt_lower or "tech stack" in prompt_lower:
            config["focus"] = "architecture"

        if "dry run" in prompt_lower or "dry-run" in prompt_lower:
            self.dry_run = True
            config["include_intelligence"] = False
            config["dry_run"] = True

        if "verbose" in prompt_lower:
            self.verbose = True

        # Extract repository path from prompt
        import re

        path_match = re.search(r"repository path:?\s*([^\s\n]+)", prompt_lower)
        if path_match:
            config["repo_path"] = path_match.group(1)

        config["description"] = (
            task_prompt[:100] + "..." if len(task_prompt) > 100 else task_prompt
        )

        return config

    async def _execute_comprehensive_analysis(
        self, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute comprehensive repository analysis based on configuration."""
        repo_path = Path(config["repo_path"]).resolve()

        if not repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

        print(f"📁 Analyzing repository: {repo_path.name}")

        # Propagate verbose flag to utility engines
        self.file_discovery.verbose = self.verbose
        self.intelligence_processor.verbose = self.verbose
        self.repository_analyzer.verbose = self.verbose

        # Phase 1: Repository Context & Discovery
        context = await self.repository_analyzer.establish_repository_context(repo_path)
        print(
            f"🔍 Repository context established: {context['files_count']} total files"
        )

        # Phase 2: Intelligent File Discovery & Prioritization
        discovered_files = await self.file_discovery.discover_and_prioritize_files(
            repo_path, config["max_files"]
        )
        self.stats["files_discovered"] = len(discovered_files)
        print(f"⚡ Discovered {len(discovered_files)} relevant files for analysis")

        # Phase 3: Content Processing with Intelligence Integration
        processed_files = (
            await self.intelligence_processor.process_files_with_intelligence(
                discovered_files, config, self.stats
            )
        )
        self.stats["intelligence_calls"] = sum(
            1 for f in processed_files if f.get("intelligence_analysis")
        )
        print(f"🧠 Processed {len(processed_files)} files with intelligence analysis")

        # Phase 4: Repository-Level Analysis & Insights
        repository_insights = (
            await self.repository_analyzer.generate_repository_insights(
                processed_files, context, config
            )
        )
        print("📊 Generated repository-level intelligence insights")

        # Phase 5: Recommendations & Action Items
        recommendations = await self.repository_analyzer.generate_recommendations(
            repository_insights, config
        )
        print(f"🎯 Generated {len(recommendations)} actionable recommendations")

        return {
            "context": context,
            "discovered_files": discovered_files,
            "processed_files": processed_files,
            "repository_insights": repository_insights,
            "recommendations": recommendations,
            "config": config,
        }

    async def _format_claude_code_output(
        self, results: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Format results for Claude Code consumption."""
        output = {
            "task_summary": {
                "repository": results["context"]["name"],
                "analysis_type": config["focus"],
                "files_processed": self.stats["files_processed"],
                "intelligence_coverage": f"{(self.stats['intelligence_calls'] / max(self.stats['files_processed'], 1) * 100):.1f}%",
                "processing_time": f"{(self.stats['end_time'] - self.stats['start_time']):.2f}s",
            },
            "key_insights": {},
            "recommendations": results["recommendations"],
            "detailed_results": {},
            "next_steps": [],
        }

        # Extract key insights based on focus
        insights = results["repository_insights"]

        if config["focus"] in ["comprehensive", "quality"]:
            quality_analysis = insights.get("quality_analysis", {})
            if quality_analysis:
                output["key_insights"]["code_quality"] = {
                    "average_score": quality_analysis.get(
                        "average_quality_score", "N/A"
                    ),
                    "files_analyzed": quality_analysis.get("files_analyzed", 0),
                    "quality_distribution": quality_analysis.get(
                        "quality_distribution", {}
                    ),
                }

        if config["focus"] in ["comprehensive", "documentation"]:
            doc_analysis = insights.get("documentation_analysis", {})
            output["key_insights"]["documentation"] = {
                "total_docs": doc_analysis.get("documentation_files", 0),
                "coverage_ratio": f"{doc_analysis.get('docs_to_code_ratio', 0):.2f}",
                "has_readme": doc_analysis.get("has_readme", False),
            }

        if config["focus"] in ["comprehensive", "architecture"]:
            tech_analysis = insights.get("technology_analysis", {})
            output["key_insights"]["technology"] = {
                "primary_language": tech_analysis.get("primary_language", "unknown"),
                "repository_type": tech_analysis.get(
                    "repository_classification", "unknown"
                ),
                "technology_stack": tech_analysis.get("technology_stack", []),
            }

        # Generate next steps based on recommendations
        for rec in results["recommendations"][:3]:  # Top 3 recommendations
            output["next_steps"].append(
                {
                    "action": rec["title"],
                    "priority": rec["priority"],
                    "description": rec["description"],
                }
            )

        # Include detailed results if requested
        if config.get("generate_reports", True):
            output["detailed_results"] = {
                "file_summary": insights["summary"],
                "processing_stats": self.stats,
                "sample_files": [
                    {
                        "path": f["file_info"]["relative_path"],
                        "type": f["file_info"]["file_type"],
                        "language": f["file_info"]["language"],
                        "has_intelligence": bool(f.get("intelligence_analysis")),
                    }
                    for f in results["processed_files"][
                        :10
                    ]  # Sample of processed files
                ],
            }

        return output


# Claude Code Task Integration Point
async def main():
    """
    Main entry point for Claude Code Task system integration.

    This function is called when the agent is invoked via Claude Code's Task tool.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Claude Code Repository Crawler Subagent"
    )
    parser.add_argument(
        "--task-prompt", required=True, help="Task prompt from Claude Code"
    )
    parser.add_argument("--repo-path", default=".", help="Repository path to analyze")
    parser.add_argument(
        "--max-files", type=int, default=50, help="Maximum files to process"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run without intelligence calls"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--focus",
        choices=["comprehensive", "quality", "documentation", "architecture"],
        default="comprehensive",
        help="Analysis focus area",
    )

    args = parser.parse_args()

    # Create and configure crawler
    crawler = ClaudeCodeRepositoryCrawler()
    crawler.verbose = args.verbose
    crawler.dry_run = args.dry_run

    # Execute task
    try:
        results = await crawler.execute_task(
            args.task_prompt,
            repo_path=args.repo_path,
            max_files=args.max_files,
            focus=args.focus,
        )

        # Output results for Claude Code consumption
        if results["success"]:
            print("\n" + "=" * 60)
            print("🎉 CLAUDE CODE REPOSITORY CRAWLER - TASK COMPLETE")
            print("=" * 60)

            task_summary = results["task_results"]["task_summary"]
            print(f"📁 Repository: {task_summary['repository']}")
            print(f"🔍 Analysis Type: {task_summary['analysis_type']}")
            print(f"📊 Files Processed: {task_summary['files_processed']}")
            print(f"🧠 Intelligence Coverage: {task_summary['intelligence_coverage']}")
            print(f"⏱️ Processing Time: {task_summary['processing_time']}")

            # Show key insights
            key_insights = results["task_results"]["key_insights"]
            if key_insights:
                print("\n🔍 KEY INSIGHTS:")
                for insight_type, data in key_insights.items():
                    print(f"  {insight_type.title()}: {data}")

            # Show top recommendations
            recommendations = results["task_results"]["recommendations"]
            if recommendations:
                print(f"\n🎯 TOP RECOMMENDATIONS ({len(recommendations)}):")
                for i, rec in enumerate(recommendations[:3], 1):
                    print(f"  {i}. [{rec['priority'].upper()}] {rec['title']}")

            # Save detailed results
            results_file = Path("claude_code_crawler_results.json")
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n📄 Detailed results saved to: {results_file}")

        else:
            print(f"❌ Task failed: {results['error']}")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️ Task cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
