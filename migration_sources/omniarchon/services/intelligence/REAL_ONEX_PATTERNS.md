# Real ONEX Compliance Patterns

**Source**: Analyzed from `/Volumes/PRO-G40/Code/omnibase_core`
**Date**: 2025-10-14

## 1. Container & Dependency Injection

### ✅ Correct
```python
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

class MyNode(NodeEffect):
    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        self.container = container
```

### ❌ Wrong
```python
container: ONEXContainer  # Wrong! It's ModelONEXContainer
container: ONEXRegistry  # Wrong naming
```

## 2. Error Handling

### ✅ Correct
```python
from omnibase_core.errors import OnexError
from omnibase_core.errors.error_codes import CoreErrorCode

raise OnexError(
    code=CoreErrorCode.OPERATION_FAILED,
    message="Operation failed",
    context={"node_id": str(self.node_id)},
    correlation_id=correlation_id,
)
```

### ❌ Wrong
```python
raise Exception("error")  # Generic exceptions
raise ValueError("error")  # Non-ONEX errors
```

## 3. Logging

### ✅ Correct
```python
from omnibase_core.logging.structured import emit_log_event_sync as emit_log_event
from omnibase_core.enums.enum_log_level import EnumLogLevel as LogLevel

emit_log_event(
    LogLevel.INFO,
    "Operation completed",
    {
        "node_id": str(self.node_id),
        "duration_ms": duration_ms,
    },
)
```

### ❌ Wrong
```python
print("logging")  # No print statements
logger.info()  # No direct logger usage
```

## 4. Node Types

### ✅ Correct
```python
from omnibase_core.infrastructure.node_base import NodeBase
from omnibase_core.infrastructure.node_effect import NodeEffect
from omnibase_core.infrastructure.node_compute import NodeCompute

class MyEffect(NodeEffect):
    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
```

### ❌ Wrong
```python
class MyTool:  # Not inheriting from Node types
    pass
```

## 5. Model Naming Conventions

### ✅ Correct
```python
class ModelUserData(BaseModel):
    user_id: str
    email: str

class ModelEffectInput(BaseModel):
    effect_type: EnumEffectType
    operation_data: dict[str, ModelSchemaValue]
```

### ❌ Wrong
```python
class UserData(BaseModel):  # Missing "Model" prefix
    pass

class myModel(BaseModel):  # Non-CamelCase
    pass
```

## 6. Protocols (from omnibase-spi)

### ✅ Correct
```python
from omnibase_spi import ProtocolLogger
from omnibase_spi.protocols.xxx import ProtocolXXX
```

### ❌ Wrong
```python
from omnibase.protocols  # Wrong package
```

## 7. Contract-Driven Architecture

### ✅ Correct
```python
from pathlib import Path
from omnibase_core.utils.safe_yaml_loader import load_and_validate_yaml_model
from omnibase_core.models.contracts.model_contract_effect import ModelContractEffect

contract_model = load_and_validate_yaml_model(
    contract_path,
    ModelContractEffect,
)
```

### ❌ Wrong
```python
import yaml
with open("config.yaml") as f:  # Direct YAML loading
    config = yaml.safe_load(f)
```

## 8. Forbidden Patterns

### ❌ Critical (Auto-Reject, Score = 0.0)
```python
from typing import Any

def process(data: Any):  # Any types forbidden
    pass

class myservice:  # Non-CamelCase
    pass

import os  # Direct OS imports (should use container)
```

## 9. Architecture Eras

### Pre-NodeBase (Legacy)
```python
class UserTool:
    def main():
        parser = argparse.ArgumentParser()
```

### Early NodeBase
```python
class UserService(NodeBase):
    def __init__(self):
        super().__init__()
```

### Contract-Driven
```python
contract_path = Path("contract.yaml")
config = from_contract(CONTRACT_FILENAME)
```

### Modern ONEX (Current)
```python
class MyEffect(NodeEffect):
    def __init__(self, container: ModelONEXContainer) -> None:
        super().__init__(container)
        self.contract_model: ModelContractEffect = self._load_contract_model()
```

## 10. Key Imports Reference

```python
# Container
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Nodes
from omnibase_core.infrastructure.node_base import NodeBase
from omnibase_core.infrastructure.node_effect import NodeEffect
from omnibase_core.infrastructure.node_compute import NodeCompute
from omnibase_core.infrastructure.node_orchestrator import NodeOrchestrator
from omnibase_core.infrastructure.node_reducer import NodeReducer

# Errors
from omnibase_core.errors import OnexError
from omnibase_core.errors.error_codes import CoreErrorCode

# Logging
from omnibase_core.logging.structured import emit_log_event_sync as emit_log_event
from omnibase_core.enums.enum_log_level import EnumLogLevel as LogLevel

# Models
from omnibase_core.models.contracts.model_contract_effect import ModelContractEffect
from omnibase_core.models.common.model_schema_value import ModelSchemaValue

# Protocols (from omnibase-spi)
from omnibase_spi import ProtocolLogger

# Utilities
from omnibase_core.utils.safe_yaml_loader import load_and_validate_yaml_model
from pathlib import Path
```

## Summary

**Key Takeaways:**
1. **Container is `ModelONEXContainer`**, not `ONEXContainer`
2. **All models** start with `Model` prefix and use CamelCase
3. **Error handling** uses `OnexError` with `CoreErrorCode`
4. **Logging** uses `emit_log_event` from structured logging
5. **Nodes** inherit from `NodeBase`, `NodeEffect`, etc.
6. **No `Any` types**, no direct OS imports, no manual class instantiation
7. **Contract-driven** architecture with YAML contracts
8. **Protocols** imported from `omnibase_spi`
