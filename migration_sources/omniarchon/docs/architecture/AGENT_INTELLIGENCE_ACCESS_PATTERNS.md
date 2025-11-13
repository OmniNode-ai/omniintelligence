# Agent Intelligence Access Patterns

**Optimal strategies for agents to access repository intelligence and project context**

## 🎯 **Problem Statement**

After comprehensive repository ingestion (97 files, 69 protocols, 5 intelligence documents), agents need efficient patterns to access project-specific intelligence rather than generic documentation.

## ✅ **Most Effective Access Patterns**

### 1. **Direct Project Document Access** (⭐ RECOMMENDED)

```python
# Get structured project data with rich content
project = await get_project(project_id="project-uuid")
documents = project["docs"]  # Rich analysis documents with metadata
```

**Why it works:**
- Returns structured, categorized intelligence with metadata and tags
- Contains detailed class inventories, method signatures, architectural insights
- Includes performance metrics, validation requirements, implementation guidance

**Example Output:**
```python
{
  "key_classes": [
    {
      "file": "scripts/compare_import_performance.py",
      "name": "ImportPerformanceComparator",
      "purpose": "Compare performance between eager and lazy loading",
      "key_methods": ["run_comparison", "_benchmark_implementation"]
    }
  ],
  "performance_targets": ["60-80% import time reduction"],
  "validation_requirements": ["<50ms root module import time"]
}
```

### 2. **Task-Based Context Retrieval** (⭐ RECOMMENDED)

```python
# Get implementation-ready tasks with context
tasks = await list_tasks(
    project_id="project-uuid",
    filter_by="status",
    filter_value="todo"
)
```

**Why it works:**
- Tasks auto-created from repository ingestion contain specific implementation context
- Include acceptance criteria, technical notes, and feature classifications
- Provide workflow-ready implementation guidance

## ❌ **Less Effective Patterns**

### General RAG Queries (Avoid for Project-Specific Content)

```python
# Returns generic documentation, not project-specific intelligence
results = await perform_rag_query("ImportPerformanceComparator")
```

**Why it fails:**
- RAG searches general knowledge base, not project-specific ingested content
- Returns Claude Code documentation instead of repository intelligence
- Misses rich structured analysis from repository crawling

## 🚀 **Recommended Agent Implementation Patterns**

### **Development Agents (Code Implementation)**

```python
async def get_implementation_context(project_id: str, feature: str):
    """Get implementation-ready context for specific feature"""
    project = await get_project(project_id)

    # Filter by feature tags
    feature_docs = [
        doc for doc in project["docs"]
        if feature in doc["tags"] or feature in doc["title"].lower()
    ]

    # Extract actionable context
    return {
        "classes": extract_classes_from_docs(feature_docs),
        "methods": extract_methods_from_docs(feature_docs),
        "protocols": extract_protocols_from_docs(feature_docs),
        "performance_targets": extract_targets_from_docs(feature_docs),
        "validation_requirements": extract_validation_from_docs(feature_docs)
    }

# Usage example
context = await get_implementation_context(
    project_id="45a229a8-5eaa-4be7-84cb-5b6541322b81",
    feature="performance-optimization"
)
```

### **Analysis Agents (Architecture Review)**

```python
async def get_architecture_analysis(project_id: str):
    """Get comprehensive architecture intelligence"""
    project = await get_project(project_id)

    # Filter architecture-focused documents
    arch_docs = [
        doc for doc in project["docs"]
        if doc["document_type"] == "spec" or "architecture" in doc["tags"]
    ]

    return {
        "protocol_domains": extract_protocol_domains(arch_docs),  # 7 domains, 69 protocols
        "type_system": extract_type_definitions(arch_docs),
        "spi_compliance": extract_compliance_status(arch_docs),
        "architectural_principles": extract_principles(arch_docs)
    }
```

### **Workflow Agents (Task Coordination)**

```python
async def get_workflow_context(project_id: str):
    """Get comprehensive workflow coordination context"""
    project = await get_project(project_id)
    active_tasks = await list_tasks(
        project_id=project_id,
        filter_by="status",
        filter_value="doing"
    )

    return {
        "project_intelligence": project["docs"],
        "active_tasks": active_tasks,
        "implementation_guidance": extract_implementation_guidance(project["docs"]),
        "validation_frameworks": extract_validation_frameworks(project["docs"])
    }
```

## 💡 **Key Intelligence Document Types**

Based on successful omnibase-spi ingestion, expect these document types:

### **"spec" Documents**
- Protocol inventories and architectural specifications
- Type system definitions and compliance requirements
- Performance requirements and validation criteria

### **"design" Documents**  
- Implementation mechanisms and patterns
- Lazy loading strategies and caching approaches
- Backward compatibility and optimization designs

### **"note" Documents**
- Processing statistics and success metrics
- Actionable insights and deployment readiness assessments
- Comprehensive analysis summaries

## 🔧 **Document Filtering Strategies**

### **By Tags** (Most Specific)
```python
perf_docs = [doc for doc in project["docs"] if "performance" in doc["tags"]]
impl_docs = [doc for doc in project["docs"] if "implementation" in doc["tags"]]  
test_docs = [doc for doc in project["docs"] if "testing" in doc["tags"]]
```

### **By Document Type** (Broad Categories)
```python
specs = [doc for doc in project["docs"] if doc["document_type"] == "spec"]
designs = [doc for doc in project["docs"] if doc["document_type"] == "design"]
analysis = [doc for doc in project["docs"] if doc["document_type"] == "note"]
```

### **By Content Patterns** (Semantic Search)
```python
class_docs = [doc for doc in project["docs"] if "key_classes" in doc["content"]]
protocol_docs = [doc for doc in project["docs"] if "protocol_domains" in doc["content"]]
```

## 📊 **Expected Intelligence Quality**

From successful omnibase-spi ingestion (97 files → 5 documents):

- **Class Discovery**: 45 classes with method signatures and purposes
- **Protocol Mapping**: 69 protocols across 7 architectural domains  
- **Performance Metrics**: Specific targets (60-80% improvement, <50ms thresholds)
- **Validation Coverage**: 100% test coverage analysis with framework details
- **Implementation Guidance**: File-specific recommendations with line counts

## 🎯 **Agent Architecture Recommendations**

### **1. Project-First Approach**
Always start with project context, not general searches:
```python
project = await get_project(project_id)  # Rich structured intelligence
# NOT: results = await perform_rag_query("general topic")
```

### **2. Tag-Based Filtering**  
Use document tags for precise context:
```python
feature_docs = [doc for doc in docs if target_feature in doc["tags"]]
```

### **3. Multi-Document Synthesis**
Combine multiple document types for complete picture:
```python
context = {
    "architecture": get_spec_docs(docs),
    "implementation": get_design_docs(docs),
    "validation": get_note_docs(docs),
    "tasks": await get_related_tasks(project_id, feature)
}
```

### **4. Content Structure Awareness**
Different documents have different content structures:
```python
# Spec documents: protocol_domains, type_system, architectural_principles
# Design documents: lazy_loading_mechanism, performance_improvements
# Note documents: processing_success_rate, actionable_insights
```

## ✨ **Success Example: omnibase-spi Performance Optimization**

Using these patterns, agents can access:

- **Import optimization classes** with specific method signatures
- **Performance targets** (60-80% reduction, <50ms thresholds)  
- **Protocol inventories** (69 protocols across 7 domains)
- **Validation frameworks** with 100% coverage details
- **Implementation files** with exact line counts (543, 476, 550 lines)

All from structured, tagged, categorized intelligence documents rather than unstructured searches.

## 🔄 **Integration with Agent Factory**

These patterns should be integrated into:
- **Pydantic AI agents** for implementation context
- **Task coordination agents** for workflow management  
- **Code quality agents** for validation frameworks
- **Performance agents** for optimization guidance

The repository crawler creates the intelligence foundation - these patterns ensure agents can effectively leverage that intelligence for development workflows.
