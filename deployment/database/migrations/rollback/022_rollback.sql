-- Rollback: 022_add_project_scope_to_learned_patterns
-- Ticket: OMN-1607

DROP INDEX IF EXISTS idx_learned_patterns_domain_project_scope;
DROP INDEX IF EXISTS idx_learned_patterns_project_scope;
ALTER TABLE learned_patterns DROP COLUMN IF EXISTS project_scope;
