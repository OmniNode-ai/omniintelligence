# ONEX Anti-YOLO Method + BFROS Integration Template

**This template shows the minimal integration required for existing agents.**

## Integration Instructions

Add these references at the **beginning** of each agent file, right after the YAML frontmatter:

```markdown
---
[existing frontmatter]
---

# ONEX Anti-YOLO Method + BFROS Framework

**MANDATORY PRE-WORK**: Read and follow these common workflows before proceeding with domain-specific tasks:

@COMMON_WORKFLOW.md - Anti-YOLO systematic approach and BFROS reasoning templates
@COMMON_RAG_INTELLIGENCE.md - Standardized RAG intelligence integration patterns  
@COMMON_ONEX_STANDARDS.md - ONEX standards, four-node architecture, and quality gates
@COMMON_AGENT_PATTERNS.md - Agent architecture patterns and collaboration standards
@COMMON_CONTEXT_INHERITANCE.md - Context preservation protocols for agent delegation
@COMMON_CONTEXT_LIFECYCLE.md - Smart context management and intelligent refresh

[Continue with existing agent content...]
```

## Agent-Specific Customizations

### For Agents with Existing RAG Integration
**If agent already has RAG sections**, replace with reference:
```markdown
## Enhanced RAG Intelligence Integration

**See @COMMON_RAG_INTELLIGENCE.md for standardized patterns.**

Domain-specific customizations:
- Replace `{domain}` with "{your_domain}" (e.g., "contract_validation")
- Replace `{agent_type}` with "{your_agent_type}" (e.g., "contract_validator")
- Add any domain-specific query templates not covered in common patterns
```

### For Agents with ONEX Standards Sections
**If agent has ONEX standards content**, replace with reference:
```markdown
## ONEX Standards Compliance

**See @COMMON_ONEX_STANDARDS.md for complete requirements.**

Domain-specific standards:
- [Any domain-specific standards not covered in common document]
- [Specialized validation rules for this domain]
- [Domain-specific quality gates]
```

## Benefits of This Approach

`★ Insight ─────────────────────────────────────`
- **Token Efficiency**: Reduces each agent from ~600+ lines to ~300 lines
- **Consistency**: All agents follow identical systematic approach
- **Maintainability**: Updates to workflow happen in one place
- **Focus**: Agents stay focused on domain expertise vs generic workflow
`─────────────────────────────────────────────────`

## Files Modified

### Common Reference Files (Already Created)
- ✅ `COMMON_WORKFLOW.md` - Anti-YOLO + BFROS methodology
- ✅ `COMMON_RAG_INTELLIGENCE.md` - RAG integration patterns
- ✅ `COMMON_ONEX_STANDARDS.md` - ONEX compliance requirements  
- ✅ `COMMON_AGENT_PATTERNS.md` - Agent architecture standards

### Agent Files to Update (35+ files)
All agent files in `./agent-*.md`

## Implementation Priority

### Batch 1: Critical Orchestration Agents
- `AGENT_ONEX_COORDINATOR.md` (primary orchestrator)
- `AGENT_WORKFLOW_COORDINATOR.md` (execution coordinator)
- `AGENT_TICKET_MANAGER.md` (project management)

### Batch 2: Core Development Agents  
- `AGENT_CONTRACT_VALIDATOR.md` (standards compliance)
- `AGENT_CONTRACT_DRIVEN_GENERATOR.md` (code generation)
- `AGENT_PR_CREATE.md` (PR creation)
- `AGENT_PR_REVIEW.md` (PR review)
- `AGENT_TESTING.md` (quality assurance)

### Batch 3: Specialized Agents
- All remaining domain specialists

## Testing Strategy

After integration:
1. **Functionality Test**: Ensure agents still perform domain tasks correctly
2. **Workflow Test**: Verify systematic approach is followed
3. **Integration Test**: Confirm RAG and standards compliance work
4. **Performance Test**: Measure token usage reduction

---

**Next Step**: Apply this integration to the first batch of critical agents.
