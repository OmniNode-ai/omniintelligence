# Archon Repository Mapping System

## Overview
Automatic repository detection and Archon project association for all Claude Code agents.

## Repository Detection Strategy
```bash
# 1. Git Repository Detection
git remote get-url origin
git rev-parse --show-toplevel
git branch --show-current

# 2. Project Identification
# From git URL: https://github.com/user/repo-name
# Extract: user/repo-name as project identifier
```

## Archon Project Mapping Configuration
```yaml
# ~/.claude/archon_project_mapping.yaml
repository_mappings:
  "coleam00/context-engineering-intro":
    archon_project_id: "d221bd38-4b18-4c13-afc2-8c8599e927ac"
    project_name: "Context Engineering Introduction"
    auto_create_tasks: true
    github_integration: true

  "myorg/api-service":
    archon_project_id: "auto-create"  # Will create if doesn't exist
    project_name: "API Service Development"
    auto_create_tasks: true
    github_integration: true

  "myorg/frontend-app":
    archon_project_id: "auto-create"
    project_name: "Frontend Application"
    auto_create_tasks: false  # Manual task creation only
    github_integration: true

# Default settings for unmapped repositories
default_settings:
  auto_create_project: true
  project_name_template: "Development: {repo_name}"
  auto_create_tasks: true
  github_integration: true
```

## Agent Integration Template
```python
class ArchonRepositoryAware:
    """Mixin for repository-aware Archon integration."""

    def __init__(self):
        self.repo_info = None
        self.archon_project_id = None
        self.project_mapping = None

    async def initialize_repository_context(self):
        """Initialize repository and Archon project context."""

        # 1. Detect current repository
        self.repo_info = await self.detect_repository()

        # 2. Load project mapping
        self.project_mapping = await self.load_project_mapping()

        # 3. Get or create Archon project
        self.archon_project_id = await self.get_or_create_archon_project()

        # 4. Validate project association
        await self.validate_project_association()

    async def detect_repository(self) -> dict:
        """Detect current git repository information."""
        try:
            # Get git remote URL
            remote_url = subprocess.check_output(['git', 'remote', 'get-url', 'origin'],
                                                text=True).strip()

            # Get repository root
            repo_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'],
                                              text=True).strip()

            # Get current branch
            current_branch = subprocess.check_output(['git', 'branch', '--show-current'],
                                                   text=True).strip()

            # Extract repo identifier from URL
            repo_identifier = self.extract_repo_identifier(remote_url)

            return {
                "remote_url": remote_url,
                "repo_root": repo_root,
                "current_branch": current_branch,
                "repo_identifier": repo_identifier,
                "repo_name": repo_identifier.split('/')[-1] if repo_identifier else None
            }
        except Exception as e:
            return {"error": f"Repository detection failed: {e}"}

    async def get_or_create_archon_project(self) -> str:
        """Get existing Archon project or create new one."""

        if not self.repo_info or not self.repo_info.get('repo_identifier'):
            raise ValueError("Repository information required for project association")

        repo_id = self.repo_info['repo_identifier']

        # Check if mapping exists
        if repo_id in self.project_mapping.get('repository_mappings', {}):
            mapping = self.project_mapping['repository_mappings'][repo_id]

            if mapping['archon_project_id'] == 'auto-create':
                # Create new project
                return await self.create_archon_project(mapping)
            else:
                # Use existing project ID
                return mapping['archon_project_id']

        # Use default settings to create project
        return await self.create_archon_project_default()

    async def create_archon_project(self, mapping: dict) -> str:
        """Create new Archon project for repository."""

        project_data = {
            "title": mapping.get('project_name', f"Development: {self.repo_info['repo_name']}"),
            "description": f"Automated project for repository: {self.repo_info['repo_identifier']}",
            "github_repo": self.repo_info.get('remote_url')
        }

        # Use mcp__archon__create_project
        result = await mcp__archon__create_project(**project_data)

        if result.get('success'):
            project_id = result['project_id']

            # Update mapping file
            await self.update_project_mapping(self.repo_info['repo_identifier'], project_id)

            return project_id
        else:
            raise Exception(f"Failed to create Archon project: {result}")
```

## Agent Enhancement Pattern
```python
# Enhanced agent with repository awareness
class EnhancedAgent(ArchonRepositoryAware):
    """Agent enhanced with repository awareness and Archon integration."""

    async def execute_task(self, task_description: str):
        """Execute task with full repository and project context."""

        # 1. Initialize repository context
        await self.initialize_repository_context()

        # 2. Create task in Archon project
        task_result = await mcp__archon__create_task(
            project_id=self.archon_project_id,
            title=f"{self.__class__.__name__}: {task_description[:50]}...",
            description=task_description,
            assignee=self.__class__.__name__,
            sources=[{
                "url": f"Repository: {self.repo_info['remote_url']}",
                "type": "repository",
                "relevance": "Working repository context"
            }]
        )

        # 3. Execute task with context
        try:
            result = await self.perform_agent_work(task_description)

            # 4. Update task with results
            await mcp__archon__update_task(
                task_id=task_result['task_id'],
                status="done",
                description=f"{task_description}\n\nCompleted successfully."
            )

            # 5. Create documentation
            await self.create_result_documentation(result)

            return result

        except Exception as e:
            # Update task with failure
            await mcp__archon__update_task(
                task_id=task_result['task_id'],
                status="review",
                description=f"{task_description}\n\nFailed: {str(e)}"
            )
            raise
```

## Setup Script
```python
#!/usr/bin/env python3
"""Setup script for Archon repository mapping."""

import asyncio
import subprocess
import yaml
from pathlib import Path

async def setup_repository_mapping():
    """Interactive setup for repository-Archon mapping."""

    print("🎯 Archon Repository Mapping Setup")
    print("=" * 50)

    # 1. Detect current repository
    repo_info = detect_current_repository()

    if repo_info.get('error'):
        print(f"❌ {repo_info['error']}")
        return

    print(f"📁 Repository: {repo_info['repo_identifier']}")
    print(f"🌿 Branch: {repo_info['current_branch']}")

    # 2. Check existing Archon projects
    projects = await mcp__archon__list_projects()

    print(f"\n📊 Found {projects['count']} existing Archon projects:")
    for i, project in enumerate(projects['projects'][:10]):
        print(f"  {i+1}. {project['title']} (ID: {project['id']})")

    # 3. Interactive mapping setup
    choice = input(f"\n🔗 Map repository '{repo_info['repo_identifier']}' to:\n"
                   "  1. Existing project (enter number)\n"
                   "  2. Create new project\n"
                   "  3. Skip for now\n"
                   "Choice: ")

    if choice == "2":
        # Create new project
        project_name = input(f"Project name [Development: {repo_info['repo_name']}]: ") or f"Development: {repo_info['repo_name']}"
        description = input("Project description: ") or f"Development project for {repo_info['repo_identifier']}"

        result = await mcp__archon__create_project(
            title=project_name,
            description=description,
            github_repo=repo_info.get('remote_url')
        )

        if result.get('success'):
            project_id = result['project_id']
            print(f"✅ Created project: {project_name} (ID: {project_id})")
        else:
            print(f"❌ Failed to create project: {result}")
            return

    elif choice.isdigit() and 1 <= int(choice) <= len(projects['projects']):
        # Use existing project
        project_id = projects['projects'][int(choice)-1]['id']
        print(f"✅ Using existing project: {projects['projects'][int(choice)-1]['title']}")

    else:
        print("⏭️ Skipping mapping setup")
        return

    # 4. Save mapping
    await save_repository_mapping(repo_info['repo_identifier'], project_id)

    print(f"🎉 Repository mapping saved!")
    print(f"   Repository: {repo_info['repo_identifier']}")
    print(f"   Archon Project ID: {project_id}")

if __name__ == "__main__":
    asyncio.run(setup_repository_mapping())
```

## Agent Integration Instructions

Add this to **every agent** in `/Users/jonah/.claude/agents/`:

```markdown
## Archon Repository Integration

### Pre-Execution Setup
```python
# Initialize repository context
await self.initialize_repository_context()

# This provides:
# - self.repo_info: Current repository information
# - self.archon_project_id: Associated Archon project
# - self.project_mapping: Configuration settings
```

### Task Creation Pattern
```python
# Create tracked task in Archon
task_result = await mcp__archon__create_task(
    project_id=self.archon_project_id,
    title=f"{self.agent_name}: {brief_description}",
    description=detailed_description,
    assignee=self.agent_name
)
```

### Research Enhancement
```python
# Enhanced research with repository context
research_results = await mcp__archon__perform_rag_query(
    query=f"{task_description} for {self.repo_info['repo_name']} repository",
    match_count=5
)
```

### Documentation Integration
```python
# Auto-create documentation
await mcp__archon__create_document(
    project_id=self.archon_project_id,
    title=f"{self.agent_name} Results: {task_name}",
    document_type="analysis",
    content={"results": results, "repository": self.repo_info}
)
```
```

This gives every agent:
✅ **Repository Awareness** - Knows which repo it's working in
✅ **Project Association** - Automatically linked to correct Archon project  
✅ **Task Tracking** - All work tracked in Archon
✅ **Research Context** - Repository-specific RAG queries
✅ **Documentation** - Results stored in project knowledge base

Would you like me to create the setup script and update some key agents as examples?
