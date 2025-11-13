# Common RAG Intelligence Integration Patterns

**MANDATORY**: All ONEX agents use these standardized RAG intelligence patterns for enhanced performance and consistency.

**⚠️ CRITICAL**: Use Archon MCP tools for knowledge queries - Archon provides comprehensive RAG intelligence and project management. Use `mcp__archon__perform_rag_query` and `mcp__archon__search_code_examples` for intelligent context retrieval.

## Standard RAG Integration Framework

### Primary: Archon MCP RAG Integration Protocol
```yaml
rag_integration:
  primary_method: "mcp__archon__perform_rag_query"  # Archon intelligence system
  query_strategy: "{domain}_specific_context_retrieval"
  fallback_enabled: true
  context_integration: "mandatory"
  code_examples: "mcp__archon__search_code_examples"  # Code pattern search
```

### Secondary: Direct Knowledge Base Integration
**Fallback Protocol** when MCP RAG unavailable:
```python
from omnibase.agents.base.rag_knowledge_integration import RAGKnowledgeIntegration

class BaseAgent:
    def __init__(self):
        self.rag_integration = RAGKnowledgeIntegration(agent_id="{agent_type}_agent")

    async def gather_intelligence(self, context):
        """Enhanced pre-task intelligence gathering."""

        # 1. Query Archon MCP RAG intelligence system
        try:
            mcp_results = mcp__archon__perform_rag_query(
                query=f"{self.domain}: {context.task_type} {context.scope}",
                match_count=5
            )
        except Exception:
            mcp_results = []

        # 2. Direct RAG fallback for historical patterns
        historical_patterns = await self.rag_integration.query_knowledge(
            KnowledgeQuery(
                query=f"{self.domain}: {context.task_type} {context.scope}",
                agent_context=f"{self.domain}:patterns",
                top_k=5
            )
        )

        return {
            "mcp_intelligence": mcp_results,
            "historical_patterns": historical_patterns,
            "intelligence_confidence": self.calculate_confidence(mcp_results, historical_patterns)
        }
```

## Standard RAG Query Templates

**⚠️ ONLY use `mcp__archon__perform_rag_query` - NEVER Context7 for ONEX queries**

### Primary Domain Query
```bash
# ✅ CORRECT - Internal ONEX knowledge
mcp__archon__perform_rag_query("Find ONEX {domain} patterns for {task_type} with {complexity_level}. Include successful methodologies, common patterns, and effective approaches.")

# ❌ FORBIDDEN - Context7 has no ONEX knowledge
mcp__context7__get-library-docs("ONEX")  # Will fail
```

### Problem Resolution Query  
```bash
# ✅ CORRECT - Internal ONEX knowledge
mcp__archon__perform_rag_query("Retrieve ONEX {domain} resolution patterns for {issue_category}. Include root cause methodologies, successful solutions, and resolution shortcuts.")
```

### Best Practices Query
```bash
# ✅ CORRECT - Internal ONEX knowledge
mcp__archon__perform_rag_query("Find ONEX {domain} best practices for {specific_area}. Include quality patterns, compliance approaches, and validated methodologies.")
```

### Standards Compliance Query
```bash
# ✅ CORRECT - Internal ONEX knowledge
mcp__archon__perform_rag_query("Find current ONEX standards compliance patterns for {compliance_area}. Include modern approaches, deprecated pattern detection, and modernization strategies.")
```

## Enhanced Codanna Code Intelligence Integration

### Standard Codanna Integration Protocol
```yaml
codanna_integration:
  primary_method: "mcp__codanna__semantic_search_with_context"
  symbol_search: "mcp__codanna__search_symbols"
  impact_analysis: "mcp__codanna__analyze_impact"
  caller_analysis: "mcp__codanna__find_callers"
  fallback_enabled: true
  context_integration: "mandatory"
```

### Standard Codanna Query Templates
```bash
# Semantic code search for domain patterns
mcp__codanna__semantic_search_with_context("Find {domain_pattern_type} patterns in ONEX codebase related to {specific_topic}. Include implementation examples and usage patterns.")

# Symbol search for precise targets
mcp__codanna__search_symbols("query: {target_symbol} kind: {Function|Class|Trait}")

# Impact analysis for scope assessment
mcp__codanna__analyze_impact("symbol_name: {target_component}")

# Caller analysis for understanding context
mcp__codanna__find_callers("function_name: {relevant_function}")
```

## Intelligence-Enhanced Workflow Phases

### Phase 1: Enhanced Context Gathering
```yaml
compound_intelligence_gathering:
  rag_patterns: "mcp__archon__perform_rag_query: Find {domain} patterns for {task_domain}"
  codebase_context: "mcp__codanna__semantic_search_with_context: Locate {pattern} implementations"
  symbol_analysis: "mcp__codanna__search_symbols: Find specific {components}"
  dependency_mapping: "mcp__codanna__analyze_impact: Assess {change_scope}"
```

### Phase 2: Intelligence-Guided Analysis
```yaml
enhanced_analysis_framework:
  semantic_code_search: "Find actual implementations of concepts being worked on"
  symbol_relationship_analysis: "Understand how components interact in codebase"
  impact_assessment: "Evaluate findings against actual codebase usage"
  caller_pattern_analysis: "Identify real usage patterns and dependencies"
```

### Phase 3: Learning Capture
```python
async def log_outcome(self, task_id, result):
    """Enhanced post-task learning capture."""

    if result.success:
        # Log successful pattern
        await self.rag_integration.update_knowledge(
            KnowledgeUpdate(
                title=f"{self.domain} Success: {result.task_name}",
                content=f"""## Task Overview
{result.task_description}

## Methodology
{result.methodology_details}

## Key Findings
{result.key_findings}

## Effective Patterns
{result.effective_patterns}

## Lessons Learned
{result.insights}""",
                agent_id=f"{self.domain}_agent",
                solution_type=f"{self.domain}_methodology",
                context={
                    "task_id": task_id,
                    "duration": result.time_spent,
                    "complexity": result.complexity,
                    "effectiveness": result.effectiveness_score
                }
            )
        )
```

## Quality-Filtered RAG Preferences

### Standard Quality Filters
```yaml
quality_preferences:
  quality_threshold: 0.7
  onex_compliance_threshold: 0.8
  temporal_preference: "last_9_months"
  architectural_era_preference: "modern_onex"
  exclude_legacy_patterns: true
```

### Pattern Filters
```yaml
pattern_filters:
  forbidden_patterns:
    - "Any types"
    - "manual import patterns"
    - "legacy patterns"
  preferred_patterns:
    - "current ONEX standards"
    - "modern validation patterns"
    - "contract-driven architecture"
    - "protocol-based interfaces"
```

### Standards Evolution Awareness
```yaml
standards_currency:
  track_standard_changes: true
  flag_deprecated_patterns: true
  recommend_modernization: true
```

## Intelligence Quality Metrics

### Standard Metrics Framework
```python
intelligence_metrics = {
    "rag_hit_rate": "Percentage of tasks enhanced by RAG intelligence",
    "pattern_prediction_accuracy": "How often historical patterns predict current solutions",
    "task_efficiency": "Time saved through intelligence-guided execution",
    "solution_effectiveness": "Quality of RAG-enhanced outcomes",
    "learning_integration": "Effectiveness of continuous learning capture"
}
```

## Usage Instructions

### For Agent Authors
1. **Copy standard patterns** instead of rewriting RAG integration
2. **Customize domain variables** in templates (replace `{domain}`, `{task_type}`, etc.)
3. **Use standard quality filters** unless domain-specific requirements differ
4. **Follow standard learning capture** for consistency across agents

### Template Variables to Customize
- `{domain}`: Agent's domain (e.g., "contract_validation", "testing", "research")
- `{agent_type}`: Agent type identifier (e.g., "contract_validator", "testing", "research")
- `{task_type}`: Specific task being performed
- `{complexity_level}`: Task complexity assessment
- `{scope}`: Task scope or target area

---

**Remember**: Use these patterns consistently across all agents to ensure standardized RAG intelligence integration and reduce context duplication.
