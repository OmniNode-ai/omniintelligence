"""
Base Entity Extractor for Archon Intelligence Service

AST-based entity extraction for code analysis and documentation processing.
Adapted from omnibase_3 patterns for Archon's knowledge graph requirements.
"""

import ast
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from models.entity_models import (
    EntityType,
    KnowledgeEntity,
    KnowledgeRelationship,
    RelationshipType,
)


class BaseEntityExtractor:
    """
    Base class for entity extraction from code and documentation.

    Provides AST parsing, pattern matching, and basic entity detection
    for various programming languages and document types.
    """

    def __init__(self):
        """Initialize base extractor with language mappings and patterns"""
        self.supported_languages = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".md": "markdown",
            ".rst": "restructuredtext",
            ".txt": "text",
        }

        # Language-specific entity patterns
        self.entity_patterns = {
            "python": {
                "class": r"class\s+([A-Za-z_][A-Za-z0-9_]*)",
                "function": r"def\s+([A-Za-z_][A-Za-z0-9_]*)",
                "variable": r"([A-Za-z_][A-Za-z0-9_]*)\s*=",
                "import": r"(?:from\s+[\w.]+\s+)?import\s+([\w.,\s]+)",
            },
            "javascript": {
                "class": r"class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
                "function": r"(?:function\s+([A-Za-z_$][A-Za-z0-9_$]*)|([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>))",
                "variable": r"(?:var|let|const)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
                "import": r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]',
            },
            "markdown": {
                "heading": r"^#{1,6}\s+(.+)$",
                "code_block": r"```(\w+)?\n(.*?)```",
                "link": r"\[([^\]]+)\]\(([^)]+)\)",
            },
        }

    def extract_entities_from_content(
        self, content: str, source_path: str, language: Optional[str] = None
    ) -> List[KnowledgeEntity]:
        """
        Extract entities from content using appropriate extraction method.

        Args:
            content: Source content to analyze
            source_path: Path to source file/document
            language: Programming language (auto-detected if None)

        Returns:
            List of extracted knowledge entities
        """
        if not content.strip():
            return []

        # Detect language if not provided
        if not language:
            language = self._detect_language(source_path)

        entities = []

        # Extract based on content type
        if language == "python":
            entities.extend(self._extract_python_entities(content, source_path))
        elif language in ["javascript", "typescript"]:
            entities.extend(
                self._extract_javascript_entities(content, source_path, language)
            )
        elif language in ["markdown", "restructuredtext"]:
            entities.extend(
                self._extract_document_entities(content, source_path, language)
            )
        else:
            # Fallback to pattern-based extraction
            entities.extend(
                self._extract_pattern_entities(content, source_path, language)
            )

        # Add source metadata to all entities
        for entity in entities:
            self._enrich_entity_metadata(entity, content, source_path)

        return entities

    def _extract_python_entities(
        self, content: str, source_path: str
    ) -> List[KnowledgeEntity]:
        """Extract entities from Python code using AST parsing"""
        entities = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    entity = self._create_entity_from_ast_node(
                        node, EntityType.CLASS, source_path, content
                    )
                    entities.append(entity)

                    # Extract methods from class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_entity = self._create_entity_from_ast_node(
                                item,
                                EntityType.METHOD,
                                source_path,
                                content,
                                parent_name=node.name,
                            )
                            entities.append(method_entity)

                elif isinstance(node, ast.FunctionDef):
                    # Top-level function
                    entity = self._create_entity_from_ast_node(
                        node, EntityType.FUNCTION, source_path, content
                    )
                    entities.append(entity)

                elif isinstance(node, ast.Assign):
                    # Variable assignments at module level
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            entity = KnowledgeEntity(
                                entity_id=self._generate_entity_id(
                                    target.id, source_path
                                ),
                                name=target.id,
                                entity_type=EntityType.VARIABLE,
                                description=f"Variable assignment: {target.id}",
                                source_path=source_path,
                                confidence_score=0.7,
                                source_line_number=getattr(node, "lineno", None),
                            )
                            entities.append(entity)

        except SyntaxError:
            # Handle syntax errors gracefully
            pass

        return entities

    def _extract_javascript_entities(
        self, content: str, source_path: str, language: str
    ) -> List[KnowledgeEntity]:
        """Extract entities from JavaScript/TypeScript using pattern matching"""
        entities = []

        patterns = self.entity_patterns.get(language, {})
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Class definitions
            if "class" in patterns:
                matches = re.findall(patterns["class"], line)
                for match in matches:
                    entity = KnowledgeEntity(
                        entity_id=self._generate_entity_id(match, source_path),
                        name=match,
                        entity_type=EntityType.CLASS,
                        description=f"JavaScript class: {match}",
                        source_path=source_path,
                        confidence_score=0.8,
                        source_line_number=line_num,
                    )
                    entities.append(entity)

            # Function definitions
            if "function" in patterns:
                matches = re.findall(patterns["function"], line)
                for match_tuple in matches:
                    # Handle tuple results from complex regex
                    func_name = (
                        next(m for m in match_tuple if m)
                        if isinstance(match_tuple, tuple)
                        else match_tuple
                    )
                    if func_name:
                        entity = KnowledgeEntity(
                            entity_id=self._generate_entity_id(func_name, source_path),
                            name=func_name,
                            entity_type=EntityType.FUNCTION,
                            description=f"JavaScript function: {func_name}",
                            source_path=source_path,
                            confidence_score=0.8,
                            source_line_number=line_num,
                        )
                        entities.append(entity)

        return entities

    def _extract_document_entities(
        self, content: str, source_path: str, doc_type: str
    ) -> List[KnowledgeEntity]:
        """Extract entities from documentation (Markdown, RST, etc.)"""
        entities = []

        if doc_type == "markdown":
            entities.extend(self._extract_markdown_entities(content, source_path))

        # Generic document entity
        doc_entity = KnowledgeEntity(
            entity_id=self._generate_entity_id(Path(source_path).stem, source_path),
            name=Path(source_path).stem,
            entity_type=EntityType.DOCUMENT,
            description=f"Documentation: {Path(source_path).name}",
            source_path=source_path,
            confidence_score=0.9,
        )
        entities.append(doc_entity)

        return entities

    def _extract_markdown_entities(
        self, content: str, source_path: str
    ) -> List[KnowledgeEntity]:
        """Extract entities from Markdown content"""
        entities = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Headings
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                entity = KnowledgeEntity(
                    entity_id=self._generate_entity_id(f"heading_{title}", source_path),
                    name=title,
                    entity_type=EntityType.CONCEPT,
                    description=f"Markdown heading (level {level}): {title}",
                    source_path=source_path,
                    confidence_score=0.8,
                    source_line_number=line_num,
                    properties={"heading_level": level},
                )
                entities.append(entity)

            # Code blocks
            code_match = re.match(r"^```(\w+)?", line)
            if code_match:
                language = code_match.group(1) or "unknown"
                entity = KnowledgeEntity(
                    entity_id=self._generate_entity_id(
                        f"code_block_{line_num}", source_path
                    ),
                    name=f"Code Block ({language})",
                    entity_type=EntityType.CODE_EXAMPLE,
                    description=f"Code block in {language}",
                    source_path=source_path,
                    confidence_score=0.7,
                    source_line_number=line_num,
                    properties={"language": language},
                )
                entities.append(entity)

        return entities

    def _extract_pattern_entities(
        self, content: str, source_path: str, language: str
    ) -> List[KnowledgeEntity]:
        """Fallback pattern-based extraction for unsupported languages"""
        entities = []

        patterns = self.entity_patterns.get(language, {})
        if not patterns:
            return entities

        lines = content.split("\n")

        for pattern_type, pattern in patterns.items():
            for line_num, line in enumerate(lines, 1):
                matches = re.findall(pattern, line)
                for match in matches:
                    # Handle different match types
                    name = (
                        match
                        if isinstance(match, str)
                        else (match[0] if match else "unknown")
                    )

                    entity_type = self._pattern_to_entity_type(pattern_type)

                    entity = KnowledgeEntity(
                        entity_id=self._generate_entity_id(name, source_path),
                        name=name,
                        entity_type=entity_type,
                        description=f"{language} {pattern_type}: {name}",
                        source_path=source_path,
                        confidence_score=0.6,
                        source_line_number=line_num,
                    )
                    entities.append(entity)

        return entities

    def _create_entity_from_ast_node(
        self,
        node: ast.AST,
        entity_type: EntityType,
        source_path: str,
        content: str,
        parent_name: Optional[str] = None,
    ) -> KnowledgeEntity:
        """Create entity from AST node"""
        name = getattr(node, "name", "unknown")

        # Generate description based on node type and content
        description = self._generate_entity_description(node, entity_type, parent_name)

        entity = KnowledgeEntity(
            entity_id=self._generate_entity_id(
                f"{parent_name}.{name}" if parent_name else name, source_path
            ),
            name=name,
            entity_type=entity_type,
            description=description,
            source_path=source_path,
            confidence_score=0.9,  # High confidence for AST-based extraction
            source_line_number=getattr(node, "lineno", None),
        )

        return entity

    def _generate_entity_description(
        self, node: ast.AST, entity_type: EntityType, parent_name: Optional[str] = None
    ) -> str:
        """Generate descriptive text for entity based on AST node"""
        name = getattr(node, "name", "unknown")

        if isinstance(node, ast.ClassDef):
            bases = [base.id for base in node.bases if hasattr(base, "id")]
            base_info = f" inheriting from {', '.join(bases)}" if bases else ""
            return f"Python class {name}{base_info}"

        elif isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args] if hasattr(node, "args") else []
            arg_info = f"({', '.join(args)})" if args else "()"
            context = f" in class {parent_name}" if parent_name else ""
            return f"Python function {name}{arg_info}{context}"

        else:
            return f"Python {entity_type.value.lower()}: {name}"

    def _enrich_entity_metadata(
        self, entity: KnowledgeEntity, content: str, source_path: str
    ):
        """Enrich entity with metadata and quality scores"""
        # Calculate file hash for change detection
        file_hash = hashlib.md5(content.encode()).hexdigest()

        # Update metadata
        entity.metadata.file_hash = file_hash
        entity.metadata.extraction_method = "base_ast_parsing"
        entity.metadata.extraction_confidence = entity.confidence_score
        entity.metadata.created_at = datetime.now(timezone.utc)

        # Add basic properties
        entity.properties.update(
            {
                "file_extension": Path(source_path).suffix,
                "file_size": len(content),
                "lines_of_code": len(content.split("\n")),
            }
        )

    def _detect_language(self, source_path: str) -> str:
        """Detect programming language from file extension"""
        ext = Path(source_path).suffix.lower()
        return self.supported_languages.get(ext, "unknown")

    def _pattern_to_entity_type(self, pattern_type: str) -> EntityType:
        """Map pattern type to EntityType enum"""
        mapping = {
            "class": EntityType.CLASS,
            "function": EntityType.FUNCTION,
            "method": EntityType.METHOD,
            "variable": EntityType.VARIABLE,
            "constant": EntityType.CONSTANT,
            "import": EntityType.MODULE,
            "heading": EntityType.CONCEPT,
            "code_block": EntityType.CODE_EXAMPLE,
            "link": EntityType.DOCUMENT,
        }
        return mapping.get(pattern_type, EntityType.CONCEPT)

    def _generate_entity_id(self, name: str, source_path: str) -> str:
        """Generate unique entity ID"""
        source_hash = hashlib.md5(source_path.encode()).hexdigest()[:8]
        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        return f"entity_{name_hash}_{source_hash}"

    def extract_relationships(
        self, entities: List[KnowledgeEntity], content: str, source_path: str
    ) -> List[KnowledgeRelationship]:
        """Extract relationships between entities"""
        relationships = []

        # Simple relationship extraction based on proximity and references
        for i, entity in enumerate(entities):
            for j, other_entity in enumerate(entities):
                if i != j:
                    # Check if entities are related (same file, references, etc.)
                    relationship = self._detect_relationship(
                        entity, other_entity, content
                    )
                    if relationship:
                        relationships.append(relationship)

        return relationships

    def _detect_relationship(
        self, entity1: KnowledgeEntity, entity2: KnowledgeEntity, content: str
    ) -> Optional[KnowledgeRelationship]:
        """Detect relationship between two entities"""

        # Method belongs to class
        if (
            entity1.entity_type == EntityType.CLASS
            and entity2.entity_type == EntityType.METHOD
            and entity2.name in content
        ):
            return KnowledgeRelationship(
                relationship_id=self._generate_relationship_id(
                    entity1.entity_id, entity2.entity_id
                ),
                source_entity_id=entity1.entity_id,
                target_entity_id=entity2.entity_id,
                relationship_type=RelationshipType.CONTAINS,
                confidence_score=0.8,
            )

        # Function calls or references
        if entity1.name in content and entity2.name in content:
            # Simple heuristic: if one entity name appears near the other
            lines = content.split("\n")
            for line_num, line in enumerate(lines):
                if entity1.name in line and entity2.name in line:
                    return KnowledgeRelationship(
                        relationship_id=self._generate_relationship_id(
                            entity1.entity_id, entity2.entity_id
                        ),
                        source_entity_id=entity1.entity_id,
                        target_entity_id=entity2.entity_id,
                        relationship_type=RelationshipType.RELATES_TO,
                        confidence_score=0.6,
                        properties={"detected_line": line_num + 1},
                    )

        return None

    def _generate_relationship_id(self, source_id: str, target_id: str) -> str:
        """Generate unique relationship ID"""
        combined = f"{source_id}_{target_id}"
        return f"rel_{hashlib.md5(combined.encode()).hexdigest()[:12]}"
