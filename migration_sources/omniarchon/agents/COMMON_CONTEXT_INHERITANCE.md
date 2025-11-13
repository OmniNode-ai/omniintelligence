# Common Context Inheritance Chains

**MANDATORY**: All ONEX agents must use context inheritance protocols when delegating to other agents to prevent information loss and maintain systematic workflow compliance.

## Quick Reference Navigation
- [Core Protocol](#core-context-inheritance-protocol) • [Templates](#standard-delegation-templates) • [Validation](#context-preservation-validation)
- [Prevention](#context-loss-prevention) • [Synchronization](#cross-agent-context-synchronization) • [Troubleshooting](#troubleshooting-context-issues)

---

## 📋 Quick Reference Card

### Essential Context Package (Always Include)
```yaml
inheritance_package:
  work_ticket_context: {active_ticket_id, requirements, success_criteria}
  bfros_reasoning_state: {desired_outcome, success_criteria, constraints, canonical_refs, pitfalls, validation}
  architectural_context: {node_type, canonical_patterns, compliance, validation_checkpoints}
  execution_state: {current_phase, completed_validations, pending_validations, risk_mitigation}
```

### Standard Delegation Format
```bash
> Use agent-{specialist} to {task} with inherited context:
**Work Ticket Context**: {ticket_info}
**BFROS State**: {outcome_and_criteria}
**Architectural Context**: {node_type_and_patterns}
**Validation Requirements**: {validation_strategy}
**Risk Awareness**: {potential_pitfalls}
```

**✅ Success Indicators**: Zero context loss • Validation continuity • Risk awareness • Architectural compliance

**❌ Failure Indicators**: Context truncation • Validation gaps • Risk blindness • Pattern drift

## Core Context Inheritance Protocol

### When Agent A Delegates to Agent B

**Context Inheritance Package** (Always Include):
```yaml
inheritance_package:
  work_ticket_context:
    active_ticket_id: "Current work ticket being executed"
    ticket_requirements: "Extracted requirements and constraints"
    success_criteria: "Defined completion criteria"

  bfros_reasoning_state:
    desired_outcome: "What specific result we want"
    success_criteria: "How we'll know we succeeded"
    architectural_constraints: "ONEX patterns we must follow"
    canonical_references: "Which canonical files provide the pattern"
    potential_pitfalls: "What could go wrong"
    validation_strategy: "How we'll verify correctness"

  architectural_context:
    node_type_classification: "COMPUTE/EFFECT/ORCHESTRATOR/REDUCER"
    canonical_pattern_refs: "Specific canonical files being followed"
    four_node_compliance: "Architecture alignment requirements"
    validation_checkpoints: "Required validation steps"

  execution_state:
    current_phase: "Which workflow phase we're in"
    completed_validations: "What validations have already passed"
    pending_validations: "What still needs to be validated"
    risk_mitigation: "Active risk prevention measures"
```

## Standard Delegation Templates

### Basic Delegation with Full Context
```bash
# ✅ CORRECT - Full context inheritance
> Use agent-{specialist} to {perform_task} with the following inherited context:

**Work Ticket Context**: {active_ticket_id} - {ticket_requirements}
**BFROS State**: Desired outcome: {outcome}, Success criteria: {criteria}
**Architectural Context**: {node_type} node following {canonical_pattern}
**Validation Requirements**: {validation_strategy}
**Risk Awareness**: {potential_pitfalls}

Please proceed with {specific_task} while maintaining all inherited constraints and validation requirements.
```

### Complex Multi-Agent Delegation
```bash
# ✅ CORRECT - Coordinated delegation with context distribution
> Use agent-{orchestrator} to coordinate the following multi-agent workflow with inherited context:

**Inherited Context Package**:
- Work Ticket: {ticket_context}
- BFROS Reasoning: {reasoning_state}
- Architecture: {architectural_constraints}
- Validation Chain: {validation_requirements}

**Sub-Agent Coordination**:
1. Route to agent-{specialist1} for {task1} with canonical reference {pattern1}
2. Route to agent-{specialist2} for {task2} with canonical reference {pattern2}
3. Validate results against {inherited_validation_strategy}

Ensure all sub-agents receive full context inheritance to maintain workflow continuity.
```

## Context Preservation Validation

### Pre-Delegation Checklist
**Before delegating to another agent, verify:**
- ✅ **Work ticket context** clearly extracted and summarized
- ✅ **BFROS reasoning state** completely documented  
- ✅ **Canonical references** specifically identified
- ✅ **Validation strategy** explicitly defined
- ✅ **Risk awareness** from current context included

**⏱️ Time Investment**: 30-60 seconds of verification prevents hours of rework

### Post-Delegation Verification
**After receiving delegation results:**
- ✅ **Context continuity** - Verify inherited context was maintained throughout execution
- ✅ **Validation adherence** - Confirm validation strategy was followed as specified
- ✅ **Pattern preservation** - Validate canonical patterns were preserved
- ✅ **Risk management** - Check that risk mitigation measures were applied

**🎯 Quality Gate**: If any verification fails, request context correction before accepting results

## Context Loss Prevention

### Common Context Loss Scenarios (PREVENT THESE)
```bash
# ❌ FORBIDDEN - Context loss delegation
> Use agent-testing to create tests for the contract validator.
```

```bash
# ✅ CORRECT - Context inheritance delegation  
> Use agent-testing to create tests for the contract validator with inherited context:

**Work Ticket Context**: CLAUDE-001 - Implement Anti-YOLO Method compliance
**BFROS State**: Desired outcome: Comprehensive test coverage for COMPUTE node validation
**Architectural Context**: Contract validator classified as COMPUTE node per canonical pattern
**Validation Requirements**: File-by-file atomic validation against canonical patterns
**Risk Awareness**: Avoid Any types, ensure OnexError chaining, validate four-node compliance
```

## Cross-Agent Context Synchronization

### Context Update Protocol
**When context changes during execution:**
```yaml
context_update_protocol:
  trigger: "When new information affects inherited context"
  update_scope: "All agents in current workflow chain"  
  update_format: "Structured context diff with change reasoning"
  validation: "Verify all agents acknowledge context update"
```

**📢 Update Template:**
```bash
**CONTEXT UPDATE REQUIRED**
Changed: {what_changed}
Reason: {why_it_changed}
Impact: {who_needs_updated_context}
Action: All agents in workflow chain update your inherited context
```

### Context Conflict Resolution
**When inherited context conflicts with agent-specific requirements:**

**Priority Hierarchy** (highest to lowest):
1. **Work ticket requirements** (always wins)
2. **BFROS reasoning state** (architectural guidance)
3. **Canonical patterns** (system consistency)
4. **Agent preferences** (lowest priority)

**Resolution Process:**
```yaml
conflict_resolution:
  step_1: "Identify conflicting elements and priority levels"
  step_2: "Apply priority hierarchy to resolve conflicts"
  step_3: "Flag unresolvable conflicts to coordinating agent"
  step_4: "Document resolution rationale for future reference"
```

## Integration with Existing Framework

### Common Document References
Context Inheritance integrates with existing framework:
- **@COMMON_WORKFLOW.md**: Provides base systematic approach
- **@COMMON_RAG_INTELLIGENCE.md**: Supplies pattern intelligence
- **@COMMON_ONEX_STANDARDS.md**: Defines compliance requirements
- **@COMMON_AGENT_PATTERNS.md**: Establishes collaboration standards
- **@COMMON_CONTEXT_INHERITANCE.md**: Ensures seamless context flow (this document)

### Enhanced Agent Coordination
```yaml
enhanced_coordination_pattern:
  step1: "Read common workflow documents"
  step2: "Apply BFROS reasoning with full context"
  step3: "Create context inheritance package"
  step4: "Delegate with complete context preservation"
  step5: "Validate context maintenance in results"
  step6: "Update context based on outcomes"
```

## Context Inheritance Quality Metrics

### Success Indicators
- **Zero Context Loss**: All delegations preserve full context
- **Validation Continuity**: Validation strategies maintained across handoffs
- **Risk Awareness**: Potential pitfalls consistently tracked
- **Architectural Compliance**: Four-node patterns preserved throughout workflows

### Failure Indicators (Address Immediately)
- **Context Truncation**: Partial context in delegations
- **Validation Gaps**: Missing validation requirements in handoffs
- **Risk Blindness**: Failure to inherit risk awareness
- **Pattern Drift**: Canonical references lost during delegation

## Troubleshooting Context Issues

### Common Problems & Solutions

**❌ Problem**: "Agent didn't follow the canonical pattern I specified"
**✅ Solution**: Check if canonical reference was included in delegation. Re-delegate with explicit pattern reference.

**❌ Problem**: "Results don't match work ticket requirements"
**✅ Solution**: Verify work ticket context was passed completely. Include ticket ID and specific requirements in re-delegation.

**❌ Problem**: "Validation failed unexpectedly"
**✅ Solution**: Check if validation strategy was preserved in context inheritance. Update context with current validation requirements.

**❌ Problem**: "Risk mitigation wasn't applied"
**✅ Solution**: Ensure risk awareness was included in inherited context. Update delegation with explicit risk mitigation requirements.

### Emergency Context Recovery
**When context is completely lost:**
1. **Stop current workflow** - Prevent further context degradation
2. **Return to work ticket** - Re-establish authoritative context source
3. **Rebuild context package** - Create fresh inheritance package from current state
4. **Validate completeness** - Ensure all required elements are present
5. **Resume with fresh context** - Continue workflow with validated context

---

**Remember**: Context Inheritance Chains prevent the #1 cause of "wait, that's not what I meant" moments - information loss during agent handoffs. Always include full context inheritance packages in all delegations.
