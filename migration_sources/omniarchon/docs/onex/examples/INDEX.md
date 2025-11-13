# ONEX Canonical Examples - Complete Index

## 📖 Documentation Files

| File | Purpose | Lines |
|------|---------|-------|
| **README.md** | Comprehensive documentation with all patterns explained | Full guide |
| **QUICKSTART.md** | Quick start guide and validation results | Quick reference |
| **INDEX.md** | This file - complete file listing | Navigation |

## 🎯 Core Files

### Canonical Effect Node
- **nodes/v1_0_0/node_database_writer_effect.py** (1,321 lines)
  - THE canonical reference implementation
  - Merges base infrastructure + canary business logic
  - Demonstrates all 15 canonical patterns
  - Production-ready with comprehensive documentation

## 📜 Contract Models

### Base Contract
- **contracts/model_contract_base.py**
  - Abstract foundation for all node contracts
  - Pydantic BaseModel with strong typing
  - Common fields: name, version, description, node_type
  - Performance requirements and lifecycle config
  - Dependency management and validation rules

### Specialized Contracts
- **contracts/specialized/model_contract_effect.py**
  - Effect node contract for side effects and I/O
  - I/O operations, transaction management
  - Retry policies, circuit breaker configuration
  - External service integrations

- **contracts/specialized/model_contract_compute.py**
  - Compute node contract for pure functions
  - Algorithm configuration and parameters
  - Parallel processing configuration
  - Caching strategies

- **contracts/specialized/model_contract_reducer.py**
  - Reducer node contract for aggregation
  - State management and persistence
  - Snapshot and recovery strategies

- **contracts/specialized/model_contract_orchestrator.py**
  - Orchestrator node contract for workflow coordination
  - Routing and dependency management
  - Workflow stages and parallel execution

## 🔧 Subcontract Models

### Infrastructure Patterns (Composition)
- **contracts/subcontracts/model_fsm_subcontract.py**
  - Finite State Machine functionality
  - State definitions with entry/exit actions
  - Transition specifications with conditions
  - Operation definitions with permissions

- **contracts/subcontracts/model_event_type_subcontract.py**
  - Event-driven architecture functionality
  - Event definitions with categories and routing
  - Event transformation and filtering rules
  - Event persistence and replay configuration

- **contracts/subcontracts/model_aggregation_subcontract.py**
  - Aggregation patterns for Reducer nodes
  - Window configurations (time-based, count-based)
  - Grouping and partitioning rules

- **contracts/subcontracts/model_state_management_subcontract.py**
  - State persistence and management
  - Snapshot and recovery strategies
  - Consistency guarantees

- **contracts/subcontracts/model_routing_subcontract.py**
  - Message routing for Orchestrator nodes
  - Load balancing policies
  - Circuit breaker integration

- **contracts/subcontracts/model_caching_subcontract.py**
  - Performance optimization through caching
  - Cache strategies (LRU, LFU, TTL)
  - Eviction policies and invalidation rules

## 📊 Type Definitions

### Pydantic Models (from canary)
Located in `types/` directory:
- **enum_canary_impure_action.py** - Action type enumerations
- **model_audit_entry.py** - Audit log entry model
- **model_audit_metadata.py** - Audit metadata model
- **model_http_headers.py** - HTTP header model
- **model_http_request_body.py** - HTTP request body model
- **model_input_state.py** - Input state model
- **model_operation_metadata.py** - Operation metadata model
- **model_operation_parameters.py** - Operation parameters model
- **model_output_field.py** - Output field model
- **model_output_state.py** - Output state model
- **model_request_body.py** - Request body model
- **model_security_assessment_result.py** - Security assessment model

## 📄 Manifest Files (3-Tier Configuration)

### Tier 1: Interface Definition
- **manifests/contract.yaml**
  - Node interface and API contract
  - Input/output model specifications
  - Performance requirements
  - Dependencies and protocols

### Tier 2: Runtime Configuration
- **manifests/node_config.yaml**
  - Feature flags and behavior settings
  - Retry policies and circuit breaker thresholds
  - Logging levels and resource limits
  - Runtime-specific configuration

### Tier 3: Deployment Settings
- **manifests/deployment_config.yaml**
  - Environment-specific settings
  - Resource allocation (CPU, memory)
  - Scaling policies and health checks
  - Monitoring and observability configuration

## 🗂️ Directory Structure

```
onex_canonical_examples/
├── nodes/
│   └── v1_0_0/
│       └── node_database_writer_effect.py  ← THE canonical node (1,321 lines)
├── contracts/
│   ├── model_contract_base.py              ← Base (all inherit)
│   ├── specialized/                         ← 4 specialized contracts
│   │   ├── model_contract_effect.py
│   │   ├── model_contract_compute.py
│   │   ├── model_contract_reducer.py
│   │   └── model_contract_orchestrator.py
│   └── subcontracts/                        ← 6 subcontracts
│       ├── model_fsm_subcontract.py
│       ├── model_event_type_subcontract.py
│       ├── model_aggregation_subcontract.py
│       ├── model_state_management_subcontract.py
│       ├── model_routing_subcontract.py
│       └── model_caching_subcontract.py
├── types/                                   ← 13 Pydantic models
│   ├── enum_canary_impure_action.py
│   ├── model_audit_entry.py
│   ├── model_http_headers.py
│   └── ... (10 more models)
├── manifests/                               ← 3-tier config
│   ├── contract.yaml
│   ├── node_config.yaml
│   └── deployment_config.yaml
├── README.md                                ← Full documentation
├── QUICKSTART.md                            ← Quick reference
└── INDEX.md                                 ← This file
```

## 📊 Statistics

| Category | Count | Description |
|----------|-------|-------------|
| **Total Files** | 29 | Python + YAML files |
| **Canonical Nodes** | 1 | Production-ready Effect node |
| **Contract Models** | 5 | Base + 4 specialized |
| **Subcontract Models** | 6 | Infrastructure patterns |
| **Type Definitions** | 13 | Pydantic models + Enums |
| **Manifest Files** | 3 | 3-tier configuration |
| **Documentation** | 3 | README, QUICKSTART, INDEX |
| **Total Lines** | 1,321 | Canonical Effect node |

## 🎯 Primary Entry Points

### For Learning
1. **Start here:** `QUICKSTART.md` - Quick reference
2. **Deep dive:** `README.md` - Comprehensive guide
3. **Code study:** `nodes/v1_0_0/node_database_writer_effect.py` - THE example

### For Implementation
1. **Copy canonical node:** `nodes/v1_0_0/node_database_writer_effect.py`
2. **Study contracts:** `contracts/specialized/model_contract_effect.py`
3. **Review subcontracts:** `contracts/subcontracts/` (as needed)
4. **Configure manifests:** `manifests/` (3-tier system)

### For Reference
1. **Contract base:** `contracts/model_contract_base.py`
2. **Type system:** `types/` directory
3. **Patterns:** Search "CANONICAL PATTERN:" in canonical node
4. **Examples:** Inline docstrings in canonical node

## 🔍 Search Guide

### Find Specific Patterns

```bash
# Container injection pattern
grep -n "ONEXContainer" nodes/v1_0_0/node_database_writer_effect.py

# Transaction management
grep -n "class Transaction" nodes/v1_0_0/node_database_writer_effect.py

# Circuit breaker
grep -n "class CircuitBreaker" nodes/v1_0_0/node_database_writer_effect.py

# Retry logic
grep -n "_execute_with_retry" nodes/v1_0_0/node_database_writer_effect.py

# All canonical patterns
grep -n "CANONICAL PATTERN:" nodes/v1_0_0/node_database_writer_effect.py
```

### Find Contract Examples

```bash
# Effect contract
cat contracts/specialized/model_contract_effect.py

# FSM subcontract
cat contracts/subcontracts/model_fsm_subcontract.py

# Event subcontract
cat contracts/subcontracts/model_event_type_subcontract.py
```

## 📚 Related Documentation

### External References
- **ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md** - Full architecture guide
- **PHASE_1_IMPLEMENTATION_PLAN.md** - Implementation roadmap
- **PHASE_1_QUICKSTART.md** - Quick start guide

### Inline Documentation
- Every file has comprehensive docstrings
- Search for "CANONICAL PATTERN:" for key patterns
- Read lines 1-200 of canonical node for overview
- Check method docstrings for detailed explanations

---

**Navigation Tips:**
1. Start with `QUICKSTART.md` for quick reference
2. Read `README.md` for comprehensive documentation
3. Study canonical node for implementation details
4. Use this index to find specific files

**Key Files:**
- **THE canonical node:** `nodes/v1_0_0/node_database_writer_effect.py`
- **Quick reference:** `QUICKSTART.md`
- **Full guide:** `README.md`
