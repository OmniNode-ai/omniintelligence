"""
Code Relationship Detector - AST-based relationship extraction for code files

This module provides code-specific relationship detection using AST analysis
to complement the natural language relationship_mapper for documentation.

Detects relationships in Python code:
- IMPORTS: Import relationships (import X, from X import Y)
- INHERITANCE: Class inheritance (class A(B))
- CALLS: Function/method calls (function_name())
- DEFINITIONS: Function and class definitions

For other languages, basic pattern-based detection is used.
"""

import ast
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CodeRelationship(BaseModel):
    """A relationship detected in code"""

    id: str = Field(default_factory=lambda: f"rel_{hash(id(object()))}")
    source: str
    target: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence: List[str] = Field(default_factory=list)
    context: str = ""
    properties: Dict[str, Any] = Field(default_factory=dict)
    bidirectional: bool = False
    temporal_indicator: Optional[str] = None
    relationship_subtype: str = ""


class CodeRelationshipDetector:
    """
    Detects relationships in code using AST analysis (Python)
    or pattern matching (other languages)
    """

    def __init__(self):
        """Initialize code relationship detector"""
        self.supported_languages = {
            "python": self._detect_python_relationships,
            "py": self._detect_python_relationships,
        }

    async def detect_relationships(
        self,
        content: str,
        language: str = "python",
        document_path: str = "inline.py",
    ) -> List[CodeRelationship]:
        """
        Detect relationships in code

        Args:
            content: Code content
            language: Programming language
            document_path: Document path for context

        Returns:
            List of detected code relationships
        """
        # Normalize language
        language = language.lower().replace(".", "")

        # Use language-specific detector if available
        detector = self.supported_languages.get(
            language, self._detect_generic_relationships
        )

        try:
            relationships = await detector(content, document_path)
            logger.info(
                f"🔍 [CODE REL] Detected {len(relationships)} relationships | "
                f"language={language} | types={set(r.relationship_type for r in relationships)}"
            )
            return relationships
        except Exception as e:
            logger.error(f"❌ [CODE REL] Detection failed: {e}")
            return []

    async def _detect_python_relationships(
        self, content: str, document_path: str
    ) -> List[CodeRelationship]:
        """Detect relationships in Python code using AST analysis"""
        relationships = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.warning(f"⚠️ [CODE REL] Python syntax error: {e}")
            return []

        # Extract module/class name from path for source
        source_name = self._extract_module_name(document_path)

        # Detect IMPORTS relationships
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    relationships.append(
                        CodeRelationship(
                            source=source_name,
                            target=alias.name,
                            relationship_type="IMPORTS",
                            confidence=1.0,
                            evidence=[f"import {alias.name}"],
                            context=f"Direct import: import {alias.name}",
                            properties={
                                "import_type": "direct",
                                "alias": alias.asname if alias.asname else None,
                            },
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        relationships.append(
                            CodeRelationship(
                                source=source_name,
                                target=(
                                    node.module
                                    if alias.name == "*"
                                    else f"{node.module}.{alias.name}"
                                ),
                                relationship_type="IMPORTS",
                                confidence=1.0,
                                evidence=[f"from {node.module} import {alias.name}"],
                                context=f"From import: from {node.module} import {alias.name}",
                                properties={
                                    "import_type": "from_import",
                                    "module": node.module,
                                    "name": alias.name,
                                    "alias": alias.asname if alias.asname else None,
                                },
                            )
                        )

        # Detect INHERITANCE relationships
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                for base in node.bases:
                    base_name = self._extract_name_from_node(base)
                    if base_name:
                        relationships.append(
                            CodeRelationship(
                                source=f"{source_name}.{class_name}",
                                target=base_name,
                                relationship_type="INHERITS",
                                confidence=1.0,
                                evidence=[f"class {class_name}({base_name})"],
                                context=f"Class inheritance: {class_name} extends {base_name}",
                                properties={
                                    "class_name": class_name,
                                    "base_class": base_name,
                                },
                            )
                        )

        # Detect CALLS relationships (function calls)
        call_counts: Dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called_name = self._extract_name_from_node(node.func)
                if called_name and not called_name.startswith(
                    "_"
                ):  # Skip private functions
                    call_counts[called_name] = call_counts.get(called_name, 0) + 1

        # Create CALLS relationships with confidence based on frequency
        for called_name, count in call_counts.items():
            confidence = min(0.8 + (count - 1) * 0.05, 1.0)
            relationships.append(
                CodeRelationship(
                    source=source_name,
                    target=called_name,
                    relationship_type="CALLS",
                    confidence=confidence,
                    evidence=[f"{called_name}() called {count} time(s)"],
                    context=f"Function call: {called_name}() invoked {count} time(s)",
                    properties={
                        "call_count": count,
                        "confidence_calculation": f"min(0.8 + ({count} - 1) * 0.05, 1.0)",
                    },
                )
            )

        # Detect DEFINES relationships (function/class definitions)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                relationships.append(
                    CodeRelationship(
                        source=source_name,
                        target=f"{source_name}.{node.name}",
                        relationship_type="DEFINES",
                        confidence=1.0,
                        evidence=[f"def {node.name}(...)"],
                        context=f"Function definition: {node.name}",
                        properties={
                            "definition_type": "function",
                            "function_name": node.name,
                        },
                    )
                )

            elif isinstance(node, ast.ClassDef):
                relationships.append(
                    CodeRelationship(
                        source=source_name,
                        target=f"{source_name}.{node.name}",
                        relationship_type="DEFINES",
                        confidence=1.0,
                        evidence=[f"class {node.name}"],
                        context=f"Class definition: {node.name}",
                        properties={
                            "definition_type": "class",
                            "class_name": node.name,
                        },
                    )
                )

        return relationships

    async def _detect_generic_relationships(
        self, content: str, document_path: str
    ) -> List[CodeRelationship]:
        """Generic relationship detection for non-Python languages"""
        # TODO: Add pattern-based detection for other languages
        logger.info(f"ℹ️ [CODE REL] Generic detection not yet implemented")
        return []

    def _extract_module_name(self, document_path: str) -> str:
        """Extract module name from document path"""
        # Example: "services/intelligence/src/foo/bar.py" -> "bar"
        if "/" in document_path:
            name = document_path.split("/")[-1]
        else:
            name = document_path

        # Remove extension
        if "." in name:
            name = name.rsplit(".", 1)[0]

        return name

    def _extract_name_from_node(self, node: ast.AST) -> Optional[str]:
        """Extract name from AST node (handles Name, Attribute, etc.)"""
        if isinstance(node, ast.Name):
            return node.id

        elif isinstance(node, ast.Attribute):
            # Handle module.name or object.method
            value_name = self._extract_name_from_node(node.value)
            if value_name:
                return f"{value_name}.{node.attr}"
            return node.attr

        elif isinstance(node, ast.Call):
            # Handle function calls
            return self._extract_name_from_node(node.func)

        return None
