-- Rollback: 016_create_review_pairing_tables
-- Description: Drop all five Review-Fix Pairing tables (reverse of 016_create_review_pairing_tables.sql)
-- Ticket: OMN-2535
--
-- Tables are dropped in reverse dependency order:
--   1. pattern_lifecycle (depends on pattern_candidates)
--   2. finding_fix_pairs (depends on review_findings)
--   3. review_fixes (depends on review_findings)
--   4. pattern_candidates (no FK dependencies)
--   5. review_findings (base table)

DROP TABLE IF EXISTS pattern_lifecycle CASCADE;
DROP TABLE IF EXISTS finding_fix_pairs CASCADE;
DROP TABLE IF EXISTS review_fixes CASCADE;
DROP TABLE IF EXISTS pattern_candidates CASCADE;
DROP TABLE IF EXISTS review_findings CASCADE;
