# Common Agent Architecture Patterns

**MANDATORY**: All ONEX agents follow these standardized patterns for consistency and maintainability.

## Standard Agent Structure

### YAML Frontmatter (Required)
```yaml
---
name: agent-{domain}-{specialty}
description: {One-line description of agent's single responsibility}
color: {blue|green|gray|purple|red|yellow}
task_agent_type: {domain}_{specialty}
---
```

### Agent Philosophy Section (Required)
```markdown
## Agent Philosophy
Following clean agent principles:
- Single, clear responsibility: {Specific responsibility statement}
- Context-focused on {Primary context area}
- {Approach description} approach to {Domain area}
```

### Core Responsibility Section (Required)  
```markdown
## Core Responsibility
{Single, clear sentence describing the agent's primary responsibility and value proposition.}
```

### Activation Triggers Section (Required)
```markdown
## Activation Triggers
AUTOMATICALLY activate when users request:
- "{primary_trigger}" / "{secondary_trigger}" / "{tertiary_trigger}"
- "{category_trigger}" / "{action_trigger}" / "{domain_trigger}"
- "{specific_trigger}" / "{alternative_trigger}" / "{context_trigger}"
```

## Standard Workflow Patterns

### Pre-Work Intelligence Gathering
```markdown
### Enhanced {Domain} Context Gathering
```yaml
compound_intelligence_gathering:
  rag_patterns: "mcp__archon__perform_rag_query: Find {domain} patterns for {task_domain}"
  codebase_context: "mcp__codanna__semantic_search_with_context: Locate {pattern} implementations"
  symbol_analysis: "mcp__codanna__search_symbols: Find specific {components}"
  dependency_mapping: "mcp__codanna__analyze_impact: Assess {change_scope}"
```

### Domain-Specific Analysis Framework
```markdown
### Enhanced {Domain} Analysis Framework
```yaml
enhanced_{domain}_analysis_framework:
  semantic_code_search: "Find actual implementations of {domain_concepts}"
  symbol_relationship_analysis: "Understand how {domain_components} interact"
  impact_assessment: "Evaluate {domain_findings} against actual usage"
  caller_pattern_analysis: "Identify real {domain_usage} patterns and dependencies"
```

### Learning Capture Pattern
```markdown
### Continuous Learning Integration
```python
# Enhanced Pattern Extraction with Dual RAG
learning_extraction = {
    "mcp_intelligence": "Query MCP for ONEX-specific {domain} patterns and standards",
    "direct_rag_patterns": "Historical {domain} patterns and effectiveness metrics",
    "successful_{domain}": "Which {domain} approaches consistently achieve goals?",
    "{domain}_indicators": "{Domain} patterns that predict success/issues",
    "effective_{domain}_methods": "{Domain} approaches that lead to successful outcomes",
    "{domain}_evolution": "How {domain} needs change over time and system evolution"
}

# {Domain} Intelligence Quality Metrics
intelligence_metrics = {
    "rag_hit_rate": "Percentage of {domain} tasks enhanced by RAG intelligence",
    "{domain}_accuracy": "How often historical patterns predict current {domain} outcomes",
    "{domain}_efficiency": "Time saved through intelligence-guided {domain} work",
    "solution_effectiveness": "Quality of RAG-enhanced {domain} outputs",
    "{domain}_learning": "Effectiveness of {domain} learning capture"
}
```

## Standard Color Coding

### Color Semantics
- **Blue**: Coordination, orchestration, management agents
- **Green**: Execution, implementation, action agents  
- **Gray**: Analysis, research, investigation agents
- **Purple**: Intelligence, knowledge, learning agents
- **Red**: Security, validation, compliance agents
- **Yellow**: Generation, creation, building agents

### Agent Categories by Color
```markdown
**Blue Agents** (Coordination):
- agent-onex-coordinator
- agent-workflow-coordinator
- agent-ticket-manager

**Green Agents** (Execution):
- agent-commit
- agent-pr-create
- agent-address-pr-comments

**Gray Agents** (Analysis):
- agent-research
- agent-contract-validator
- agent-performance

**Purple Agents** (Intelligence):
- agent-debug-intelligence
- agent-rag-query
- agent-rag-update

**Red Agents** (Security):
- agent-security-audit
- agent-type-validator

**Yellow Agents** (Generation):
- agent-contract-driven-generator
- agent-ast-generator
```

## Standard Section Templates

### Categories Section Template
```markdown
## {Domain} Categories

### {Category 1}
- **{Subcategory 1}**: {Description}
- **{Subcategory 2}**: {Description}
- **{Subcategory 3}**: {Description}
- **{Subcategory 4}**: {Description}

### {Category 2}
- **{Subcategory 1}**: {Description}
- **{Subcategory 2}**: {Description}

### ONEX-Specific {Domain}
- **{ONEX Subcategory 1}**: {ONEX-specific description}
- **{ONEX Subcategory 2}**: {ONEX-specific description}
```

### Workflow Section Template
```markdown
## Enhanced {Domain} Workflow

### 1. Enhanced {Step 1} Analysis
- {Action 1} with intelligence enhancement
  - **RAG Enhancement**: Query historical {context} patterns
- {Action 2} with pattern integration
  - **Intelligence Integration**: Reference {domain} patterns from knowledge base
- {Action 3} with context awareness
  - **Pattern Matching**: Apply {pattern_type} from successful {domain} work
```

### Integration Points Template  
```markdown
## Integration with ONEX Tools

### Tool Coordination
- **{Tool 1}**: {Coordination description}
- **{Tool 2}**: {Coordination description}

### {Domain} Pipeline
1. **Pre-{Action}**: {Pre-work description}
2. **During-{Action}**: {During-work description}
3. **Post-{Action}**: {Post-work description}
```

### Collaboration Points Template
```markdown
## Collaboration Points
Route to complementary agents when:
- {Condition 1} → `agent-{target-agent-1}`
- {Condition 2} → `agent-{target-agent-2}`
- {Condition 3} → `agent-{target-agent-3}`
- {Condition 4} → `agent-{target-agent-4}`
```

### Success Metrics Template
```markdown
## Success Metrics
- {Metric 1 description}
- {Metric 2 description}
- {Metric 3 description}
- {Metric 4 description}
- {Metric 5 description}

Focus on {summary of agent's value proposition and key outcomes}.
```

## Agent Naming Conventions

### Naming Pattern
```
agent-{domain}-{specialty}
```

### Domain Categories
- **contract**: Contract-related operations (validator, generator)
- **pr**: Pull request operations (create, review, address-comments)
- **debug**: Debugging and troubleshooting (intelligence, log-writer)
- **workflow**: Workflow orchestration (coordinator, generator)
- **rag**: Knowledge operations (query, update)
- **velocity**: Metrics and tracking (tracker, log-writer)
- **security**: Security operations (audit)
- **testing**: Quality assurance (testing)
- **research**: Investigation and analysis (research)
- **performance**: Performance optimization (performance)

### Specialty Suffixes
- **coordinator**: Orchestration and routing
- **validator**: Validation and compliance  
- **generator**: Creation and generation
- **manager**: Management and lifecycle
- **tracker**: Tracking and monitoring
- **writer**: Data writing and persistence
- **intelligence**: AI-enhanced analysis
- **audit**: Security and compliance review

## File Organization Standards

### Directory Structure
```
.claude/agents/onex/
├── COMMON_WORKFLOW.md
├── COMMON_RAG_INTELLIGENCE.md
├── COMMON_ONEX_STANDARDS.md
├── COMMON_AGENT_PATTERNS.md
├── AGENT_ONEX_COORDINATOR.md (primary orchestrator)
├── AGENT_WORKFLOW_COORDINATOR.md  
├── AGENT_TICKET_MANAGER.md
├── AGENT_CONTRACT_VALIDATOR.md
├── AGENT_CONTRACT_DRIVEN_GENERATOR.md
├── AGENT_PR_CREATE.md
├── AGENT_PR_REVIEW.md
├── AGENT_ADDRESS_PR_COMMENTS.md
├── AGENT_TESTING.md
├── AGENT_SECURITY_AUDIT.md
├── AGENT_RESEARCH.md
├── AGENT_PERFORMANCE.md
├── AGENT_DEBUG_INTELLIGENCE.md
├── AGENT_RAG_QUERY.md
├── AGENT_RAG_UPDATE.md
├── AGENT_COMMIT.md
└── [other specialized agents]
```

### Agent Size Guidelines
- **Primary content**: Agent-specific domain expertise and workflows
- **Common references**: Use `@COMMON_*.md` references instead of duplication
- **Target size**: 200-400 lines per agent (excluding common content)
- **Focus**: Domain-specific intelligence and specialized capabilities

## Usage Instructions

### For Agent Creation
1. **Copy agent template structure** from this document
2. **Customize domain variables** throughout template
3. **Add `@COMMON_*.md` references** at beginning
4. **Focus on unique domain expertise** in main content
5. **Follow naming conventions** consistently

### For Agent Updates
1. **Preserve existing structure** and established patterns
2. **Update common references** instead of duplicating content
3. **Maintain color coding** and categorization consistency
4. **Keep domain focus** without drifting into generic functionality

### Template Variables to Replace
- `{domain}`: Agent's primary domain (contract, pr, debug, etc.)
- `{specialty}`: Agent's specialty (validator, generator, coordinator, etc.)
- `{Domain}`: Capitalized domain name for headings
- `{description}`: One-line agent description
- `{responsibility}`: Core responsibility statement
- `{triggers}`: Activation trigger keywords

---

**Remember**: Use these patterns to maintain consistency across all agents while keeping individual agents focused on their domain expertise.
