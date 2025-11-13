# ONEX Anti-YOLO Framework - Troubleshooting Guide

**PURPOSE**: Systematic problem resolution for ONEX framework issues with step-by-step recovery procedures.

## Quick Navigation
- [Context Issues](#context-issues) • [Validation Problems](#validation-problems) • [Agent Delegation](#agent-delegation-issues)
- [Framework Errors](#framework-errors) • [Performance Issues](#performance-issues) • [Emergency Procedures](#emergency-procedures)

---

## 🚨 Emergency Procedures (Critical Issues)

### 🔥 Framework Completely Broken
**Symptoms**: No agents responding, total workflow failure
**Recovery**:
1. **Immediate**: Stop all current workflows
2. **Assess**: Check if @COMMON_* files are corrupted
3. **Recovery**: Restore from last known good framework state
4. **Validate**: Test with simple agent delegation
5. **Resume**: Gradually restore full operations

### 🔥 Massive Context Loss
**Symptoms**: All agents returning irrelevant results
**Recovery**:
1. **Stop**: Halt all delegations immediately
2. **Reset**: Clear all inherited context
3. **Rebuild**: Start fresh with current work ticket
4. **Test**: Verify with single agent before proceeding
5. **Monitor**: Watch for context preservation

### 🔥 Validation System Down
**Symptoms**: No validation feedback, files passing incorrectly
**Recovery**:
1. **Manual mode**: Switch to manual canonical validation
2. **Document**: Log all changes made during outage
3. **Repair**: Fix validation tools/scripts
4. **Retroactive**: Validate all changes made during outage
5. **Resume**: Return to automated validation

---

## 🔧 Context Issues

### Context Loss During Delegation
**Problem**: Agent returns results that ignore provided context
**Diagnosis**:
```bash
# Check delegation format
✓ Was full context inheritance package included?
✓ Are all required context components present?
✓ Is context freshness score ≥ 0.8?
```
**Solution**:
```bash
1. Re-delegate with complete context package
2. Use explicit context validation before delegation
3. Check agent @COMMON_* references are working
```

### Stale Context Propagation
**Problem**: Agents using outdated work ticket/canonical information
**Diagnosis**:
```bash
# Context freshness analysis
✓ Check work ticket ID vs. current active ticket
✓ Verify canonical files haven't changed recently  
✓ Confirm BFROS reasoning matches current objectives
```
**Solution**:
```bash
1. Force context refresh with freshness validation
2. Update context components individually
3. Increment context version and update timestamp
```

### Context Conflicts Between Agents
**Problem**: Different agents have inconsistent context  
**Diagnosis**:
```bash
# Conflict source analysis
✓ Identify which context elements conflict
✓ Check if work ticket changed during workflow
✓ Verify canonical patterns haven't evolved
```
**Solution**:
```bash
1. Apply context conflict resolution hierarchy:
   Work ticket > BFROS reasoning > Canonical patterns > Agent preferences
2. Update all agents with resolved context
3. Document resolution rationale
```

---

## ✅ Validation Problems

### Canonical Pattern Mismatch
**Problem**: File structure doesn't match expected canonical pattern
**Diagnosis**:
```bash
# Pattern identification
✓ Is node type correctly identified (COMPUTE/EFFECT/ORCHESTRATOR/REDUCER)?
✓ Are we comparing against correct canonical reference?
✓ Has canonical pattern evolved since last check?
```
**Solution**:
```bash
1. Re-identify node type against current patterns
2. Compare against correct canonical reference file
3. If pattern evolved, update canonical references
4. Manual validation if patterns unclear
```

### OnexTree Duplicate Detection False Positives
**Problem**: Duplicate detection flagging legitimate files
**Diagnosis**:
```bash
# Content analysis  
✓ Compare actual file contents vs. duplicate detection results
✓ Check for template sections vs. custom implementations
✓ Verify file structure matches canonical exactly
```
**Solution**:
```bash
1. Compare files manually to identify real differences
2. Update OnexTree configuration if too sensitive
3. Document known false positive patterns
4. Proceed with human validation override if confirmed false positive
```

### Contract Compliance Failures
**Problem**: Generated files don't meet contract standards
**Diagnosis**:
```bash
# Contract validation analysis
✓ Which contract requirements are failing?
✓ Is contract specification current and valid?
✓ Are generated models using correct patterns?
```
**Solution**:
```bash
1. Re-generate from current contract specification
2. Verify contract hasn't changed during generation
3. Check template vs. custom section compliance
4. Manual fix if contract-generator mismatch
```

---

## 🤖 Agent Delegation Issues

### Agent Not Following Instructions
**Problem**: Agent returns unexpected or irrelevant results
**Diagnosis**:
```bash
# Agent state analysis
✓ Was agent given complete context inheritance package?
✓ Are @COMMON_* references working in agent file?
✓ Is agent using current framework version?
```
**Solution**:
```bash
1. Re-delegate with explicit, complete context
2. Verify agent file has all @COMMON_* references
3. Check if agent needs framework update
4. Use different specialist agent if first doesn't work
```

### Orchestration Agent Routing Failures
**Problem**: Coordinator agents routing to wrong specialists
**Diagnosis**:
```bash
# Routing logic analysis
✓ Is task classification correct?
✓ Are specialist agents available and working?
✓ Is routing logic current with agent capabilities?
```
**Solution**:
```bash
1. Manually route to appropriate specialist
2. Update coordinator routing rules if needed
3. Test specialist agents individually
4. Use agent-onex-coordinator as backup router
```

### Multi-Agent Workflow Breakdown
**Problem**: Complex workflows stalling or producing inconsistent results
**Diagnosis**:
```bash
# Workflow state analysis
✓ Where in workflow did breakdown occur?
✓ Is context being preserved across handoffs?
✓ Are agents coordinating properly?
```
**Solution**:
```bash
1. Restart workflow from last successful checkpoint
2. Use agent-workflow-coordinator for better orchestration
3. Ensure context inheritance at each handoff
4. Break complex workflow into simpler sub-workflows
```

---

## ⚙️ Framework Errors

### BFROS Reasoning Incomplete
**Problem**: Results don't align with desired outcomes
**Diagnosis**:
```bash
# BFROS completeness check
✓ Were all BFROS template fields completed?
✓ Is desired outcome clearly defined?
✓ Are architectural constraints appropriate?
```
**Solution**:
```bash
1. Complete BFROS template fully before proceeding
2. Validate desired outcome against work ticket
3. Ensure architectural constraints match four-node patterns
4. Re-apply BFROS with more specific criteria
```

### Work Ticket Misalignment
**Problem**: Implementation doesn't match ticket requirements
**Diagnosis**:
```bash
# Requirements alignment check
✓ Was current work ticket read completely?
✓ Are requirements clearly understood?
✓ Have requirements changed during implementation?
```
**Solution**:
```bash
1. Re-read current work ticket carefully
2. Extract specific requirements and constraints
3. Validate implementation against each requirement
4. Update implementation to match or clarify requirements
```

### Architecture Drift
**Problem**: Implementation deviates from four-node architecture
**Diagnosis**:
```bash
# Architecture compliance check
✓ Is node type classification correct?
✓ Does implementation match canonical patterns?
✓ Are template sections preserved exactly?
```
**Solution**:
```bash
1. Re-identify correct node type
2. Compare implementation against canonical reference
3. Restore template sections to exact canonical match
4. Modify only custom sections while preserving architecture
```

---

## 🐌 Performance Issues

### Slow Context Refresh
**Problem**: Context verification taking too long
**Diagnosis**:
```bash
# Performance bottleneck analysis
✓ Which context components are slow to validate?
✓ Are we over-refreshing fresh context?
✓ Is canonical file access slow?
```
**Solution**:
```bash
1. Cache context components with longer lifespans
2. Skip refresh for recently validated context (< 5 min)
3. Optimize canonical file access patterns
4. Use context version timestamps for smarter refresh
```

### Agent Response Delays
**Problem**: Agents taking unusually long to respond
**Diagnosis**:
```bash
# Agent performance analysis
✓ Which agents are slow? (orchestrators vs. specialists)
✓ Is RAG query performance impacting response time?
✓ Are agents waiting for external dependencies?
```
**Solution**:
```bash
1. Use simpler specialist agents for routine tasks
2. Optimize RAG queries for performance
3. Check external dependency health
4. Consider parallel agent execution for independent tasks
```

### Framework Overhead
**Problem**: Framework adding too much process overhead
**Diagnosis**:
```bash
# Overhead source analysis
✓ Which steps are taking most time?
✓ Can any validations be streamlined?
✓ Are we over-validating simple changes?
```
**Solution**:
```bash
1. Use quick validation paths for simple changes
2. Batch similar validations together
3. Cache validation results for identical patterns
4. Skip unnecessary context refresh for trivial tasks
```

---

## 🔍 Diagnostic Commands

### Framework Health Check
```bash
# Verify all @COMMON_* files accessible
✓ @COMMON_WORKFLOW.md
✓ @COMMON_CONTEXT_INHERITANCE.md  
✓ @COMMON_CONTEXT_LIFECYCLE.md
✓ @COMMON_ONEX_STANDARDS.md
✓ @COMMON_RAG_INTELLIGENCE.md
✓ @COMMON_AGENT_PATTERNS.md
```

### Agent Availability Check
```bash
# Test core agents respond properly
> Use agent-onex-coordinator for simple routing test
> Use agent-workflow-coordinator for simple workflow test  
> Use agent-contract-validator for simple validation test
```

### Context Inheritance Test
```bash
# Verify context flows between agents
1. Create test context package
2. Delegate to test agent with context
3. Verify agent received complete context
4. Check context preservation in response
```

---

## 📚 Advanced Troubleshooting

### Framework Extension Issues
**Problem**: New agents or patterns not working correctly
**Solution**: Verify new components follow @COMMON_AGENT_PATTERNS.md exactly

### Integration Problems  
**Problem**: Framework conflicts with external tools
**Solution**: Check @COMMON_ONEX_STANDARDS.md compliance and tool coordination patterns

### Performance Optimization
**Problem**: Framework becoming slow with complex workflows
**Solution**: Profile bottlenecks and apply caching, parallel execution, or workflow simplification

### Quality Degradation
**Problem**: Results quality declining over time
**Solution**: Review and update RAG intelligence, refresh canonical patterns, validate agent performance

---

## 📞 Escalation Procedures

### When to Escalate to Human
- Canonical pattern conflicts requiring architectural decisions
- Work ticket requirements that conflict with framework standards
- Persistent agent coordination failures
- Framework bugs affecting core functionality

### How to Document Issues for Escalation
```yaml
issue_report:
  problem_description: "Clear, specific problem statement"
  reproduction_steps: "Exact steps to reproduce the issue"
  expected_behavior: "What should have happened"
  actual_behavior: "What actually happened"  
  diagnostic_information: "Results of troubleshooting steps attempted"
  impact_assessment: "How this affects workflow and quality"
  suggested_solution: "Proposed fix if identified"
```

---

**Remember**: Most issues stem from incomplete context inheritance or BFROS reasoning. Start troubleshooting with these fundamentals before diving into complex diagnostics.
