# Common ONEX Standards and Requirements

**MANDATORY**: All ONEX agents must enforce these standards consistently across all operations.

## Quick Reference Navigation
- [Tool Usage](#critical-onex-tool-usage-requirements) • [Typing Standards](#typing-standards) • [Architecture](#four-node-architecture)
- [Error Handling](#error-handling-standards) • [File Management](#file-organization) • [Quality Gates](#quality-requirements)

---

## 🔧 Quick Standards Reference

### Essential ONEX Patterns
- **✅ ONEX CLI**: `onex run {tool_name} --{action}` (primary)
- **✅ Sub-Agent**: `> Use agent-{specialist} to {task}` (delegation)
- **✅ Strong Typing**: Never use `Any` - Always specific Pydantic models
- **✅ Node Classification**: COMPUTE/EFFECT/ORCHESTRATOR/REDUCER
- **✅ OnexError**: Convert all exceptions to OnexError with chaining

### Forbidden Anti-Patterns
- **❌ `Any` types** (use specific types always)
- **❌ Hand-written Pydantic models** (generate from contracts)
- **❌ Manual tool combinations** (use proper agent delegation)
- **❌ isinstance checks** (use protocol resolution instead)

## Critical ONEX Tool Usage Requirements

### ALWAYS Use These Patterns
- **ONEX CLI FORMAT**: Primary method, manual Poetry as fallback if CLI broken
  ```bash
  # ✅ PRIMARY - Use ONEX CLI
  onex run {tool_name} --{action} {parameters}

  # ⚠️ FALLBACK ONLY - If ONEX CLI is broken
  poetry run python -m omnibase.tools.{domain}.{tool_name}.v1_0_0.node
  ```

- **Sub-Agent Delegation**: Use official Claude Code sub-agent invocation
  ```bash
  # ✅ CORRECT - Official Claude Code pattern
  > Use the {specialist}-agent to {perform_task}

  # ❌ AVOID - Manual tool combinations
  "Run tool X then tool Y then check Z"
  ```

- **Strong Typing**: ZERO tolerance for `Any` types in all ONEX code
  ```python
  # ✅ REQUIRED
  def process_data(data: ModelDataSchema) -> ModelProcessingResults:

  # ❌ ABSOLUTELY FORBIDDEN
  def process_data(data: Any) -> Any:
  ```

- **OnexError with Exception Chaining**: All ONEX exceptions must be properly chained
  ```python
  # ✅ REQUIRED
  try:
      result = process_operation(data)
  except ProcessingError as e:
      raise OnexError(
          code=CoreErrorCode.PROCESSING_ERROR,
          message=f"Operation failed for {context}",
          details={"context": context, "error": str(e)}
      ) from e
  ```

### NEVER Do These Things
- **NEVER use `Any` types**: All ONEX code must be strongly typed
- **NEVER bypass ONEX patterns**: Always follow contract-driven architecture
- **NEVER use manual Poetry as primary**: Always try ONEX CLI first
- **NEVER skip exception chaining**: Always use `from e` for OnexError
- **NEVER include AI attribution**: All outputs are professional human work

## Four-Node Architecture Standards

### Node Type Requirements

#### COMPUTE Nodes
- **Stateless logic processing only**
- **Algorithm specification required**
- **Performance constraints mandatory**
- **Example**: `{{project_root}}_4/src/omnibase/tools/infrastructure/tool_kafka_wrapper/v1_0_0/`

#### EFFECT Nodes  
- **Side effect operations only**
- **External system interactions**
- **State modification operations**
- **Example**: `{{project_root}}_4/src/omnibase/tools/docker/tool_docker_template_generator_effect/v1_0_0/`

#### ORCHESTRATOR Nodes
- **Workflow coordination only**
- **Multi-component orchestration**
- **Decision-making logic**
- **Example**: `{{project_root}}_4/src/omnibase/tools/infrastructure/tool_infrastructure_orchestrator/v1_0_0/`

#### REDUCER Nodes
- **State aggregation only**
- **Data reduction operations**
- **Result consolidation**
- **Example**: `{{project_root}}_4/src/omnibase/tools/docker/tool_docker_infrastructure_reducer/v1_0_0/`

### Architecture Validation Rules
1. **Single node type per tool** - no hybrid nodes allowed
2. **Clear separation of concerns** - each node has distinct responsibilities
3. **Canonical pattern compliance** - must match reference implementations
4. **Contract-driven validation** - all nodes validated against contracts

## ONEX Development Patterns

### Model Standards
- **CamelCase Models**: All model classes use `ModelDataName` format
- **snake_case Files**: All filenames use `model_data_name.py` format
- **One Model Per File**: Each file contains exactly one `Model*` class
- **Pydantic Models Only**: All data structures must be proper Pydantic models

### Registry & Injection Standards
- **Registry Injection**: All dependencies injected via registry
  ```python
  def __init__(self, registry: BaseOnexRegistry):
  ```
- **Protocol Resolution**: Use duck typing through protocols, never isinstance
- **No Direct Imports**: Use registry pattern for dependency management
- **Container Integration**: All tools integrate with ONEXContainer

### Error Handling Standards
- **OnexError Only**: All exceptions converted to OnexError with chaining
- **Proper Error Codes**: Use CoreErrorCode enumeration
- **Context Preservation**: Include relevant context in error details
- **Chain Original Exceptions**: Always use `from e` for exception chaining

### Contract-Driven Development
- **Contract First**: All tools/services follow contract patterns
- **Schema Validation**: All contracts validated against ONEX schema
- **Generated Models**: Prefer contract-generated over hand-written models
- **Standards Compliance**: All contracts must meet ONEX compliance requirements

## Quality Gate Requirements

### Pre-Development Gates
- **Work Ticket Analysis**: Must analyze active work tickets before proceeding
- **Canonical Reference Validation**: Must compare against canonical patterns
- **Architecture Compliance**: Must align with four-node architecture
- **Contract Validation**: Must validate contract compliance if applicable

### During Development Gates
- **File-by-File Validation**: Must validate each file against canonical patterns
- **Atomic Changes**: Complete validation before proceeding to next file
- **Duplicate Detection**: Use OnexTree system to prevent duplicate files
- **Type Safety Validation**: Ensure no `Any` types introduced

### Post-Development Gates
- **Comprehensive Testing**: All critical paths must be tested
- **Standards Compliance**: Must pass all ONEX standards validation
- **Performance Validation**: Must meet performance requirements
- **Integration Testing**: Must validate integration points

## Legacy Pattern Detection

### Automatic Detection Required
- **Any Types**: Identify and flag usage of Any types
- **Manual Imports**: Detect direct imports instead of registry injection
- **Outdated Patterns**: Identify patterns from deprecated eras
- **Legacy Error Handling**: Detect non-OnexError exception patterns

### Modernization Requirements
- **Registry Migration**: Convert manual imports to registry-based injection
- **Protocol Adoption**: Migrate concrete types to protocol-based interfaces
- **Contract-Driven Updates**: Update hand-written patterns to contract-generated
- **Error Handling Modernization**: Migrate to OnexError with proper chaining

### Standards Evolution Tracking
- **Pattern Currency Analysis**: Evaluate patterns against current standards
- **Deprecation Warnings**: Flag patterns scheduled for deprecation
- **Migration Pathways**: Provide specific modernization steps
- **Quality Improvement**: Track quality gains from modernization

## Collaboration Standards

### Agent Coordination
- **Specialist Delegation**: Route complex tasks to appropriate specialists
- **Context Preservation**: Maintain context across agent handoffs
- **Quality Validation**: Cross-validate outputs with other agents
- **Failure Recovery**: Handle agent failures gracefully

### Tool Integration
- **ONEX CLI Priority**: Always try ONEX CLI before fallback methods
- **Contract Validation**: Validate all tool interactions against contracts
- **Registry Resolution**: Use registry for tool discovery and instantiation
- **Error Propagation**: Properly propagate errors through tool chains

### Knowledge Integration
- **RAG Intelligence**: Use RAG queries for historical patterns
- **Continuous Learning**: Capture successful patterns for knowledge base
- **Pattern Sharing**: Share effective patterns across agent ecosystem
- **Intelligence Quality**: Maintain high-quality intelligence integration

## Validation Scripts (To Be Created)

### Required Validation Tools
- `validate-file-canonical.py`: Compare files against canonical patterns
- `detect-duplicates-onextree.py`: Use OnexTree for duplicate detection
- `validate-contract-compliance.py`: Ensure contract standards compliance
- `validate-onex-standards.py`: Comprehensive ONEX standards validation

### Validation Requirements
- **Atomic Validation**: Run after each file modification
- **Canonical Compliance**: Validate against reference implementations
- **Architecture Alignment**: Ensure four-node architecture compliance
- **Standards Evolution**: Check for deprecated patterns and modernization opportunities

---

**Remember**: These standards are non-negotiable. All agents must enforce these requirements consistently to maintain ONEX system integrity and quality.
