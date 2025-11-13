#!/usr/bin/env python3
"""
Test Project Generator for Tree-Stamping Integration POC

Generates realistic Python test projects with varying:
- Quality scores (0.6-0.95)
- ONEX types (Effect, Compute, Reducer, Orchestrator)
- Semantic concepts (auth, api, database, config)
- Directory structures

Usage:
    python3 generate_test_project.py --output /tmp/test-project --files 50
    python3 generate_test_project.py --output /tmp/large-project --files 1000
"""

import argparse
import random
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

# ONEX types and their characteristics
ONEX_TYPES = {
    "effect": {
        "suffix": "_effect",
        "concepts": ["api", "database", "external", "io", "network"],
        "quality_range": (0.70, 0.92),
    },
    "compute": {
        "suffix": "_compute",
        "concepts": ["transform", "calculation", "validation", "parsing"],
        "quality_range": (0.75, 0.95),
    },
    "reducer": {
        "suffix": "_reducer",
        "concepts": ["aggregation", "accumulation", "state", "persistence"],
        "quality_range": (0.72, 0.90),
    },
    "orchestrator": {
        "suffix": "_orchestrator",
        "concepts": ["workflow", "coordination", "pipeline", "process"],
        "quality_range": (0.65, 0.88),
    },
}

# Semantic domains and their file types
DOMAINS = {
    "auth": {
        "subdirs": ["jwt", "sessions", "permissions"],
        "concepts": ["authentication", "authorization", "jwt", "token", "security"],
        "files": [
            "jwt_handler",
            "user_authenticator",
            "session_manager",
            "permission_checker",
            "token_validator",
            "password_hasher",
        ],
    },
    "api": {
        "subdirs": ["endpoints", "middleware", "validators"],
        "concepts": ["api", "endpoint", "validation", "request", "response"],
        "files": [
            "endpoints",
            "validators",
            "rate_limiter",
            "request_parser",
            "response_formatter",
            "middleware_chain",
        ],
    },
    "database": {
        "subdirs": ["queries", "connections", "models"],
        "concepts": ["database", "query", "connection", "orm", "persistence"],
        "files": [
            "connection_pool",
            "query_builder",
            "result_aggregator",
            "transaction_manager",
            "model_mapper",
            "migration_runner",
        ],
    },
    "config": {
        "subdirs": ["loaders", "validators", "managers"],
        "concepts": ["configuration", "settings", "environment", "validation"],
        "files": [
            "config_loader",
            "env_validator",
            "settings_manager",
            "secret_handler",
            "config_merger",
        ],
    },
}

# Code templates by ONEX type
CODE_TEMPLATES = {
    "effect": '''"""
{description}

ONEX Type: Effect
Quality Score: {quality}
Concepts: {concepts}
"""
import asyncio
from typing import Any, Dict


class {class_name}:
    """
    {description}

    This is an Effect node - handles external I/O and side effects.
    """

    def __init__(self):
        self.connection = None

    async def execute_effect(self, contract: Dict[str, Any]) -> Any:
        """
        Execute effect operation.

        Args:
            contract: Effect contract with operation details

        Returns:
            Result of effect execution
        """
        # Validate contract
        if not self._validate_contract(contract):
            raise ValueError("Invalid contract")

        # Execute effect
        result = await self._perform_operation(contract)

        return result

    def _validate_contract(self, contract: Dict[str, Any]) -> bool:
        """Validate effect contract."""
        return "operation" in contract

    async def _perform_operation(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual effect operation."""
        await asyncio.sleep(0.01)  # Simulate I/O
        return {{"success": True, "data": "Effect completed"}}
''',
    "compute": '''"""
{description}

ONEX Type: Compute
Quality Score: {quality}
Concepts: {concepts}
"""
from typing import Any, Dict, List


class {class_name}:
    """
    {description}

    This is a Compute node - pure transformations and calculations.
    """

    def execute_compute(self, contract: Dict[str, Any]) -> Any:
        """
        Execute compute operation.

        Args:
            contract: Compute contract with transformation details

        Returns:
            Transformed result
        """
        # Validate input
        if not self._validate_input(contract):
            raise ValueError("Invalid input")

        # Perform computation
        result = self._transform(contract)

        return result

    def _validate_input(self, contract: Dict[str, Any]) -> bool:
        """Validate compute input."""
        return "data" in contract

    def _transform(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Perform pure transformation."""
        data = contract["data"]

        # Transform data
        transformed = self._apply_transformation(data)

        return {{"success": True, "result": transformed}}

    def _apply_transformation(self, data: Any) -> Any:
        """Apply transformation logic."""
        # Pure computation
        return data
''',
    "reducer": '''"""
{description}

ONEX Type: Reducer
Quality Score: {quality}
Concepts: {concepts}
"""
from typing import Any, Dict, List


class {class_name}:
    """
    {description}

    This is a Reducer node - aggregation and state management.
    """

    def __init__(self):
        self.state = {{}}

    def execute_reduction(self, contract: Dict[str, Any]) -> Any:
        """
        Execute reduction operation.

        Args:
            contract: Reducer contract with aggregation details

        Returns:
            Reduced/aggregated result
        """
        # Validate contract
        if not self._validate_contract(contract):
            raise ValueError("Invalid contract")

        # Perform reduction
        result = self._reduce(contract)

        # Update state
        self._update_state(result)

        return result

    def _validate_contract(self, contract: Dict[str, Any]) -> bool:
        """Validate reducer contract."""
        return "items" in contract

    def _reduce(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Perform reduction/aggregation."""
        items = contract["items"]

        # Aggregate items
        aggregated = self._aggregate(items)

        return {{"success": True, "aggregated": aggregated}}

    def _aggregate(self, items: List[Any]) -> Any:
        """Aggregate items."""
        return items

    def _update_state(self, result: Dict[str, Any]) -> None:
        """Update internal state."""
        self.state.update(result)
''',
    "orchestrator": '''"""
{description}

ONEX Type: Orchestrator
Quality Score: {quality}
Concepts: {concepts}
"""
import asyncio
from typing import Any, Dict, List


class {class_name}:
    """
    {description}

    This is an Orchestrator node - workflow coordination.
    """

    def __init__(self):
        self.workflow_state = {{}}

    async def execute_orchestration(self, contract: Dict[str, Any]) -> Any:
        """
        Execute orchestration workflow.

        Args:
            contract: Orchestrator contract with workflow details

        Returns:
            Workflow execution result
        """
        # Validate contract
        if not self._validate_contract(contract):
            raise ValueError("Invalid contract")

        # Execute workflow
        result = await self._execute_workflow(contract)

        return result

    def _validate_contract(self, contract: Dict[str, Any]) -> bool:
        """Validate orchestrator contract."""
        return "workflow" in contract

    async def _execute_workflow(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow steps."""
        workflow = contract["workflow"]

        # Execute steps in sequence
        results = []
        for step in workflow.get("steps", []):
            step_result = await self._execute_step(step)
            results.append(step_result)

        return {{"success": True, "results": results}}

    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute single workflow step."""
        await asyncio.sleep(0.01)  # Simulate processing
        return {{"step": step.get("name"), "completed": True}}
''',
}


def generate_file_content(
    domain: str,
    file_name: str,
    onex_type: str,
    quality_score: float,
    concepts: List[str],
) -> str:
    """Generate Python file content."""
    class_name = "".join(word.capitalize() for word in file_name.split("_"))

    description = f"{domain.capitalize()} {file_name.replace('_', ' ')} - {onex_type.upper()} node"

    template = CODE_TEMPLATES[onex_type]

    return template.format(
        description=description,
        quality=f"{quality_score:.2f}",
        concepts=", ".join(concepts),
        class_name=class_name,
    )


def generate_test_file(file_path: Path) -> str:
    """Generate test file content."""
    module_name = file_path.stem
    class_name = "".join(word.capitalize() for word in module_name.split("_"))

    return f'''"""
Tests for {module_name}
"""
import pytest


class Test{class_name}:
    """Test suite for {class_name}."""

    def test_initialization(self):
        """Test object initialization."""
        assert True

    def test_execution(self):
        """Test execution."""
        assert True
'''


def generate_readme(project_path: Path, file_count: int) -> str:
    """Generate README for test project."""
    return f"""# Test Project for Tree-Stamping Integration

**Generated**: Automatically
**Files**: {file_count} Python files
**Purpose**: Testing Tree-Stamping Integration POC

## Structure

```
{project_path.name}/
├── src/
│   ├── auth/         # Authentication and security
│   ├── api/          # API endpoints and middleware
│   ├── database/     # Database operations
│   └── config/       # Configuration management
└── tests/           # Test files
```

## Quality Characteristics

- Quality scores: 0.6-0.95
- ONEX types: Effect, Compute, Reducer, Orchestrator
- Semantic concepts: auth, api, database, config
- Various complexity levels

## Usage

This project is generated for testing the Tree-Stamping Integration POC.
It provides realistic Python files with varying quality scores and ONEX types
for comprehensive testing of:

1. Tree discovery (OnexTree)
2. Intelligence generation (Bridge)
3. Metadata stamping (Stamping)
4. Vector indexing (Qdrant)
5. Graph indexing (Memgraph)
6. File search (semantic + quality)
"""


def generate_test_project(
    output_path: str = "/tmp/archon-test-project",
    file_count: int = 50,
    seed: int = 42,
    force: bool = False,
) -> Path:
    """
    Generate test project with specified number of files.

    Args:
        output_path: Output directory path
        file_count: Number of files to generate
        seed: Random seed for reproducibility

    Returns:
        Path to generated project
    """
    random.seed(seed)

    project_path = Path(output_path)

    # Clean existing project
    if project_path.exists():
        if not force:
            raise FileExistsError(
                f"Directory {project_path} already exists. "
                f"Use --force to overwrite or choose a different output path."
            )
        shutil.rmtree(project_path)

    # Create directory structure
    project_path.mkdir(parents=True)
    src_path = project_path / "src"
    tests_path = project_path / "tests"

    src_path.mkdir()
    tests_path.mkdir()

    # Create __init__.py for src package
    (src_path / "__init__.py").write_text('"""src package."""\n')

    # Calculate files per domain
    files_per_domain = file_count // len(DOMAINS)
    remaining_files = file_count % len(DOMAINS)

    generated_files = []

    # Generate files for each domain
    for domain_idx, (domain, config) in enumerate(DOMAINS.items()):
        domain_files = files_per_domain
        if domain_idx < remaining_files:
            domain_files += 1

        # Create domain directory
        domain_path = src_path / domain
        domain_path.mkdir()

        # Create __init__.py
        (domain_path / "__init__.py").write_text(
            f'"""{domain.capitalize()} module."""\n'
        )

        # Create subdirectories
        for subdir in config["subdirs"]:
            subdir_path = domain_path / subdir
            subdir_path.mkdir()
            (subdir_path / "__init__.py").write_text(
                f'"""{subdir.capitalize()} submodule."""\n'
            )

        # Generate files
        files_generated = 0
        file_idx = 0

        while files_generated < domain_files:
            # Select file name
            file_base = config["files"][file_idx % len(config["files"])]

            # Select ONEX type (weighted distribution)
            onex_type = random.choices(
                list(ONEX_TYPES.keys()),
                weights=[
                    0.30,
                    0.30,
                    0.25,
                    0.15,
                ],  # Effect, Compute, Reducer, Orchestrator
            )[0]

            onex_config = ONEX_TYPES[onex_type]

            # Generate quality score
            quality_score = random.uniform(*onex_config["quality_range"])

            # Select concepts
            all_concepts = config["concepts"] + onex_config["concepts"]
            num_concepts = random.randint(2, 4)
            concepts = random.sample(all_concepts, min(num_concepts, len(all_concepts)))

            # Create file name
            file_name = f"{file_base}_{onex_type}"
            if files_generated > 0 and file_idx % len(config["files"]) == 0:
                file_name = f"{file_base}_{files_generated}_{onex_type}"

            file_path = domain_path / f"{file_name}.py"

            # Generate content
            content = generate_file_content(
                domain=domain,
                file_name=file_name,
                onex_type=onex_type,
                quality_score=quality_score,
                concepts=concepts,
            )

            # Write file
            file_path.write_text(content)

            generated_files.append(
                {
                    "path": str(file_path.relative_to(project_path)),
                    "domain": domain,
                    "onex_type": onex_type,
                    "quality_score": quality_score,
                    "concepts": concepts,
                }
            )

            files_generated += 1
            file_idx += 1

    # Generate test files (20% of source files)
    test_file_count = max(1, file_count // 5)
    sampled_files = random.sample(
        generated_files, min(test_file_count, len(generated_files))
    )

    for file_info in sampled_files:
        # Create test file
        source_path = Path(file_info["path"])
        test_name = f"test_{source_path.stem}.py"
        test_path = tests_path / test_name

        test_content = generate_test_file(source_path)
        test_path.write_text(test_content)

    # Create tests __init__.py
    (tests_path / "__init__.py").write_text('"""Test suite."""\n')

    # Generate README
    readme_content = generate_readme(project_path, file_count)
    (project_path / "README.md").write_text(readme_content)

    # Generate project manifest
    import json

    manifest = {
        "project_name": project_path.name,
        "file_count": file_count,
        "generated_files": len(generated_files),
        "test_files": len(sampled_files),
        "domains": list(DOMAINS.keys()),
        "onex_types": list(ONEX_TYPES.keys()),
        "files": generated_files,
    }

    (project_path / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"✅ Generated test project: {project_path}")
    print(f"   Files: {len(generated_files)}")
    print(f"   Tests: {len(sampled_files)}")
    print(f"   Domains: {len(DOMAINS)}")
    print(f"   Quality range: 0.6-0.95")

    return project_path


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate test project for Tree-Stamping Integration POC"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/archon-test-project",
        help="Output directory path (default: /tmp/archon-test-project)",
    )
    parser.add_argument(
        "--files",
        type=int,
        default=50,
        help="Number of files to generate (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting existing project directory",
    )

    args = parser.parse_args()

    project_path = generate_test_project(
        output_path=args.output,
        file_count=args.files,
        seed=args.seed,
        force=args.force,
    )

    print(f"\n📁 Project generated at: {project_path}")
    print(f"📊 Manifest: {project_path / 'manifest.json'}")


if __name__ == "__main__":
    main()
