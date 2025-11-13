# Intelligence Integration Guide

**Common Intelligence Tools Reference for All ONEX Agents**

This document provides standardized integration patterns for Quality & Performance Intelligence capabilities. All agents should reference this file using `@INTELLIGENCE_INTEGRATION.md` rather than duplicating integration examples.

## 🧠 Available Intelligence Tools

### Quality Assessment Tools

#### assess_code_quality
Comprehensive code quality analysis with ONEX architectural compliance:
```python
quality_result = mcp__archon__assess_code_quality(
    content=code_content,
    source_path=file_path,
    language="python"  # or auto-detected language
)
```

#### analyze_document_quality  
Documentation and markdown quality analysis:
```python
doc_analysis = mcp__archon__analyze_document_quality(
    content=document_content,
    document_type="markdown",
    check_completeness=True
)
```

#### get_quality_patterns
Extract quality patterns and anti-patterns from code:
```python
patterns = mcp__archon__get_quality_patterns(
    content=code_content,
    pattern_type="best_practices"  # or "anti_patterns"
)
```

#### check_architectural_compliance
Verify ONEX architectural compliance:
```python
compliance = mcp__archon__check_architectural_compliance(
    content=code_content,
    architecture_type="onex"  # or "clean", "microservices"
)
```

### Performance Optimization Tools

#### establish_performance_baseline
Create performance baselines for systematic optimization:
```python
baseline_result = mcp__archon__establish_performance_baseline(
    operation_name="api_endpoint_processing",
    metrics={
        "response_time_ms": 245,
        "throughput_rps": 1200,
        "cpu_usage_percent": 65,
        "memory_usage_mb": 512
    }
)
```

#### identify_optimization_opportunities
Discover performance optimization opportunities:
```python
opportunities = mcp__archon__identify_optimization_opportunities(
    operation_name="database_query_processing"
)
```

#### apply_performance_optimization
Apply specific performance optimizations:
```python
optimization_result = mcp__archon__apply_performance_optimization(
    operation_name="file_processing",
    optimization_type="caching",
    parameters={
        "cache_size_mb": 256,
        "cache_ttl_seconds": 3600,
        "cache_strategy": "lru"
    }
)
```

#### get_optimization_report
Generate comprehensive performance reports:
```python
performance_report = mcp__archon__get_optimization_report(
    time_window_hours=24
)
```

#### monitor_performance_trends
Monitor performance trends with predictive analysis:
```python
trends = mcp__archon__monitor_performance_trends(
    time_window_hours=168,  # 1 week
    include_predictions=True
)
```

## 🔄 Common Intelligence Patterns

### Quality-Enhanced Task Creation
```python
def create_intelligence_enhanced_task(project_id, component_name, task_type):
    """Standard task creation with intelligence context"""
    return mcp__archon__create_task(
        project_id=project_id,
        title=f"{task_type}: {component_name}",
        description=f"""
        ## {task_type} Scope
        - Component: {component_name}
        - Intelligence: Quality & Performance tools enabled
        - Standards: ONEX compliance and best practices

        ## Intelligence-Enhanced Analysis
        - Automated quality assessment and compliance verification
        - Performance baseline establishment and optimization
        - Pattern detection and trend analysis
        - Predictive issue identification
        """,
        assignee=f"{task_type} Team",
        feature=task_type.lower().replace(' ', '_')
    )
```

### Multi-Dimensional Analysis Pattern
```python
def perform_comprehensive_analysis(code_content, file_path, component_name):
    """Standard comprehensive analysis using all intelligence tools"""
    analysis_results = {}

    # Quality Assessment
    analysis_results['quality'] = mcp__archon__assess_code_quality(
        content=code_content,
        source_path=file_path,
        language=detect_language(file_path)
    )

    # Architectural Compliance
    analysis_results['compliance'] = mcp__archon__check_architectural_compliance(
        content=code_content,
        architecture_type="onex"
    )

    # Pattern Analysis
    analysis_results['patterns'] = mcp__archon__get_quality_patterns(
        content=code_content,
        pattern_type="best_practices"
    )

    # Performance Baseline
    analysis_results['performance'] = mcp__archon__establish_performance_baseline(
        operation_name=f"analysis_{component_name}",
        metrics=measure_component_performance(component_name)
    )

    return analysis_results
```

### Intelligence-Enhanced Research Pattern
```python
def perform_intelligence_research(domain_context, technology_stack):
    """Standard research pattern combining RAG and intelligence tools"""
    # RAG Intelligence Query
    rag_research = mcp__archon__perform_rag_query(
        query=f"{domain_context} {technology_stack} best practices patterns",
        match_count=5
    )

    # Code Examples Search
    code_examples = mcp__archon__search_code_examples(
        query=f"{domain_context} {technology_stack} implementation patterns",
        match_count=3
    )

    # Performance Trends Analysis
    performance_trends = mcp__archon__monitor_performance_trends(
        time_window_hours=168,
        include_predictions=True
    )

    return {
        'rag_intelligence': rag_research,
        'code_examples': code_examples,
        'performance_trends': performance_trends
    }
```

## 📊 Intelligence Integration Workflow

### Step 1: Context & Intelligence Establishment
1. Create intelligence-enhanced task using `create_intelligence_enhanced_task()`
2. Perform comprehensive analysis using `perform_comprehensive_analysis()`
3. Gather research intelligence using `perform_intelligence_research()`

### Step 2: Intelligence-Guided Execution
1. Apply intelligence insights to guide implementation decisions
2. Use quality tools for continuous compliance verification
3. Use performance tools for optimization opportunities
4. Monitor trends for predictive analysis

### Step 3: Intelligence Capture & Learning
1. Document all intelligence insights in RAG using `mcp__archon__create_document()`
2. Update task progress with intelligence findings
3. Capture patterns for future intelligence enhancement

## 🎯 Success Metrics with Intelligence

**Quality Intelligence Metrics:**
- Automated quality scoring with objective measurements
- ONEX architectural compliance percentage  
- Anti-pattern identification and elimination
- Best practice adoption rate

**Performance Intelligence Metrics:**
- Baseline establishment and improvement tracking
- Optimization opportunity identification rate
- Performance trend prediction accuracy
- Proactive optimization success rate

**Knowledge Intelligence Metrics:**
- RAG query relevance and accuracy
- Pattern recognition improvement over time
- Predictive analysis effectiveness
- Cross-agent intelligence sharing success

## 🔧 Agent-Specific Integration

Each agent should:
1. Reference this file with `@PHASE_5A_INTELLIGENCE_INTEGRATION.md`
2. Customize intelligence tools based on agent domain (quality, performance, debug, etc.)
3. Follow common patterns while adding agent-specific intelligence logic
4. Contribute intelligence insights back to RAG for community benefit

## 📚 Intelligence Tool Reference Quick Guide

**Quality Focus:** Use `assess_code_quality`, `check_architectural_compliance`, `get_quality_patterns`
**Performance Focus:** Use `establish_performance_baseline`, `identify_optimization_opportunities`, `apply_performance_optimization`
**Debug Focus:** Use quality tools for bug analysis + performance tools for performance issues
**Research Focus:** Combine all tools with RAG queries for comprehensive analysis
**Monitoring Focus:** Use `monitor_performance_trends`, `get_optimization_report` for ongoing intelligence

---

**Integration Status:** ✅ Intelligence Tools Deployed and Accessible
**Last Updated:** September 2025
**Tool Count:** 9 intelligence tools (4 quality + 5 performance)
