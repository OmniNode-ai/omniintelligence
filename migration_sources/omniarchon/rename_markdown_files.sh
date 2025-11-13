#!/bin/bash
# Generated script to rename markdown files to ALL_CAPS_WITH_UNDERSCORES
# Run from repository root: /Volumes/PRO-G40/Code/omniarchon

set -e  # Exit on error

# OTHER (28 files)
git mv "PRPs/story_refactor_large_test_files.md" "PRPs/STORY_REFACTOR_LARGE_TEST_FILES.md"
git mv "PRPs/templates/prp_base.md" "PRPs/templates/PRP_BASE.md"
git mv "PRPs/templates/prp_story_task.md" "PRPs/templates/PRP_STORY_TASK.md"
git mv "docs/guides/PRD-TaskManagement.md" "docs/guides/PRD_TASK_MANAGEMENT.md"
git mv "docs/hybrid_scoring/adr/ADR-001-hybrid-scoring-approach.md" "docs/hybrid_scoring/adr/ADR_001_HYBRID_SCORING_APPROACH.md"
git mv "docs/hybrid_scoring/adr/ADR-002-caching-strategy.md" "docs/hybrid_scoring/adr/ADR_002_CACHING_STRATEGY.md"
git mv "docs/hybrid_scoring/adr/ADR-003-adaptive-weights.md" "docs/hybrid_scoring/adr/ADR_003_ADAPTIVE_WEIGHTS.md"
git mv "docs/hybrid_scoring/adr/ADR-004-circuit-breaker-pattern.md" "docs/hybrid_scoring/adr/ADR_004_CIRCUIT_BREAKER_PATTERN.md"
git mv "docs/hybrid_scoring/api_reference.md" "docs/hybrid_scoring/API_REFERENCE.md"
git mv "docs/hybrid_scoring/integration_guide.md" "docs/hybrid_scoring/INTEGRATION_GUIDE.md"
git mv "docs/hybrid_scoring/operational_runbook.md" "docs/hybrid_scoring/OPERATIONAL_RUNBOOK.md"
git mv "docs/hybrid_scoring/training/hybrid_scoring_training_guide.md" "docs/hybrid_scoring/training/HYBRID_SCORING_TRAINING_GUIDE.md"
git mv "docs/hybrid_scoring/training/onboarding_checklist.md" "docs/hybrid_scoring/training/ONBOARDING_CHECKLIST.md"
git mv "docs/implementation/integrations/omninode_bridge_integration.md" "docs/implementation/integrations/OMNINODE_BRIDGE_INTEGRATION.md"
git mv "docs/implementation/metadata_stamping_integration_plan.md" "docs/implementation/METADATA_STAMPING_INTEGRATION_PLAN.md"
git mv "docs/infrastructure/logs/jonah/debug/debug_log_2025_01_31_134500.md" "docs/infrastructure/logs/jonah/debug/DEBUG_LOG_2025_01_31_134500.md"
git mv "docs/reports/semantic_correlation_improvements_summary.md" "docs/reports/SEMANTIC_CORRELATION_IMPROVEMENTS_SUMMARY.md"
git mv "docs/research/omnibase_3_contracts_subcontracts.md" "docs/research/OMNIBASE_3_CONTRACTS_SUBCONTRACTS.md"
git mv "docs/research/omnibase_core_node_architecture.md" "docs/research/OMNIBASE_CORE_NODE_ARCHITECTURE.md"
git mv "docs/research/omnibase_infra_contracts_subcontracts.md" "docs/research/OMNIBASE_INFRA_CONTRACTS_SUBCONTRACTS.md"
git mv "python/docs/dev_logs/jonah/debug/debug_log_2025_01_30_163000.md" "python/docs/dev_logs/jonah/debug/DEBUG_LOG_2025_01_30_163000.md"
git mv "python/docs/menu_poc/integration_test_report.md" "python/docs/menu_poc/INTEGRATION_TEST_REPORT.md"
git mv "python/docs/menu_poc/wave1_agent3_test_results.md" "python/docs/menu_poc/WAVE1_AGENT3_TEST_RESULTS.md"
git mv "python/src/server/integration_verification_report.md" "python/src/server/INTEGRATION_VERIFICATION_REPORT.md"
git mv "python/tests/api_integration_issues.md" "python/tests/API_INTEGRATION_ISSUES.md"
git mv "python/tests/api_integration_test_report.md" "python/tests/API_INTEGRATION_TEST_REPORT.md"
git mv "scripts/README-sync-hooks.md" "scripts/README_SYNC_HOOKS.md"
git mv "services/langextract/test_document_onex.md" "services/langextract/TEST_DOCUMENT_ONEX.md"

# STARTS_WITH_NUMBER (2 files)
git mv "docs/onex/archive/2025-10-01_final_design_review.md" "docs/onex/archive/2025_10_01_FINAL_DESIGN_REVIEW.md"
git mv "docs/onex/archive/2025-10-01_innovation_analysis.md" "docs/onex/archive/2025_10_01_INNOVATION_ANALYSIS.md"

echo 'Renamed 30 files'
