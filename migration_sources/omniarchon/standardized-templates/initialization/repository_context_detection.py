"""
Agent Initialization Template: Repository Context Detection
===========================================================

Standardized template for detecting and establishing repository context
across all agents. This template provides consistent repository information
extraction that forms the foundation for project association.

Template Parameters:
- FALLBACK_REPO_NAME: Default repository name if detection fails
- FALLBACK_BRANCH: Default branch name if detection fails
- CONTEXT_VALIDATION_LEVEL: Level of validation required (basic, standard, strict)

Usage:
    1. Import this template into your agent
    2. Call detect_repository_context() during initialization
    3. Use the returned context for project association
    4. Handle fallback scenarios appropriately

Dependencies:
    - git command-line tool
    - Shell environment access
    - File system read permissions

Quality Gates:
    - Git repository validation
    - URL sanitization
    - Branch existence verification
    - Commit hash validation
"""

import os
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional


def detect_repository_context(validation_level: str = "standard") -> Dict[str, Any]:
    """
    Detect and extract repository context information.

    This function implements comprehensive repository detection following
    the standardized patterns from the Archon MCP Integration Framework.
    It provides consistent context across all agents.

    Args:
        validation_level: Level of validation to perform
                         - basic: Minimal validation
                         - standard: Standard validation (default)
                         - strict: Comprehensive validation

    Returns:
        dict: Repository context information

    Raises:
        RepositoryDetectionError: If repository detection fails with strict validation
    """
    context = {
        "detection_timestamp": datetime.utcnow().isoformat(),
        "validation_level": validation_level,
        "detection_success": False,
        "errors": [],
        "warnings": [],
    }

    try:
        # Phase 1: Basic Git Repository Detection
        if not _is_git_repository():
            context["errors"].append("Not a git repository")
            if validation_level == "strict":
                raise RepositoryDetectionError(
                    "Current directory is not a git repository"
                )
            else:
                context["warnings"].append(
                    "Git repository not detected - using fallback values"
                )
                return _create_fallback_context(context)

        # Phase 2: Remote URL Detection
        repo_url = _detect_remote_url()
        if not repo_url:
            context["errors"].append("No remote URL found")
            repo_url = "local-development"

        # Phase 3: Repository Name Extraction
        repo_name = _extract_repository_name(repo_url)
        if not repo_name:
            context["errors"].append("Could not extract repository name")
            repo_name = "[FALLBACK_REPO_NAME]" or "unnamed-project"

        # Phase 4: Branch Detection
        repo_branch = _detect_current_branch()
        if not repo_branch:
            context["warnings"].append("Could not detect current branch")
            repo_branch = "[FALLBACK_BRANCH]" or "main"

        # Phase 5: Commit Hash Detection
        commit_hash = _detect_commit_hash()
        if not commit_hash:
            context["warnings"].append("Could not detect commit hash")
            commit_hash = "unknown"

        # Phase 6: Additional Repository Information
        additional_info = _gather_additional_repository_info()

        # Phase 7: Context Validation
        validation_results = _validate_repository_context(
            repo_url, repo_name, repo_branch, commit_hash, validation_level
        )

        context.update(
            {
                "detection_success": True,
                "repository": {
                    "url": repo_url,
                    "name": repo_name,
                    "branch": repo_branch,
                    "commit": commit_hash,
                    "is_local": repo_url == "local-development",
                    "has_remote": repo_url != "local-development",
                },
                "additional_info": additional_info,
                "validation_results": validation_results,
            }
        )

        return context

    except Exception as e:
        context["errors"].append(f"Repository detection failed: {str(e)}")
        if validation_level == "strict":
            raise
        return _create_fallback_context(context)


def _is_git_repository() -> bool:
    """Check if current directory is a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _detect_remote_url() -> Optional[str]:
    """Detect the remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            return _sanitize_repository_url(url)
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _extract_repository_name(repo_url: str) -> Optional[str]:
    """Extract repository name from URL."""
    if repo_url == "local-development":
        # Try to get directory name as fallback
        return os.path.basename(os.getcwd()) or "local-project"

    # Handle various URL formats
    patterns = [
        r"([^/]+)\.git$",  # Standard .git suffix
        r"([^/]+)$",  # No .git suffix
        r"/([^/]+?)(?:\.git)?/?$",  # Full path patterns
    ]

    for pattern in patterns:
        match = re.search(pattern, repo_url)
        if match:
            name = match.group(1)
            # Sanitize the name
            name = re.sub(r"[^a-zA-Z0-9\-_]", "", name)
            if name:
                return name

    return None


def _detect_current_branch() -> Optional[str]:
    """Detect the current git branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch else None
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _detect_commit_hash() -> Optional[str]:
    """Detect the current commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            return commit if commit else None
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _gather_additional_repository_info() -> Dict[str, Any]:
    """Gather additional repository information."""
    info = {}

    try:
        # Repository status
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info["has_uncommitted_changes"] = bool(result.stdout.strip())
            info["status_clean"] = not bool(result.stdout.strip())

        # Last commit info
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%an|%ae|%ad", "--date=iso"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|")
            if len(parts) >= 4:
                info["last_commit"] = {
                    "hash": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "date": parts[3],
                }

        # Remote tracking
        result = subprocess.run(
            ["git", "rev-list", "--count", "--left-right", "HEAD...@{upstream}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            counts = result.stdout.strip().split("\t")
            if len(counts) >= 2:
                info["commits_ahead"] = int(counts[0])
                info["commits_behind"] = int(counts[1])

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    return info


def _sanitize_repository_url(url: str) -> str:
    """Sanitize repository URL for safe storage and display."""
    if not url:
        return "local-development"

    # Remove sensitive information from URLs
    url = re.sub(r"(https?://)[^@]+@", r"\1", url)  # Remove user:pass@
    url = re.sub(r"\.git/?$", "", url)  # Remove .git suffix

    return url


def _validate_repository_context(
    url: str, name: str, branch: str, commit: str, level: str
) -> Dict[str, Any]:
    """Validate the detected repository context."""
    validation = {
        "level": level,
        "passed": True,
        "checks": {},
        "warnings": [],
        "errors": [],
    }

    # Basic validation
    validation["checks"]["url_format"] = _validate_url_format(url)
    validation["checks"]["name_format"] = _validate_name_format(name)
    validation["checks"]["branch_format"] = _validate_branch_format(branch)
    validation["checks"]["commit_format"] = _validate_commit_format(commit)

    if level in ["standard", "strict"]:
        # Standard validation
        validation["checks"][
            "repository_accessible"
        ] = _validate_repository_accessible()
        validation["checks"]["branch_exists"] = _validate_branch_exists(branch)

    if level == "strict":
        # Strict validation
        validation["checks"]["remote_accessible"] = _validate_remote_accessible(url)
        validation["checks"]["commit_exists"] = _validate_commit_exists(commit)

    # Determine overall validation result
    validation["passed"] = all(validation["checks"].values())

    return validation


def _validate_url_format(url: str) -> bool:
    """Validate URL format."""
    if url == "local-development":
        return True
    return bool(re.match(r"https?://|git@|ssh://|file://", url))


def _validate_name_format(name: str) -> bool:
    """Validate repository name format."""
    return bool(name and re.match(r"^[a-zA-Z0-9\-_.]+$", name))


def _validate_branch_format(branch: str) -> bool:
    """Validate branch name format."""
    return bool(branch and re.match(r"^[a-zA-Z0-9\-_/.]+$", branch))


def _validate_commit_format(commit: str) -> bool:
    """Validate commit hash format."""
    return commit == "unknown" or bool(re.match(r"^[a-f0-9]{7,40}$", commit))


def _validate_repository_accessible() -> bool:
    """Validate that repository is accessible."""
    return _is_git_repository()


def _validate_branch_exists(branch: str) -> bool:
    """Validate that branch exists."""
    try:
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _validate_remote_accessible(url: str) -> bool:
    """Validate that remote repository is accessible."""
    if url == "local-development":
        return True
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "--heads", url],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _validate_commit_exists(commit: str) -> bool:
    """Validate that commit exists in repository."""
    if commit == "unknown":
        return True
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", commit], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _create_fallback_context(base_context: Dict[str, Any]) -> Dict[str, Any]:
    """Create fallback context when detection fails."""
    base_context.update(
        {
            "detection_success": False,
            "repository": {
                "url": "local-development",
                "name": "[FALLBACK_REPO_NAME]" or "unnamed-project",
                "branch": "[FALLBACK_BRANCH]" or "main",
                "commit": "unknown",
                "is_local": True,
                "has_remote": False,
            },
            "additional_info": {},
            "validation_results": {
                "level": "fallback",
                "passed": False,
                "checks": {},
                "warnings": ["Using fallback values due to detection failure"],
                "errors": base_context.get("errors", []),
            },
        }
    )
    return base_context


class RepositoryDetectionError(Exception):
    """Exception raised when repository detection fails with strict validation."""

    pass


# Template Usage Example:
"""
# Basic usage:
context = detect_repository_context()
if context['detection_success']:
    repo_info = context['repository']
    print(f"Repository: {repo_info['name']} ({repo_info['url']})")
    print(f"Branch: {repo_info['branch']}, Commit: {repo_info['commit']}")

# With strict validation:
try:
    context = detect_repository_context(validation_level="strict")
    # Proceed with confirmed repository context
except RepositoryDetectionError as e:
    # Handle repository detection failure
    print(f"Repository detection failed: {e}")
"""
