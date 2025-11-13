"""
Test configuration and fixtures for Documentation Indexer Agent tests.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from pydantic_ai.messages import TextPart  # Correct import for text responses
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from ..agent import agent
from ..dependencies import create_test_dependencies


@pytest.fixture
def test_dependencies():
    """Create test dependencies with appropriate configuration."""
    return create_test_dependencies(
        chunk_size_target=500, max_file_size_mb=1, continue_on_error=True
    )


@pytest.fixture
def test_agent():
    """Create agent with TestModel for testing."""
    test_model = TestModel()
    return agent.override(model=test_model)


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory with test documentation."""
    temp_dir = tempfile.mkdtemp()
    project_path = Path(temp_dir)

    # Create test documentation structure
    docs_dir = project_path / "docs"
    docs_dir.mkdir()

    agents_dir = project_path / "agents"
    agents_dir.mkdir()

    # Create test files
    test_files = {
        "README.md": """# Test Project

This is a test project for documentation indexing.

## Features
- Feature 1: Documentation processing
- Feature 2: Content chunking
- Feature 3: Metadata extraction

## Architecture
The system consists of multiple components working together.
        """,
        "docs/api.md": """# API Documentation

## Authentication
All endpoints require authentication.

### POST /login
Login endpoint for user authentication.

### GET /users
Get list of users.

## Error Handling
The API uses standard HTTP status codes.
        """,
        "agents/test-agent.yaml": """---
name: test-agent
description: A test agent for validation
color: blue
task_agent_type: test
---

# Test Agent Specification

This is a test agent used for validation purposes.

## Responsibilities
- Process test data
- Validate functionality
- Report results

## Activation Triggers
- "run test" / "validate system"
        """,
        "docs/setup.txt": """Setup Instructions

1. Install dependencies
2. Configure environment
3. Run the application

Prerequisites:
- Python 3.12+
- Docker

Environment Variables:
- API_KEY=your_key_here
- DEBUG=true
        """,
        "config.yaml": """
# Application Configuration
app:
  name: test-app
  version: 1.0.0
  debug: true

database:
  host: localhost
  port: 5432
  name: testdb

features:
  - documentation_indexing
  - content_processing
  - metadata_extraction
        """,
    }

    # Write test files
    for file_path, content in test_files.items():
        full_path = project_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content.strip())

    yield project_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def archon_project_structure():
    """Create a structure mimicking the actual Archon project."""
    temp_dir = tempfile.mkdtemp()
    project_path = Path(temp_dir)

    # Create Archon-like structure
    files = {
        "CLAUDE.md": """# Archon - AI Agent Orchestration Platform

**Version**: 1.0.0
**Status**: Alpha - Rapid iteration and development

## Overview
Archon is a sophisticated command center for AI coding assistants.

## Architecture
- True Microservices Architecture
- Independent Scaling
- Clear Separation of Concerns

## MCP Server Integration
Comprehensive Model Context Protocol server capabilities.
        """,
        "agents/agent-documentation-indexer.md": """---
name: agent-documentation-indexer
description: Documentation discovery and indexing specialist
color: purple
task_agent_type: documentation_indexer
---

# Documentation Indexer Agent

Specialized agent for processing documentation files.

## Core Responsibilities
- Discover documentation files
- Process diverse formats
- Create searchable indexes
        """,
        "monitoring/README.md": """# Monitoring

System monitoring and observability documentation.

## Metrics
- Performance metrics
- Error rates
- System health

## Alerts
Configure alerts for critical issues.
        """,
        "docs/deployment.md": """# Deployment Guide

## Docker Deployment
Use docker-compose for local development.

## Production Deployment
Follow production deployment guidelines.
        """,
    }

    for file_path, content in files.items():
        full_path = project_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content.strip())

    yield project_path

    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_markdown_content():
    """Sample markdown content for testing."""
    return """---
title: Sample Document
description: A sample document for testing
tags: [test, documentation, sample]
---

# Sample Document

This is a sample document for testing documentation processing.

## Introduction

The document contains multiple sections to test chunking behavior.

### Subsection 1

This is the first subsection with some content.

### Subsection 2

This is the second subsection with different content.

## Implementation

Here's how to implement the feature:

1. Step one
2. Step two
3. Step three

## Code Examples

```python
def example_function():
    return "Hello, World!"
```

## Cross References

See also: [API Documentation](docs/api.md) and [Setup Guide](setup.txt).

## Conclusion

This concludes the sample document.
    """


@pytest.fixture
def sample_yaml_content():
    """Sample YAML content for testing."""
    return """---
name: sample-agent
description: A sample agent specification
color: green
task_agent_type: sample
version: 1.0.0
---

# Sample Agent

This is a sample agent specification for testing.

## Configuration

The agent supports the following configuration:
- Parameter 1: Description
- Parameter 2: Another description

## Usage

Activate the agent with:
- "process sample" / "run sample"
    """


def create_function_model_for_indexing():
    """Create a FunctionModel that simulates indexing behavior."""
    call_count = 0

    async def indexing_function(messages, tools):
        nonlocal call_count
        call_count += 1

        # Simulate different responses based on call sequence
        if call_count == 1:
            return TextPart(
                content="I'll analyze the documentation structure and begin indexing"
            )
        elif call_count == 2:
            return {
                "index_documentation": {
                    "target_path": "test_project",
                    "processing_mode": "comprehensive",
                    "enable_cross_references": True,
                }
            }
        else:
            return TextPart(
                content="Documentation indexing completed successfully with comprehensive analysis"
            )

    return indexing_function


@pytest.fixture
def function_model_agent():
    """Create agent with FunctionModel for controlled behavior testing."""
    function_model = FunctionModel(create_function_model_for_indexing())
    return agent.override(model=function_model)


@pytest.fixture
def mock_archon_responses():
    """Mock responses for Archon MCP integration testing."""
    return {
        "project_creation": {
            "project_id": "test-project-123",
            "title": "Documentation Knowledge System: test-project",
            "description": "Test project documentation",
        },
        "task_creation": {
            "task_id": "task-456",
            "title": "Documentation Indexing: comprehensive",
            "status": "pending",
        },
        "document_creation": {
            "doc_id": "doc-789",
            "title": "Test Document",
            "document_type": "knowledge_base",
        },
    }


@pytest.fixture
def edge_case_files(tmp_path):
    """Create files with edge cases for testing error handling."""

    # Empty file
    (tmp_path / "empty.md").touch()

    # Very large file (simulated)
    large_content = "# Large File\n" + "Lorem ipsum " * 10000
    (tmp_path / "large.md").write_text(large_content)

    # Binary file
    (tmp_path / "binary.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    # File with encoding issues
    (tmp_path / "encoding.md").write_bytes(
        "# Título com açéntos\nConteúdo português".encode("latin-1")
    )

    # Malformed YAML
    (tmp_path / "malformed.yaml").write_text(
        """
name: test
description: [unclosed list
invalid: yaml: content
    """
    )

    # Nested directory structure
    deep_dir = tmp_path / "a" / "very" / "deep" / "directory" / "structure"
    deep_dir.mkdir(parents=True)
    (deep_dir / "deep.md").write_text("# Deep File\nContent in deep directory.")

    return tmp_path


@pytest.fixture
def performance_test_data(tmp_path):
    """Create test data for performance testing."""

    # Create multiple documentation files
    for i in range(50):
        file_path = tmp_path / f"doc_{i}.md"
        content = f"""# Document {i}

This is test document number {i}.

## Section A
Content for section A in document {i}.

## Section B
Content for section B in document {i}.

## References
- [Document {i-1}](doc_{i-1}.md) (if exists)
- [Document {i+1}](doc_{i+1}.md) (if exists)
        """
        file_path.write_text(content)

    # Create YAML files
    for i in range(20):
        yaml_path = tmp_path / f"config_{i}.yaml"
        content = f"""
name: config-{i}
description: Configuration file number {i}
version: 1.{i}.0
settings:
  enabled: true
  level: {i % 5}
  tags: [config, test, number-{i}]
        """
        yaml_path.write_text(content)

    return tmp_path
