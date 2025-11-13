"""
Intelligence Gathering Template: Orchestrated Intelligence Research
==================================================================

Standardized template for gathering orchestrated intelligence across multiple
backend services (RAG, Vector, Knowledge Graph) with intelligent synthesis.
This template implements Phase 2 patterns from the Archon MCP Integration Framework.

Template Parameters:
- AGENT_DOMAIN: Short domain identifier for specialized queries
- DOMAIN_QUERY: Primary domain-specific query pattern
- AGENT_CONTEXT: Context for orchestrated search (api_development, debugging, architecture)
- MATCH_COUNT: Number of results to retrieve per service (default: 5)
- CONFIDENCE_THRESHOLD: Minimum confidence score for results (default: 0.6)

Usage:
    1. Copy this template to your agent implementation
    2. Replace template parameters with agent-specific values
    3. Customize query patterns for your domain
    4. Implement domain-specific intelligence extraction
    5. Add intelligence application logic

Dependencies:
    - mcp__archon__perform_rag_query()
    - mcp__archon__search_code_examples()
    - mcp__archon__enhanced_search()

Quality Gates:
    - Multi-service orchestration
    - Intelligence synthesis validation
    - Confidence scoring
    - Graceful degradation handling
"""

from datetime import datetime
from typing import Any, Dict, List


async def gather_agent_domain_intelligence(
    context_params: Dict[str, Any],
) -> Dict[str, Any]:  # Template: Replace with gather_[AGENT_DOMAIN]_intelligence(
    """
    Gather orchestrated intelligence for [AGENT_PURPOSE] across multiple services.

    This function implements the standardized Phase 2 orchestrated intelligence
    research pattern. It queries RAG, Vector, and Knowledge Graph services in
    parallel and provides intelligent synthesis of results.

    Args:
        context_params: Domain-specific context parameters
            - domain: Primary domain for the query
            - technology_stack: List of technologies involved
            - complexity_level: Task complexity (simple, moderate, complex, critical)
            - task_type: Type of task being performed
            - repository_context: Repository information
            - user_requirements: Specific user requirements

    Returns:
        dict: Synthesized intelligence from all backend services
            - orchestrated_results: Raw results from orchestration
            - rag_patterns: Patterns from RAG search
            - vector_insights: Insights from vector search
            - knowledge_relationships: Relationships from knowledge graph
            - intelligent_synthesis: AI synthesis of all results
            - execution_metrics: Performance and quality metrics
    """
    print(
        f"🧠 Gathering orchestrated intelligence for {context_params.get('domain', '[AGENT_DOMAIN]')}"
    )

    try:
        # Phase 2.1: Prepare Orchestrated Query
        primary_query = _build_primary_domain_query(context_params)
        print(f"🔍 Primary Query: {primary_query}")

        # Phase 2.2: Execute Orchestrated Research (Parallel Services)
        orchestrated_research = await _execute_orchestrated_research(
            primary_query, context_params
        )

        # Phase 2.3: Extract Service-Specific Results
        service_results = _extract_service_results(orchestrated_research)

        # Phase 2.4: Perform Intelligence Synthesis
        synthesis = _synthesize_intelligence(service_results, context_params)

        # Phase 2.5: Calculate Execution Metrics
        execution_metrics = _calculate_execution_metrics(
            orchestrated_research, synthesis
        )

        # Phase 2.6: Validate Intelligence Quality
        quality_validation = _validate_intelligence_quality(
            synthesis, execution_metrics
        )

        intelligence_results = {
            "orchestrated_results": orchestrated_research,
            "rag_patterns": service_results.get("rag_patterns", []),
            "vector_insights": service_results.get("vector_insights", []),
            "knowledge_relationships": service_results.get(
                "knowledge_relationships", []
            ),
            "intelligent_synthesis": synthesis,
            "execution_metrics": execution_metrics,
            "quality_validation": quality_validation,
            "intelligence_confidence": synthesis.get("confidence_score", 0.0),
            "gathering_timestamp": datetime.utcnow().isoformat(),
        }

        print("✅ Intelligence gathering complete:")
        print(
            f"   Services: {execution_metrics.get('sources_successful', [])} successful"
        )
        print(f"   Confidence: {synthesis.get('confidence_score', 0.0):.2f}")
        print(f"   Duration: {execution_metrics.get('duration_ms', 0)}ms")

        return intelligence_results

    except Exception as e:
        print(f"⚠️ Intelligence gathering failed: {str(e)}")
        return _create_fallback_intelligence(context_params, str(e))


def _build_primary_domain_query(context_params: Dict[str, Any]) -> str:
    """Build the primary domain-specific query for orchestrated research."""
    context_params.get("domain", "[AGENT_DOMAIN]")
    technology_stack = context_params.get("technology_stack", [])
    task_type = context_params.get("task_type", "general")

    # Base domain query pattern
    base_query = "[DOMAIN_QUERY] patterns best practices standards compliance"

    # Enhance with technology stack
    if technology_stack:
        tech_context = " ".join(technology_stack)
        base_query = f"{base_query} {tech_context}"

    # Add task-specific context
    if task_type != "general":
        base_query = f"{base_query} {task_type}"

    # Add complexity-specific patterns
    complexity = context_params.get("complexity_level", "moderate")
    if complexity in ["complex", "critical"]:
        base_query = f"{base_query} advanced patterns enterprise solutions"

    return base_query


async def _execute_orchestrated_research(
    query: str, context_params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute orchestrated research across all backend services."""
    try:
        # Primary orchestrated research call
        orchestrated_research = mcp__archon__perform_rag_query(
            query=query,
            match_count=context_params.get("match_count", 5),
            context="[AGENT_CONTEXT]",  # e.g., "api_development", "debugging", "architecture"
        )

        # Enhance with code examples if applicable
        if context_params.get("include_code_examples", True):
            code_research = mcp__archon__search_code_examples(
                query=f"{query} implementation examples",
                match_count=context_params.get("code_match_count", 3),
            )
            orchestrated_research["code_examples"] = code_research

        return orchestrated_research

    except Exception as e:
        print(f"⚠️ Orchestrated research failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": {},
            "synthesis": {},
            "duration_ms": 0,
        }


def _extract_service_results(orchestrated_research: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and organize results from individual services."""
    results = orchestrated_research.get("results", {})

    return {
        "rag_patterns": _extract_rag_patterns(results.get("rag_search", {})),
        "vector_insights": _extract_vector_insights(results.get("vector_search", {})),
        "knowledge_relationships": _extract_knowledge_relationships(
            results.get("knowledge_graph", {})
        ),
        "code_examples": _extract_code_examples(
            orchestrated_research.get("code_examples", {})
        ),
    }


def _extract_rag_patterns(rag_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract patterns from RAG search results."""
    patterns = []

    for result in rag_results.get("results", []):
        pattern = {
            "source": result.get("source", "unknown"),
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "relevance_score": result.get("score", 0.0),
            "pattern_type": _classify_pattern_type(result),
            "applicability": _assess_pattern_applicability(result),
            "domain_relevance": "[AGENT_DOMAIN]",
        }
        patterns.append(pattern)

    return patterns


def _extract_vector_insights(vector_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract insights from vector search results."""
    insights = []

    for result in vector_results.get("results", []):
        insight = {
            "semantic_similarity": result.get("similarity_score", 0.0),
            "content": result.get("content", ""),
            "metadata": result.get("metadata", {}),
            "context_relevance": _assess_context_relevance(result),
            "insight_type": _classify_insight_type(result),
            "domain_alignment": "[AGENT_DOMAIN]",
        }
        insights.append(insight)

    return insights


def _extract_knowledge_relationships(
    graph_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract relationships from knowledge graph results."""
    relationships = []

    for result in graph_results.get("results", []):
        relationship = {
            "entities": result.get("entities", []),
            "relationship_type": result.get("relationship_type", "unknown"),
            "strength": result.get("strength", 0.0),
            "context": result.get("context", ""),
            "domain_connection": _assess_domain_connection(result),
            "cross_domain_insights": _identify_cross_domain_insights(result),
        }
        relationships.append(relationship)

    return relationships


def _extract_code_examples(code_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and classify code examples."""
    examples = []

    for result in code_results.get("results", []):
        example = {
            "code_snippet": result.get("code", ""),
            "language": result.get("language", "unknown"),
            "functionality": result.get("description", ""),
            "quality_score": _assess_code_quality(result),
            "applicability": _assess_code_applicability(result),
            "adaptation_notes": _generate_adaptation_notes(result),
        }
        examples.append(example)

    return examples


def _synthesize_intelligence(
    service_results: Dict[str, Any], context_params: Dict[str, Any]
) -> Dict[str, Any]:
    """Synthesize intelligence from all service results."""
    synthesis = {
        "key_findings": [],
        "recommended_approaches": [],
        "patterns_identified": [],
        "best_practices": [],
        "potential_pitfalls": [],
        "cross_service_insights": [],
        "confidence_score": 0.0,
        "synthesis_quality": "pending",
    }

    # Synthesize key findings
    synthesis["key_findings"] = _synthesize_key_findings(service_results)

    # Identify patterns across services
    synthesis["patterns_identified"] = _identify_cross_service_patterns(service_results)

    # Extract best practices
    synthesis["best_practices"] = _extract_best_practices(service_results)

    # Identify potential pitfalls
    synthesis["potential_pitfalls"] = _identify_potential_pitfalls(service_results)

    # Generate recommendations
    synthesis["recommended_approaches"] = _generate_recommendations(
        service_results, context_params
    )

    # Cross-service insights
    synthesis["cross_service_insights"] = _generate_cross_service_insights(
        service_results
    )

    # Calculate confidence score
    synthesis["confidence_score"] = _calculate_synthesis_confidence(
        service_results, synthesis
    )

    # Assess synthesis quality
    synthesis["synthesis_quality"] = _assess_synthesis_quality(synthesis)

    return synthesis


def _calculate_execution_metrics(
    orchestrated_research: Dict[str, Any], synthesis: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate execution metrics for the intelligence gathering process."""
    return {
        "duration_ms": orchestrated_research.get("duration_ms", 0),
        "sources_queried": orchestrated_research.get("sources_queried", []),
        "sources_successful": orchestrated_research.get("sources_successful", []),
        "total_results": orchestrated_research.get("total_results", 0),
        "synthesis_confidence": synthesis.get("confidence_score", 0.0),
        "quality_indicators": {
            "result_diversity": _calculate_result_diversity(orchestrated_research),
            "cross_service_correlation": _calculate_cross_service_correlation(
                orchestrated_research
            ),
            "domain_relevance": _calculate_domain_relevance(orchestrated_research),
        },
    }


def _validate_intelligence_quality(
    synthesis: Dict[str, Any], metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate the quality of gathered intelligence."""
    validation = {
        "passed": False,
        "confidence_threshold_met": False,
        "diversity_adequate": False,
        "synthesis_quality_acceptable": False,
        "recommendations": [],
    }

    # Check confidence threshold
    confidence_threshold = 0.6  # [CONFIDENCE_THRESHOLD]
    validation["confidence_threshold_met"] = (
        synthesis.get("confidence_score", 0.0) >= confidence_threshold
    )

    # Check result diversity
    diversity_score = metrics.get("quality_indicators", {}).get("result_diversity", 0.0)
    validation["diversity_adequate"] = diversity_score >= 0.5

    # Check synthesis quality
    synthesis_quality = synthesis.get("synthesis_quality", "poor")
    validation["synthesis_quality_acceptable"] = synthesis_quality in [
        "good",
        "excellent",
    ]

    # Overall validation
    validation["passed"] = all(
        [
            validation["confidence_threshold_met"],
            validation["diversity_adequate"],
            validation["synthesis_quality_acceptable"],
        ]
    )

    # Generate recommendations for improvement
    if not validation["passed"]:
        validation["recommendations"] = _generate_improvement_recommendations(
            validation
        )

    return validation


def _create_fallback_intelligence(
    context_params: Dict[str, Any], error: str
) -> Dict[str, Any]:
    """Create fallback intelligence when orchestrated research fails."""
    return {
        "orchestrated_results": {"success": False, "error": error},
        "rag_patterns": [],
        "vector_insights": [],
        "knowledge_relationships": [],
        "intelligent_synthesis": {
            "key_findings": [
                "Intelligence gathering failed - operating with limited context"
            ],
            "recommended_approaches": ["Proceed with basic domain knowledge"],
            "patterns_identified": [],
            "best_practices": [],
            "potential_pitfalls": ["Limited intelligence available"],
            "cross_service_insights": [],
            "confidence_score": 0.1,
            "synthesis_quality": "fallback",
        },
        "execution_metrics": {
            "duration_ms": 0,
            "sources_successful": [],
            "total_results": 0,
            "error": error,
        },
        "quality_validation": {"passed": False, "fallback_mode": True},
        "intelligence_confidence": 0.1,
        "gathering_timestamp": datetime.utcnow().isoformat(),
    }


# Helper functions for pattern classification and analysis
def _classify_pattern_type(result: Dict[str, Any]) -> str:
    """Classify the type of pattern found in results."""
    content = result.get("content", "").lower()

    if any(
        keyword in content for keyword in ["best practice", "recommended", "should"]
    ):
        return "best_practice"
    elif any(
        keyword in content for keyword in ["anti-pattern", "avoid", "dont", "don't"]
    ):
        return "anti_pattern"
    elif any(keyword in content for keyword in ["example", "implementation", "code"]):
        return "implementation_pattern"
    elif any(keyword in content for keyword in ["architecture", "design", "structure"]):
        return "architectural_pattern"
    else:
        return "general_pattern"


def _assess_pattern_applicability(result: Dict[str, Any]) -> str:
    """Assess how applicable a pattern is to the current domain."""
    # This would be customized based on [AGENT_DOMAIN]
    domain_keywords = ["[AGENT_DOMAIN]"]  # Replace with actual domain keywords
    content = result.get("content", "").lower()

    if any(keyword in content for keyword in domain_keywords):
        return "high"
    elif result.get("score", 0.0) > 0.7:
        return "medium"
    else:
        return "low"


def _assess_context_relevance(result: Dict[str, Any]) -> str:
    """Assess context relevance of vector search results."""
    similarity = result.get("similarity_score", 0.0)

    if similarity > 0.8:
        return "high"
    elif similarity > 0.6:
        return "medium"
    else:
        return "low"


def _classify_insight_type(result: Dict[str, Any]) -> str:
    """Classify the type of insight from vector search."""
    metadata = result.get("metadata", {})
    content_type = metadata.get("type", "unknown")

    insight_types = {
        "documentation": "knowledge_insight",
        "code": "implementation_insight",
        "example": "practical_insight",
        "tutorial": "learning_insight",
        "reference": "technical_insight",
    }

    return insight_types.get(content_type, "general_insight")


def _assess_domain_connection(result: Dict[str, Any]) -> str:
    """Assess how strongly a knowledge graph result connects to the domain."""
    entities = result.get("entities", [])
    domain_entities = ["[AGENT_DOMAIN]"]  # Replace with actual domain entities

    connection_count = sum(
        1
        for entity in entities
        if any(
            domain_entity in str(entity).lower() for domain_entity in domain_entities
        )
    )

    if connection_count >= 2:
        return "strong"
    elif connection_count == 1:
        return "moderate"
    else:
        return "weak"


def _identify_cross_domain_insights(result: Dict[str, Any]) -> List[str]:
    """Identify insights that span across domains."""
    # This would identify patterns that apply to multiple domains
    return []  # Placeholder for cross-domain analysis


def _assess_code_quality(result: Dict[str, Any]) -> float:
    """Assess the quality of code examples."""
    # Simple heuristic - would be more sophisticated in practice
    code = result.get("code", "")

    quality_score = 0.5  # Base score

    # Positive indicators
    if "def " in code or "function " in code:
        quality_score += 0.1
    if "class " in code:
        quality_score += 0.1
    if '"""' in code or "'''" in code:  # Documentation
        quality_score += 0.2
    if "test" in code.lower():
        quality_score += 0.1

    return min(quality_score, 1.0)


def _assess_code_applicability(result: Dict[str, Any]) -> str:
    """Assess how applicable code examples are to the current context."""
    language = result.get("language", "unknown")

    # Would be customized based on technology stack
    applicable_languages = ["python", "javascript", "typescript"]  # Example

    if language in applicable_languages:
        return "high"
    elif language != "unknown":
        return "medium"
    else:
        return "low"


def _generate_adaptation_notes(result: Dict[str, Any]) -> List[str]:
    """Generate notes on how to adapt code examples."""
    notes = []

    language = result.get("language", "unknown")
    if language != "python":  # Assuming Python as target
        notes.append(f"Adapt from {language} to Python")

    # Add more adaptation logic based on context

    return notes


# Additional helper functions for synthesis
def _synthesize_key_findings(service_results: Dict[str, Any]) -> List[str]:
    """Synthesize key findings from all service results."""
    findings = []

    # Extract high-confidence patterns from RAG
    for pattern in service_results.get("rag_patterns", []):
        if pattern.get("relevance_score", 0.0) > 0.7:
            findings.append(
                f"High-relevance pattern: {pattern.get('title', 'Unknown pattern')}"
            )

    # Extract high-similarity insights from vector search
    for insight in service_results.get("vector_insights", []):
        if insight.get("semantic_similarity", 0.0) > 0.8:
            findings.append(
                f"Strong semantic match: {insight.get('insight_type', 'Unknown insight')}"
            )

    return findings


def _identify_cross_service_patterns(
    service_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Identify patterns that appear across multiple services."""
    patterns = []

    # This would implement sophisticated pattern matching across services
    # For now, return a placeholder structure

    return patterns


def _extract_best_practices(service_results: Dict[str, Any]) -> List[str]:
    """Extract best practices from all service results."""
    practices = []

    for pattern in service_results.get("rag_patterns", []):
        if pattern.get("pattern_type") == "best_practice":
            practices.append(pattern.get("content", ""))

    return practices


def _identify_potential_pitfalls(service_results: Dict[str, Any]) -> List[str]:
    """Identify potential pitfalls from service results."""
    pitfalls = []

    for pattern in service_results.get("rag_patterns", []):
        if pattern.get("pattern_type") == "anti_pattern":
            pitfalls.append(pattern.get("content", ""))

    return pitfalls


def _generate_recommendations(
    service_results: Dict[str, Any], context_params: Dict[str, Any]
) -> List[str]:
    """Generate actionable recommendations based on gathered intelligence."""
    recommendations = []

    # Generate recommendations based on patterns and context
    complexity = context_params.get("complexity_level", "moderate")

    if complexity in ["complex", "critical"]:
        recommendations.append(
            "Consider enterprise-grade patterns for complex requirements"
        )

    # Add more recommendation logic based on service results

    return recommendations


def _generate_cross_service_insights(service_results: Dict[str, Any]) -> List[str]:
    """Generate insights that span across multiple services."""
    insights = []

    # Correlate findings across RAG, Vector, and Knowledge Graph
    # This would implement sophisticated cross-service analysis

    return insights


def _calculate_synthesis_confidence(
    service_results: Dict[str, Any], synthesis: Dict[str, Any]
) -> float:
    """Calculate confidence score for the intelligence synthesis."""
    confidence_factors = []

    # Factor 1: Number of successful services
    rag_patterns = len(service_results.get("rag_patterns", []))
    vector_insights = len(service_results.get("vector_insights", []))
    knowledge_relationships = len(service_results.get("knowledge_relationships", []))

    service_coverage = (
        (rag_patterns > 0) + (vector_insights > 0) + (knowledge_relationships > 0)
    )
    confidence_factors.append(service_coverage / 3.0)

    # Factor 2: Quality of findings
    key_findings_count = len(synthesis.get("key_findings", []))
    confidence_factors.append(min(key_findings_count / 5.0, 1.0))

    # Factor 3: Pattern diversity
    patterns_count = len(synthesis.get("patterns_identified", []))
    confidence_factors.append(min(patterns_count / 3.0, 1.0))

    return sum(confidence_factors) / len(confidence_factors)


def _assess_synthesis_quality(synthesis: Dict[str, Any]) -> str:
    """Assess the overall quality of intelligence synthesis."""
    confidence = synthesis.get("confidence_score", 0.0)
    findings_count = len(synthesis.get("key_findings", []))
    recommendations_count = len(synthesis.get("recommended_approaches", []))

    if confidence > 0.8 and findings_count >= 3 and recommendations_count >= 2:
        return "excellent"
    elif confidence > 0.6 and findings_count >= 2 and recommendations_count >= 1:
        return "good"
    elif confidence > 0.4:
        return "fair"
    else:
        return "poor"


def _calculate_result_diversity(orchestrated_research: Dict[str, Any]) -> float:
    """Calculate diversity of results across services."""
    results = orchestrated_research.get("results", {})
    service_counts = [
        len(results.get("rag_search", {}).get("results", [])),
        len(results.get("vector_search", {}).get("results", [])),
        len(results.get("knowledge_graph", {}).get("results", [])),
    ]

    # Calculate diversity as variance normalized
    if not service_counts or all(count == 0 for count in service_counts):
        return 0.0

    mean_count = sum(service_counts) / len(service_counts)
    variance = sum((count - mean_count) ** 2 for count in service_counts) / len(
        service_counts
    )

    # Return normalized diversity score (0.0 to 1.0)
    return min(1.0 - (variance / (mean_count + 1)), 1.0)


def _calculate_cross_service_correlation(
    orchestrated_research: Dict[str, Any],
) -> float:
    """Calculate correlation between results from different services."""
    # This would implement sophisticated correlation analysis
    # For now, return a placeholder score
    return 0.5


def _calculate_domain_relevance(orchestrated_research: Dict[str, Any]) -> float:
    """Calculate how relevant results are to the specific domain."""
    # This would analyze content relevance to the agent domain
    # For now, return a placeholder score
    return 0.7


def _generate_improvement_recommendations(validation: Dict[str, Any]) -> List[str]:
    """Generate recommendations for improving intelligence quality."""
    recommendations = []

    if not validation.get("confidence_threshold_met", False):
        recommendations.append("Increase match_count to gather more results")
        recommendations.append("Refine query patterns for better relevance")

    if not validation.get("diversity_adequate", False):
        recommendations.append("Expand query scope to improve result diversity")

    if not validation.get("synthesis_quality_acceptable", False):
        recommendations.append("Enhance synthesis logic for better pattern recognition")

    return recommendations


# Template Usage Example:
"""
# Basic usage:
context_params = {
    'domain': 'api_design',
    'technology_stack': ['fastapi', 'python', 'postgresql'],
    'complexity_level': 'moderate',
    'task_type': 'endpoint_creation',
    'repository_context': {...},
    'user_requirements': [...]
}

intelligence = await gather_api_design_intelligence(context_params)
if intelligence['quality_validation']['passed']:
    # Use high-quality intelligence
    apply_intelligence_to_execution(intelligence)
else:
    # Handle low-quality intelligence
    proceed_with_fallback_approach()
"""
