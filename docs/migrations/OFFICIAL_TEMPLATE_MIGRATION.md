# Official omnibase_core Template Migration Guide

## Overview

This guide documents the migration of all omniintelligence nodes to the official omnibase_core template structure as defined in:
- https://github.com/OmniNode-ai/omnibase_core/blob/main/docs/guides/node-building/README.md
- https://github.com/OmniNode-ai/omnibase_core/blob/main/docs/reference/templates/COMPUTE_NODE_TEMPLATE.md

## Migration Status

### ✅ Completed Nodes (1/14)
1. **vectorization_compute** - Full migration complete (reference implementation)

### ⏳ Pending Nodes (13/14)
2. entity_extraction_compute
3. pattern_matching_compute
4. quality_scoring_compute
5. semantic_analysis_compute
6. relationship_detection_compute
7. kafka_event_effect
8. qdrant_vector_effect
9. memgraph_graph_effect
10. postgres_pattern_effect
11. intelligence_api_effect
12. haystack_adapter_effect
13. intelligence_orchestrator
14. intelligence_reducer

---

## Official Template Structure

### For COMPUTE Nodes:
```
node_{name}_compute/v1_0_0/
├── node.py                          # Main implementation (renamed from compute.py)
├── config.py                        # Configuration wrapper class
├── contracts/
│   ├── compute_contract.py         # Python contract (NEW)
│   └── subcontracts/
│       ├── input_subcontract.yaml
│       ├── output_subcontract.yaml
│       └── config_subcontract.yaml
├── models/
│   ├── __init__.py
│   ├── model_{name}_compute_input.py      # Separated
│   ├── model_{name}_compute_output.py     # Separated
│   └── model_{name}_compute_config.py     # Separated
├── enums/
│   ├── __init__.py
│   └── enum_{name}_operation_type.py
├── utils/
│   ├── __init__.py
│   └── {name}_helper.py
└── manifest.yaml                    # Node metadata (NEW)
```

### For EFFECT Nodes:
```
node_{name}_effect/v1_0_0/
├── node.py                          # Main implementation (renamed from effect.py)
├── config.py                        # Configuration wrapper class
├── contracts/
│   ├── effect_contract.py          # Python contract (NEW)
│   └── subcontracts/
│       ├── input_subcontract.yaml
│       ├── output_subcontract.yaml
│       └── config_subcontract.yaml
├── models/
│   ├── __init__.py
│   ├── model_{name}_effect_input.py
│   ├── model_{name}_effect_output.py
│   └── model_{name}_effect_config.py
├── enums/
│   ├── __init__.py
│   └── enum_{name}_operation_type.py
├── utils/
│   ├── __init__.py
│   └── {name}_helper.py
└── manifest.yaml
```

---

## Migration Checklist (Per Node)

### Phase 1: Create New Structure
- [ ] Create `models/` subdirectories
- [ ] Create `enums/` subdirectory
- [ ] Create `utils/` subdirectory
- [ ] Create `contracts/subcontracts/` subdirectory

### Phase 2: Separate Models
- [ ] Extract input model to `models/model_{name}_{type}_input.py`
- [ ] Extract output model to `models/model_{name}_{type}_output.py`
- [ ] Extract config model to `models/model_{name}_{type}_config.py`
- [ ] Update `models/__init__.py` to export all models
- [ ] Add correlation_id: UUID field to input models
- [ ] Add processing_time_ms: float field to output models

### Phase 3: Create Python Contract
- [ ] Create `contracts/{type}_contract.py` (Python, not YAML)
- [ ] Inherit from `ModelContractBase`
- [ ] Define node metadata (name, version, description, type)
- [ ] Define model specifications (input, output, config)
- [ ] Define subcontract references
- [ ] Define capabilities list
- [ ] Define performance requirements
- [ ] Define dependencies
- [ ] Implement `validate_node_specific_config()` method

### Phase 4: Create YAML Subcontracts
- [ ] Create `subcontracts/input_subcontract.yaml`
  - Define required/optional fields
  - Define validation rules
  - Define field constraints
- [ ] Create `subcontracts/output_subcontract.yaml`
  - Define required/optional fields
  - Define performance guarantees
  - Define result confidence rules
- [ ] Create `subcontracts/config_subcontract.yaml`
  - Define configuration fields
  - Define environment profiles (production/staging/development)
  - Define validation rules

### Phase 5: Create Enums
- [ ] Create `enums/enum_{name}_operation_type.py`
- [ ] Define operation type enum values
- [ ] Add helper methods (is_computational, is_system, etc.)
- [ ] Update `enums/__init__.py`

### Phase 6: Create Utilities
- [ ] Create `utils/{name}_helper.py`
- [ ] Add utility functions (cache key generation, validation, etc.)
- [ ] Update `utils/__init__.py`

### Phase 7: Create Config Wrapper
- [ ] Create `config.py`
- [ ] Wrap the config model
- [ ] Add `for_environment()` class method
- [ ] Add `default()` class method
- [ ] Add config validation methods
- [ ] Add convenience methods

### Phase 8: Create Manifest
- [ ] Create `manifest.yaml`
- [ ] Define node classification
- [ ] Define performance specifications (latency, throughput, memory)
- [ ] Define reliability specifications (availability, error rates)
- [ ] Define resource requirements (CPU, memory, disk, network)
- [ ] Define security specifications
- [ ] Define dependencies (Python version, packages)
- [ ] Define testing specifications
- [ ] Define monitoring metrics and health checks
- [ ] Define operational metadata
- [ ] Define deployment specifications

### Phase 9: Update Node Implementation
- [ ] Rename `{type}.py` to `node.py`
- [ ] Update imports to use separated model files
- [ ] Add performance tracking (_request_count, _cache_hits, etc.)
- [ ] Add `get_performance_metrics()` method
- [ ] Add `health_check()` method
- [ ] Add proper error handling with ModelOnexError
- [ ] Add input validation method
- [ ] Update process() method with metrics tracking

### Phase 10: Update Exports
- [ ] Update `v1_0_0/__init__.py` to export all components
- [ ] Export Node class
- [ ] Export all model classes
- [ ] Export config class
- [ ] Export enum classes
- [ ] Export contract class
- [ ] Update parent `__init__.py` if needed

### Phase 11: Remove Old Files
- [ ] Delete old `{type}.py` file (after creating node.py)
- [ ] Delete old YAML main contract (keep Python contract only)
- [ ] Clean up any deprecated files

---

## Reference Implementation: vectorization_compute

See `/src/omniintelligence/nodes/vectorization_compute/v1_0_0/` for the complete reference implementation.

### Key Files Created:

**Models (3 files):**
- `models/model_vectorization_compute_input.py`
- `models/model_vectorization_compute_output.py`
- `models/model_vectorization_compute_config.py`

**Contract (1 Python + 3 YAML):**
- `contracts/compute_contract.py` (Python main contract)
- `contracts/subcontracts/input_subcontract.yaml`
- `contracts/subcontracts/output_subcontract.yaml`
- `contracts/subcontracts/config_subcontract.yaml`

**Enums (1 file):**
- `enums/enum_vectorization_operation_type.py`

**Utils (1 file):**
- `utils/vectorization_helper.py`

**Core Files:**
- `node.py` (main implementation, 250+ lines)
- `config.py` (configuration wrapper)
- `manifest.yaml` (metadata)

**Total:** 14 new files created, 1 file removed (compute.py)

---

## Code Templates

### Python Contract Template (COMPUTE)

```python
"""
Python Contract for {NodeName} Compute Node
"""

from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List


class {NodeName}ComputeContract(ModelContractBase):
    """Contract for {node_name} compute node."""

    # Core identification
    name: str = "{node_name}_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "{Description of what this node does}"
    node_type: EnumNodeType = EnumNodeType.COMPUTE

    # Model specifications
    input_model: str = "Model{NodeName}ComputeInput"
    output_model: str = "Model{NodeName}ComputeOutput"
    config_model: str = "Model{NodeName}ComputeConfig"

    # Subcontract references
    subcontracts: dict = Field(
        default={
            "input": "./subcontracts/input_subcontract.yaml",
            "output": "./subcontracts/output_subcontract.yaml",
            "config": "./subcontracts/config_subcontract.yaml",
        }
    )

    # Node capabilities
    capabilities: List[str] = Field(
        default=[
            # List capabilities
        ]
    )

    # Performance requirements
    performance_requirements: dict = Field(
        default={
            "max_latency_ms": 5000,
            "max_memory_mb": 512,
            "min_throughput_per_second": 20,
        }
    )

    # Dependencies
    dependencies: List[str] = Field(default=[])
    external_services: List[str] = Field(default=[])

    def validate_node_specific_config(self) -> None:
        """Validate node-specific configuration."""
        pass
```

### Config Wrapper Template

```python
"""
Configuration for {NodeName} {Type} Node
"""

from typing import Literal
from .models import Model{NodeName}{Type}Config


class {NodeName}{Type}Config:
    """Configuration wrapper for {node_name} {type} operations."""

    def __init__(self, config: Model{NodeName}{Type}Config):
        """Initialize configuration."""
        self.config = config
        self._validate_config()

    @classmethod
    def for_environment(
        cls,
        env: Literal["production", "staging", "development"]
    ) -> "{NodeName}{Type}Config":
        """Create environment-specific configuration."""
        config = Model{NodeName}{Type}Config.for_environment(env)
        return cls(config)

    @classmethod
    def default(cls) -> "{NodeName}{Type}Config":
        """Create default configuration for production."""
        return cls.for_environment("production")

    def _validate_config(self) -> None:
        """Validate configuration constraints."""
        # Add validation logic
        pass
```

---

## Automated Migration Script Template

```python
#!/usr/bin/env python3
"""
Automated migration script for omnibase_core template compliance.

Usage:
    python scripts/migrate_node.py <node_name> <node_type>

Example:
    python scripts/migrate_node.py entity_extraction compute
"""

import sys
import os
from pathlib import Path

def migrate_node(node_name: str, node_type: str):
    """Migrate a single node to official template structure."""

    node_dir = Path(f"src/omniintelligence/nodes/{node_name}_{node_type}/v1_0_0")

    # 1. Create directories
    (node_dir / "models").mkdir(exist_ok=True)
    (node_dir / "enums").mkdir(exist_ok=True)
    (node_dir / "utils").mkdir(exist_ok=True)
    (node_dir / "contracts/subcontracts").mkdir(parents=True, exist_ok=True)

    # 2. Extract and separate models
    # ... (implementation needed)

    # 3. Create Python contract
    # ... (implementation needed)

    # 4. Create YAML subcontracts
    # ... (implementation needed)

    # 5. Create enums
    # ... (implementation needed)

    # 6. Create utils
    # ... (implementation needed)

    # 7. Create config wrapper
    # ... (implementation needed)

    # 8. Create manifest
    # ... (implementation needed)

    # 9. Update node implementation
    # ... (implementation needed)

    # 10. Update exports
    # ... (implementation needed)

    print(f"✅ Migrated {node_name}_{node_type}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python migrate_node.py <node_name> <node_type>")
        sys.exit(1)

    migrate_node(sys.argv[1], sys.argv[2])
```

---

## Next Steps

1. **Review vectorization_compute** as the reference implementation
2. **Use this migration guide** to systematically migrate remaining nodes
3. **Test each migrated node** to ensure functionality is preserved
4. **Update imports** in dependent code as needed
5. **Document any deviations** from the template where necessary

---

## Notes

- **Python contracts** are preferred over YAML main contracts (per official template)
- **YAML subcontracts** are still used for organized configuration
- **manifest.yaml** is required for all nodes (per official template)
- **Separated model files** improve modularity and testability
- **Config wrappers** provide environment-specific configurations
- **Performance tracking** is built into all nodes
- **Health checks** are required for production deployments

---

## Questions or Issues?

- Review official templates: https://github.com/OmniNode-ai/omnibase_core/blob/main/docs/reference/templates/
- Check node building guide: https://github.com/OmniNode-ai/omnibase_core/blob/main/docs/guides/node-building/
- Reference vectorization_compute implementation

---

**Migration Progress:** 1/14 nodes complete (7%)
**Last Updated:** 2025-11-16
