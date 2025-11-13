# ONEX Anti-YOLO Method + BFROS Common Workflow

**MANDATORY**: All ONEX agents must read and follow this workflow before proceeding with actual work.

**🔗 CONTEXT INHERITANCE**: When delegating to other agents, always use @COMMON_CONTEXT_INHERITANCE.md protocols to prevent information loss.

**🔄 SMART CONTEXT MANAGEMENT**: Use @COMMON_CONTEXT_LIFECYCLE.md for intelligent context refresh and lifecycle management.

## Quick Reference Navigation
- [Core Methodology](#core-methodology) • [Work Ticket First](#work-ticket-first-principle) • [BFROS Framework](#bfros-framework-integration)
- [Architecture Diagrams](#ascii-architecture-diagrams-multi-node-interactions) • [Four-Node Validation](#four-node-architecture-enforcement) • [File Validation](#file-by-file-atomic-validation)
- [Anti-YOLO Process](#anti-yolo-systematic-approach) • [Error Recovery](#error-recovery-patterns) • [Success Metrics](#success-metrics)

---

## ⚡ Quick Start Checklist

### Before Starting Any Work (2 minutes)
1. **📋 Read active work ticket** - `/work_tickets/active/` for requirements
2. **🎯 Apply BFROS reasoning** - Work backwards from desired outcome
3. **📐 Create architecture diagram** - Visual system representation
4. **📋 Plan file-by-file sequence** - Atomic modification approach

### During Implementation (Per File)
1. **🔍 Identify node type** - COMPUTE/EFFECT/ORCHESTRATOR/REDUCER
2. **📖 Compare against canonical** - Validate pattern alignment
3. **✅ Atomic validation** - Complete validation before next file
4. **🧪 Incremental testing** - Test after each change

**🎯 Success Indicator**: Zero architectural drift + Zero duplicate files + Work ticket alignment

## Core Methodology

### Work Ticket First Principle
**BEFORE any work begins, agents MUST:**
1. **Read active work ticket** from `{{project_root}}_4/work_tickets/active/`
2. **Extract specific requirements** and constraints from the ticket
3. **Identify canonical references** mentioned in the ticket
4. **Validate ticket scope** matches the requested task

### BFROS Framework Integration
**Before implementing/fixing, reason backwards from the outcome or issue**

#### 🎯 Implementation BFROS Template
**Use this for new features or improvements:**
```yaml
bfros_implementation:
  desired_outcome: "What specific result do we want?"
  success_criteria: "How will we know we succeeded?"
  architectural_constraints: "What ONEX patterns must we follow?"
  canonical_references: "Which canonical files provide the pattern?"
  potential_pitfalls: "What could go wrong?"
  validation_strategy: "How will we verify correctness?"
```

#### 🔧 Debugging BFROS Template  
**Use this for fixing problems or investigating issues:**
```yaml
bfros_debugging:
  symptom_analysis: "What exactly is the observable problem?"
  root_cause_hypothesis: "What underlying issue could cause this?"
  four_node_compliance: "Does this align with COMPUTE/EFFECT/ORCHESTRATOR/REDUCER?"
  canonical_deviation: "Where might we have deviated from canonical patterns?"
  validation_failure: "What validation step did we miss?"
  correction_strategy: "How do we fix this systematically?"
```

**💡 BFROS Pro Tip**: Spend 90 seconds on reasoning to save 30 minutes of rework

## ASCII Architecture Diagrams (Multi-Node Interactions)

For tasks involving multiple node types, create ASCII diagrams:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  ORCHESTRATOR   │───▶│    COMPUTE      │───▶│     EFFECT      │
│  (Coordination) │    │ (Pure Logic)    │    │ (Side Effects)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    REDUCER      │◀───┤   Data Flow     │◀───┤    Output       │
│ (State Aggr.)   │    │   Processing    │    │   Generation    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Four-Node Architecture Enforcement

### Canonical Reference Files
**MUST validate against these patterns:**

#### 🔢 COMPUTE Nodes
**Path**: `/src/omnibase/tools/infrastructure/tool_kafka_wrapper/v1_0_0/`
- ✅ **Stateless logic processing**
- ✅ **Algorithm specification required**
- ✅ **Performance constraints mandatory**
- 🎯 **Use Case**: Pure calculation, data transformation, business logic

#### ⚡ EFFECT Nodes  
**Path**: `/src/omnibase/tools/docker/tool_docker_template_generator_effect/v1_0_0/`
- ✅ **Side effect operations**
- ✅ **External system interactions**
- ✅ **State modification operations**
- 🎯 **Use Case**: Database writes, API calls, file operations

#### 🎭 ORCHESTRATOR Nodes
**Path**: `/src/omnibase/tools/infrastructure/tool_infrastructure_orchestrator/v1_0_0/`
- ✅ **Workflow coordination**
- ✅ **Multi-component orchestration**
- ✅ **Decision-making logic**
- 🎯 **Use Case**: Process management, service coordination

#### 📊 REDUCER Nodes
**Path**: `/src/omnibase/tools/docker/tool_docker_infrastructure_reducer/v1_0_0/`
- ✅ **State aggregation**
- ✅ **Data reduction operations**
- ✅ **Result consolidation**
- 🎯 **Use Case**: Data aggregation, report generation, summary creation

### Validation Requirements
**Before any file modification:**
1. **Identify node type** from canonical patterns
2. **Compare structure** against canonical reference
3. **Validate [TEMPLATE] sections** are identical
4. **Ensure [CUSTOM] sections** follow business logic patterns
5. **Run duplicate detection** via OnexTree system

## File-by-File Atomic Validation

### Mandatory Validation Sequence
**After EVERY file modification:**
```yaml
atomic_validation:
  step_1: "Validate file against canonical reference"
  step_2: "Run OnexTree duplicate detection check"  
  step_3: "Verify contract compliance (if applicable)"
  step_4: "Check four-node architecture alignment"
  step_5: "Confirm no legacy patterns introduced"
```

### Validation Scripts (To Be Created)
- `validate-file-canonical.py`: Compare against canonical patterns
- `detect-duplicates-onextree.py`: Use OnexTree for duplicate detection
- `validate-contract-compliance.py`: Ensure contract standards

## Anti-YOLO Systematic Approach

### Before Any Implementation
1. **ASCII Architecture Diagram**: Visual representation of the system
2. **Canonical Pattern Matching**: Identify which patterns apply
3. **BFROS Reasoning**: Work backwards from desired outcome
4. **File-by-File Planning**: Atomic modification sequence

### During Implementation
1. **One File at a Time**: Complete validation before next file
2. **Template vs Custom**: Preserve template sections exactly
3. **Canonical Compliance**: Match patterns precisely
4. **Incremental Testing**: Test after each atomic change

### After Implementation
1. **Comprehensive Validation**: All validation scripts pass
2. **Architecture Compliance**: Four-node pattern maintained
3. **No Duplicates**: OnexTree confirms no duplicate files created
4. **Work Ticket Alignment**: Original requirements satisfied

## Integration with Existing Agent Capabilities

### RAG Intelligence Enhancement
- **Pre-work RAG queries** for historical patterns and solutions
- **Canonical pattern queries** to understand reference implementations
- **Post-work learning capture** for continuous improvement

### MCP Tool Coordination
- **Context7**: For library documentation and framework patterns
- **Sequential Thinking**: For complex architectural analysis
- **Codanna**: For semantic code navigation and impact analysis

### Specialized Agent Coordination
- Agents can still delegate to other specialists after following this workflow
- Workflow ensures consistent approach across all agent types
- Maintains agent autonomy while enforcing systematic approach

## Error Recovery Patterns

### 🚨 When Validation Fails
**Stop-Analyze-Fix-Resume Protocol:**
1. **🛑 Stop immediately** - Do not proceed to next file
2. **🔍 Analyze against canonical** - Identify deviation source
3. **🎯 Apply BFROS debugging** - Reason backwards from failure
4. **📋 Consult work ticket** - Verify requirements understanding
5. **✅ Re-validate atomically** - Ensure fix before proceeding

**⏱️ Time Box**: Spend max 15 minutes on analysis before escalating

### 🤔 When Canonical Patterns Conflict
**Escalation Protocol:**
1. **📝 Document conflict clearly** - Specific pattern differences
2. **🎯 Provide options** - Show canonical alternatives
3. **💡 Recommend path** - Based on work ticket requirements
4. **⏳ Wait for guidance** - Do not make assumptions

### 🚨 Common Recovery Scenarios

**❌ Problem**: "File doesn't match any canonical pattern"
**✅ Solution**: Check if new node type needed or misidentified existing pattern.

**❌ Problem**: "OnexTree shows duplicate files after modification"
**✅ Solution**: Compare file contents to identify actual differences vs. false positives.

**❌ Problem**: "Work ticket requirements conflict with canonical patterns"
**✅ Solution**: Escalate to human - may need canonical pattern update or ticket clarification.

**❌ Problem**: "Validation scripts don't exist yet"
**✅ Solution**: Manual validation against canonical patterns until scripts created.

## Success Metrics

- **Zero architectural drift** - all files match canonical patterns
- **Zero duplicate files** - OnexTree validation passes
- **Work ticket alignment** - requirements met precisely  
- **Atomic validation** - every file change validated before proceeding
- **BFROS compliance** - reasoning documented for all decisions

---

**Remember**: This workflow is mandatory for ALL ONEX agents. Read this document first, apply the methodology systematically, then execute domain-specific expertise.
