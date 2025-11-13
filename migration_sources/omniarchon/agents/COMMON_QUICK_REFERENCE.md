# ONEX Anti-YOLO Framework - Quick Reference Guide

**PURPOSE**: Instant access to essential framework patterns, commands, and troubleshooting for rapid development workflows.

## 🚀 Quick Start (5-Minute Framework Onboarding)

### Essential Framework Flow
```bash
1. Read work ticket → 2. Apply BFROS reasoning → 3. Create diagram → 4. Validate atomically
```

### Agent Delegation Pattern
```bash
> Use agent-{specialist} to {task} with inherited context:
**Work Ticket Context**: {ticket_info}
**BFROS State**: {outcome_and_criteria}
**Architectural Context**: {node_type_and_patterns}
**Validation Requirements**: {validation_strategy}
**Risk Awareness**: {potential_pitfalls}
```

### Context Freshness Check (60 seconds)
```bash
✓ Work ticket currency (15s) → ✓ Enhancement detection (15s) → ✓ Package refresh (20s) → ✓ Fresh delegation (10s)
```

---

## 📚 Framework Navigation Map

### Core Documents (Read First)
- **@COMMON_WORKFLOW.md** - Anti-YOLO Method + BFROS Framework
- **@COMMON_CONTEXT_INHERITANCE.md** - Context preservation protocols
- **@COMMON_CONTEXT_LIFECYCLE.md** - Smart context management
- **@COMMON_ONEX_STANDARDS.md** - Standards and requirements
- **@COMMON_RAG_INTELLIGENCE.md** - RAG integration patterns
- **@COMMON_AGENT_PATTERNS.md** - Agent architecture patterns

### Quick Access Sections
| Need | Document | Section |
|------|----------|---------|
| Context delegation template | CONTEXT_INHERITANCE | [Standard Delegation Templates](#) |
| Context freshness scoring | CONTEXT_LIFECYCLE | [Freshness Scoring Thresholds](#) |
| BFROS reasoning template | WORKFLOW | [BFROS Framework Integration](#) |
| Four-node validation | WORKFLOW | [Four-Node Architecture](#) |
| Error recovery | WORKFLOW | [Error Recovery Patterns](#) |
| Agent color coding | AGENT_PATTERNS | [Standard Color Coding](#) |

---

## 🔧 Essential Commands & Patterns

### ONEX CLI Commands
```bash
# Primary method (preferred)
onex run {tool_name} --{action} {parameters}

# Fallback if CLI broken  
poetry run python -m omnibase.tools.{domain}.{tool_name}.v1_0_0.node
```

### Agent Invocation Patterns
```bash
# Single specialist
> Use agent-{specialist} to {specific_task}

# Orchestrated workflow
> Use agent-onex-coordinator to route {complex_task} across multiple specialists

# Multi-step execution  
> Use agent-workflow-coordinator to manage {workflow_name} with progress tracking
```

### Four-Node Architecture Quick Reference
| Node Type | Purpose | Example Use | Path Pattern |
|-----------|---------|-------------|--------------|
| 🔢 COMPUTE | Stateless logic | Calculation, transformation | `tool_kafka_wrapper/v1_0_0/` |
| ⚡ EFFECT | Side effects | Database, API calls | `tool_docker_template_generator_effect/v1_0_0/` |
| 🎭 ORCHESTRATOR | Coordination | Process management | `tool_infrastructure_orchestrator/v1_0_0/` |
| 📊 REDUCER | Aggregation | Data consolidation | `tool_docker_infrastructure_reducer/v1_0_0/` |

---

## 🎯 BFROS Framework Quick Templates

### Implementation Template (Copy-Paste Ready)
```yaml
bfros_implementation:
  desired_outcome: "What specific result do we want?"
  success_criteria: "How will we know we succeeded?"
  architectural_constraints: "What ONEX patterns must we follow?"
  canonical_references: "Which canonical files provide the pattern?"
  potential_pitfalls: "What could go wrong?"
  validation_strategy: "How will we verify correctness?"
```

### Debugging Template (Copy-Paste Ready)
```yaml
bfros_debugging:
  symptom_analysis: "What exactly is the observable problem?"
  root_cause_hypothesis: "What underlying issue could cause this?"
  four_node_compliance: "Does this align with COMPUTE/EFFECT/ORCHESTRATOR/REDUCER?"
  canonical_deviation: "Where might we have deviated from canonical patterns?"
  validation_failure: "What validation step did we miss?"
  correction_strategy: "How do we fix this systematically?"
```

---

## 🔄 Context Management Cheat Sheet

### Context Freshness Scoring
- **Fresh (≥ 0.8)**: Proceed with current context
- **Stale (0.5-0.79)**: Mandatory refresh before use
- **Invalid (< 0.5)**: Force complete context reset

### Context Lifecycle Scopes  
- **Task-Level**: Single agent execution → Reset on completion
- **Workflow-Level**: Multi-step workflow → Reset on workflow change
- **Session-Level**: Claude Code session → Reset on session restart
- **Project-Level**: Major project phase → Reset on architectural change

### Emergency Context Recovery
```bash
1. Stop workflow → 2. Return to work ticket → 3. Rebuild context → 4. Validate completeness → 5. Resume
```

---

## 🚨 Troubleshooting Quick Fixes

### Context Issues
| Problem | Quick Fix | Time |
|---------|-----------|------|
| Agent didn't follow canonical pattern | Check canonical reference in delegation | 30s |
| Results don't match work ticket | Verify ticket context passed completely | 60s |
| Validation failed unexpectedly | Check validation strategy preservation | 45s |
| Risk mitigation not applied | Ensure risk awareness in context | 30s |

### Validation Issues
| Problem | Quick Fix | Time |
|---------|-----------|------|
| File doesn't match canonical | Check node type identification | 2min |
| OnexTree shows duplicates | Compare contents for real differences | 3min |
| Work ticket conflicts with canonical | Escalate to human for resolution | N/A |
| Validation scripts missing | Manual validation against patterns | 5min |

### Framework Issues
| Problem | Quick Fix | Time |
|---------|-----------|------|
| Context freshness < 0.5 | Force context reset and rebuild | 2min |
| Multiple context conflicts | Escalate to coordinator agent | N/A |
| Agent returns unexpected results | Verify @COMMON_* references included | 1min |
| Workflow stalled | Check context inheritance completeness | 90s |

---

## 📈 Quality Gates & Success Metrics

### Before Delegation (30-60 seconds)
- ✅ Work ticket context extracted
- ✅ BFROS reasoning documented  
- ✅ Canonical references identified
- ✅ Validation strategy defined
- ✅ Risk awareness included

### After Implementation (Per File)
- ✅ Canonical pattern compliance
- ✅ OnexTree duplicate detection passed
- ✅ Contract compliance validated
- ✅ Four-node architecture aligned
- ✅ No legacy patterns introduced

### Success Indicators
- **Zero context loss** in delegations
- **Zero architectural drift** from patterns
- **Zero duplicate files** created
- **Work ticket alignment** maintained
- **BFROS compliance** documented

---

## 🏃‍♂️ Performance Optimization Tips

### Time-Saving Shortcuts
- **Most contexts are fresh**: Quick 5-second check vs. full 60-second refresh
- **Batch validations**: Validate multiple files together when possible
- **Reuse BFROS reasoning**: Similar tasks often have similar reasoning
- **Template delegation**: Keep delegation templates for common patterns

### Efficiency Multipliers
- **Use orchestrators**: Let coordinators handle complex routing
- **Leverage RAG intelligence**: Historical patterns accelerate decisions  
- **Apply context inheritance**: Prevent rework from information loss
- **Follow atomic validation**: Catch issues early when cheap to fix

---

## 🎓 Learning Path Recommendations

### New to Framework (First Week)
1. **Master @COMMON_WORKFLOW.md** - Core methodology and BFROS
2. **Practice context delegation** - Use @COMMON_CONTEXT_INHERITANCE.md templates
3. **Learn four-node patterns** - Study canonical references
4. **Apply to simple tasks** - Build muscle memory

### Intermediate Users (After 1 Month)  
1. **Optimize context lifecycle** - Master @COMMON_CONTEXT_LIFECYCLE.md
2. **Leverage RAG intelligence** - Use @COMMON_RAG_INTELLIGENCE.md patterns
3. **Create custom agents** - Follow @COMMON_AGENT_PATTERNS.md
4. **Contribute improvements** - Enhance framework based on experience

### Advanced Users (After 3 Months)
1. **Orchestrate complex workflows** - Design multi-agent systems
2. **Optimize framework patterns** - Propose optimizations
3. **Mentor other users** - Share knowledge and best practices
4. **Extend framework capabilities** - Add new patterns and tools

---

**Remember**: This framework prevents the #1 development issue - "wait, that's not what I meant" moments. Use it systematically for consistent, predictable, high-quality outcomes.
