"""
Document Freshness Monitor for Archon Intelligence Service

Core monitoring engine for document freshness analysis, dependency tracking,
and intelligent staleness detection with comprehensive document classification.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    Dependency,
    DependencyType,
    DocumentClassification,
    DocumentFreshness,
    DocumentType,
    FreshnessAnalysis,
    FreshnessLevel,
    RefreshPriority,
    RefreshStrategy,
)
from .scoring import FreshnessScorer

logger = logging.getLogger(__name__)


class DocumentFreshnessMonitor:
    """
    Comprehensive document freshness monitoring with intelligent
    dependency tracking and classification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize document freshness monitor"""

        # Default configuration
        self.config = {
            # Analysis settings
            "max_file_size_mb": 50,  # Skip files larger than this
            "supported_extensions": [  # File extensions to analyze
                ".md",
                ".rst",
                ".txt",
                ".adoc",
                ".tex",  # Documentation
                ".py",
                ".js",
                ".ts",
                ".java",
                ".cpp",
                ".c",
                ".go",
                ".rs",  # Code
                ".json",
                ".yaml",
                ".yml",
                ".toml",
                ".ini",
                ".cfg",  # Config
                ".html",
                ".htm",
                ".xml",  # Markup
            ],
            "exclude_patterns": [  # Patterns to exclude
                "*/node_modules/*",
                "*/.git/*",
                "*/.venv/*",
                "*/venv/*",
                "*/__pycache__/*",
                "*/dist/*",
                "*/build/*",
                "*/.cache/*",
            ],
            # Document classification
            "classification_patterns": {
                DocumentType.README: [
                    r"^readme\.md$",
                    r"^readme\.txt$",
                    r"^readme\.rst$",
                    r"^readme$",
                ],
                DocumentType.API_DOCUMENTATION: [
                    r"api",
                    r"reference",
                    r"endpoints",
                    r"swagger",
                    r"openapi",
                ],
                DocumentType.TUTORIAL: [
                    r"tutorial",
                    r"guide",
                    r"walkthrough",
                    r"getting-started",
                    r"quickstart",
                    r"examples",
                ],
                DocumentType.CHANGELOG: [
                    r"changelog",
                    r"changes",
                    r"history",
                    r"releases",
                    r"news",
                ],
                DocumentType.CONFIGURATION: [
                    r"config",
                    r"settings",
                    r"environment",
                    r"\.env",
                    r"\.json$",
                    r"\.yaml$",
                    r"\.yml$",
                    r"\.toml$",
                    r"\.ini$",
                ],
                DocumentType.TROUBLESHOOTING: [
                    r"troubleshoot",
                    r"debug",
                    r"issues",
                    r"problems",
                    r"faq",
                ],
                DocumentType.ARCHITECTURE: [
                    r"architecture",
                    r"design",
                    r"spec",
                    r"specification",
                ],
            },
            # Dependency detection patterns
            "dependency_patterns": {
                DependencyType.FILE_REFERENCE: [
                    r"\[([^\]]+)\]\(([^)]+\.(md|rst|txt|py|js|json|yaml|yml))\)",  # Markdown links
                    r"!\[([^\]]*)\]\(([^)]+\.(png|jpg|jpeg|gif|svg|pdf))\)",  # Images
                    r'```[a-z]*\n.*?include\s+["\']([^"\']+)["\']',  # Include statements
                    r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",  # Python imports
                ],
                DependencyType.LINK_REFERENCE: [
                    r"\[([^\]]+)\]\((https?://[^)]+)\)",  # External links
                    r"<(https?://[^>]+)>",  # Angle bracket links
                    r"https?://[^\s\)]+",  # Plain URLs
                ],
                DependencyType.CONFIG_REFERENCE: [
                    r"config[.\[]([^}\]]+)",  # Config references
                    r"env[.\[]([^}\]]+)",  # Environment variables
                    r"\$\{([^}]+)\}",  # Variable substitution
                ],
                DependencyType.CODE_IMPORT: [
                    r"(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)",  # Python
                    r'(?:import|require)\s*\(?["\']([^"\']+)["\']',  # JavaScript/Node
                    r'#include\s*[<"]([^>"]+)[>"]',  # C/C++
                ],
            },
            # Batch processing settings
            "batch_size": 10,  # Files to process in parallel
            "timeout_seconds": 300,  # Total analysis timeout
            "file_timeout_seconds": 30,  # Per-file timeout
            # Freshness scoring
            "scorer_config": None,  # Will use FreshnessScorer defaults
        }

        # Update with provided config
        if config:
            self._update_config(config)

        # Initialize components
        self.scorer = FreshnessScorer(self.config.get("scorer_config"))

        # Compile regex patterns for efficiency
        self._compiled_patterns = {}
        self._compile_dependency_patterns()
        self._compile_classification_patterns()

        # Analysis state
        self._analysis_cache = {}
        self._dependency_graph = {}

        logger.info("DocumentFreshnessMonitor initialized")

    def _update_config(self, new_config: Dict[str, Any]):
        """Recursively update configuration"""

        def update_dict(base: dict, updates: dict):
            for key, value in updates.items():
                if (
                    key in base
                    and isinstance(base[key], dict)
                    and isinstance(value, dict)
                ):
                    update_dict(base[key], value)
                else:
                    base[key] = value

        update_dict(self.config, new_config)

    def _compile_dependency_patterns(self):
        """Compile dependency detection regex patterns"""
        self._compiled_patterns["dependencies"] = {}

        for dep_type, patterns in self.config["dependency_patterns"].items():
            compiled_patterns = []
            for pattern in patterns:
                try:
                    compiled_patterns.append(
                        re.compile(pattern, re.MULTILINE | re.IGNORECASE)
                    )
                except re.error as e:
                    logger.warning(f"Invalid dependency pattern '{pattern}': {e}")

            self._compiled_patterns["dependencies"][dep_type] = compiled_patterns

    def _compile_classification_patterns(self):
        """Compile document classification regex patterns"""
        self._compiled_patterns["classification"] = {}

        for doc_type, patterns in self.config["classification_patterns"].items():
            compiled_patterns = []
            for pattern in patterns:
                try:
                    compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error as e:
                    logger.warning(f"Invalid classification pattern '{pattern}': {e}")

            self._compiled_patterns["classification"][doc_type] = compiled_patterns

    async def analyze_document(
        self,
        file_path: str,
        content: Optional[str] = None,
        include_dependencies: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentFreshness:
        """
        Analyze a single document for freshness and dependencies.

        Args:
            file_path: Path to the document
            content: Document content (will read from file if None)
            include_dependencies: Whether to analyze dependencies
            metadata: Additional metadata (access patterns, etc.)

        Returns:
            Complete document freshness analysis
        """
        start_time = datetime.now(timezone.utc)
        path_obj = Path(file_path)

        try:
            # Check if file exists and is readable
            if not path_obj.exists():
                raise FileNotFoundError(f"Document not found: {file_path}")

            if not path_obj.is_file():
                raise ValueError(f"Path is not a file: {file_path}")

            # Get file metadata
            stat = path_obj.stat()
            file_size = stat.st_size
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            created_at = datetime.fromtimestamp(stat.st_ctime)

            # Check file size limit
            max_size_bytes = self.config["max_file_size_mb"] * 1024 * 1024
            if file_size > max_size_bytes:
                logger.warning(
                    f"Skipping large file: {file_path} ({file_size / 1024 / 1024:.1f}MB)"
                )
                raise ValueError(f"File too large: {file_size} bytes")

            # Read content if not provided
            if content is None:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Try with different encoding
                    with open(file_path, "r", encoding="latin-1", errors="ignore") as f:
                        content = f.read()

            # Generate document ID
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
            document_id = f"doc_{content_hash}_{int(last_modified.timestamp())}"

            # Classify document
            classification = await self._classify_document(file_path, content)

            # Find dependencies
            dependencies = []
            if include_dependencies:
                dependencies = await self._find_dependencies(file_path, content)

            # Calculate freshness score
            freshness_score = await self.scorer.calculate_freshness_score(
                document_path=file_path,
                content=content,
                last_modified=last_modified,
                dependencies=dependencies,
                document_type=classification.document_type,
                metadata=metadata,
            )

            # Determine freshness level
            freshness_level = self.scorer.determine_freshness_level(
                freshness_score.overall_score
            )

            # Count dependency stats
            critical_deps = len([d for d in dependencies if d.is_critical])
            broken_deps = len(
                [d for d in dependencies if d.verification_status == "broken"]
            )

            # Determine refresh needs
            needs_refresh = freshness_level in [
                FreshnessLevel.STALE,
                FreshnessLevel.OUTDATED,
                FreshnessLevel.CRITICAL,
            ]
            refresh_priority = self._determine_refresh_priority(
                freshness_level, classification.document_type
            )

            # Estimate refresh effort
            refresh_effort = self._estimate_refresh_effort(
                classification.document_type, len(dependencies), broken_deps
            )

            # Create document freshness object
            document_freshness = DocumentFreshness(
                document_id=document_id,
                file_path=file_path,
                file_size_bytes=file_size,
                last_modified=last_modified,
                created_at=created_at,
                classification=classification,
                freshness_score=freshness_score,
                freshness_level=freshness_level,
                dependencies=dependencies,
                critical_dependencies_count=critical_deps,
                broken_dependencies_count=broken_deps,
                needs_refresh=needs_refresh,
                refresh_priority=refresh_priority,
                estimated_refresh_effort_minutes=refresh_effort,
                analyzer_metadata={
                    "analysis_time_ms": (
                        datetime.now(timezone.utc) - start_time
                    ).total_seconds()
                    * 1000,
                    "content_length": len(content),
                    "file_extension": path_obj.suffix,
                },
            )

            # Cache the result
            self._analysis_cache[file_path] = document_freshness

            logger.debug(
                f"Analyzed {file_path}: {freshness_level.value} ({freshness_score.overall_score:.2f})"
            )

            return document_freshness

        except Exception as e:
            logger.error(f"Failed to analyze document {file_path}: {e}")
            raise

    async def analyze_directory(
        self,
        directory_path: str,
        recursive: bool = True,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        max_files: Optional[int] = None,
    ) -> FreshnessAnalysis:
        """
        Analyze all documents in a directory for freshness.

        Args:
            directory_path: Path to directory to analyze
            recursive: Whether to analyze subdirectories
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude
            max_files: Maximum number of files to analyze

        Returns:
            Complete freshness analysis with statistics
        """
        start_time = datetime.now(timezone.utc)
        directory = Path(directory_path)

        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Invalid directory: {directory_path}")

        logger.info(f"Starting directory analysis: {directory_path}")

        # Find files to analyze
        files_to_analyze = await self._find_files_to_analyze(
            directory, recursive, include_patterns, exclude_patterns, max_files
        )

        logger.info(f"Found {len(files_to_analyze)} files to analyze")

        # Initialize analysis result
        analysis_id = f"analysis_{int(start_time.timestamp())}_{hashlib.md5(directory_path.encode()).hexdigest()[:8]}"

        analysis = FreshnessAnalysis(
            analysis_id=analysis_id,
            analyzed_at=start_time,
            base_path=directory_path,
            total_documents=len(files_to_analyze),
            analyzed_documents=0,
            skipped_documents=0,
        )

        # Process files in batches
        batch_size = self.config["batch_size"]
        documents = []
        errors = []

        for i in range(0, len(files_to_analyze), batch_size):
            batch = files_to_analyze[i : i + batch_size]
            batch_results = await self._process_batch(batch)

            for result in batch_results:
                if isinstance(result, DocumentFreshness):
                    documents.append(result)
                    analysis.analyzed_documents += 1
                else:
                    # Error occurred
                    analysis.skipped_documents += 1
                    errors.append(str(result))

        # Calculate statistics
        analysis.documents = documents

        if documents:
            # Freshness distribution
            freshness_counts = {}
            for doc in documents:
                level = doc.freshness_level.value
                freshness_counts[level] = freshness_counts.get(level, 0) + 1

            analysis.freshness_distribution = freshness_counts

            # Statistics
            scores = [doc.freshness_score.overall_score for doc in documents]
            analysis.average_freshness_score = sum(scores) / len(scores)

            analysis.stale_documents_count = len([d for d in documents if d.is_stale])
            analysis.critical_documents_count = len(
                [d for d in documents if d.is_critical]
            )

            analysis.total_dependencies = sum(
                len(doc.dependencies) for doc in documents
            )
            analysis.broken_dependencies = sum(
                doc.broken_dependencies_count for doc in documents
            )

        # Generate refresh strategies
        analysis.refresh_strategies = await self._generate_refresh_strategies(documents)

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)
        analysis.priority_actions = self._generate_priority_actions(analysis)

        # Performance metadata
        end_time = datetime.now(timezone.utc)
        analysis.analysis_time_seconds = (end_time - start_time).total_seconds()
        analysis.error_count = len(errors)
        analysis.warnings = errors[:10]  # Limit warnings

        logger.info(
            f"Analysis complete: {analysis.analyzed_documents} docs, "
            f"{analysis.stale_documents_count} stale, "
            f"avg score {analysis.average_freshness_score:.2f}"
        )

        return analysis

    async def _find_files_to_analyze(
        self,
        directory: Path,
        recursive: bool,
        include_patterns: Optional[List[str]],
        exclude_patterns: Optional[List[str]],
        max_files: Optional[int],
    ) -> List[str]:
        """Find files that should be analyzed"""

        # Combine exclude patterns
        all_exclude_patterns = self.config["exclude_patterns"].copy()
        if exclude_patterns:
            all_exclude_patterns.extend(exclude_patterns)

        # Use supported extensions if no include patterns provided
        if not include_patterns:
            include_patterns = [
                f"*{ext}" for ext in self.config["supported_extensions"]
            ]

        files = []

        # Find files
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue

            file_str = str(file_path)

            # Check exclude patterns
            excluded = False
            for exclude_pattern in all_exclude_patterns:
                if Path(file_str).match(exclude_pattern):
                    excluded = True
                    break

            if excluded:
                continue

            # Check include patterns
            included = False
            for include_pattern in include_patterns:
                if Path(file_path.name).match(include_pattern):
                    included = True
                    break

            if not included:
                continue

            # Check file size
            try:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                if size_mb > self.config["max_file_size_mb"]:
                    continue
            except OSError:
                continue

            files.append(file_str)

            # Respect max_files limit
            if max_files and len(files) >= max_files:
                break

        return files

    async def _process_batch(self, file_paths: List[str]) -> List[Any]:
        """Process a batch of files concurrently"""

        async def analyze_with_timeout(file_path: str):
            try:
                return await asyncio.wait_for(
                    self.analyze_document(file_path),
                    timeout=self.config["file_timeout_seconds"],
                )
            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                return e

        # Process files concurrently
        tasks = [analyze_with_timeout(fp) for fp in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def _classify_document(
        self, file_path: str, content: str
    ) -> DocumentClassification:
        """Classify document type based on path and content"""
        path_obj = Path(file_path)
        filename = path_obj.name.lower()

        # Check classification patterns
        best_type = DocumentType.UNKNOWN
        best_confidence = 0.0

        for doc_type, patterns in self._compiled_patterns["classification"].items():
            confidence = 0.0

            # Check filename patterns
            for pattern in patterns:
                if pattern.search(filename):
                    confidence += 0.6
                    break

            # Check content patterns (if we have specific content indicators)
            content_lower = content.lower()

            if doc_type == DocumentType.API_DOCUMENTATION:
                if any(
                    word in content_lower
                    for word in ["endpoint", "api", "rest", "graphql", "swagger"]
                ):
                    confidence += 0.3
            elif doc_type == DocumentType.TUTORIAL:
                if any(
                    word in content_lower
                    for word in ["step", "tutorial", "guide", "example"]
                ):
                    confidence += 0.3
            elif doc_type == DocumentType.TROUBLESHOOTING:
                if any(
                    word in content_lower
                    for word in ["error", "issue", "problem", "debug", "troubleshoot"]
                ):
                    confidence += 0.3

            if confidence > best_confidence:
                best_confidence = confidence
                best_type = doc_type

        # Analyze additional document properties
        has_code_examples = bool(re.search(r"```|<code>", content))
        has_images = bool(re.search(r"!\[.*?\]\(.*?\)|<img", content))
        has_links = bool(re.search(r"\[.*?\]\(https?://.*?\)", content))

        # Estimate reading time (average 200 words per minute)
        word_count = len(content.split())
        reading_time = max(1, word_count // 200)

        # Detect programming language or framework
        language = None
        framework = None

        if path_obj.suffix in [".py"]:
            language = "python"
        elif path_obj.suffix in [".js", ".ts"]:
            language = "javascript"
        elif path_obj.suffix in [".java"]:
            language = "java"

        # Framework detection (basic)
        content_lower = content.lower()
        if "react" in content_lower or "jsx" in content_lower:
            framework = "react"
        elif "vue" in content_lower:
            framework = "vue"
        elif "django" in content_lower:
            framework = "django"
        elif "fastapi" in content_lower:
            framework = "fastapi"

        return DocumentClassification(
            document_type=best_type,
            confidence=min(1.0, best_confidence),
            language=language,
            framework=framework,
            has_code_examples=has_code_examples,
            has_images=has_images,
            has_links=has_links,
            estimated_reading_time_minutes=reading_time,
            word_count=word_count,
        )

    async def _find_dependencies(
        self, file_path: str, content: str
    ) -> List[Dependency]:
        """Find all dependencies in document content"""
        dependencies = []
        base_path = Path(file_path).parent

        for dep_type, patterns in self._compiled_patterns["dependencies"].items():
            for pattern in patterns:
                matches = pattern.finditer(content)

                for match in matches:
                    # Extract dependency information
                    target_path = None
                    context = None
                    line_number = None

                    if match.groups():
                        target_path = (
                            match.group(1)
                            if len(match.groups()) >= 1
                            else match.group(0)
                        )
                        if len(match.groups()) >= 2:
                            # For markdown-style links, second group is the path
                            target_path = match.group(2)
                    else:
                        target_path = match.group(0)

                    if not target_path:
                        continue

                    # Calculate line number
                    line_number = content[: match.start()].count("\\n") + 1

                    # Get context (surrounding text)
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end].replace("\\n", " ").strip()

                    # Determine if dependency is critical
                    is_critical = self._is_critical_dependency(
                        dep_type, target_path, context
                    )

                    # Generate dependency ID
                    dep_id = hashlib.md5(
                        f"{file_path}:{target_path}:{line_number}".encode()
                    ).hexdigest()[:16]

                    # Resolve relative paths
                    resolved_path = self._resolve_dependency_path(
                        base_path, target_path, dep_type
                    )

                    dependency = Dependency(
                        dependency_id=dep_id,
                        source_path=file_path,
                        target_path=resolved_path,
                        dependency_type=dep_type,
                        line_number=line_number,
                        context=context,
                        is_critical=is_critical,
                        verification_status="unverified",  # Will be verified separately
                    )

                    dependencies.append(dependency)

        # Remove duplicates
        seen = set()
        unique_dependencies = []
        for dep in dependencies:
            key = (dep.target_path, dep.dependency_type)
            if key not in seen:
                seen.add(key)
                unique_dependencies.append(dep)

        return unique_dependencies

    def _is_critical_dependency(
        self, dep_type: DependencyType, target_path: str, context: str
    ) -> bool:
        """Determine if a dependency is critical"""
        # Configuration files are usually critical
        if dep_type == DependencyType.CONFIG_REFERENCE:
            return True

        # Code imports are critical
        if dep_type == DependencyType.CODE_IMPORT:
            return True

        # READMEs and main documentation are critical
        if "readme" in target_path.lower() or "index" in target_path.lower():
            return True

        # Links in navigation or main sections are critical
        if any(
            word in context.lower()
            for word in ["navigation", "menu", "toc", "table of contents"]
        ):
            return True

        return False

    def _resolve_dependency_path(
        self, base_path: Path, target_path: str, dep_type: DependencyType
    ) -> str:
        """Resolve dependency path to absolute or normalized form"""

        # Handle URLs - return as-is
        if target_path.startswith(("http://", "https://")):
            return target_path

        # Handle absolute paths
        if target_path.startswith("/"):
            return target_path

        # Handle relative paths
        try:
            resolved = (base_path / target_path).resolve()
            return str(resolved)
        except Exception:
            # If resolution fails, return the original path
            return target_path

    def _determine_refresh_priority(
        self, freshness_level: FreshnessLevel, doc_type: DocumentType
    ) -> RefreshPriority:
        """Determine refresh priority based on freshness and document type"""

        # Critical staleness always gets high priority
        if freshness_level == FreshnessLevel.CRITICAL:
            return RefreshPriority.CRITICAL

        # Important document types get higher priority
        high_priority_types = [
            DocumentType.README,
            DocumentType.API_DOCUMENTATION,
            DocumentType.CONFIGURATION,
        ]
        medium_priority_types = [
            DocumentType.TUTORIAL,
            DocumentType.GUIDE,
            DocumentType.TROUBLESHOOTING,
        ]

        if freshness_level == FreshnessLevel.OUTDATED:
            if doc_type in high_priority_types:
                return RefreshPriority.HIGH
            elif doc_type in medium_priority_types:
                return RefreshPriority.MEDIUM
            else:
                return RefreshPriority.LOW

        if freshness_level == FreshnessLevel.STALE:
            if doc_type in high_priority_types:
                return RefreshPriority.MEDIUM
            else:
                return RefreshPriority.LOW

        return RefreshPriority.LOW

    def _estimate_refresh_effort(
        self, doc_type: DocumentType, dep_count: int, broken_deps: int
    ) -> int:
        """Estimate refresh effort in minutes"""

        # Base effort by document type
        base_effort = {
            DocumentType.README: 30,
            DocumentType.API_DOCUMENTATION: 60,
            DocumentType.TUTORIAL: 45,
            DocumentType.GUIDE: 40,
            DocumentType.CONFIGURATION: 20,
            DocumentType.TROUBLESHOOTING: 35,
            DocumentType.ARCHITECTURE: 90,
            DocumentType.CHANGELOG: 15,
            DocumentType.UNKNOWN: 25,
        }.get(doc_type, 25)

        # Add time for dependencies
        dependency_effort = dep_count * 5  # 5 minutes per dependency
        broken_dependency_effort = broken_deps * 10  # 10 minutes per broken dependency

        total_effort = base_effort + dependency_effort + broken_dependency_effort

        return min(240, total_effort)  # Cap at 4 hours

    async def _generate_refresh_strategies(
        self, documents: List[DocumentFreshness]
    ) -> List[RefreshStrategy]:
        """Generate refresh strategies for stale documents"""
        strategies = []

        # Group documents by staleness level and type
        stale_docs = [doc for doc in documents if doc.is_stale]

        for doc in stale_docs:
            strategy_id = f"refresh_{doc.document_id}_{int(datetime.now(timezone.utc).timestamp())}"

            # Determine refresh actions
            actions = []

            if doc.freshness_level == FreshnessLevel.CRITICAL:
                actions.extend(
                    [
                        "Urgent review required - document may contain incorrect information",
                        "Verify all links and references",
                        "Update content to reflect current state",
                        "Check for deprecated information",
                    ]
                )
            elif doc.freshness_level == FreshnessLevel.OUTDATED:
                actions.extend(
                    [
                        "Review document content for accuracy",
                        "Update outdated references",
                        "Verify dependency links",
                    ]
                )
            else:  # STALE
                actions.extend(
                    [
                        "Review document for minor updates",
                        "Check recent changes for relevance",
                    ]
                )

            # Add dependency-specific actions
            if doc.broken_dependencies_count > 0:
                actions.append(
                    f"Fix {doc.broken_dependencies_count} broken dependencies"
                )

            # Determine automation potential
            can_automate = (
                doc.classification.document_type
                in [DocumentType.CHANGELOG, DocumentType.CONFIGURATION]
                and doc.broken_dependencies_count == 0
            )

            automation_confidence = 0.8 if can_automate else 0.2

            strategy = RefreshStrategy(
                strategy_id=strategy_id,
                document_path=doc.file_path,
                refresh_type=f"{doc.freshness_level.value}_refresh",
                priority=doc.refresh_priority,
                estimated_effort_minutes=doc.estimated_refresh_effort_minutes or 30,
                risk_level=(
                    "low" if doc.freshness_level == FreshnessLevel.STALE else "medium"
                ),
                actions=actions,
                dependencies_to_update=[
                    dep.target_path
                    for dep in doc.dependencies
                    if dep.verification_status == "broken"
                ],
                validation_steps=[
                    "Review updated content",
                    "Test all links and references",
                    "Verify technical accuracy",
                ],
                can_automate=can_automate,
                automation_confidence=automation_confidence,
                manual_review_required=not can_automate
                or doc.freshness_level == FreshnessLevel.CRITICAL,
            )

            strategies.append(strategy)

        # Sort by priority and effort
        strategies.sort(
            key=lambda s: (
                {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}[s.priority.value],
                -s.estimated_effort_minutes,  # Higher effort first within same priority
            ),
            reverse=True,
        )

        return strategies

    def _generate_recommendations(self, analysis: FreshnessAnalysis) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []

        if analysis.analyzed_documents == 0:
            return ["No documents found to analyze"]

        # Overall health assessment
        health_score = analysis.health_score
        staleness_pct = analysis.staleness_percentage

        if health_score < 0.6:
            recommendations.append(
                f"Documentation health is poor ({health_score:.1%}). "
                "Consider a comprehensive documentation audit."
            )
        elif health_score < 0.8:
            recommendations.append(
                f"Documentation health is moderate ({health_score:.1%}). "
                "Focus on addressing the most critical issues first."
            )

        if staleness_pct > 50:
            recommendations.append(
                f"{staleness_pct:.0f}% of documents are stale. "
                "Implement regular documentation review cycles."
            )

        # Critical documents
        if analysis.critical_documents_count > 0:
            recommendations.append(
                f"{analysis.critical_documents_count} documents are critically stale "
                "and require immediate attention."
            )

        # Dependencies
        if analysis.broken_dependencies > 0:
            broken_pct = (
                analysis.broken_dependencies / max(analysis.total_dependencies, 1)
            ) * 100
            recommendations.append(
                f"{analysis.broken_dependencies} broken dependencies found ({broken_pct:.0f}%). "
                "Regular dependency validation should be automated."
            )

        # Document type specific recommendations
        if analysis.documents:
            doc_types = {}
            for doc in analysis.documents:
                dt = doc.classification.document_type.value
                if dt not in doc_types:
                    doc_types[dt] = {"total": 0, "stale": 0}
                doc_types[dt]["total"] += 1
                if doc.is_stale:
                    doc_types[dt]["stale"] += 1

            for doc_type, stats in doc_types.items():
                if stats["stale"] / stats["total"] > 0.5:
                    recommendations.append(
                        f"Most {doc_type} documents are stale ({stats['stale']}/{stats['total']}). "
                        f"Review {doc_type} maintenance processes."
                    )

        return recommendations

    def _generate_priority_actions(self, analysis: FreshnessAnalysis) -> List[str]:
        """Generate priority actions based on analysis"""
        actions = []

        # Critical documents first
        critical_docs = [doc for doc in analysis.documents if doc.is_critical]
        if critical_docs:
            actions.append(
                f"URGENT: Review {len(critical_docs)} critically stale documents immediately"
            )

        # High priority refreshes
        high_priority_strategies = [
            s
            for s in analysis.refresh_strategies
            if s.priority == RefreshPriority.CRITICAL
            or s.priority == RefreshPriority.HIGH
        ]
        if high_priority_strategies:
            total_effort = sum(
                s.estimated_effort_minutes for s in high_priority_strategies
            )
            actions.append(
                f"Address {len(high_priority_strategies)} high-priority refresh strategies "
                f"(estimated {total_effort} minutes total)"
            )

        # Broken dependencies
        if analysis.broken_dependencies > 10:
            actions.append(
                f"Fix {analysis.broken_dependencies} broken dependencies to improve document health"
            )

        # Automation opportunities
        automatable_strategies = [
            s for s in analysis.refresh_strategies if s.can_automate
        ]
        if automatable_strategies:
            actions.append(
                f"Implement automation for {len(automatable_strategies)} refresh strategies "
                "to reduce manual effort"
            )

        return actions
