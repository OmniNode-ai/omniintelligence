#!/bin/bash
# Documentation Reorganization Script
# Uses git mv to preserve history

# Helper function to move files (git mv for tracked, mv for untracked)
move_file() {
  local src="$1"
  local dest="$2"

  if [ ! -e "$src" ]; then
    return 0
  fi

  if git ls-files --error-unmatch "$src" > /dev/null 2>&1; then
    # File is tracked, use git mv
    git mv "$src" "$dest" 2>/dev/null || {
      echo "  Warning: Could not git mv $src (may already be moved)"
      return 0
    }
  else
    # File is not tracked, use regular mv
    mv "$src" "$dest" 2>/dev/null || {
      echo "  Warning: Could not mv $src"
      return 0
    }
  fi
}

echo "=========================================="
echo "Archon Documentation Reorganization"
echo "=========================================="
echo ""

# Create new directory structure
echo "Creating directory structure..."
mkdir -p docs/onex
mkdir -p docs/architecture
mkdir -p docs/phases
mkdir -p docs/api
mkdir -p docs/research
mkdir -p docs/guides
mkdir -p docs/reports
mkdir -p docs/site
mkdir -p tests/integration
mkdir -p tests/unit
mkdir -p tests/performance
mkdir -p scripts

echo "✓ Directory structure created"
echo ""

# ==========================================
# Phase 1: Move ONEX-related documentation
# ==========================================
echo "Phase 1: Organizing ONEX documentation..."

# Move ONEX files from root to docs/onex
if [ -f "ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md" ]; then
  git mv ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md docs/onex/
fi

if [ -f "FINAL_DESIGN_REVIEW_ONEX_STRUCTURE.md" ]; then
  git mv FINAL_DESIGN_REVIEW_ONEX_STRUCTURE.md docs/onex/
fi

if [ -f "INNOVATION_ANALYSIS_ONEX_STRUCTURE.md" ]; then
  git mv INNOVATION_ANALYSIS_ONEX_STRUCTURE.md docs/onex/
fi

if [ -f "NODE_GROUP_STRUCTURE.md" ]; then
  git mv NODE_GROUP_STRUCTURE.md docs/onex/
fi

if [ -f "SHARED_RESOURCE_VERSIONING.md" ]; then
  git mv SHARED_RESOURCE_VERSIONING.md docs/onex/
fi

# Move onex_canonical_examples if it exists in docs
if [ -d "docs/onex_canonical_examples" ]; then
  # Remove .DS_Store files that git doesn't track
  find docs/onex_canonical_examples -name ".DS_Store" -delete 2>/dev/null || true
  git mv docs/onex_canonical_examples docs/onex/examples 2>/dev/null || {
    echo "  Note: Could not move onex_canonical_examples, may already be moved"
  }
fi

if [ -d "onex_canonical_examples" ]; then
  find onex_canonical_examples -name ".DS_Store" -delete 2>/dev/null || true
  git mv onex_canonical_examples docs/onex/examples 2>/dev/null || {
    echo "  Note: Could not move onex_canonical_examples from root"
  }
fi

echo "✓ ONEX documentation organized"
echo ""

# ==========================================
# Phase 2: Move Architecture documentation
# ==========================================
echo "Phase 2: Organizing architecture documentation..."

if [ -f "HYBRID_ARCHITECTURE_FRAMEWORK_DOCUMENTATION.md" ]; then
  git mv HYBRID_ARCHITECTURE_FRAMEWORK_DOCUMENTATION.md docs/architecture/
fi

if [ -f "FRAMEWORK_MIGRATION_GUIDELINES.md" ]; then
  git mv FRAMEWORK_MIGRATION_GUIDELINES.md docs/architecture/
fi

if [ -f "VECTOR_ROUTING_SYSTEM.md" ]; then
  git mv VECTOR_ROUTING_SYSTEM.md docs/architecture/
fi

if [ -f "MCP_DOCUMENT_INDEXING_ARCHITECTURE.md" ]; then
  git mv MCP_DOCUMENT_INDEXING_ARCHITECTURE.md docs/architecture/
fi

if [ -f "MIGRATION_GUIDE.md" ]; then
  git mv MIGRATION_GUIDE.md docs/architecture/
fi

if [ -f "REAL_TIME_INDEXING_IMPLEMENTATION.md" ]; then
  git mv REAL_TIME_INDEXING_IMPLEMENTATION.md docs/architecture/
fi

if [ -f "indexing-strategy.md" ]; then
  git mv indexing-strategy.md docs/architecture/
fi

if [ -f "filtering-algorithms.md" ]; then
  git mv filtering-algorithms.md docs/architecture/
fi

if [ -f "schema-design-decisions.md" ]; then
  git mv schema-design-decisions.md docs/architecture/
fi

echo "✓ Architecture documentation organized"
echo ""

# ==========================================
# Phase 3: Move Phase documentation
# ==========================================
echo "Phase 3: Organizing phase documentation..."

if [ -f "PHASE_1_IMPLEMENTATION_PLAN.md" ]; then
  git mv PHASE_1_IMPLEMENTATION_PLAN.md docs/phases/
fi

if [ -f "PHASE_1_PROGRESS.md" ]; then
  git mv PHASE_1_PROGRESS.md docs/phases/
fi

if [ -f "PHASE_1_QUICKSTART.md" ]; then
  git mv PHASE_1_QUICKSTART.md docs/phases/
fi

if [ -f "PHASE_2_AGENT_EXECUTION_COMMANDS.md" ]; then
  git mv PHASE_2_AGENT_EXECUTION_COMMANDS.md docs/phases/
fi

if [ -f "PHASE_2_COMPLETION_REPORT.md" ]; then
  git mv PHASE_2_COMPLETION_REPORT.md docs/phases/
fi

if [ -f "PHASE_2_PARALLEL_IMPLEMENTATION_PLAN.md" ]; then
  git mv PHASE_2_PARALLEL_IMPLEMENTATION_PLAN.md docs/phases/
fi

if [ -f "PHASE_2_PARALLEL_ORCHESTRATION_PLAN.md" ]; then
  git mv PHASE_2_PARALLEL_ORCHESTRATION_PLAN.md docs/phases/
fi

if [ -f "PHASE_6_REFLEX_ARC_ARCHITECTURE.md" ]; then
  git mv PHASE_6_REFLEX_ARC_ARCHITECTURE.md docs/phases/
fi

# Move phase1 directory if it exists
if [ -d "docs/phase1" ]; then
  git mv docs/phase1 docs/phases/phase1
fi

if [ -d "phase1" ]; then
  git mv phase1 docs/phases/phase1
fi

echo "✓ Phase documentation organized"
echo ""

# ==========================================
# Phase 4: Move API documentation
# ==========================================
echo "Phase 4: Organizing API documentation..."

if [ -f "KNOWLEDGE_API_IMPLEMENTATION_GUIDE.md" ]; then
  git mv KNOWLEDGE_API_IMPLEMENTATION_GUIDE.md docs/api/
fi

if [ -f "KNOWLEDGE_API_MIGRATION_STRATEGY.md" ]; then
  git mv KNOWLEDGE_API_MIGRATION_STRATEGY.md docs/api/
fi

# Move api-contracts if it exists
if [ -d "docs/api-contracts" ]; then
  git mv docs/api-contracts docs/api/contracts
fi

if [ -d "api-contracts" ]; then
  git mv api-contracts docs/api/contracts
fi

echo "✓ API documentation organized"
echo ""

# ==========================================
# Phase 5: Move Research documentation
# ==========================================
echo "Phase 5: Organizing research documentation..."

if [ -f "AST_CORRECTION_RESEARCH.md" ]; then
  git mv AST_CORRECTION_RESEARCH.md docs/research/
fi

if [ -f "LANGEXTRACT_COMPREHENSIVE_ANALYSIS.md" ]; then
  git mv LANGEXTRACT_COMPREHENSIVE_ANALYSIS.md docs/research/
fi

if [ -f "LANGEXTRACT_INTERFACE_ANALYSIS.md" ]; then
  git mv LANGEXTRACT_INTERFACE_ANALYSIS.md docs/research/
fi

if [ -f "ARCHON_PROJECT_ANALYSIS_REPORT.md" ]; then
  git mv ARCHON_PROJECT_ANALYSIS_REPORT.md docs/research/
fi

if [ -f "ARCHON_STABILITY_ANALYSIS_REPORT.md" ]; then
  git mv ARCHON_STABILITY_ANALYSIS_REPORT.md docs/research/
fi

if [ -f "SEARCH_SERVICE_INVESTIGATION_REPORT.md" ]; then
  git mv SEARCH_SERVICE_INVESTIGATION_REPORT.md docs/research/
fi

if [ -f "MCP_SERVICE_DEBUG_ANALYSIS.md" ]; then
  git mv MCP_SERVICE_DEBUG_ANALYSIS.md docs/research/
fi

if [ -f "INVESTIGATION_FINDINGS_REPORT.md" ]; then
  git mv INVESTIGATION_FINDINGS_REPORT.md docs/research/
fi

# Move research directory if exists in docs
if [ -d "docs/research" ] && [ "$(ls -A docs/research 2>/dev/null)" ]; then
  # Research directory already exists in docs, merge if needed
  echo "  Note: Research directory already exists in docs/"
fi

if [ -d "research" ] && [ "$(ls -A research 2>/dev/null)" ]; then
  # Move contents from root research to docs/research
  for item in research/*; do
    if [ -e "$item" ]; then
      git mv "$item" docs/research/
    fi
  done
  rmdir research 2>/dev/null || true
fi

echo "✓ Research documentation organized"
echo ""

# ==========================================
# Phase 6: Move Guide documentation
# ==========================================
echo "Phase 6: Organizing guide documentation..."

if [ -f "DEVELOPER_GUIDE.md" ]; then
  git mv DEVELOPER_GUIDE.md docs/guides/
fi

if [ -f "TROUBLESHOOTING_GUIDE.md" ]; then
  git mv TROUBLESHOOTING_GUIDE.md docs/guides/
fi

if [ -f "OPERATIONAL_RUNBOOK.md" ]; then
  git mv OPERATIONAL_RUNBOOK.md docs/guides/
fi

if [ -f "MONITORING_INTEGRATION_GUIDE.md" ]; then
  git mv MONITORING_INTEGRATION_GUIDE.md docs/guides/
fi

if [ -f "pr-workflow-guide.md" ]; then
  git mv pr-workflow-guide.md docs/guides/
fi

if [ -f "template-usage-guide.md" ]; then
  git mv template-usage-guide.md docs/guides/
fi

if [ -f "query-ux-design.md" ]; then
  git mv query-ux-design.md docs/guides/
fi

if [ -f "PRODUCTION_ROLLOUT_PROCEDURES.md" ]; then
  git mv PRODUCTION_ROLLOUT_PROCEDURES.md docs/guides/
fi

if [ -f "DEPLOYMENT.md" ]; then
  git mv DEPLOYMENT.md docs/guides/
fi

echo "✓ Guide documentation organized"
echo ""

# ==========================================
# Phase 7: Move Report documentation
# ==========================================
echo "Phase 7: Organizing report documentation..."

if [ -f "WS4_QUALITY_GATES_VALIDATION_REPORT.md" ]; then
  git mv WS4_QUALITY_GATES_VALIDATION_REPORT.md docs/reports/
fi

if [ -f "WS5_PERFORMANCE_INTEGRATION_TESTING_REPORT.md" ]; then
  git mv WS5_PERFORMANCE_INTEGRATION_TESTING_REPORT.md docs/reports/
fi

if [ -f "WS6_FINAL_VALIDATION_REPORT.md" ]; then
  git mv WS6_FINAL_VALIDATION_REPORT.md docs/reports/
fi

if [ -f "WS7_COMPREHENSIVE_VALIDATION_REPORT.md" ]; then
  git mv WS7_COMPREHENSIVE_VALIDATION_REPORT.md docs/reports/
fi

if [ -f "WS7_CRITICAL_MEMORY_FOOTPRINT_ANALYSIS.md" ]; then
  git mv WS7_CRITICAL_MEMORY_FOOTPRINT_ANALYSIS.md docs/reports/
fi

if [ -f "WFC-07_COMPREHENSIVE_VALIDATION_REPORT.md" ]; then
  git mv WFC-07_COMPREHENSIVE_VALIDATION_REPORT.md docs/reports/
fi

if [ -f "PIPELINE_VALIDATION_REPORT.md" ]; then
  git mv PIPELINE_VALIDATION_REPORT.md docs/reports/
fi

if [ -f "PERFORMANCE_OPTIMIZATION_FINAL_REPORT.md" ]; then
  git mv PERFORMANCE_OPTIMIZATION_FINAL_REPORT.md docs/reports/
fi

if [ -f "TEST_SUITE_SUMMARY.md" ]; then
  git mv TEST_SUITE_SUMMARY.md docs/reports/
fi

if [ -f "VALIDATION_SUMMARY.md" ]; then
  git mv VALIDATION_SUMMARY.md docs/reports/
fi

if [ -f "SOLUTION_SUMMARY.md" ]; then
  git mv SOLUTION_SUMMARY.md docs/reports/
fi

if [ -f "CODEEXTRACTION_TEST_RESULTS.md" ]; then
  git mv CODEEXTRACTION_TEST_RESULTS.md docs/reports/
fi

if [ -f "pattern-integration-testing-report.md" ]; then
  git mv pattern-integration-testing-report.md docs/reports/
fi

if [ -f "template-performance-validation.md" ]; then
  git mv template-performance-validation.md docs/reports/
fi

if [ -f "correlation-cleanup-summary.md" ]; then
  git mv correlation-cleanup-summary.md docs/reports/
fi

if [ -f "semantic_correlation_improvements_summary.md" ]; then
  git mv semantic_correlation_improvements_summary.md docs/reports/
fi

if [ -f "AST_CORRECTION_IMPLEMENTATION_SUMMARY.md" ]; then
  git mv AST_CORRECTION_IMPLEMENTATION_SUMMARY.md docs/reports/
fi

echo "✓ Report documentation organized"
echo ""

# ==========================================
# Phase 8: Move Agent Framework documentation
# ==========================================
echo "Phase 8: Organizing agent framework documentation..."

if [ -f "AGENT_FRAMEWORK_HYBRID_IMPLEMENTATION_PLAN.md" ]; then
  git mv AGENT_FRAMEWORK_HYBRID_IMPLEMENTATION_PLAN.md docs/architecture/
fi

if [ -f "AGENT_FRAMEWORK_PHASE1_FINAL_INTEGRATION_REPORT.md" ]; then
  git mv AGENT_FRAMEWORK_PHASE1_FINAL_INTEGRATION_REPORT.md docs/reports/
fi

if [ -f "AGENT_FRAMEWORK_PHASE1_PARALLEL_ADDENDUM.md" ]; then
  git mv AGENT_FRAMEWORK_PHASE1_PARALLEL_ADDENDUM.md docs/architecture/
fi

if [ -f "agent-6-preparation-summary.md" ]; then
  git mv agent-6-preparation-summary.md docs/reports/
fi

if [ -f "agent-6-schema-preparation.md" ]; then
  git mv agent-6-schema-preparation.md docs/architecture/
fi

if [ -f "agent-framework-core-draft.yaml" ]; then
  git mv agent-framework-core-draft.yaml docs/architecture/
fi

if [ -d "docs/agent-framework" ]; then
  # Already in docs, keep it there
  echo "  Note: agent-framework directory already in docs/"
fi

if [ -d "agent-framework" ]; then
  git mv agent-framework docs/
fi

echo "✓ Agent framework documentation organized"
echo ""

# ==========================================
# Phase 9: Move Intelligence and Integration docs
# ==========================================
echo "Phase 9: Organizing intelligence and integration documentation..."

if [ -f "AGENT_INTELLIGENCE_ACCESS_PATTERNS.md" ]; then
  git mv AGENT_INTELLIGENCE_ACCESS_PATTERNS.md docs/architecture/
fi

if [ -f "INTELLIGENCE_SERVICE_ENDPOINT_SOLUTION.md" ]; then
  git mv INTELLIGENCE_SERVICE_ENDPOINT_SOLUTION.md docs/architecture/
fi

if [ -f "INTELLIGENCE_SYSTEM_INTEGRATION.md" ]; then
  git mv INTELLIGENCE_SYSTEM_INTEGRATION.md docs/architecture/
fi

if [ -f "INTELLIGENCE_CORRELATION_INTEGRATION_PLAN.md" ]; then
  git mv INTELLIGENCE_CORRELATION_INTEGRATION_PLAN.md docs/architecture/
fi

if [ -f "CORRELATION_DEBUG_SYSTEM_IMPLEMENTATION.md" ]; then
  git mv CORRELATION_DEBUG_SYSTEM_IMPLEMENTATION.md docs/architecture/
fi

if [ -f "intelligence-statistics-debug-report.md" ]; then
  git mv intelligence-statistics-debug-report.md docs/reports/
fi

if [ -f "KNOWLEDGE_OPTIMISTIC_UPDATES_INTEGRATION_STRATEGY.md" ]; then
  git mv KNOWLEDGE_OPTIMISTIC_UPDATES_INTEGRATION_STRATEGY.md docs/architecture/
fi

if [ -d "docs/integration" ]; then
  # Already in docs, keep it there
  echo "  Note: integration directory already in docs/"
fi

if [ -d "integration" ]; then
  git mv integration docs/
fi

echo "✓ Intelligence and integration documentation organized"
echo ""

# ==========================================
# Phase 10: Move remaining technical docs
# ==========================================
echo "Phase 10: Organizing remaining technical documentation..."

if [ -f "COMPREHENSIVE_KNOWLEDGE_TESTING_STRATEGY.md" ]; then
  git mv COMPREHENSIVE_KNOWLEDGE_TESTING_STRATEGY.md docs/guides/
fi

if [ -f "RAG_INTEGRATION_TESTS_SETUP.md" ]; then
  git mv RAG_INTEGRATION_TESTS_SETUP.md docs/guides/
fi

if [ -f "cross-reference-analysis.md" ]; then
  git mv cross-reference-analysis.md docs/architecture/
fi

if [ -f "test-intelligence-creation.md" ]; then
  git mv test-intelligence-creation.md docs/guides/
fi

if [ -f "PIPELINE_MONITORING_OPERATIONS.md" ]; then
  git mv PIPELINE_MONITORING_OPERATIONS.md docs/guides/
fi

if [ -f "PERFORMANCE_MONITORING_SETUP.md" ]; then
  git mv PERFORMANCE_MONITORING_SETUP.md docs/guides/
fi

if [ -f "MCP_KNOWLEDGE_BASE.md" ]; then
  git mv MCP_KNOWLEDGE_BASE.md docs/guides/
fi

if [ -f "MCP_SESSION_VALIDATION_ISSUE.md" ]; then
  git mv MCP_SESSION_VALIDATION_ISSUE.md docs/research/
fi

if [ -f "OmniNode_Orchestrator_Context_Development_Readiness.md" ]; then
  git mv OmniNode_Orchestrator_Context_Development_Readiness.md docs/reports/
fi

if [ -f "PRD-TaskManagement.md" ]; then
  git mv PRD-TaskManagement.md docs/guides/
fi

echo "✓ Remaining documentation organized"
echo ""

# ==========================================
# Phase 11: Move Docusaurus site files
# ==========================================
echo "Phase 11: Organizing Docusaurus site files..."

if [ -d "docs/docs" ]; then
  git mv docs/docs docs/site/content
fi

if [ -d "docs/src" ]; then
  git mv docs/src docs/site/src
fi

if [ -d "docs/static" ]; then
  git mv docs/static docs/site/static
fi

if [ -f "docusaurus.config.js" ]; then
  git mv docusaurus.config.js docs/site/
fi

if [ -f "sidebars.js" ]; then
  git mv sidebars.js docs/site/
fi

if [ -f "babel.config.js" ]; then
  git mv babel.config.js docs/site/
fi

echo "✓ Docusaurus site files organized"
echo ""

# ==========================================
# Phase 12: Move Infrastructure docs
# ==========================================
echo "Phase 12: Organizing infrastructure documentation..."

if [ -d "docs/infrastructure" ]; then
  # Already in docs, keep it there
  echo "  Note: infrastructure directory already in docs/"
fi

if [ -d "infrastructure" ]; then
  git mv infrastructure docs/
fi

if [ -d "docs/dev_logs" ]; then
  git mv docs/dev_logs docs/infrastructure/logs
fi

if [ -d "dev_logs" ]; then
  git mv dev_logs docs/infrastructure/logs
fi

echo "✓ Infrastructure documentation organized"
echo ""

# ==========================================
# Phase 13: Move test files
# ==========================================
echo "Phase 13: Organizing test files..."

# Integration tests
if [ -f "test_mcp_vs_qdrant.py" ]; then
  git mv test_mcp_vs_qdrant.py tests/integration/
fi

if [ -f "test_qdrant_vs_rag_search.py" ]; then
  git mv test_qdrant_vs_rag_search.py tests/integration/
fi

if [ -f "test_agent_compatibility.py" ]; then
  git mv test_agent_compatibility.py tests/integration/
fi

if [ -f "remaining_agent_compatibility_test.py" ]; then
  git mv remaining_agent_compatibility_test.py tests/integration/
fi

if [ -f "test_real_time_indexing_pipeline.py" ]; then
  git mv test_real_time_indexing_pipeline.py tests/integration/
fi

if [ -f "test_mcp_indexing_pipeline.py" ]; then
  git mv test_mcp_indexing_pipeline.py tests/integration/
fi

if [ -f "intelligence_service_api_test.py" ]; then
  git mv intelligence_service_api_test.py tests/integration/
fi

if [ -f "test_intelligence_integration.py" ]; then
  git mv test_intelligence_integration.py tests/integration/
fi

# Unit tests
if [ -f "test_code_extraction_service_independent.py" ]; then
  git mv test_code_extraction_service_independent.py tests/unit/
fi

if [ -f "test_code_extraction_isolated.py" ]; then
  git mv test_code_extraction_isolated.py tests/unit/
fi

if [ -f "test_service_methods_direct.py" ]; then
  git mv test_service_methods_direct.py tests/unit/
fi

if [ -f "test_core_logic_extracted.py" ]; then
  git mv test_core_logic_extracted.py tests/unit/
fi

if [ -f "test_qdrant_direct.py" ]; then
  git mv test_qdrant_direct.py tests/unit/
fi

if [ -f "test_naming_violations.py" ]; then
  git mv test_naming_violations.py tests/unit/
fi

if [ -f "test_blocking.py" ]; then
  git mv test_blocking.py tests/unit/
fi

# Performance tests
if [ -f "test_framework_performance_real.py" ]; then
  git mv test_framework_performance_real.py tests/performance/
fi

if [ -f "test_vector_health_monitoring.py" ]; then
  git mv test_vector_health_monitoring.py tests/performance/
fi

# Other tests
if [ -f "framework_validation_test.py" ]; then
  git mv framework_validation_test.py tests/
fi

if [ -f "test_hook.py" ]; then
  git mv test_hook.py tests/
fi

if [ -f "test_auto_apply_in_repo.py" ]; then
  git mv test_auto_apply_in_repo.py tests/
fi

if [ -f "test_permissive_mode.py" ]; then
  git mv test_permissive_mode.py tests/
fi

if [ -f "test_post_tool_use.py" ]; then
  git mv test_post_tool_use.py tests/
fi

echo "✓ Test files organized"
echo ""

# ==========================================
# Phase 14: Move scripts
# ==========================================
echo "Phase 14: Organizing scripts..."

if [ -f "deploy-intelligence-hooks.sh" ]; then
  git mv deploy-intelligence-hooks.sh scripts/
fi

if [ -f "run_integration_tests.py" ]; then
  git mv run_integration_tests.py scripts/
fi

if [ -f "run_rag_tests.py" ]; then
  git mv run_rag_tests.py scripts/
fi

echo "✓ Scripts organized"
echo ""

# ==========================================
# Phase 15: Create index files
# ==========================================
echo "Phase 15: Creating index files..."

# Create docs/README.md
cat > docs/README.md << 'EOF'
# Archon Documentation

This directory contains all documentation for the Archon project, organized by category.

## Directory Structure

- **onex/** - ONEX architecture patterns and design documentation
- **architecture/** - System architecture and design documents
- **phases/** - Implementation phase plans and progress reports
- **api/** - API documentation and contracts
- **research/** - Research documents and analysis reports
- **guides/** - User and developer guides
- **reports/** - Validation reports and test summaries
- **site/** - Docusaurus documentation site source
- **agent-framework/** - Agent framework documentation
- **infrastructure/** - Infrastructure and operations documentation
- **integration/** - Integration patterns and documentation

## Quick Links

### Getting Started
- [Developer Guide](guides/DEVELOPER_GUIDE.md)
- [Troubleshooting Guide](guides/TROUBLESHOOTING_GUIDE.md)
- [Operational Runbook](guides/OPERATIONAL_RUNBOOK.md)

### Architecture
- [ONEX Architecture Patterns](onex/ONEX_ARCHITECTURE_PATTERNS_COMPLETE.md)
- [Hybrid Architecture Framework](architecture/HYBRID_ARCHITECTURE_FRAMEWORK_DOCUMENTATION.md)
- [Migration Guide](architecture/MIGRATION_GUIDE.md)

### Implementation
- [Phase 1 Implementation Plan](phases/PHASE_1_IMPLEMENTATION_PLAN.md)
- [Phase 6 Reflex Arc Architecture](phases/PHASE_6_REFLEX_ARC_ARCHITECTURE.md)

## Contributing

When adding new documentation:
1. Place it in the appropriate category directory
2. Update this README with relevant links
3. Follow the existing naming conventions
4. Use descriptive filenames in UPPER_SNAKE_CASE or kebab-case
EOF

git add docs/README.md

echo "✓ Index files created"
echo ""

# ==========================================
# Final Report
# ==========================================
echo "=========================================="
echo "Reorganization Complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - ONEX documentation → docs/onex/"
echo "  - Architecture docs → docs/architecture/"
echo "  - Phase docs → docs/phases/"
echo "  - API docs → docs/api/"
echo "  - Research docs → docs/research/"
echo "  - Guides → docs/guides/"
echo "  - Reports → docs/reports/"
echo "  - Site files → docs/site/"
echo "  - Test files → tests/"
echo "  - Scripts → scripts/"
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Verify structure: tree docs/"
echo "  3. Commit changes: git commit -m 'docs: reorganize documentation structure'"
echo ""
