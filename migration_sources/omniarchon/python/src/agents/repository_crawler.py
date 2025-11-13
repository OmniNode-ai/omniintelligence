#!/usr/bin/env python3
"""
Repository Crawler Agent - Claude Code Subagent
Discovers, processes, and indexes all relevant documents across repositories
with comprehensive intelligence service integration.
"""

import asyncio
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import httpx


class IntelligentRepositoryCrawler:
    """
    Claude Code subagent for comprehensive repository crawling with intelligence integration.
    Discovers, analyzes, and indexes repository content with quality assessment and performance optimization.
    """

    def __init__(
        self,
        intelligence_service_url: str = "http://localhost:8053",
        archon_server_url: str = "http://localhost:8181",
    ):
        self.intelligence_service_url = intelligence_service_url
        self.archon_server_url = archon_server_url

        # File type configurations
        self.supported_code_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
        }

        self.supported_doc_extensions = {
            ".md",
            ".rst",
            ".txt",
            ".adoc",
            ".org",
            ".wiki",
        }

        self.supported_config_extensions = {
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".ini",
            ".cfg",
            ".conf",
            ".properties",
            ".env",
            ".dockerfile",
        }

        # Processing configurations
        self.chunk_size_target = 1500
        self.chunk_overlap = 300
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.timeout = 30.0

        # Exclude patterns
        self.exclude_patterns = {
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            "env",
            ".venv",
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
        }

        # Runtime configuration
        self.dry_run = False
        self.verbose = False

        # Statistics tracking
        self.stats = {
            "files_discovered": 0,
            "files_processed": 0,
            "intelligence_assessments": 0,
            "knowledge_items_extracted": 0,
            "processing_errors": 0,
            "start_time": None,
            "end_time": None,
        }

    async def find_existing_archon_project(
        self, repo_context: dict[str, Any]
    ) -> Optional[str]:
        """
        Search for existing Archon projects that match this repository.

        Args:
            repo_context: Repository context with name, git info, etc.

        Returns:
            Project ID if found, None otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get all projects from Archon
                response = await client.get(f"{self.archon_server_url}/api/projects")

                if response.status_code != 200:
                    print(f"⚠️ Failed to fetch Archon projects: {response.status_code}")
                    return None

                projects_data = response.json()
                projects = (
                    projects_data.get("projects", projects_data)
                    if isinstance(projects_data, dict)
                    else projects_data
                )

                repo_name = repo_context.get("name", "").lower()
                git_info = repo_context.get("git_info", {})
                git_remote = git_info.get("remote_url", "").lower()

                print(
                    f"🔍 Searching {len(projects)} existing projects for matches to '{repo_name}'..."
                )

                # Search for matches using multiple criteria
                matches = []

                for project in projects:
                    project_title = project.get("title", "").lower()
                    project_desc = project.get("description", "").lower()
                    project_github = (
                        project.get("github_repo", "").lower()
                        if project.get("github_repo")
                        else ""
                    )
                    project_id = project.get("id")

                    match_score = 0
                    match_reasons = []

                    # Exact name match (highest priority)
                    if repo_name and repo_name == project_title:
                        match_score += 100
                        match_reasons.append("exact title match")

                    # GitHub repository URL match (very high priority)
                    if git_remote and project_github and git_remote in project_github:
                        match_score += 90
                        match_reasons.append("github URL match")
                    elif git_remote and project_github:
                        # Check if repo names match in URLs
                        try:
                            remote_repo_name = git_remote.split("/")[-1].replace(
                                ".git", ""
                            )
                            github_repo_name = project_github.split("/")[-1].replace(
                                ".git", ""
                            )
                            if remote_repo_name == github_repo_name:
                                match_score += 80
                                match_reasons.append("github repo name match")
                        except (IndexError, AttributeError) as e:
                            # Failed to extract repo names from URLs
                            print(f"⚠️ Error extracting repo names from URLs: {e}")
                            pass

                    # Repository name in project title (high priority)
                    if repo_name and repo_name in project_title:
                        match_score += 70
                        match_reasons.append("name in title")

                    # Repository name in description (medium priority)
                    if repo_name and len(repo_name) > 3 and repo_name in project_desc:
                        match_score += 50
                        match_reasons.append("name in description")

                    # Repository-related keywords in title/description
                    try:
                        if any(
                            keyword in project_title or keyword in project_desc
                            for keyword in [
                                f"{repo_name} repository",
                                f"{repo_name} analysis",
                                f"{repo_name} intelligence",
                            ]
                        ):
                            match_score += 40
                            match_reasons.append("repository keywords")
                    except (TypeError, AttributeError) as e:
                        # Handle cases where repo_name might be None or unexpected type
                        print(f"⚠️ Error checking repository keywords: {e}")

                    if match_score > 0:
                        matches.append(
                            {
                                "project_id": project_id,
                                "title": project.get("title", ""),
                                "score": match_score,
                                "reasons": match_reasons,
                                "github_repo": project.get("github_repo", ""),
                                "created_at": project.get("created_at", ""),
                            }
                        )

                if matches:
                    # Sort by score (descending), then by creation date (most recent first)
                    matches.sort(
                        key=lambda x: (x["score"], x["created_at"]), reverse=True
                    )

                    best_match = matches[0]
                    print(f"✅ Found matching project: '{best_match['title']}'")
                    print(
                        f"   Match Score: {best_match['score']}, Reasons: {', '.join(best_match['reasons'])}"
                    )
                    print(f"   Project ID: {best_match['project_id']}")

                    if len(matches) > 1:
                        print(f"   ({len(matches) - 1} other potential matches found)")

                    return best_match["project_id"]
                else:
                    print(f"❌ No matching projects found for '{repo_name}'")
                    return None

        except Exception as e:
            print(f"⚠️ Project search failed: {e}")
            return None

    async def crawl_repository_comprehensive(
        self, repo_path: str, project_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Main entry point for comprehensive repository crawling with intelligence integration.

        Args:
            repo_path: Path to repository root
            project_id: Optional Archon project ID for integration

        Returns:
            Comprehensive crawling results with intelligence insights
        """
        self.stats["start_time"] = time.time()
        print(f"🚀 Starting comprehensive repository crawling: {repo_path}")

        try:
            # Phase 1: Repository Discovery & Context Establishment
            repo_context = await self.establish_repository_context(repo_path)
            print(
                f"📁 Repository context established: {repo_context['name']} ({repo_context['total_files']} files)"
            )

            # Phase 1.5: Find or Link to Existing Archon Project
            if not project_id:
                project_id = await self.find_existing_archon_project(repo_context)
                if project_id:
                    print(f"🔗 Linked to existing Archon project: {project_id}")
                else:
                    print(
                        "📝 No existing project found - will proceed without project linking"
                    )

            # Phase 2: Intelligent File Discovery
            repository_structure = await self.discover_repository_structure(repo_path)
            print(f"🔍 Files discovered: {len(repository_structure['all_files'])}")

            # Phase 3: Quality-Based Filtering
            filtered_files = await self.apply_intelligent_filtering(
                repository_structure["all_files"]
            )
            print(f"⚡ Files filtered for processing: {len(filtered_files)}")

            # Phase 4: Content Processing with Intelligence Integration
            processed_content = await self.process_files_with_intelligence(
                filtered_files
            )
            print(f"🧠 Files processed with intelligence: {len(processed_content)}")

            # Phase 5: Repository-Level Intelligence Analysis
            repository_intelligence = await self.extract_repository_intelligence(
                processed_content, repo_context
            )
            print("📊 Intelligence insights extracted")

            # Phase 6: Results Compilation
            results = await self.compile_comprehensive_results(
                repo_context,
                repository_structure,
                processed_content,
                repository_intelligence,
                project_id,
            )

            self.stats["end_time"] = time.time()
            processing_time = self.stats["end_time"] - self.stats["start_time"]
            print(f"✅ Repository crawling completed in {processing_time:.2f}s")

            return results

        except Exception as e:
            print(f"❌ Repository crawling failed: {e}")
            raise

    async def establish_repository_context(self, repo_path: str) -> dict[str, Any]:
        """Establish comprehensive repository context with git information."""
        repo_path = Path(repo_path).resolve()

        context = {
            "path": str(repo_path),
            "name": repo_path.name,
            "total_files": 0,
            "git_info": {},
            "technology_indicators": {},
        }

        # Get git information
        try:
            git_commands = {
                "remote_url": ["git", "remote", "get-url", "origin"],
                "current_branch": ["git", "branch", "--show-current"],
                "commit_hash": ["git", "rev-parse", "--short", "HEAD"],
            }

            for key, cmd in git_commands.items():
                try:
                    result = subprocess.run(
                        cmd, cwd=repo_path, capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        context["git_info"][key] = result.stdout.strip()
                except (
                    subprocess.TimeoutExpired,
                    subprocess.SubprocessError,
                    OSError,
                ) as e:
                    print(f"⚠️ Failed to get git {key}: {e}")
                    context["git_info"][key] = "unknown"

        except Exception as e:
            print(f"⚠️ Git information extraction failed: {e}")
            context["git_info"] = {"status": "not_available"}

        # Count total files
        try:
            context["total_files"] = sum(1 for _ in repo_path.rglob("*") if _.is_file())
        except (OSError, PermissionError) as e:
            print(f"⚠️ Failed to count files: {e}")
            context["total_files"] = 0

        # Detect technology stack
        context["technology_indicators"] = await self.detect_technology_stack(repo_path)

        return context

    async def detect_technology_stack(self, repo_path: Path) -> dict[str, Any]:
        """Detect technology stack and project characteristics."""
        indicators = {
            "languages": set(),
            "frameworks": set(),
            "build_tools": set(),
            "package_managers": set(),
        }

        # Check for specific files that indicate technology
        tech_files = {
            "package.json": ("javascript", "npm"),
            "requirements.txt": ("python", "pip"),
            "Pipfile": ("python", "pipenv"),
            "pyproject.toml": ("python", "poetry"),
            "pom.xml": ("java", "maven"),
            "build.gradle": ("java", "gradle"),
            "Cargo.toml": ("rust", "cargo"),
            "go.mod": ("go", "go-modules"),
            "composer.json": ("php", "composer"),
            "Gemfile": ("ruby", "bundler"),
            "Dockerfile": ("docker", "docker"),
            "docker-compose.yml": ("docker", "docker-compose"),
        }

        for file_name, (lang, tool) in tech_files.items():
            if (repo_path / file_name).exists():
                indicators["languages"].add(lang)
                indicators["package_managers"].add(tool)

        # Convert sets to lists for JSON serialization
        return {k: list(v) for k, v in indicators.items()}

    async def discover_repository_structure(self, repo_path: str) -> dict[str, Any]:
        """Discover comprehensive repository structure with intelligent categorization."""
        repo_path = Path(repo_path)
        structure = {
            "all_files": [],
            "code_files": [],
            "documentation_files": [],
            "config_files": [],
            "other_files": [],
        }

        print("🔍 Scanning repository structure...")

        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip excluded patterns
            if any(pattern in str(file_path) for pattern in self.exclude_patterns):
                continue

            # Skip large files
            try:
                if file_path.stat().st_size > self.max_file_size:
                    continue
            except (OSError, PermissionError) as e:
                print(f"⚠️ Cannot access file {file_path.name}: {e}")
                continue

            relative_path = file_path.relative_to(repo_path)
            file_info = {
                "path": file_path,
                "relative_path": str(relative_path),
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
                "extension": file_path.suffix.lower(),
                "name": file_path.name,
            }

            structure["all_files"].append(file_info)
            self.stats["files_discovered"] += 1

            # Categorize files
            if file_info["extension"] in self.supported_code_extensions:
                file_info["category"] = "code"
                file_info["language"] = self.supported_code_extensions[
                    file_info["extension"]
                ]
                structure["code_files"].append(file_info)
            elif file_info["extension"] in self.supported_doc_extensions:
                file_info["category"] = "documentation"
                structure["documentation_files"].append(file_info)
            elif file_info["extension"] in self.supported_config_extensions:
                file_info["category"] = "configuration"
                structure["config_files"].append(file_info)
            else:
                file_info["category"] = "other"
                structure["other_files"].append(file_info)

        return structure

    async def apply_intelligent_filtering(
        self, all_files: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply intelligent filtering based on quality heuristics and content relevance."""
        print("⚡ Applying intelligent filtering...")

        filtered_files = []

        for file_info in all_files:
            # Calculate intelligence scores
            quality_score = await self._calculate_file_quality_score(file_info)
            relevance_score = await self._calculate_file_relevance_score(file_info)

            # Combined intelligence score
            intelligence_score = (quality_score * 0.6) + (relevance_score * 0.4)

            # Filter threshold based on category
            thresholds = {
                "code": 0.2,
                "documentation": 0.3,
                "configuration": 0.4,
                "other": 0.6,
            }

            threshold = thresholds.get(file_info.get("category", "other"), 0.5)

            if intelligence_score >= threshold:
                file_info["intelligence_score"] = intelligence_score
                file_info["quality_score"] = quality_score
                file_info["relevance_score"] = relevance_score
                filtered_files.append(file_info)

        # Sort by intelligence score and limit to top files
        sorted_files = sorted(
            filtered_files, key=lambda x: x["intelligence_score"], reverse=True
        )
        return sorted_files[:50]  # Limit to top 50 files for testing

    async def _calculate_file_quality_score(self, file_info: dict[str, Any]) -> float:
        """Calculate file quality score based on heuristics."""
        score = 0.5  # Base score

        # Size-based scoring
        size = file_info["size"]
        if 100 < size < 10000:  # Sweet spot for most files
            score += 0.2
        elif size < 100:  # Too small
            score -= 0.1
        elif size > 100000:  # Very large
            score -= 0.2

        # Name-based scoring
        name = file_info["name"].lower()
        if any(term in name for term in ["test", "spec", "readme", "docs"]):
            score += 0.2
        if any(term in name for term in ["temp", "tmp", "backup", "old"]):
            score -= 0.3

        # Extension-based scoring
        if file_info.get("category") == "code":
            score += 0.1
        elif file_info.get("category") == "documentation":
            score += 0.2

        return max(0.0, min(1.0, score))

    async def _calculate_file_relevance_score(self, file_info: dict[str, Any]) -> float:
        """Calculate file relevance score based on location and naming patterns."""
        score = 0.5  # Base score

        path = str(file_info["relative_path"]).lower()

        # High-value directories
        if any(term in path for term in ["src", "lib", "app", "main", "core"]):
            score += 0.2
        if any(term in path for term in ["docs", "documentation", "readme"]):
            score += 0.3
        if any(term in path for term in ["config", "settings", "conf"]):
            score += 0.1

        # Low-value directories
        if any(term in path for term in ["node_modules", "vendor", "third_party"]):
            score -= 0.4
        if any(term in path for term in ["test", "tests", "__tests__"]):
            score += 0.1  # Tests are valuable but not highest priority

        return max(0.0, min(1.0, score))

    async def process_files_with_intelligence(
        self, filtered_files: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process files with intelligence service integration."""
        print("🧠 Processing files with intelligence integration...")

        processed_content = []

        for file_info in filtered_files[:20]:  # Process top 20 files for testing
            try:
                result = await self._process_file_with_intelligence(file_info)
                if result:
                    processed_content.append(result)
                    self.stats["files_processed"] += 1
            except Exception as e:
                print(f"⚠️ Error processing {file_info['relative_path']}: {e}")
                self.stats["processing_errors"] += 1

        return processed_content

    async def _process_file_with_intelligence(
        self, file_info: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Process individual file with intelligence service integration."""
        try:
            # Read file content
            content = file_info["path"].read_text(encoding="utf-8", errors="ignore")

            # Truncate very large content for processing
            if len(content) > 10000:
                content = content[:10000] + "\n... [truncated for processing]"

            # Base processed item
            processed_item = {
                "file_path": str(file_info["path"]),
                "relative_path": file_info["relative_path"],
                "file_type": file_info.get("category", "other"),
                "language": file_info.get("language"),
                "content": content,
                "title": file_info["name"],
                "size": len(content),
                "modified": file_info["modified"],
                "intelligence_score": file_info["intelligence_score"],
                "metadata": {
                    "quality_score": file_info["quality_score"],
                    "relevance_score": file_info["relevance_score"],
                    "file_category": file_info.get("category", "other"),
                },
            }

            # Apply intelligence service processing based on file type
            if file_info.get("category") == "code":
                intelligence_result = await self._apply_code_intelligence(
                    processed_item
                )
            elif file_info.get("category") == "documentation":
                intelligence_result = await self._apply_document_intelligence(
                    processed_item
                )
            else:
                intelligence_result = await self._apply_generic_intelligence(
                    processed_item
                )

            # Merge intelligence results
            if intelligence_result:
                processed_item["intelligence_analysis"] = intelligence_result
                self.stats["intelligence_assessments"] += 1

            return processed_item

        except Exception as e:
            print(f"⚠️ Failed to process {file_info['relative_path']}: {e}")
            return None

    async def _apply_code_intelligence(
        self, processed_item: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Apply intelligence service analysis to code files."""
        if self.dry_run:
            # Return mock intelligence analysis for dry run
            return {
                "type": "code_analysis",
                "quality_assessment": {
                    "mock_analysis": True,
                    "language": processed_item.get("language", "unknown"),
                    "complexity_score": 0.7,
                    "quality_score": 0.8,
                },
                "analysis_timestamp": datetime.now(UTC).isoformat(),
                "service_used": "dry_run_mock",
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Code quality assessment
                quality_payload = {
                    "content": processed_item["content"],
                    "source_path": processed_item["relative_path"],
                    "language": processed_item.get("language", "python"),
                }

                if self.verbose:
                    print(f"🔍 Analyzing code file: {processed_item['relative_path']}")

                response = await client.post(
                    f"{self.intelligence_service_url}/extract/code",
                    json=quality_payload,
                )

                if response.status_code == 200:
                    quality_result = response.json()
                    return {
                        "type": "code_analysis",
                        "quality_assessment": quality_result,
                        "analysis_timestamp": datetime.now(UTC).isoformat(),
                        "service_used": "intelligence_service",
                    }
                else:
                    if self.verbose:
                        print(
                            f"⚠️ Intelligence service returned {response.status_code} for code analysis"
                        )

        except Exception as e:
            if self.verbose:
                print(
                    f"⚠️ Code intelligence failed for {processed_item['relative_path']}: {e}"
                )

        return None

    async def _apply_document_intelligence(
        self, processed_item: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Apply intelligence service analysis to documentation files."""
        if self.dry_run:
            # Return mock intelligence analysis for dry run
            return {
                "type": "document_analysis",
                "entity_extraction": {
                    "mock_analysis": True,
                    "entities_found": 3,
                    "document_type": "documentation",
                    "quality_score": 0.75,
                },
                "analysis_timestamp": datetime.now(UTC).isoformat(),
                "service_used": "dry_run_mock",
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Document processing
                doc_payload = {
                    "content": processed_item["content"],
                    "source_path": processed_item["relative_path"],
                    "metadata": processed_item.get("metadata", {}),
                    "store_entities": False,  # Don't store for testing
                    "trigger_freshness_analysis": False,
                }

                if self.verbose:
                    print(f"📄 Analyzing document: {processed_item['relative_path']}")

                response = await client.post(
                    f"{self.intelligence_service_url}/extract/document",
                    json=doc_payload,
                )

                if response.status_code == 200:
                    doc_result = response.json()
                    return {
                        "type": "document_analysis",
                        "entity_extraction": doc_result,
                        "analysis_timestamp": datetime.now(UTC).isoformat(),
                        "service_used": "intelligence_service",
                    }
                else:
                    if self.verbose:
                        print(
                            f"⚠️ Intelligence service returned {response.status_code} for document analysis"
                        )

        except Exception as e:
            if self.verbose:
                print(
                    f"⚠️ Document intelligence failed for {processed_item['relative_path']}: {e}"
                )

        return None

    async def _apply_generic_intelligence(
        self, processed_item: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Apply basic intelligence analysis to other file types."""
        # Simple heuristic-based analysis
        content = processed_item["content"]

        analysis = {
            "type": "generic_analysis",
            "content_stats": {
                "char_count": len(content),
                "line_count": content.count("\n") + 1,
                "word_count": len(content.split()),
                "complexity_estimate": min(1.0, len(content.split()) / 1000),
            },
            "content_indicators": {
                "has_urls": "http" in content.lower(),
                "has_code_blocks": "```" in content or "    " in content,
                "has_structured_data": any(char in content for char in ["{", "[", "<"]),
                "language_indicators": [],
            },
            "analysis_timestamp": datetime.now(UTC).isoformat(),
            "service_used": "local_heuristics",
        }

        return analysis

    async def extract_repository_intelligence(
        self, processed_content: list[dict[str, Any]], repo_context: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract comprehensive repository-level intelligence."""
        print("📊 Extracting repository-level intelligence...")

        intelligence = {
            "quality_assessments": [],
            "technology_analysis": {},
            "documentation_coverage": {},
            "repository_health": {},
        }

        # Aggregate quality assessments
        code_files = [
            item for item in processed_content if item.get("file_type") == "code"
        ]
        for code_file in code_files:
            intelligence_analysis = code_file.get("intelligence_analysis", {})
            if intelligence_analysis.get("type") == "code_analysis":
                quality_data = intelligence_analysis.get("quality_assessment", {})
                intelligence["quality_assessments"].append(
                    {"file": code_file["relative_path"], "quality_data": quality_data}
                )

        # Technology stack analysis
        languages = set()
        for item in processed_content:
            if item.get("language"):
                languages.add(item["language"])

        intelligence["technology_analysis"] = {
            "primary_languages": list(languages),
            "technology_diversity": len(languages),
            "repository_type": self._classify_repository_type(
                processed_content, repo_context
            ),
        }

        # Documentation coverage analysis
        doc_files = [
            item
            for item in processed_content
            if item.get("file_type") == "documentation"
        ]
        intelligence["documentation_coverage"] = {
            "total_docs": len(doc_files),
            "docs_to_code_ratio": len(doc_files) / max(len(code_files), 1),
            "documentation_quality": sum(
                item.get("intelligence_score", 0) for item in doc_files
            )
            / max(len(doc_files), 1),
        }

        # Repository health assessment
        intelligence["repository_health"] = {
            "processing_success_rate": self.stats["files_processed"]
            / max(self.stats["files_discovered"], 1),
            "intelligence_coverage": self.stats["intelligence_assessments"]
            / max(self.stats["files_processed"], 1),
            "content_quality_average": sum(
                item.get("intelligence_score", 0) for item in processed_content
            )
            / max(len(processed_content), 1),
            "error_rate": self.stats["processing_errors"]
            / max(self.stats["files_discovered"], 1),
        }

        return intelligence

    def _classify_repository_type(
        self, processed_content: list[dict[str, Any]], repo_context: dict[str, Any]
    ) -> str:
        """Classify repository type based on content analysis."""
        languages = [
            item.get("language") for item in processed_content if item.get("language")
        ]

        if not languages:
            return "documentation"

        language_counts = {}
        for lang in languages:
            language_counts[lang] = language_counts.get(lang, 0) + 1

        primary_language = max(language_counts, key=language_counts.get)

        # Classify based on primary language
        if primary_language == "python":
            return "python_project"
        elif primary_language in ["javascript", "typescript"]:
            return "javascript_project"
        elif primary_language == "java":
            return "java_project"
        elif len(language_counts) > 3:
            return "multi_language_project"
        else:
            return f"{primary_language}_project"

    async def compile_comprehensive_results(
        self,
        repo_context: dict[str, Any],
        repository_structure: dict[str, Any],
        processed_content: list[dict[str, Any]],
        repository_intelligence: dict[str, Any],
    ) -> dict[str, Any]:
        """Compile comprehensive crawling results."""
        end_time = time.time()
        self.stats["end_time"] = end_time
        processing_time = self.stats["end_time"] - self.stats["start_time"]

        results = {
            "crawling_summary": {
                "repository_name": repo_context["name"],
                "repository_path": repo_context["path"],
                "processing_time_seconds": processing_time,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "statistics": {
                "files_discovered": self.stats["files_discovered"],
                "files_processed": self.stats["files_processed"],
                "intelligence_assessments": self.stats["intelligence_assessments"],
                "processing_errors": self.stats["processing_errors"],
                "processing_success_rate": self.stats["files_processed"]
                / max(self.stats["files_discovered"], 1),
                "intelligence_coverage": self.stats["intelligence_assessments"]
                / max(self.stats["files_processed"], 1),
            },
            "repository_context": repo_context,
            "file_distribution": {
                "code_files": len(repository_structure["code_files"]),
                "documentation_files": len(repository_structure["documentation_files"]),
                "config_files": len(repository_structure["config_files"]),
                "other_files": len(repository_structure["other_files"]),
            },
            "intelligence_insights": repository_intelligence,
            "performance_metrics": {
                "files_per_second": (
                    self.stats["files_processed"] / processing_time
                    if processing_time > 0
                    else 0
                ),
                "average_file_processing_time": processing_time
                / max(self.stats["files_processed"], 1),
                "intelligence_processing_ratio": self.stats["intelligence_assessments"]
                / max(self.stats["files_processed"], 1),
            },
            "sample_processed_files": [
                {
                    "path": item["relative_path"],
                    "type": item["file_type"],
                    "intelligence_score": item["intelligence_score"],
                    "has_intelligence_analysis": bool(
                        item.get("intelligence_analysis")
                    ),
                }
                for item in processed_content[:10]  # Show first 10 as sample
            ],
        }

        return results


# Main execution for testing
async def main():
    """Main function for testing the repository crawler."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Repository Crawler for Intelligence Services"
    )
    parser.add_argument(
        "--repo-path",
        "-r",
        default=".",
        help="Path to repository to crawl (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without calling intelligence services",
    )
    parser.add_argument("--project-id", "-p", help="Archon project ID for integration")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    print(f"Testing repository crawler on: {args.repo_path}")

    crawler = IntelligentRepositoryCrawler()

    # Configure crawler based on arguments
    if args.dry_run:
        # For dry run, we'll mock the intelligence service calls
        crawler.dry_run = True

    if args.verbose:
        crawler.verbose = True

    try:
        results = await crawler.crawl_repository_comprehensive(
            args.repo_path, project_id=args.project_id
        )

        # Print summary
        print("\n" + "=" * 60)
        print("🎉 REPOSITORY CRAWLING COMPLETE")
        print("=" * 60)
        print(f"📁 Repository: {results['crawling_summary']['repository_name']}")
        print(
            f"⏱️ Processing Time: {results['crawling_summary']['processing_time_seconds']:.2f}s"
        )
        print(f"📊 Files Discovered: {results['statistics']['files_discovered']}")
        print(f"✅ Files Processed: {results['statistics']['files_processed']}")
        print(
            f"🧠 Intelligence Assessments: {results['statistics']['intelligence_assessments']}"
        )
        print(
            f"📈 Success Rate: {results['statistics']['processing_success_rate']:.1%}"
        )
        print(
            f"🔍 Intelligence Coverage: {results['statistics']['intelligence_coverage']:.1%}"
        )

        # Show technology analysis
        tech_analysis = results["intelligence_insights"]["technology_analysis"]
        print(f"💻 Repository Type: {tech_analysis['repository_type']}")
        print(
            f"📝 Primary Languages: {', '.join(tech_analysis['primary_languages']) or 'None detected'}"
        )

        # Save detailed results
        results_file = Path("repository_crawl_results.json")
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"📄 Detailed results saved to: {results_file}")

        return results

    except Exception as e:
        print(f"❌ Error during crawling: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(main())
