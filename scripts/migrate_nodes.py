#!/usr/bin/env python3
"""
Automated node migration script for omnibase_core template compliance.

Migrates nodes from old structure to official template structure.
"""

import os
from pathlib import Path
from typing import Literal

# Template for separated input model
INPUT_MODEL_TEMPLATE = '''"""
Input model for {NodeName} {Type} Node
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from uuid import UUID, uuid4


class Model{NodeName}{Type}Input(BaseModel):
    """Input model for {node_name} operations."""

    # Add specific fields here
    correlation_id: UUID = Field(
        default_factory=uuid4,
        description="Correlation ID for request tracing"
    )

    class Config:
        json_schema_extra = {{
            "example": {{
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
            }}
        }}
'''

# Template for separated output model
OUTPUT_MODEL_TEMPLATE = '''"""
Output model for {NodeName} {Type} Node
"""

from pydantic import BaseModel, Field
from typing import Dict, Any
from uuid import UUID


class Model{NodeName}{Type}Output(BaseModel):
    """Output model for {node_name} operations."""

    success: bool = Field(..., description="Whether operation succeeded")
    correlation_id: UUID = Field(..., description="Correlation ID from request")
    processing_time_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
        ge=0.0
    )

    class Config:
        json_schema_extra = {{
            "example": {{
                "success": True,
                "processing_time_ms": 45.2
            }}
        }}
'''

# Template for separated config model
CONFIG_MODEL_TEMPLATE = '''"""
Configuration model for {NodeName} {Type} Node
"""

from pydantic import BaseModel, Field
from typing import Literal


class Model{NodeName}{Type}Config(BaseModel):
    """Configuration for {node_name} operations."""

    timeout_ms: int = Field(
        default=30000,
        description="Operation timeout in milliseconds",
        gt=0
    )

    @classmethod
    def for_environment(cls, env: Literal["production", "staging", "development"]):
        """Factory method for environment-specific configurations."""
        if env == "production":
            return cls(timeout_ms=30000)
        elif env == "staging":
            return cls(timeout_ms=60000)
        else:  # development
            return cls(timeout_ms=120000)

    class Config:
        json_schema_extra = {{
            "example": {{
                "timeout_ms": 30000
            }}
        }}
'''

# Script continues...
def create_node_structure(node_name: str, node_type: str, base_path: Path):
    """Create directory structure for a node."""
    node_dir = base_path / f"{node_name}_{node_type}" / "v1_0_0"

    # Create directories
    (node_dir / "models").mkdir(parents=True, exist_ok=True)
    (node_dir / "enums").mkdir(parents=True, exist_ok=True)
    (node_dir / "utils").mkdir(parents=True, exist_ok=True)
    (node_dir / "contracts" / "subcontracts").mkdir(parents=True, exist_ok=True)

    return node_dir

def generate_models(node_dir: Path, node_name: str, node_type: str):
    """Generate separated model files."""
    # Convert snake_case to PascalCase
    words = node_name.split('_')
    pascal_name = ''.join(word.capitalize() for word in words)

    # Input model
    (node_dir / "models" / f"model_{node_name}_{node_type}_input.py").write_text(
        INPUT_MODEL_TEMPLATE.format(
            NodeName=pascal_name,
            Type=node_type.capitalize(),
            node_name=node_name
        )
    )

    # Output model
    (node_dir / "models" / f"model_{node_name}_{node_type}_output.py").write_text(
        OUTPUT_MODEL_TEMPLATE.format(
            NodeName=pascal_name,
            Type=node_type.capitalize(),
            node_name=node_name
        )
    )

    # Config model
    (node_dir / "models" / f"model_{node_name}_{node_type}_config.py").write_text(
        CONFIG_MODEL_TEMPLATE.format(
            NodeName=pascal_name,
            Type=node_type.capitalize(),
            node_name=node_name
        )
    )

    # Models __init__.py
    (node_dir / "models" / "__init__.py").write_text(f'''"""
Models for {pascal_name} {node_type.capitalize()} Node
"""

from .model_{node_name}_{node_type}_input import Model{pascal_name}{node_type.capitalize()}Input
from .model_{node_name}_{node_type}_output import Model{pascal_name}{node_type.capitalize()}Output
from .model_{node_name}_{node_type}_config import Model{pascal_name}{node_type.capitalize()}Config

__all__ = [
    "Model{pascal_name}{node_type.capitalize()}Input",
    "Model{pascal_name}{node_type.capitalize()}Output",
    "Model{pascal_name}{node_type.capitalize()}Config",
]
''')

if __name__ == "__main__":
    # Base path
    base_path = Path("src/omniintelligence/nodes")

    # Nodes to migrate
    compute_nodes = [
        "entity_extraction",
        "pattern_matching",
        "quality_scoring",
        "semantic_analysis",
        "relationship_detection"
    ]

    print("Starting migration...")
    for node in compute_nodes:
        print(f"  Migrating {node}_compute...")
        node_dir = create_node_structure(node, "compute", base_path)
        generate_models(node_dir, node, "compute")

    print("✅ Migration script complete!")
