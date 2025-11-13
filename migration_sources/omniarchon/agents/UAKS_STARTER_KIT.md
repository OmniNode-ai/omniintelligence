# 🚀 UAKS Starter Kit - Get Knowledge Capture Working Today

## Current Status
- ✅ All 39 agents reference @ARCHON_INTEGRATION.md framework
- ✅ Archon MCP is healthy and running
- ❌ Knowledge base is empty (no agent executions yet)
- ❌ Need to test actual knowledge capture

## Step 1: Create Test Project & Task

Let's start knowledge capture by creating a test project and running an agent:

```python
# Create test project for UAKS validation
test_project = mcp__archon__create_project(
    title="UAKS Knowledge Capture Test",
    description="""
Test project to validate Unified Agent Knowledge System (UAKS)
knowledge capture and cross-domain intelligence sharing.

This project will test:
- Basic knowledge capture via Phase 4
- Enhanced RAG query patterns  
- Cross-agent intelligence sharing
- Progressive intelligence improvement
    """,
    github_repo="https://github.com/test/uaks-validation"
)

# Create test task
test_task = mcp__archon__create_task(
    project_id=test_project['project_id'],
    title="Test agent knowledge capture",
    description="Execute an agent to validate knowledge capture works",
    assignee="User"
)
```

## Step 2: Enhanced RAG Query Templates

Update agents to use these enhanced query patterns:

### Basic Enhanced Query Pattern
```python
# Instead of simple queries:
OLD: "API design patterns"

# Use collective intelligence queries:
NEW: f"""
{base_query} enhanced with Claude Code agent collective intelligence.

Include insights from previous agent executions:
- Successful patterns from execution_report documents
- Lessons learned from similar tasks  
- Cross-domain insights from related agents
- Proven approaches with high effectiveness

Context: {current_repository} - {current_task_type}
Focus: Reusable solutions with demonstrated success
"""
```

### Cross-Domain Query Patterns
```python
# For debug agents:
debug_enhanced_query = f"""
Debugging patterns for {issue_type} including:
- Similar incidents resolved by agent-debug-intelligence
- Performance implications from agent-performance reports
- Security considerations from agent-security-audit findings
- Code quality insights from agent-code-quality-analyzer
- Infrastructure patterns from agent-devops-infrastructure

Repository: {repo_name}
Issue context: {issue_description}
"""

# For performance agents:  
performance_enhanced_query = f"""
Performance optimization for {performance_issue} leveraging:
- Previous optimizations from agent-performance executions
- Code quality patterns from agent-code-quality-analyzer  
- Infrastructure insights from agent-devops-infrastructure
- Debugging patterns from successful incident resolutions

System context: {system_description}
Performance target: {target_metrics}
"""
```

## Step 3: Simple Knowledge Capture Function

Add this to any agent that gets executed:

```python
async def capture_basic_knowledge(execution_results, agent_type, task_id):
    """
    Basic knowledge capture for UAKS - simplified version to start.
    """

    knowledge_summary = {
        "agent_execution": {
            "agent_type": agent_type,
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": task_id,
            "success": execution_results.get('success', True),
            "duration_seconds": execution_results.get('duration', 0)
        },
        "patterns_discovered": execution_results.get('patterns_found', []),
        "successful_strategies": execution_results.get('successful_approaches', []),
        "lessons_learned": execution_results.get('lessons', []),
        "reusable_insights": execution_results.get('reusable_solutions', []),
        "cross_domain_notes": execution_results.get('cross_domain_insights', [])
    }

    # Store in Archon for RAG access
    knowledge_doc = mcp__archon__create_document(
        project_id=execution_results['project_id'],
        title=f"Knowledge Capture - {agent_type} - {datetime.now().strftime('%Y%m%d-%H%M%S')}",
        document_type="agent_knowledge",
        content=knowledge_summary,
        tags=["uaks", "knowledge_capture", agent_type, "collective_intelligence"],
        author="UAKS System"
    )

    return knowledge_doc
```

## Step 4: Test With Key Agents

Start with these high-value agents for testing:

1. **agent-debug** - Good for capturing troubleshooting patterns
2. **agent-code-quality-analyzer** - Captures quality insights  
3. **agent-api-architect** - Captures design patterns
4. **agent-security-audit** - Captures security patterns

## Step 5: Validation Queries

Test that knowledge sharing works:

```python
# After running a few agents, test cross-domain queries:

# Check captured knowledge
all_knowledge = mcp__archon__perform_rag_query(
    query="agent_knowledge document_type collective_intelligence",
    match_count=10
)

# Test cross-domain intelligence
debug_security_patterns = mcp__archon__perform_rag_query(
    query="debugging patterns security implications lessons_learned",
    match_count=5
)

# Test pattern reuse
successful_strategies = mcp__archon__perform_rag_query(
    query="successful_strategies reusable_insights proven approaches",
    match_count=8
)
```

## Quick Start Commands

### 1. Create Test Environment
```bash
# Test Archon connectivity
python -c "
from mcp__archon__health_check import *
print('Health:', mcp__archon__health_check())
"
```

### 2. Run First Knowledge Capture Test
Execute any agent (debug, quality, etc.) and ensure it creates knowledge documents with the enhanced capture function.

### 3. Verify Knowledge Storage
```python
# Check knowledge was captured
knowledge = mcp__archon__perform_rag_query(
    query="agent_knowledge uaks collective_intelligence",
    match_count=5
)
print(f"Captured knowledge docs: {len(knowledge.get('results', []))}")
```

### 4. Test Enhanced Queries
Once knowledge exists, test enhanced RAG queries that reference previous agent executions.

## Success Criteria

✅ **Phase 1 Success**:
- At least 3 agents have executed and captured knowledge
- Knowledge documents are queryable via RAG
- Enhanced queries return relevant cross-domain insights

✅ **Phase 2 Success**:
- Agents consistently use enhanced RAG queries
- Cross-domain patterns are being discovered
- Knowledge base grows automatically with each execution

✅ **Phase 3 Success**:
- Measurable improvement in agent success rates
- Automatic pattern correlation across domains
- Predictive intelligence working

The key is to **start simple** - get basic knowledge capture working first, then enhance the intelligence patterns progressively!
