# Common Context Lifecycle Management

**MANDATORY**: All ONEX agents must follow smart context lifecycle protocols to ensure context freshness and prevent stale information propagation.

## Quick Reference Navigation
- [Context Freshness](#context-freshness-validation) • [Refresh Triggers](#intelligent-context-refresh-triggers) • [Scopes](#context-scope-management)
- [Refresh Protocols](#smart-context-refresh-protocols) • [Versioning](#context-versioning-system) • [Conflict Resolution](#context-conflict-resolution)
- [Troubleshooting](#troubleshooting-stale-context) • [Quality Metrics](#success-metrics)

---

## 🔄 Quick Reference Card

### Context Freshness Checklist (Before Every Delegation)
- ✅ **Work ticket currency**: Is current ticket still active?
- ✅ **Canonical validity**: Have referenced files changed?
- ✅ **BFROS relevance**: Are success criteria still accurate?
- ✅ **Validation currency**: Is validation approach still appropriate?
- ✅ **Architecture stability**: Have four-node requirements evolved?

### Context Lifecycle Scopes
- **Task-Level** (Shortest): Single agent execution → Reset on completion
- **Workflow-Level** (Medium): Multi-step workflow → Reset on workflow change
- **Session-Level** (Extended): Claude Code session → Reset on session restart
- **Project-Level** (Longest): Major project phase → Reset on architectural change

### Freshness Scoring Thresholds
- **Fresh (≥ 0.8)**: Proceed with current context
- **Stale (0.5-0.79)**: Mandatory refresh before use
- **Invalid (< 0.5)**: Force complete context reset

## Smart Context Manager Framework

### Context Freshness Validation

**Before Every Delegation** - Automatically verify:
```yaml
freshness_check_protocol:
  work_ticket_currency: "Is the current work ticket still the active one?"
  canonical_reference_validity: "Have the referenced canonical files changed?"
  bfros_reasoning_relevance: "Are our success criteria still accurate for current state?"
  validation_strategy_current: "Is our validation approach still appropriate?"
  architectural_constraints_stable: "Have four-node requirements evolved?"
```

### Intelligent Context Refresh Triggers

**Automatic Reset Scenarios:**
```yaml
context_reset_triggers:
  new_work_ticket:
    trigger: "Active work ticket ID changes"
    action: "Complete context reset with new ticket analysis"
    validation: "Confirm all agents acknowledge new context baseline"

  architectural_paradigm_shift:
    trigger: "Four-node classification changes or new canonical patterns emerge"
    action: "Reset architectural context, preserve non-architectural elements"
    validation: "Verify new canonical references are accessible and valid"

  session_boundary:
    trigger: "Claude Code session restart detected"
    action: "Reset all inherited context, start fresh with current work ticket"
    validation: "Reload current system state and active requirements"

  validation_strategy_obsolete:
    trigger: "Current validation approach no longer applies"
    action: "Reset validation context, preserve work ticket and BFROS reasoning"
    validation: "Confirm new validation strategy aligns with current goals"
```

**Smart Update Scenarios:**
```yaml
context_update_triggers:
  discovery_integration:
    trigger: "Agent discovers new constraints or requirements"
    action: "Merge discoveries into existing context without reset"
    validation: "Ensure discoveries don't conflict with existing context"

  validation_learning:
    trigger: "Validation results provide new insights"
    action: "Update risk awareness and success criteria based on findings"
    validation: "Verify updated context maintains consistency"

  pattern_evolution:
    trigger: "Better canonical patterns identified during execution"
    action: "Update canonical references while preserving validation strategy"
    validation: "Confirm new patterns are more appropriate than previous ones"

  failure_adaptation:
    trigger: "Failed approaches provide learning insights"
    action: "Update potential pitfalls and mitigation strategies"
    validation: "Ensure failure learning doesn't invalidate core objectives"
```

## Context Scope Management

### Context Scopes and Lifecycles

**Task-Level Context** (Shortest Lifespan):
```yaml
task_context:
  lifespan: "Single agent execution or specific task completion"
  reset_trigger: "Task completion, task failure, or task scope change"
  persistence: "Does not carry over to unrelated tasks"
  example: "Validating a specific contract file"
```

**Workflow-Level Context** (Medium Lifespan):
```yaml
workflow_context:
  lifespan: "Multi-step workflow execution across related tasks"
  reset_trigger: "Workflow completion, workflow cancellation, or major scope change"
  persistence: "Carries across related tasks within same workflow"
  example: "Implementing full Anti-YOLO Method across multiple agents"
```

**Session-Level Context** (Extended Lifespan):
```yaml
session_context:
  lifespan: "Current Claude Code interactive session"
  reset_trigger: "Session restart, user logout, or major project pivot"
  persistence: "Maintains across multiple workflows within session"
  example: "Working on ONEX system improvements during a development session"
```

**Project-Level Context** (Longest Lifespan):
```yaml
project_context:
  lifespan: "Major project or development phase"
  reset_trigger: "Project completion, architectural overhaul, or strategic pivot"
  persistence: "Maintains across multiple sessions and workflows"
  example: "ONEX framework development and evolution"
```

## Smart Context Refresh Protocols

### Pre-Delegation Context Verification

**⚡ Quick 60-Second Context Check:**
```bash
# Step 1: Context Freshness Validation (15 seconds)
✓ Verify work ticket ID matches current active ticket
✓ Check canonical reference files for recent modifications
✓ Validate BFROS reasoning against current objectives
✓ Confirm validation strategy remains appropriate

# Step 2: Context Enhancement Detection (15 seconds)
✓ Identify new discoveries or constraints since last update
✓ Check for improved canonical patterns or validation approaches
✓ Assess if failure learnings should be incorporated

# Step 3: Context Package Refresh (20 seconds)
✓ Update stale components with fresh information
✓ Integrate new discoveries without losing valid context
✓ Increment context version and update timestamp
✓ Document what changed and why

# Step 4: Delegation with Fresh Context (10 seconds)
✓ Pass enhanced, verified context to receiving agent
✓ Include context metadata for freshness tracking
```

**🎯 Efficiency Tip**: Most contexts require no refresh (< 5 seconds). Only stale contexts need full refresh.

### Context Versioning System

**Context Metadata Structure:**
```yaml
context_metadata:
  version_id: "semantic version of context package (1.2.3)"
  created_timestamp: "initial context creation time"
  last_updated: "most recent refresh timestamp"
  update_history: "log of changes and reasons"
  freshness_score: "calculated freshness indicator (0-1.0)"
  staleness_warnings: "components that may need attention"

context_components_freshness:
  work_ticket: {last_verified: "timestamp", status: "fresh|stale|invalid"}
  bfros_reasoning: {last_verified: "timestamp", status: "fresh|stale|invalid"}
  canonical_refs: {last_verified: "timestamp", status: "fresh|stale|invalid"}
  validation_strategy: {last_verified: "timestamp", status: "fresh|stale|invalid"}
  risk_awareness: {last_verified: "timestamp", status: "fresh|stale|invalid"}
```

## Automated Context Management

### Context Health Monitoring

**Freshness Scoring Algorithm:**
```yaml
freshness_calculation:
  work_ticket_currency: 40%    # Highest weight - must match active ticket
  canonical_reference_validity: 25%    # Files haven't changed inappropriately
  bfros_reasoning_relevance: 20%    # Success criteria still accurate
  validation_strategy_current: 10%    # Approach still appropriate
  temporal_decay: 5%    # Age-based freshness reduction

freshness_thresholds:
  fresh: ">= 0.8"    # Context is reliable and current
  stale: "0.5 - 0.79"    # Context needs refresh before use
  invalid: "< 0.5"    # Context must be reset before delegation
```

### Automatic Context Actions

**Smart Context Maintenance:**
```bash
# Automatic Actions Based on Freshness Score

# Fresh Context (>= 0.8)
> Proceed with delegation using current context
> Optional: Check for enhancement opportunities

# Stale Context (0.5 - 0.79)  
> Mandatory refresh before delegation
> Update stale components while preserving valid ones
> Re-calculate freshness score after updates

# Invalid Context (< 0.5)
> Block delegation until context reset
> Force complete context regeneration from current state
> Require validation of new context before use
```

## Context Conflict Resolution

### Conflict Detection and Resolution

**Common Conflict Scenarios:**
```yaml
conflict_types:
  work_ticket_mismatch:
    detection: "Inherited context references different work ticket than currently active"
    resolution: "Reset context with current work ticket as authoritative source"

  canonical_pattern_evolution:
    detection: "Referenced canonical files have been updated or deprecated"
    resolution: "Update canonical references, preserve compatible validation strategies"

  validation_strategy_obsolete:
    detection: "Current validation approach no longer applies to updated requirements"
    resolution: "Reset validation context, preserve work ticket and BFROS reasoning"

  bfros_reasoning_invalid:
    detection: "Success criteria no longer align with current objectives"
    resolution: "Re-apply BFROS framework with current context as starting point"
```

**Conflict Resolution Priority:**
```yaml
resolution_hierarchy:
  1_current_work_ticket: "Active work ticket requirements take precedence"
  2_canonical_patterns: "Current canonical references override outdated ones"
  3_system_constraints: "ONEX standards and four-node architecture requirements"
  4_inherited_context: "Previous context maintained when compatible"
  5_agent_preferences: "Agent-specific approaches (lowest priority)"
```

## Integration with Existing Framework

### Enhanced Context Inheritance Workflow

**Complete Lifecycle Integration:**
```bash
# Enhanced Agent Delegation Protocol:

1. Read @COMMON_WORKFLOW.md for systematic approach
2. Read @COMMON_CONTEXT_INHERITANCE.md for delegation protocols  
3. Read @COMMON_CONTEXT_LIFECYCLE.md for freshness management (NEW)
4. Verify context freshness using Smart Context Manager
5. Refresh or reset context as needed based on lifecycle rules
6. Delegate with verified, fresh context package
7. Monitor context health throughout execution
8. Update context based on discoveries and outcomes
```

### Context Lifecycle Integration Points

**Framework Integration:**
- **@COMMON_WORKFLOW.md**: Provides base systematic methodology
- **@COMMON_CONTEXT_INHERITANCE.md**: Defines delegation and preservation protocols
- **@COMMON_CONTEXT_LIFECYCLE.md**: Manages context freshness and lifecycle (this document)
- **@COMMON_RAG_INTELLIGENCE.md**: Supplies intelligence for context enhancement
- **@COMMON_ONEX_STANDARDS.md**: Provides standards for context validation

## Troubleshooting Stale Context

### Common Context Staleness Issues

**❌ Problem**: "Agent is using outdated work ticket information"
**✅ Solution**: Check context freshness score. If < 0.8, force context refresh with current work ticket.

**❌ Problem**: "Canonical patterns referenced are deprecated"
**✅ Solution**: Update canonical references in context package. Increment context version.

**❌ Problem**: "BFROS reasoning doesn't match current objectives"
**✅ Solution**: Re-apply BFROS framework with current state. Reset reasoning components.

**❌ Problem**: "Context keeps getting marked as stale immediately"
**✅ Solution**: Check if work ticket or canonical files are changing rapidly. May need shorter context lifespan.

### Context Emergency Procedures

**🚨 When Context Freshness Score < 0.5:**
1. **Immediate stop** - Block all delegations until context is refreshed
2. **Force reset** - Discard existing context entirely
3. **Fresh rebuild** - Regenerate context from current authoritative sources
4. **Validation check** - Ensure new context scores ≥ 0.8 before proceeding

**🔄 When Multiple Context Conflicts Occur:**
1. **Identify conflict source** - Usually indicates rapid system changes
2. **Escalate to coordinator** - May require workflow-level context reset
3. **Document pattern** - Track for context lifecycle optimization

## Success Metrics

### Context Management Quality Indicators

**Effectiveness Metrics:**
```yaml
success_indicators:
  zero_stale_delegations: "All delegations use fresh, verified context"
  context_continuity: "Related tasks maintain appropriate context persistence"
  adaptive_refresh: "Context updates intelligently without losing valid information"
  conflict_resolution: "Context conflicts resolved automatically with clear rationale"

quality_metrics:
  average_context_freshness: "Target >= 0.85 across all delegations"
  context_reset_frequency: "Resets only when necessary, not excessive"
  delegation_success_rate: "Improved outcomes due to better context management"
  surprise_incident_reduction: "Fewer 'wait, that's not what I meant' moments"
```

---

**Remember**: Smart Context Management prevents information decay and ensures every agent receives the most relevant, current context for their execution. Context is living, intelligent memory that evolves with the work.
