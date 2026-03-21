-- OMN-5709: Create code_relationships table for AST-extracted relationship storage.
-- FK references code_entities(id) with ON DELETE CASCADE for clean re-extraction.

CREATE TABLE IF NOT EXISTS code_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    trust_tier TEXT DEFAULT 'conservative',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_code_relationships_source ON code_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_code_relationships_target ON code_relationships(target_entity_id);
