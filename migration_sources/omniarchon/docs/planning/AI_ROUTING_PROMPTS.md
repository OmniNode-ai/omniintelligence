# AI Routing Prompt Engineering Guide

**Version**: 1.0.0
**Date**: October 1, 2025
**Purpose**: Complete prompt templates and examples for AI-powered agent routing

---

## Overview

This document contains the complete prompt engineering system for AI-powered agent routing, including system prompts, agent registry formatting, user query templates, and expected output schemas.

---

## System Prompt

### Primary System Prompt

```
You are an expert agent routing specialist for the ONEX agent ecosystem. Your role is to analyze user requests and recommend the most appropriate specialized agent(s) from a comprehensive agent registry.

**Your Expertise:**
- Deep understanding of 48+ specialized ONEX agents across 6 categories
- Semantic analysis of user intent and task requirements
- Multi-agent workflow coordination and sequencing
- Context-aware recommendations based on project domain and history

**Agent Registry Context:**
You have access to a comprehensive registry of 48 specialized agents organized into 6 categories:

1. **Development** (12 agents) - Core coding, frameworks, languages
   - Python/FastAPI expertise, code generation, debugging

2. **Architecture** (8 agents) - System design, API architecture, patterns
   - API design, microservices, system architecture

3. **Quality** (8 agents) - Testing, security, performance, code quality
   - Testing strategies, security audits, performance optimization, code quality analysis

4. **Infrastructure** (6 agents) - DevOps, monitoring, deployment
   - Container orchestration, CI/CD, production monitoring

5. **Coordination** (7 agents) - Project management, workflows, tickets
   - Task management, workflow orchestration, parameter collection

6. **Documentation** (5 agents) - Technical writing, knowledge management
   - API documentation, technical writing, knowledge indexing

**Your Task:**
Analyze the user's request and recommend the top 1-3 most suitable agents, ranked by fit quality. Consider:

1. **Explicit Capabilities**: Match user needs to agent capabilities
2. **Domain Context**: Consider the project domain and current work
3. **Task Complexity**: Single agent vs multi-agent workflow
4. **Specialization Level**: Expert vs specialist agents
5. **Workflow Considerations**: Sequential vs parallel agent usage

**Output Requirements:**
For each recommendation, provide:

1. **agent_name**: Internal identifier from registry (e.g., "debug-intelligence")
2. **confidence**: 0.0-1.0 score indicating fit quality
3. **reasoning**: 2-3 sentences explaining why this agent is appropriate
4. **capabilities_match**: List of relevant capabilities from the agent
5. **alternative_considerations**: If applicable, mention other viable options or workflow sequencing

**Confidence Score Guidelines:**
- **0.9-1.0**: Perfect match - agent explicitly designed for this exact task
- **0.7-0.9**: Strong match - agent capabilities clearly align with requirements
- **0.5-0.7**: Reasonable match - agent can handle task but may not be ideal
- **0.3-0.5**: Weak match - agent can partially help but significant gaps exist
- **0.0-0.3**: Poor match - agent not appropriate for this task

**Multi-Agent Workflow Guidelines:**
When a task requires multiple agents:
- Identify the **primary agent** for the main task
- Suggest **secondary agents** for supporting tasks
- Provide **workflow_suggestion** explaining sequencing
- Example: "Use debug-intelligence for diagnosis, then agent-performance for optimization"

**Output Format:**
Respond ONLY with valid JSON matching this schema (no additional text):

{
  "recommendations": [
    {
      "agent_name": "agent-identifier",
      "confidence": 0.0-1.0,
      "reasoning": "2-3 sentences explaining the match",
      "capabilities_match": ["capability1", "capability2"],
      "alternative_considerations": "Optional context about alternatives",
      "workflow_suggestion": "Optional workflow sequencing guidance"
    }
  ]
}

**Important Notes:**
- Be conservative with confidence scores - overconfidence is worse than underconfidence
- For ambiguous queries, provide multiple options with clear tradeoffs
- Consider domain context when choosing between similar agents
- Explain your reasoning clearly - users need to understand why you chose this agent
- If no agent is a good match, say so explicitly with low confidence scores
```

---

## Agent Registry Format

### Complete Agent Registry JSON

```json
{
  "registry_version": "1.0.0",
  "total_agents": 48,
  "last_updated": "2025-10-01",

  "categories": {
    "development": {
      "count": 12,
      "priority": "high",
      "description": "Core coding, frameworks, and language specialists"
    },
    "architecture": {
      "count": 8,
      "priority": "high",
      "description": "System design, API architecture, and patterns"
    },
    "quality": {
      "count": 8,
      "priority": "medium",
      "description": "Testing, security, performance, and code quality"
    },
    "infrastructure": {
      "count": 6,
      "priority": "medium",
      "description": "DevOps, monitoring, and deployment"
    },
    "coordination": {
      "count": 7,
      "priority": "high",
      "description": "Project management, workflows, and orchestration"
    },
    "documentation": {
      "count": 5,
      "priority": "low",
      "description": "Technical writing and knowledge management"
    }
  },

  "agents": [
    {
      "id": "api-architect",
      "name": "agent-api-architect",
      "title": "API Architect Specialist",
      "category": "architecture",
      "description": "RESTful API design, OpenAPI specification, FastAPI optimization, and API ecosystem management expert for ONEX services",
      "capabilities": [
        "api_design",
        "openapi_specs",
        "fastapi_optimization",
        "microservices",
        "http_services"
      ],
      "triggers": [
        "api design",
        "openapi",
        "rest api",
        "fastapi",
        "microservices",
        "endpoint"
      ],
      "domain": "api_development",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "debug-intelligence",
      "name": "agent-debug-intelligence",
      "title": "Debug Intelligence Specialist",
      "category": "development",
      "description": "Comprehensive debugging and root cause analysis with intelligent problem-solving",
      "capabilities": [
        "debugging",
        "root_cause_analysis",
        "error_investigation",
        "performance_correlation",
        "system_behavior"
      ],
      "triggers": [
        "debug",
        "error",
        "troubleshoot",
        "investigate",
        "root cause",
        "bug"
      ],
      "domain": "debugging",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "testing",
      "name": "agent-testing",
      "title": "Testing Specialist",
      "category": "quality",
      "description": "Testing specialist for comprehensive test strategy and quality assurance",
      "capabilities": [
        "test_strategy",
        "quality_assurance",
        "test_automation",
        "coverage_analysis",
        "onex_testing"
      ],
      "triggers": [
        "test",
        "testing",
        "quality assurance",
        "test strategy",
        "coverage"
      ],
      "domain": "quality_assurance",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "performance",
      "name": "agent-performance",
      "title": "Performance Optimization Specialist",
      "category": "quality",
      "description": "Performance optimization specialist for bottleneck detection and system efficiency",
      "capabilities": [
        "performance_optimization",
        "bottleneck_detection",
        "baseline_establishment",
        "trend_analysis"
      ],
      "triggers": [
        "performance",
        "optimization",
        "bottleneck",
        "efficiency",
        "benchmark"
      ],
      "domain": "performance_optimization",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "security-audit",
      "name": "agent-security-audit",
      "title": "Security Audit Specialist",
      "category": "quality",
      "description": "Security audit specialist for vulnerability assessment and penetration testing",
      "capabilities": [
        "vulnerability_assessment",
        "penetration_testing",
        "security_compliance",
        "threat_modeling",
        "risk_assessment"
      ],
      "triggers": [
        "security",
        "audit",
        "vulnerability",
        "penetration test",
        "compliance",
        "threat model"
      ],
      "domain": "security_assessment",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "code-quality-analyzer",
      "name": "agent-code-quality-analyzer",
      "title": "Code Quality Analyzer Specialist",
      "category": "quality",
      "description": "Focused code quality assessment for readability, complexity, and ONEX compliance",
      "capabilities": [
        "code_quality_assessment",
        "onex_compliance_verification",
        "anti_pattern_detection",
        "quality_improvement_recommendations",
        "documentation_quality_analysis"
      ],
      "triggers": [
        "code quality",
        "quality analysis",
        "compliance",
        "anti-patterns",
        "code review",
        "onex compliance"
      ],
      "domain": "quality_assurance",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "python-fastapi-expert",
      "name": "agent-python-fastapi-expert",
      "title": "Python FastAPI Expert Specialist",
      "category": "development",
      "description": "Advanced Python development, FastAPI framework mastery, and async programming",
      "capabilities": [
        "python_development",
        "fastapi_optimization",
        "async_programming",
        "python_ecosystem",
        "backend_development"
      ],
      "triggers": [
        "python",
        "fastapi",
        "async",
        "pydantic",
        "backend development"
      ],
      "domain": "python_development",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "devops-infrastructure",
      "name": "agent-devops-infrastructure",
      "title": "DevOps Infrastructure Specialist",
      "category": "infrastructure",
      "description": "Container orchestration, CI/CD pipeline optimization, and cloud deployment",
      "capabilities": [
        "container_orchestration",
        "ci_cd_pipeline_optimization",
        "cloud_deployment",
        "infrastructure_automation",
        "kubernetes_management",
        "docker_containerization"
      ],
      "triggers": [
        "devops",
        "infrastructure",
        "deployment",
        "ci/cd",
        "docker",
        "kubernetes"
      ],
      "domain": "infrastructure",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "production-monitor",
      "name": "agent-production-monitor",
      "title": "Production Monitoring Specialist",
      "category": "infrastructure",
      "description": "Comprehensive production monitoring and observability for 24/7 operations",
      "capabilities": [
        "real_time_monitoring",
        "system_observability",
        "alerting_automation",
        "performance_analytics",
        "incident_detection",
        "sla_slo_monitoring"
      ],
      "triggers": [
        "production",
        "monitor",
        "observability",
        "alerting",
        "metrics",
        "uptime"
      ],
      "domain": "infrastructure",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "ticket-manager",
      "name": "agent-ticket-manager",
      "title": "Ticket Manager Specialist",
      "category": "coordination",
      "description": "Comprehensive ticket management with AI-powered intelligence and dependency analysis",
      "capabilities": [
        "ticket_lifecycle_management",
        "ai_powered_intelligence",
        "dependency_analysis",
        "lifecycle_automation",
        "workflow_optimization",
        "smart_prioritization"
      ],
      "triggers": [
        "ticket",
        "issue",
        "task management",
        "project management"
      ],
      "domain": "project_management",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "documentation-architect",
      "name": "agent-documentation-architect",
      "title": "Documentation Architect Specialist",
      "category": "documentation",
      "description": "Technical documentation excellence and API documentation generation",
      "capabilities": [
        "documentation_architecture",
        "api_documentation_generation",
        "developer_experience_optimization",
        "knowledge_management",
        "content_discovery_indexing"
      ],
      "triggers": [
        "documentation",
        "docs",
        "api docs",
        "technical writing"
      ],
      "domain": "documentation_architecture",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "pr-review",
      "name": "agent-pr-review",
      "title": "PR Review Specialist",
      "category": "quality",
      "description": "PR review specialist for merge readiness assessment and code quality validation",
      "capabilities": [
        "pr_analysis",
        "merge_readiness",
        "code_review",
        "security_assessment",
        "performance_validation",
        "onex_compliance"
      ],
      "triggers": [
        "pr review",
        "pull request",
        "code review",
        "merge readiness"
      ],
      "domain": "code_review",
      "specialization": "expert",
      "priority": "high"
    },
    {
      "id": "commit",
      "name": "agent-commit",
      "title": "Git Commit Specialist",
      "category": "development",
      "description": "Git commit specialist for semantic commit messages",
      "capabilities": [
        "semantic_commits",
        "git_workflows",
        "commit_analysis",
        "change_categorization"
      ],
      "triggers": [
        "commit",
        "git commit",
        "semantic commit"
      ],
      "domain": "version_control",
      "specialization": "specialist",
      "priority": "medium"
    },
    {
      "id": "research",
      "name": "agent-research",
      "title": "Research and Investigation Specialist",
      "category": "documentation",
      "description": "Research and investigation specialist for complex problem analysis",
      "capabilities": [
        "systematic_investigation",
        "problem_analysis",
        "knowledge_discovery",
        "root_cause_analysis",
        "evidence_based_research"
      ],
      "triggers": [
        "research",
        "investigate",
        "analysis",
        "discovery"
      ],
      "domain": "research_investigation",
      "specialization": "expert",
      "priority": "medium"
    }
    // ... additional 34 agents truncated for brevity
  ]
}
```

### Compact Agent Registry Format (For Token Efficiency)

```json
{
  "agents": [
    {
      "id": "api-architect",
      "title": "API Architect",
      "desc": "REST API design, OpenAPI, FastAPI optimization",
      "caps": ["api_design", "openapi", "microservices"],
      "domain": "api_dev",
      "spec": "expert"
    },
    {
      "id": "debug-intelligence",
      "title": "Debug Intelligence",
      "desc": "Root cause analysis, comprehensive debugging",
      "caps": ["debugging", "root_cause", "error_investigation"],
      "domain": "debugging",
      "spec": "expert"
    }
    // ... compact format for all agents
  ]
}
```

---

## User Query Template

### Standard Query Format

```
**User Request:**
{user_query}

**Context:**
- Domain: {context.domain or "general"}
- Previous Agent: {context.previous_agent or "none"}
- Current File: {context.current_file or "none"}
- Task Type: {context.task_type or "unknown"}
- Additional Context: {json.dumps(context.additional) if context.additional else "none"}

**Available Agent Registry:**
{formatted_agent_registry_json}

**Your Task:**
Analyze this request and recommend the top 1-3 most appropriate agents. Respond ONLY with JSON (no additional text).
```

### Example Query 1: Simple Debugging

```
**User Request:**
I'm getting a timeout error in production and need to investigate the root cause

**Context:**
- Domain: backend_development
- Previous Agent: none
- Current File: api/endpoints.py
- Task Type: debugging
- Additional Context: none

**Available Agent Registry:**
{agent_registry_json}

**Your Task:**
Analyze this request and recommend the top 1-3 most appropriate agents. Respond ONLY with JSON (no additional text).
```

### Example Query 2: Complex Multi-Domain

```
**User Request:**
I have a microservice that's timing out under load, and I'm not sure if it's a code issue, database bottleneck, or infrastructure problem. How should I investigate?

**Context:**
- Domain: general
- Previous Agent: none
- Current File: none
- Task Type: unknown
- Additional Context: {"urgency": "high", "production_impact": true}

**Available Agent Registry:**
{agent_registry_json}

**Your Task:**
Analyze this request and recommend the top 1-3 most appropriate agents. Respond ONLY with JSON (no additional text).
```

### Example Query 3: Code-Focused

```
**User Request:**
I need to refactor this FastAPI endpoint to follow ONEX patterns and improve type safety

**Context:**
- Domain: python_development
- Previous Agent: none
- Current File: api/routes/users.py
- Task Type: refactoring
- Additional Context: {"language": "python", "framework": "fastapi"}

**Available Agent Registry:**
{agent_registry_json}

**Your Task:**
Analyze this request and recommend the top 1-3 most appropriate agents. Respond ONLY with JSON (no additional text).
```

---

## Expected Output Schema

### Response Schema

```json
{
  "recommendations": [
    {
      "agent_name": "string (agent identifier from registry)",
      "confidence": "float (0.0-1.0)",
      "reasoning": "string (2-3 sentences explaining the match)",
      "capabilities_match": ["array of capability strings"],
      "alternative_considerations": "string (optional context about alternatives)",
      "workflow_suggestion": "string (optional workflow sequencing guidance)"
    }
  ]
}
```

### Example Output 1: High Confidence Single Match

```json
{
  "recommendations": [
    {
      "agent_name": "debug-intelligence",
      "confidence": 0.95,
      "reasoning": "User is experiencing a production timeout error and needs systematic investigation. Debug Intelligence specializes in comprehensive debugging with root cause analysis, error investigation, and performance correlation. This is a perfect match for the user's needs.",
      "capabilities_match": [
        "debugging",
        "root_cause_analysis",
        "error_investigation",
        "performance_correlation"
      ],
      "alternative_considerations": "If the issue is determined to be purely performance-related after initial debugging, agent-performance could be used for optimization.",
      "workflow_suggestion": null
    }
  ]
}
```

### Example Output 2: Multiple Options with Workflow

```json
{
  "recommendations": [
    {
      "agent_name": "debug-intelligence",
      "confidence": 0.89,
      "reasoning": "This query requires systematic investigation starting with root cause analysis. Debug Intelligence specializes in multi-dimensional debugging including performance correlation, which is perfect for determining whether the issue is code, database, or infrastructure. The BFROS framework will systematically rule out possibilities.",
      "capabilities_match": [
        "debugging",
        "root_cause_analysis",
        "performance_correlation",
        "system_behavior"
      ],
      "alternative_considerations": "After diagnosis, may need to delegate to agent-performance (code optimization), agent-database (query optimization), or agent-devops-infrastructure (scaling) based on findings.",
      "workflow_suggestion": "Start with debug-intelligence for diagnosis, then delegate to appropriate specialist based on root cause: agent-performance for code issues, agent-devops-infrastructure for infrastructure issues."
    },
    {
      "agent_name": "performance",
      "confidence": 0.76,
      "reasoning": "If the root cause is determined to be code or query performance, this agent excels at bottleneck detection and optimization. However, it's better suited as a follow-up after initial diagnosis rather than the starting point.",
      "capabilities_match": [
        "performance_optimization",
        "bottleneck_detection",
        "baseline_establishment"
      ],
      "alternative_considerations": "Best used after debug-intelligence identifies performance as the root cause.",
      "workflow_suggestion": "Use after debug-intelligence diagnosis confirms performance issue."
    },
    {
      "agent_name": "production-monitor",
      "confidence": 0.62,
      "reasoning": "This agent is valuable for ongoing monitoring and alerting to prevent future timeout issues. Less suitable for immediate investigation but valuable for long-term solution and prevention.",
      "capabilities_match": [
        "real_time_monitoring",
        "incident_detection",
        "performance_analytics"
      ],
      "alternative_considerations": "Deploy after root cause is resolved to prevent recurrence.",
      "workflow_suggestion": "Final step: Deploy monitoring after issue resolved."
    }
  ]
}
```

### Example Output 3: Code-Focused with High Confidence

```json
{
  "recommendations": [
    {
      "agent_name": "python-fastapi-expert",
      "confidence": 0.95,
      "reasoning": "Perfect match for FastAPI refactoring. This agent specializes in FastAPI optimization, async patterns, and Python ecosystem best practices. The ONEX pattern requirement aligns with the agent's expertise in architectural compliance and type safety improvements.",
      "capabilities_match": [
        "fastapi_optimization",
        "async_programming",
        "python_ecosystem",
        "backend_development"
      ],
      "alternative_considerations": "After refactoring is complete, agent-code-quality-analyzer should be used to validate ONEX compliance and type safety improvements.",
      "workflow_suggestion": "Use python-fastapi-expert for refactoring, then agent-code-quality-analyzer to validate ONEX compliance."
    },
    {
      "agent_name": "code-quality-analyzer",
      "confidence": 0.78,
      "reasoning": "Secondary option for ONEX compliance validation after refactoring. This agent excels at architectural compliance checking and type safety validation, making it ideal for verifying that the refactored code meets ONEX standards.",
      "capabilities_match": [
        "onex_compliance_verification",
        "code_quality_assessment",
        "anti_pattern_detection"
      ],
      "alternative_considerations": "Use after python-fastapi-expert completes refactoring to ensure ONEX compliance.",
      "workflow_suggestion": "Sequential workflow: python-fastapi-expert → code-quality-analyzer."
    }
  ]
}
```

### Example Output 4: Low Confidence / No Good Match

```json
{
  "recommendations": [
    {
      "agent_name": "research",
      "confidence": 0.42,
      "reasoning": "The user's request about quantum computing algorithms doesn't align well with any specialized agent in the registry. The Research agent can help with general investigation and knowledge discovery, but lacks specific quantum computing expertise.",
      "capabilities_match": [
        "systematic_investigation",
        "knowledge_discovery",
        "evidence_based_research"
      ],
      "alternative_considerations": "This query may require external resources or domain-specific expertise not available in the current agent registry. Consider consulting quantum computing documentation or specialists outside the agent ecosystem.",
      "workflow_suggestion": "Use research agent to gather available information, but expect to need external domain expertise."
    }
  ]
}
```

---

## Prompt Optimization Techniques

### Token Efficiency

**Strategy**: Reduce token count while maintaining quality

```python
def optimize_agent_registry_for_tokens(full_registry: dict) -> dict:
    """
    Compress agent registry for token efficiency.

    Optimizations:
    - Use abbreviations for common fields
    - Remove redundant information
    - Compact capabilities lists
    - Remove low-priority metadata
    """

    optimized = {
        "agents": []
    }

    for agent in full_registry["agents"]:
        optimized["agents"].append({
            "id": agent["id"],
            "title": agent["title"],
            "desc": agent["description"][:100],  # Truncate description
            "caps": agent["capabilities"][:5],  # Top 5 capabilities only
            "domain": agent["domain"],
            "spec": agent["specialization"]
        })

    return optimized
```

### Context-Aware Filtering

**Strategy**: Only include relevant agents based on query analysis

```python
def filter_agents_by_context(
    full_registry: dict,
    query: str,
    context: dict
) -> dict:
    """
    Filter agent registry to only relevant agents.

    Reduces token count by 50-70% while maintaining relevance.
    """

    # Extract keywords from query
    keywords = extract_keywords(query)

    # Determine relevant categories
    relevant_categories = determine_relevant_categories(keywords, context)

    # Filter agents
    filtered_agents = [
        agent for agent in full_registry["agents"]
        if agent["category"] in relevant_categories
        or any(cap in keywords for cap in agent["capabilities"])
    ]

    return {
        "agents": filtered_agents,
        "filtered_from": len(full_registry["agents"]),
        "filtering_reason": f"Context: {context.get('domain', 'general')}"
    }
```

### Few-Shot Examples

**Strategy**: Include 2-3 example interactions for better results

```
**Example 1: Debugging Query**

User: "Getting timeout errors in production"
Context: domain=backend, file=api/endpoints.py

Your Response:
{
  "recommendations": [{
    "agent_name": "debug-intelligence",
    "confidence": 0.95,
    "reasoning": "Production timeout errors require systematic debugging...",
    "capabilities_match": ["debugging", "root_cause_analysis"]
  }]
}

**Example 2: Code Quality Query**

User: "Review my code for ONEX compliance"
Context: domain=python, file=models/user.py

Your Response:
{
  "recommendations": [{
    "agent_name": "code-quality-analyzer",
    "confidence": 0.93,
    "reasoning": "ONEX compliance validation is the primary specialty...",
    "capabilities_match": ["onex_compliance_verification", "code_quality_assessment"]
  }]
}

**Now analyze the actual user request:**
...
```

---

## Model-Specific Prompt Variations

### DeepSeek-R1 (Primary Reasoning)

**Optimization**: Emphasize deep reasoning and multi-step analysis

```
You are an expert agent routing specialist with deep reasoning capabilities.

Your approach:
1. Analyze query intent thoroughly
2. Consider multiple agent options
3. Evaluate pros/cons of each
4. Make confident recommendation with clear reasoning

Focus on:
- Semantic understanding of complex queries
- Multi-domain considerations
- Workflow planning for multi-step tasks

{standard_prompt}
```

### Llama 3.1 (Validation)

**Optimization**: Emphasize consistency and pattern recognition

```
You are an agent routing validator specializing in consistency checks.

Your approach:
1. Verify agent capabilities match query requirements
2. Check for overlooked alternatives
3. Ensure reasoning is sound and complete
4. Validate confidence scores are appropriate

Focus on:
- Consistency with previous routing decisions
- Pattern recognition across similar queries
- Risk assessment for recommendations

{standard_prompt}
```

### Codestral (Code Focus)

**Optimization**: Emphasize code-related routing

```
You are a code-focused agent routing specialist.

Your approach:
1. Analyze code-related aspects of query
2. Consider programming language and framework
3. Evaluate code quality and architectural needs
4. Recommend agents with strong code expertise

Focus on:
- Programming language context
- Framework-specific requirements
- Code quality and architecture

{standard_prompt}
```

### Gemini Flash (Fallback)

**Optimization**: Balanced general-purpose routing

```
You are a reliable agent routing specialist.

Your approach:
1. Quickly identify query category
2. Match to most appropriate agent
3. Provide clear, concise reasoning
4. Suggest alternatives when needed

Focus on:
- Fast, reliable recommendations
- Clear reasoning
- Balanced confidence scores

{standard_prompt}
```

---

## Testing Prompts

### Test Query Set 1: Simple Explicit

```yaml
test_queries:
  - query: "use agent-commit to create a semantic commit message"
    expected_agent: "commit"
    expected_confidence: 0.95+
    complexity: "simple"

  - query: "debug this production error"
    expected_agent: "debug-intelligence"
    expected_confidence: 0.90+
    complexity: "simple"

  - query: "optimize API performance"
    expected_agent: "performance"
    expected_confidence: 0.85+
    complexity: "simple"
```

### Test Query Set 2: Moderate Complexity

```yaml
test_queries:
  - query: "I need to refactor this FastAPI code to follow ONEX patterns"
    expected_agents: ["python-fastapi-expert", "code-quality-analyzer"]
    expected_confidence: 0.85+
    complexity: "moderate"
    workflow_expected: true

  - query: "Review my PR for security issues and code quality"
    expected_agents: ["pr-review", "security-audit"]
    expected_confidence: 0.80+
    complexity: "moderate"

  - query: "Setup monitoring for this production service"
    expected_agents: ["production-monitor", "devops-infrastructure"]
    expected_confidence: 0.80+
    complexity: "moderate"
```

### Test Query Set 3: High Complexity

```yaml
test_queries:
  - query: "I have a microservice that's timing out under load, and I'm not sure if it's a code issue, database bottleneck, or infrastructure problem"
    expected_agents: ["debug-intelligence", "performance", "devops-infrastructure"]
    expected_confidence: 0.75+
    complexity: "high"
    workflow_expected: true
    multi_agent_expected: true

  - query: "Design and implement a new payment processing API with security audit and testing"
    expected_agents: ["api-architect", "security-audit", "testing"]
    expected_confidence: 0.80+
    complexity: "high"
    workflow_expected: true

  - query: "I need help but I'm not sure which agent to use - it's a complex backend issue with performance problems and possible security concerns"
    expected_agents: ["debug-intelligence", "performance", "security-audit"]
    expected_confidence: 0.60-0.80
    complexity: "high"
    ambiguous: true
```

---

## Prompt Validation

### JSON Schema Validation

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["recommendations"],
  "properties": {
    "recommendations": {
      "type": "array",
      "minItems": 1,
      "maxItems": 3,
      "items": {
        "type": "object",
        "required": ["agent_name", "confidence", "reasoning", "capabilities_match"],
        "properties": {
          "agent_name": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]*$"
          },
          "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
          },
          "reasoning": {
            "type": "string",
            "minLength": 50,
            "maxLength": 500
          },
          "capabilities_match": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "string"
            }
          },
          "alternative_considerations": {
            "type": "string",
            "maxLength": 300
          },
          "workflow_suggestion": {
            "type": "string",
            "maxLength": 200
          }
        }
      }
    }
  }
}
```

### Response Quality Checks

```python
def validate_ai_response(response: dict, query: str) -> bool:
    """
    Validate AI routing response quality.
    """

    # Check JSON schema
    try:
        jsonschema.validate(response, RESPONSE_SCHEMA)
    except jsonschema.ValidationError as e:
        logger.error(f"Schema validation failed: {e}")
        return False

    # Check agent names exist in registry
    valid_agent_ids = [a["id"] for a in agent_registry["agents"]]
    for rec in response["recommendations"]:
        if rec["agent_name"] not in valid_agent_ids:
            logger.error(f"Invalid agent name: {rec['agent_name']}")
            return False

    # Check capabilities exist for agent
    for rec in response["recommendations"]:
        agent = next(a for a in agent_registry["agents"] if a["id"] == rec["agent_name"])
        valid_caps = agent["capabilities"]
        for cap in rec["capabilities_match"]:
            if cap not in valid_caps:
                logger.warning(f"Capability {cap} not in agent {agent['id']} capabilities")

    # Check reasoning quality (minimum length, coherent)
    for rec in response["recommendations"]:
        if len(rec["reasoning"]) < 50:
            logger.warning(f"Reasoning too short for {rec['agent_name']}")

        # Check for generic/placeholder reasoning
        generic_phrases = ["this agent", "can help", "is good for"]
        if all(phrase in rec["reasoning"].lower() for phrase in generic_phrases):
            logger.warning(f"Generic reasoning for {rec['agent_name']}")

    # Check confidence calibration
    for rec in response["recommendations"]:
        # Very high confidence should have strong reasoning
        if rec["confidence"] > 0.9 and len(rec["reasoning"]) < 100:
            logger.warning(f"High confidence but weak reasoning for {rec['agent_name']}")

    return True
```

---

## Continuous Improvement

### Prompt Evolution Strategy

```python
class PromptEvolutionTracker:
    """
    Track prompt performance and suggest improvements.
    """

    def __init__(self):
        self.prompt_versions = []
        self.performance_data = []

    def track_prompt_performance(
        self,
        prompt_version: str,
        query: str,
        response: dict,
        user_selected: str,
        task_success: bool
    ):
        """
        Track performance of specific prompt version.
        """
        self.performance_data.append({
            "prompt_version": prompt_version,
            "query": query,
            "top_recommendation": response["recommendations"][0]["agent_name"],
            "user_selected": user_selected,
            "match": response["recommendations"][0]["agent_name"] == user_selected,
            "task_success": task_success,
            "timestamp": datetime.now()
        })

    def analyze_prompt_effectiveness(self, prompt_version: str) -> dict:
        """
        Analyze effectiveness of prompt version.
        """
        version_data = [
            d for d in self.performance_data
            if d["prompt_version"] == prompt_version
        ]

        if not version_data:
            return {"error": "No data for this prompt version"}

        total = len(version_data)
        matches = sum(1 for d in version_data if d["match"])
        successes = sum(1 for d in version_data if d["task_success"])

        return {
            "prompt_version": prompt_version,
            "total_queries": total,
            "recommendation_accuracy": matches / total,
            "task_success_rate": successes / total,
            "avg_confidence": sum(d.get("confidence", 0) for d in version_data) / total
        }

    def suggest_prompt_improvements(self, prompt_version: str) -> List[str]:
        """
        Suggest improvements based on performance analysis.
        """
        analysis = self.analyze_prompt_effectiveness(prompt_version)
        suggestions = []

        if analysis["recommendation_accuracy"] < 0.85:
            suggestions.append("Consider adding more few-shot examples")
            suggestions.append("Emphasize capability matching in system prompt")

        if analysis["task_success_rate"] < 0.80:
            suggestions.append("Add workflow guidance section to system prompt")
            suggestions.append("Emphasize multi-agent coordination capabilities")

        return suggestions
```

---

## Appendix: Complete Working Example

### Full End-to-End Example

```python
# Query
user_query = "I have a FastAPI endpoint that's returning 500 errors in production and I need to debug it quickly"

# Context
context = {
    "domain": "backend_development",
    "current_file": "api/endpoints/users.py",
    "previous_agent": None,
    "urgency": "high",
    "production": True
}

# Build prompt
prompt = f"""
**User Request:**
{user_query}

**Context:**
- Domain: {context['domain']}
- Current File: {context['current_file']}
- Urgency: {context['urgency']}
- Production: {context['production']}

**Available Agent Registry:**
{json.dumps(compact_agent_registry, indent=2)}

**Your Task:**
Analyze this request and recommend the top 1-3 most appropriate agents. Respond ONLY with JSON (no additional text).
"""

# Send to AI Quorum
responses = await ai_quorum.query_parallel(
    system_prompt=PRIMARY_SYSTEM_PROMPT,
    user_prompt=prompt,
    response_format="json"
)

# Expected Response from DeepSeek-R1:
{
  "recommendations": [
    {
      "agent_name": "debug-intelligence",
      "confidence": 0.94,
      "reasoning": "Production 500 errors require immediate systematic investigation. Debug Intelligence specializes in comprehensive debugging with root cause analysis and error investigation. Given the production urgency and FastAPI context, this agent can quickly identify whether the issue is code-related, configuration, or dependency-related.",
      "capabilities_match": [
        "debugging",
        "root_cause_analysis",
        "error_investigation",
        "system_behavior"
      ],
      "alternative_considerations": "If the root cause is identified as a Python/FastAPI-specific issue, python-fastapi-expert could be consulted for the fix. If it's infrastructure-related, devops-infrastructure may be needed.",
      "workflow_suggestion": "Use debug-intelligence for initial diagnosis, then delegate to python-fastapi-expert or devops-infrastructure based on root cause."
    },
    {
      "agent_name": "python-fastapi-expert",
      "confidence": 0.72,
      "reasoning": "Secondary option if the issue is determined to be FastAPI-specific. This agent has deep expertise in FastAPI framework internals and can help with endpoint debugging and optimization. Better suited as a follow-up after initial investigation.",
      "capabilities_match": [
        "fastapi_optimization",
        "python_development",
        "backend_development"
      ],
      "alternative_considerations": "Use after debug-intelligence identifies the issue as FastAPI-specific.",
      "workflow_suggestion": "Sequential: debug-intelligence → python-fastapi-expert"
    }
  ]
}

# Build consensus across all models
consensus_result = build_consensus(responses, agent_registry)

# Final recommendation with >90% consensus
{
  "agent_name": "debug-intelligence",
  "consensus_score": 0.91,
  "reasoning": "Production 500 errors require systematic debugging...",
  "model_agreement": ["deepseek-r1", "llama3.1", "codestral", "gemini-flash"],
  "confidence_breakdown": [
    {"model": "deepseek-r1", "confidence": 0.94, "weight": 2.0},
    {"model": "llama3.1", "confidence": 0.89, "weight": 1.2},
    {"model": "codestral", "confidence": 0.91, "weight": 1.5},
    {"model": "gemini-flash", "confidence": 0.87, "weight": 1.0}
  ]
}
```

---

**Document Status**: Complete
**Last Updated**: October 1, 2025
**Next Review**: After initial AI routing implementation
**Maintainer**: Agent Workflow Coordinator
