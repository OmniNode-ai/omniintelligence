-- Migration: 025_code_entities.sql
-- AST-based code entity and relationship storage
-- Part of OMN-5657: AST-based code pattern extraction system

-- Latest-state entity table. One row per entity per repo.
-- Upsert key: (qualified_name, source_repo)
CREATE TABLE IF NOT EXISTS code_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- class, protocol, model, function, import, constant
    qualified_name TEXT NOT NULL,  -- module.ClassName.method_name
    source_repo TEXT NOT NULL,
    source_path TEXT NOT NULL,
    line_number INT,
    bases TEXT[],  -- base classes
    methods JSONB,  -- [{name, args, return_type, decorators}]
    fields JSONB,  -- for models: [{name, type, default}]
    decorators TEXT[],
    docstring TEXT,
    signature TEXT,  -- function signature string
    file_hash TEXT NOT NULL,  -- SHA256 for change detection
    -- Enrichment fields (populated by Task 7, NULL until enriched)
    classification TEXT,
    llm_description TEXT,
    architectural_pattern TEXT,
    classification_confidence FLOAT,
    enrichment_version TEXT,
    -- Freshness timestamps for derived-store coordination
    last_extracted_at TIMESTAMPTZ DEFAULT NOW(),
    last_enriched_at TIMESTAMPTZ,
    last_embedded_at TIMESTAMPTZ,
    last_graph_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(qualified_name, source_repo)
);

-- Latest-state relationship table.
-- Upsert key: (source_entity_id, target_entity_id, relationship_type)
CREATE TABLE IF NOT EXISTS code_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID REFERENCES code_entities(id) ON DELETE CASCADE,
    target_entity_id UUID REFERENCES code_entities(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    trust_tier TEXT NOT NULL DEFAULT 'strong',
    confidence FLOAT DEFAULT 1.0,
    evidence TEXT[],
    inject_into_context BOOLEAN DEFAULT true,
    source_repo TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_code_entities_repo ON code_entities(source_repo);
CREATE INDEX IF NOT EXISTS idx_code_entities_type ON code_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_code_entities_qualified ON code_entities(qualified_name);
CREATE INDEX IF NOT EXISTS idx_code_entities_classification ON code_entities(classification);
CREATE INDEX IF NOT EXISTS idx_code_entities_file_path ON code_entities(source_path);
CREATE INDEX IF NOT EXISTS idx_code_relationships_source ON code_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_code_relationships_target ON code_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_code_relationships_type ON code_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_code_relationships_injectable ON code_relationships(inject_into_context) WHERE inject_into_context = true;
