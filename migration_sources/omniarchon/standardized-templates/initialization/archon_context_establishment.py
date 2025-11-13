"""
Agent Initialization Template: Archon Context Establishment
===========================================================

Standardized template for establishing Archon MCP context across all agents.
This template provides the foundation for repository-aware initialization and
project association that all agents must implement.

Template Parameters:
- AGENT_DOMAIN: Short domain identifier (e.g., pr_comment, debug, api_design)
- AGENT_PURPOSE: Brief purpose description for docstring
- AGENT_TITLE: Human-readable title for project creation
- AGENT_DESCRIPTION: Detailed agent description
- AGENT_SPECIFIC_SCOPE: Domain-specific scope and capabilities

Usage:
    1. Copy this template to your agent implementation
    2. Replace all template parameters with agent-specific values
    3. Customize the project creation logic if needed
    4. Implement the context validation logic
    5. Add any agent-specific initialization steps

Dependencies:
    - mcp__archon__health_check()
    - mcp__archon__list_projects()
    - Repository context variables (REPO_URL, REPO_NAME, etc.)

Quality Gates:
    - Health check validation
    - Project discovery before creation
    - Human-in-loop protection
    - Error handling for MCP unavailability
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional


def establish_archon_agent_domain_context() -> (
    Optional[str]
):  # Template: Replace with establish_archon_[AGENT_DOMAIN]_context()
    """
    Establish Archon MCP context for [AGENT_PURPOSE].

    This function implements the standardized Phase 1 context establishment
    pattern from the Archon MCP Integration Framework. It handles repository
    detection, project discovery, and creates a foundation for intelligent
    agent execution.

    Returns:
        str: Project ID for task tracking, or None if Archon unavailable

    Raises:
        ConnectionError: If MCP connection fails unexpectedly
        ValueError: If repository context cannot be determined
    """
    # Phase 1.1: Repository Context Detection
    # Standard repository context variables (available to all agents)
    REPO_URL = (
        os.popen("git remote get-url origin 2>/dev/null || echo 'local-development'")
        .read()
        .strip()
    )
    REPO_NAME = (
        os.path.basename(REPO_URL.replace(".git", "")).split("/")[-1]
        or "unnamed-project"
    )
    REPO_BRANCH = (
        os.popen("git branch --show-current 2>/dev/null || echo 'main'").read().strip()
    )
    COMMIT_HASH = (
        os.popen("git rev-parse --short HEAD 2>/dev/null || echo 'unknown'")
        .read()
        .strip()
    )

    # Log repository context for debugging
    print("🔍 Repository Context Detected:")
    print(f"   URL: {REPO_URL}")
    print(f"   Name: {REPO_NAME}")
    print(f"   Branch: {REPO_BRANCH}")
    print(f"   Commit: {COMMIT_HASH}")

    # Phase 1.2: Archon MCP Connectivity Verification
    try:
        health = mcp__archon__health_check()
        if not health.get("success", False):
            print("⚠️  Archon MCP unavailable - operating in local-only mode")
            print(
                "📝 Reduced functionality: No project tracking, RAG queries, or knowledge capture"
            )
            return None
    except Exception as e:
        print(f"⚠️  Archon MCP connection failed: {str(e)}")
        print("📝 Falling back to local-only mode")
        return None

    # Phase 1.3: Project Discovery and Association
    try:
        projects = mcp__archon__list_projects()
        print(f"🔍 Searching through {len(projects)} existing projects...")

        matching_project = None
        for project in projects:
            # Match by repository URL or name
            if (project.get("github_repo") and REPO_URL in project["github_repo"]) or (
                REPO_NAME.lower() in project.get("title", "").lower()
            ):
                matching_project = project
                print(
                    f"✅ Found matching project: {project['title']} (ID: {project['project_id']})"
                )
                break

        # Phase 1.4: Human-in-Loop Project Creation Protection
        if not matching_project:
            print(f"⚠️  No existing Archon project found for repository: {REPO_NAME}")
            print(f"📁 Repository: {REPO_URL}")
            print(f"🔍 Checked {len(projects)} existing projects")
            print(
                "❌ CANNOT create new Archon project without explicit human permission"
            )
            print(
                "💡 Please manually create project for this repository or specify existing project to use"
            )
            print("📚 Available projects:")
            for i, project in enumerate(projects[:5]):
                print(
                    f"   {i+1}. {project.get('title', 'Untitled')} (ID: {project.get('project_id', 'unknown')})"
                )

            return None  # Return None to indicate no project available

        # Phase 1.5: Context Validation and Preparation
        project_id = matching_project["project_id"]

        # Validate project accessibility
        try:
            project_details = mcp__archon__get_project(project_id=project_id)
            if not project_details.get("success", False):
                print(f"⚠️  Project {project_id} exists but cannot be accessed")
                return None
        except Exception as e:
            print(f"⚠️  Failed to validate project access: {str(e)}")
            return None

        # Store context for agent use
        {
            "project_id": project_id,
            "repository_info": {
                "url": REPO_URL,
                "name": REPO_NAME,
                "branch": REPO_BRANCH,
                "commit": COMMIT_HASH,
            },
            "agent_domain": "[AGENT_DOMAIN]",
            "initialization_timestamp": datetime.utcnow().isoformat(),
            "mcp_available": True,
        }

        print("✅ Archon context established for [AGENT_TITLE]")
        print(f"📊 Project: {matching_project.get('title', 'Unknown')} ({project_id})")
        print("🚀 Ready for Phase 2: Intelligence Gathering")

        return project_id

    except Exception as e:
        print(f"⚠️  Project discovery failed: {str(e)}")
        print("📝 Falling back to local-only mode")
        return None


def validate_archon_context(project_id: Optional[str]) -> Dict[str, Any]:
    """
    Validate the established Archon context and prepare for agent execution.

    Args:
        project_id: The project ID returned from context establishment

    Returns:
        dict: Validation results and context information
    """
    if not project_id:
        return {
            "valid": False,
            "mode": "local_only",
            "capabilities": ["core_functionality"],
            "limitations": [
                "no_project_tracking",
                "no_rag_queries",
                "no_knowledge_capture",
            ],
        }

    try:
        # Verify project accessibility
        project = mcp__archon__get_project(project_id=project_id)

        return {
            "valid": True,
            "mode": "archon_integrated",
            "project_id": project_id,
            "project_title": project.get("title", "Unknown"),
            "capabilities": [
                "project_tracking",
                "task_management",
                "rag_queries",
                "knowledge_capture",
                "progress_tracking",
                "parallel_coordination",
            ],
            "limitations": [],
        }
    except Exception as e:
        return {
            "valid": False,
            "mode": "context_error",
            "error": str(e),
            "capabilities": ["core_functionality"],
            "limitations": ["context_validation_failed"],
        }


# Template Usage Example:
"""
def establish_archon_debug_context():
    # Replace template parameters:
    # [AGENT_DOMAIN] → debug
    # [AGENT_PURPOSE] → systematic debugging and root cause analysis
    # [AGENT_TITLE] → Debug Intelligence Agent
    # [AGENT_DESCRIPTION] → Specialized agent for debugging complex issues
    # [AGENT_SPECIFIC_SCOPE] → Error investigation, root cause analysis, resolution strategies

    return establish_archon_debug_context()

# Usage in agent:
project_id = establish_archon_debug_context()
context_validation = validate_archon_context(project_id)

if context_validation['valid']:
    print(f"Agent capabilities: {context_validation['capabilities']}")
    # Proceed with full agent functionality
else:
    print(f"Limited mode: {context_validation['limitations']}")
    # Proceed with reduced functionality
"""
