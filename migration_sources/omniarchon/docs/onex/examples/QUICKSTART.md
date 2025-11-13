# ONEX Canonical Examples - Quick Start Guide

## 🎯 What You Have

ONE perfect, production-ready canonical Effect node that merges ALL patterns:
- **Location:** `nodes/v1_0_0/node_database_writer_effect.py`
- **Size:** 1,321 lines
- **Patterns:** 15 canonical patterns fully documented

## ✅ Validation Results

### Naming Conventions
- ✅ Class: `NodeDatabaseWriterEffect` (NOT `Tool*`)
- ✅ File: `node_database_writer_effect.py` (NOT `tool_*`)
- ✅ Inherits: `NodeEffect` (4-node architecture)
- ✅ Container: `ONEXContainer` injection
- ✅ Models: All Pydantic `BaseModel`

### Files Created
- **Total:** 29 files (Python + YAML)
- **Contracts:** 5 files (base + 4 specialized)
- **Subcontracts:** 6 files (FSM, Event, Aggregation, State, Routing, Caching)
- **Types:** 13 Pydantic models from canary
- **Manifests:** 3 YAML files (contract, node_config, deployment_config)
- **Nodes:** 1 canonical Effect node

## 📁 Directory Structure

```
onex_canonical_examples/
├── nodes/v1_0_0/
│   └── node_database_writer_effect.py    ← START HERE (1,321 lines)
├── contracts/
│   ├── model_contract_base.py            ← All nodes inherit
│   ├── specialized/
│   │   ├── model_contract_effect.py
│   │   ├── model_contract_compute.py
│   │   ├── model_contract_reducer.py
│   │   └── model_contract_orchestrator.py
│   └── subcontracts/
│       ├── model_fsm_subcontract.py
│       ├── model_event_type_subcontract.py
│       ├── model_aggregation_subcontract.py
│       ├── model_state_management_subcontract.py
│       ├── model_routing_subcontract.py
│       └── model_caching_subcontract.py
├── types/
│   └── [13 Pydantic models and Enums]
├── manifests/
│   ├── contract.yaml                      ← Tier 1: Interface
│   ├── node_config.yaml                   ← Tier 2: Runtime
│   └── deployment_config.yaml             ← Tier 3: Infrastructure
└── README.md                              ← Full documentation
```

## 🚀 Quick Usage

### 1. Study the Canonical Node

```bash
# Open the canonical Effect node
vim nodes/v1_0_0/node_database_writer_effect.py

# Key sections to understand:
# - Lines 1-200: Documentation and imports
# - Lines 201-400: Enum and type definitions
# - Lines 401-600: Input/Output models (Pydantic)
# - Lines 601-800: Infrastructure classes (Transaction, CircuitBreaker)
# - Lines 801-1321: Main NodeDatabaseWriterEffect class
```

### 2. Create Your Own Effect Node

```bash
# Copy the canonical node
cp nodes/v1_0_0/node_database_writer_effect.py \
   nodes/v1_0_0/node_my_operation_effect.py

# Update:
# 1. Class name: NodeMyOperationEffect
# 2. Operation handlers in _execute_effect()
# 3. Validation rules in validate_input()
# 4. Security assessment in assess_security_risk()
```

### 3. Key Patterns to Keep

**ALWAYS keep these infrastructure patterns:**
- ✅ Container injection
- ✅ Transaction management with rollback
- ✅ Circuit breaker for external services
- ✅ Retry logic with exponential backoff
- ✅ Input validation with errors/warnings
- ✅ Security risk assessment
- ✅ Performance metrics tracking
- ✅ Structured logging with correlation IDs
- ✅ OnexError for exceptions
- ✅ Pydantic models for all data

**Customize these business logic patterns:**
- Operation handlers (file, HTTP, database, etc.)
- Validation rules (operation-specific)
- Security checks (risk assessment)
- Rollback instructions (operation-specific)

## 📚 15 Canonical Patterns

The canonical Effect node demonstrates these essential patterns:

1. **Container Injection** - ONEXContainer for dependency injection
2. **Transaction Management** - Rollback support with LIFO order
3. **Circuit Breaker** - Prevent cascading failures (CLOSED/OPEN/HALF_OPEN)
4. **Retry Logic** - Exponential backoff with jitter
5. **Security Assessment** - Path traversal detection, sandbox compliance
6. **Multiple Operations** - File, HTTP, database, email, audit handlers
7. **Input Validation** - Comprehensive with errors AND warnings
8. **Performance Metrics** - Per-operation timing and success rates
9. **Strong Typing** - Pydantic BaseModel + Python Enum (NO plain classes)
10. **Rollback Instructions** - Human-readable recovery steps
11. **Contract Loading** - YAML contracts with Pydantic validation
12. **Error Handling** - OnexError with structured details
13. **Structured Logging** - emit_log_event with correlation IDs
14. **Async Context Managers** - Resource cleanup with RAII
15. **Semaphore Concurrency** - Prevent resource exhaustion

## 🎓 Learning Path

### Day 1: Understand Infrastructure
- Read lines 1-800 of canonical node
- Study Transaction, CircuitBreaker classes
- Understand retry logic and exponential backoff

### Day 2: Study Business Logic
- Read lines 801-1321 of canonical node
- Understand operation routing in _execute_effect()
- Study input validation and security assessment

### Day 3: Create Your First Node
- Copy canonical node
- Modify for your use case
- Keep infrastructure, customize business logic

## 🔍 Source Attribution

| Pattern | Source File | Lines |
|---------|------------|-------|
| Base Infrastructure | `/Volumes/PRO-G40/Code/omnibase_core/archived/src/omnibase_core/core/node_effect.py` | 1,497 lines |
| Business Logic | `/Volumes/PRO-G40/Code/omnibase_3/src/omnibase/tools/canary/canary_impure_tool/v1_0_0/node.py` | 752 lines |
| **Canonical Merge** | **`nodes/v1_0_0/node_database_writer_effect.py`** | **1,321 lines** |

## ✅ Validation Checklist

Before using your Effect node in production:

- [ ] Class named `Node<Name>Effect`
- [ ] File named `node_*_effect.py`
- [ ] Inherits from `NodeEffect`
- [ ] Container injection implemented
- [ ] Transaction management with rollback
- [ ] Circuit breaker for external calls
- [ ] Retry logic with exponential backoff
- [ ] Input validation with errors/warnings
- [ ] Security assessment implemented
- [ ] Performance metrics tracked
- [ ] All data uses Pydantic BaseModel
- [ ] All enums use Python Enum
- [ ] OnexError for all exceptions
- [ ] Structured logging implemented
- [ ] Comprehensive docstrings
- [ ] Unit tests with 80%+ coverage

## 🎯 Next Steps

1. **Read the canonical node:** `nodes/v1_0_0/node_database_writer_effect.py`
2. **Study the contracts:** `contracts/specialized/model_contract_effect.py`
3. **Review subcontracts:** `contracts/subcontracts/model_fsm_subcontract.py`
4. **Create your node:** Copy and customize the canonical example
5. **Test thoroughly:** Transaction, circuit breaker, retry, security

## 📞 Support

For questions:
- **Full Documentation:** `README.md` (comprehensive guide)
- **Canonical Node:** Lines 1-200 have extensive documentation
- **Inline Comments:** Every method is documented
- **Examples:** Search for "CANONICAL PATTERN:" in the code

---

**Remember:** The canonical Effect node is your template. Copy it, understand it, adapt it to your needs. ALL infrastructure patterns should be kept intact.
