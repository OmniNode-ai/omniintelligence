"""
Memgraph Graph Database Schemas

Defines Cypher query templates for creating and querying file location knowledge graph.
Provides node types, relationship types, and common query patterns.

ONEX Pattern: Compute (Configuration and schema definitions)
Performance: Node creation <10ms, relationship creation <5ms, queries <100ms
"""

from typing import Any, Dict, List

from constants.memgraph_labels import MemgraphLabels, MemgraphRelationships


class MemgraphSchemas:
    """
    Memgraph node and relationship schemas for file location knowledge graph.

    Graph Model:
        (:Project)-[:CONTAINS]->(:File)
        (:File)-[:HAS_CONCEPT]->(:Concept)
        (:File)-[:HAS_THEME]->(:Theme)
        (:File)-[:BELONGS_TO_DOMAIN]->(:Domain)
        (:File)-[:IS_ONEX_TYPE]->(:ONEXType)

    Node Types:
        - Project: Project metadata (name, path, file_count)
        - File: File metadata (path, hash, quality_score, onex_type)
        - Concept: Semantic concept (name)
        - Theme: High-level theme (name)
        - Domain: Domain classification (name)
        - ONEXType: ONEX node type (name)

    Relationship Types:
        - CONTAINS: Project contains File
        - HAS_CONCEPT: File has semantic Concept
        - HAS_THEME: File has Theme
        - BELONGS_TO_DOMAIN: File belongs to Domain
        - IS_ONEX_TYPE: File is ONEXType
    """

    # ==========================================================================
    # Node Creation Queries
    # ==========================================================================

    CREATE_PROJECT_NODE = f"""
        MERGE (p:{MemgraphLabels.PROJECT} {{name: $name}})
        ON CREATE SET
            p.path = $path,
            p.indexed_at = datetime(),
            p.file_count = $file_count
        ON MATCH SET
            p.file_count = $file_count,
            p.last_updated = datetime()
        RETURN p
    """

    CREATE_FILE_NODE = f"""
        MERGE (f:{MemgraphLabels.FILE} {{absolute_path: $absolute_path}})
        ON CREATE SET
            f.path = $path,
            f.hash = $hash,
            f.quality_score = $quality_score,
            f.onex_type = $onex_type,
            f.file_type = $file_type,
            f.indexed_at = datetime()
        ON MATCH SET
            f.quality_score = $quality_score,
            f.hash = $hash,
            f.last_updated = datetime()
        RETURN f
    """

    CREATE_CONCEPT_NODE = f"""
        MERGE (c:{MemgraphLabels.CONCEPT} {{name: $name}})
        ON CREATE SET c.created_at = datetime()
        RETURN c
    """

    CREATE_THEME_NODE = f"""
        MERGE (t:{MemgraphLabels.THEME} {{name: $name}})
        ON CREATE SET t.created_at = datetime()
        RETURN t
    """

    CREATE_DOMAIN_NODE = f"""
        MERGE (d:{MemgraphLabels.DOMAIN} {{name: $name}})
        ON CREATE SET d.created_at = datetime()
        RETURN d
    """

    CREATE_ONEX_TYPE_NODE = f"""
        MERGE (o:{MemgraphLabels.ONEX_TYPE} {{name: $name}})
        ON CREATE SET o.created_at = datetime()
        RETURN o
    """

    # ==========================================================================
    # Relationship Creation Queries
    # ==========================================================================

    CREATE_CONTAINS_RELATIONSHIP = f"""
        MATCH (p:{MemgraphLabels.PROJECT} {{name: $project_name}})
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: $file_path}})
        MERGE (p)-[r:{MemgraphRelationships.CONTAINS}]->(f)
        ON CREATE SET r.indexed_at = datetime()
        RETURN r
    """

    CREATE_HAS_CONCEPT_RELATIONSHIP = f"""
        MERGE (c:{MemgraphLabels.CONCEPT} {{name: $concept_name}})
        WITH c
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: $file_path}})
        MERGE (f)-[r:{MemgraphRelationships.HAS_CONCEPT}]->(c)
        ON CREATE SET r.confidence = $confidence
        RETURN r
    """

    CREATE_HAS_THEME_RELATIONSHIP = f"""
        MERGE (t:{MemgraphLabels.THEME} {{name: $theme_name}})
        WITH t
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: $file_path}})
        MERGE (f)-[r:{MemgraphRelationships.HAS_THEME}]->(t)
        RETURN r
    """

    CREATE_BELONGS_TO_DOMAIN_RELATIONSHIP = f"""
        MERGE (d:{MemgraphLabels.DOMAIN} {{name: $domain_name}})
        WITH d
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: $file_path}})
        MERGE (f)-[r:{MemgraphRelationships.BELONGS_TO_DOMAIN}]->(d)
        RETURN r
    """

    CREATE_IS_ONEX_TYPE_RELATIONSHIP = f"""
        MERGE (o:{MemgraphLabels.ONEX_TYPE} {{name: $onex_type_name}})
        WITH o
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: $file_path}})
        MERGE (f)-[r:{MemgraphRelationships.IS_ONEX_TYPE}]->(o)
        RETURN r
    """

    # ==========================================================================
    # Query Patterns
    # ==========================================================================

    FIND_FILES_BY_PROJECT = f"""
        MATCH (p:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:{MemgraphRelationships.CONTAINS}]->(f:{MemgraphLabels.FILE})
        RETURN f
        ORDER BY f.quality_score DESC
    """

    FIND_FILES_BY_CONCEPT = f"""
        MATCH (f:{MemgraphLabels.FILE})-[:{MemgraphRelationships.HAS_CONCEPT}]->(c:{MemgraphLabels.CONCEPT} {{name: $concept_name}})
        WHERE f.quality_score >= $min_quality
        RETURN f
        ORDER BY f.quality_score DESC
        LIMIT $limit
    """

    FIND_FILES_BY_THEME = f"""
        MATCH (f:{MemgraphLabels.FILE})-[:{MemgraphRelationships.HAS_THEME}]->(t:{MemgraphLabels.THEME} {{name: $theme_name}})
        WHERE f.quality_score >= $min_quality
        RETURN f
        ORDER BY f.quality_score DESC
        LIMIT $limit
    """

    FIND_FILES_BY_ONEX_TYPE = f"""
        MATCH (f:{MemgraphLabels.FILE})-[:{MemgraphRelationships.IS_ONEX_TYPE}]->(o:{MemgraphLabels.ONEX_TYPE} {{name: $onex_type_name}})
        WHERE f.quality_score >= $min_quality
        RETURN f
        ORDER BY f.quality_score DESC
        LIMIT $limit
    """

    FIND_FILES_BY_DOMAIN = f"""
        MATCH (f:{MemgraphLabels.FILE})-[:{MemgraphRelationships.BELONGS_TO_DOMAIN}]->(d:{MemgraphLabels.DOMAIN} {{name: $domain_name}})
        WHERE f.quality_score >= $min_quality
        RETURN f
        ORDER BY f.quality_score DESC
        LIMIT $limit
    """

    FIND_HIGH_QUALITY_FILES = f"""
        MATCH (f:{MemgraphLabels.FILE})
        WHERE f.quality_score >= $min_quality
        RETURN f
        ORDER BY f.quality_score DESC
        LIMIT $limit
    """

    FIND_FILES_BY_MULTIPLE_CONCEPTS = f"""
        MATCH (f:{MemgraphLabels.FILE})-[:{MemgraphRelationships.HAS_CONCEPT}]->(c:{MemgraphLabels.CONCEPT})
        WHERE c.name IN $concept_names
        WITH f, count(DISTINCT c) as concept_count
        WHERE concept_count >= $min_concepts
        RETURN f, concept_count
        ORDER BY concept_count DESC, f.quality_score DESC
        LIMIT $limit
    """

    GET_FILE_METADATA = f"""
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: $file_path}})
        OPTIONAL MATCH (f)-[:{MemgraphRelationships.HAS_CONCEPT}]->(c:{MemgraphLabels.CONCEPT})
        OPTIONAL MATCH (f)-[:{MemgraphRelationships.HAS_THEME}]->(t:{MemgraphLabels.THEME})
        OPTIONAL MATCH (f)-[:{MemgraphRelationships.BELONGS_TO_DOMAIN}]->(d:{MemgraphLabels.DOMAIN})
        OPTIONAL MATCH (f)-[:{MemgraphRelationships.IS_ONEX_TYPE}]->(o:{MemgraphLabels.ONEX_TYPE})
        OPTIONAL MATCH (p:{MemgraphLabels.PROJECT})-[:{MemgraphRelationships.CONTAINS}]->(f)
        RETURN f,
               collect(DISTINCT c.name) as concepts,
               collect(DISTINCT t.name) as themes,
               collect(DISTINCT d.name) as domains,
               o.name as onex_type,
               p.name as project_name
    """

    GET_PROJECT_STATISTICS = f"""
        MATCH (p:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:{MemgraphRelationships.CONTAINS}]->(f:{MemgraphLabels.FILE})
        RETURN p.name as project,
               count(f) as total_files,
               avg(f.quality_score) as avg_quality,
               min(f.quality_score) as min_quality,
               max(f.quality_score) as max_quality
    """

    GET_CONCEPT_STATISTICS = f"""
        MATCH (c:{MemgraphLabels.CONCEPT})<-[:{MemgraphRelationships.HAS_CONCEPT}]-(f:{MemgraphLabels.FILE})
        RETURN c.name as concept,
               count(f) as file_count,
               avg(f.quality_score) as avg_quality
        ORDER BY file_count DESC
        LIMIT $limit
    """

    # ==========================================================================
    # Batch Operations
    # ==========================================================================

    BATCH_CREATE_FILES = f"""
        UNWIND $files as file_data
        MERGE (f:{MemgraphLabels.FILE} {{absolute_path: file_data.absolute_path}})
        ON CREATE SET
            f.path = file_data.path,
            f.hash = file_data.hash,
            f.quality_score = file_data.quality_score,
            f.onex_type = file_data.onex_type,
            f.file_type = file_data.file_type,
            f.indexed_at = datetime()
        ON MATCH SET
            f.quality_score = file_data.quality_score,
            f.hash = file_data.hash,
            f.last_updated = datetime()
        RETURN count(f) as files_created
    """

    BATCH_CREATE_RELATIONSHIPS = f"""
        UNWIND $relationships as rel
        MATCH (f:{MemgraphLabels.FILE} {{absolute_path: rel.file_path}})
        MERGE (c:{MemgraphLabels.CONCEPT} {{name: rel.concept}})
        MERGE (f)-[r:{MemgraphRelationships.HAS_CONCEPT}]->(c)
        ON CREATE SET r.confidence = rel.confidence
        RETURN count(r) as relationships_created
    """

    # ==========================================================================
    # Cleanup Operations
    # ==========================================================================

    DELETE_PROJECT_AND_FILES = f"""
        MATCH (p:{MemgraphLabels.PROJECT} {{name: $project_name}})-[:{MemgraphRelationships.CONTAINS}]->(f:{MemgraphLabels.FILE})
        DETACH DELETE f, p
    """

    DELETE_ORPHANED_CONCEPTS = f"""
        MATCH (c:{MemgraphLabels.CONCEPT})
        WHERE NOT (c)<-[:{MemgraphRelationships.HAS_CONCEPT}]-()
        DELETE c
        RETURN count(c) as deleted_count
    """

    @staticmethod
    def get_example_parameters() -> Dict[str, Any]:
        """
        Get example query parameters for documentation and testing.

        Returns:
            Dictionary of example parameters for different query types

        Example:
            >>> params = MemgraphSchemas.get_example_parameters()
            >>> project_params = params["create_project"]
        """
        return {
            "create_project": {
                "name": "omniarchon",
                "path": "/Volumes/PRO-G40/Code/omniarchon",
                "file_count": 1247,
            },
            "create_file": {
                "absolute_path": "/Volumes/PRO-G40/Code/omniarchon/src/auth/jwt.py",
                "path": "src/auth/jwt.py",
                "hash": "blake3_abc123",
                "quality_score": 0.87,
                "onex_type": "effect",
                "file_type": ".py",
            },
            "create_concept": {
                "name": "authentication",
            },
            "create_contains": {
                "project_name": "omniarchon",
                "file_path": "/Volumes/PRO-G40/Code/omniarchon/src/auth/jwt.py",
            },
            "create_has_concept": {
                "file_path": "/Volumes/PRO-G40/Code/omniarchon/src/auth/jwt.py",
                "concept_name": "authentication",
                "confidence": 0.92,
            },
            "find_by_concept": {
                "concept_name": "authentication",
                "min_quality": 0.7,
                "limit": 10,
            },
            "find_by_multiple_concepts": {
                "concept_names": ["authentication", "JWT", "security"],
                "min_concepts": 2,
                "limit": 10,
            },
        }

    @staticmethod
    def validate_node_type(node_type: str) -> bool:
        """
        Validate node type is supported.

        Args:
            node_type: Node type to validate

        Returns:
            True if valid, False otherwise
        """
        valid_types = ["Project", "File", "Concept", "Theme", "Domain", "ONEXType"]
        return node_type in valid_types

    @staticmethod
    def validate_relationship_type(rel_type: str) -> bool:
        """
        Validate relationship type is supported.

        Args:
            rel_type: Relationship type to validate

        Returns:
            True if valid, False otherwise
        """
        valid_types = [
            "CONTAINS",
            "HAS_CONCEPT",
            "HAS_THEME",
            "BELONGS_TO_DOMAIN",
            "IS_ONEX_TYPE",
        ]
        return rel_type in valid_types


__all__ = ["MemgraphSchemas"]
