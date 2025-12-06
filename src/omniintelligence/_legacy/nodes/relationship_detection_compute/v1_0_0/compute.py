"""
Relationship Detection Compute Node

Detects relationships between code entities using AST analysis.
"""

import ast
from typing import Any

from omnibase_core.nodes import NodeCompute
from pydantic import BaseModel, Field

from omniintelligence._legacy.enums import EnumRelationshipType
from omniintelligence._legacy.models import ModelEntity, ModelRelationship


class ModelRelationshipDetectionInput(BaseModel):
    """Input model for relationship detection."""

    content: str = Field(..., description="Source code content to analyze")
    file_path: str = Field(..., description="Path to the source file")
    entities: list[ModelEntity] = Field(
        default_factory=list, description="Extracted entities from the code"
    )
    language: str = Field(default="python", description="Programming language")
    detect_cross_file: bool = Field(
        default=True, description="Detect cross-file relationships via imports"
    )


class ModelRelationshipDetectionOutput(BaseModel):
    """Output model for relationship detection."""

    success: bool = Field(..., description="Whether detection succeeded")
    relationships: list[ModelRelationship] = Field(
        default_factory=list, description="Detected relationships"
    )
    parse_errors: list[str] = Field(
        default_factory=list, description="Parse errors encountered"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Detection metadata"
    )


class ModelRelationshipDetectionConfig(BaseModel):
    """Configuration for relationship detection."""

    supported_languages: list[str] = Field(default_factory=lambda: ["python"])
    max_content_size: int = Field(default=1_000_000, description="Max content size in bytes")
    detect_calls: bool = Field(default=True, description="Detect function calls")
    detect_imports: bool = Field(default=True, description="Detect import relationships")
    detect_inheritance: bool = Field(default=True, description="Detect class inheritance")
    detect_contains: bool = Field(default=True, description="Detect containment relationships")
    detect_uses: bool = Field(default=True, description="Detect variable usage")
    detect_decorators: bool = Field(default=True, description="Detect decorator applications")
    detect_instantiation: bool = Field(default=True, description="Detect class instantiation")


class RelationshipDetectionCompute(NodeCompute):
    """Compute node for detecting code relationships."""

    def __init__(
        self,
        container: Any | None = None,
        config: ModelRelationshipDetectionConfig | None = None,
    ) -> None:
        """Initialize the relationship detection compute node.

        Args:
            container: Optional ONEX container for dependency injection (not used in standalone mode)
            config: Optional configuration for the node
        """
        # Only initialize base class with proper container (has compute_cache_config)
        # In standalone/test mode, container is None, so we skip super().__init__
        if container is not None and hasattr(container, "compute_cache_config"):
            super().__init__(container)

        self.config = config or ModelRelationshipDetectionConfig()

    async def process(
        self, input_data: ModelRelationshipDetectionInput
    ) -> ModelRelationshipDetectionOutput:
        """Detect relationships between entities.

        Args:
            input_data: Input containing source code and extracted entities

        Returns:
            ModelRelationshipDetectionOutput with detected relationships
        """
        if input_data.language != "python":
            return ModelRelationshipDetectionOutput(
                success=False,
                parse_errors=[f"Unsupported language: {input_data.language}"],
                metadata={"language": input_data.language},
            )

        if len(input_data.content) > self.config.max_content_size:
            return ModelRelationshipDetectionOutput(
                success=False,
                parse_errors=["Content exceeds maximum size"],
                metadata={"content_size": len(input_data.content)},
            )

        if not input_data.entities:
            return ModelRelationshipDetectionOutput(
                success=True,
                relationships=[],
                metadata={
                    "file_path": input_data.file_path,
                    "message": "No entities provided for relationship detection",
                },
            )

        try:
            tree = ast.parse(input_data.content)
            relationships = self._detect_relationships(
                tree=tree,
                entities=input_data.entities,
                file_path=input_data.file_path,
            )

            return ModelRelationshipDetectionOutput(
                success=True,
                relationships=relationships,
                metadata={
                    "file_path": input_data.file_path,
                    "relationship_count": len(relationships),
                    "entity_count": len(input_data.entities),
                    "language": input_data.language,
                },
            )

        except SyntaxError as e:
            return ModelRelationshipDetectionOutput(
                success=False,
                parse_errors=[f"Syntax error at line {e.lineno}: {e.msg}"],
                metadata={"file_path": input_data.file_path},
            )
        except Exception as e:
            return ModelRelationshipDetectionOutput(
                success=False,
                parse_errors=[f"Unexpected error: {e!s}"],
                metadata={"file_path": input_data.file_path},
            )

    def _detect_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        file_path: str,
    ) -> list[ModelRelationship]:
        """Detect all relationships from AST.

        Args:
            tree: Parsed AST tree
            entities: List of extracted entities
            file_path: Path to source file

        Returns:
            List of detected relationships
        """
        relationships: list[ModelRelationship] = []

        # Build entity lookup maps for fast access
        entity_by_name = {entity.name: entity for entity in entities}
        entity_by_id = {entity.entity_id: entity for entity in entities}

        # Get module entity
        module_entity = next(
            (e for e in entities if e.entity_type.value == "MODULE"), None
        )

        # Detect different relationship types
        if self.config.detect_imports:
            relationships.extend(
                self._detect_import_relationships(tree, entities, entity_by_name, module_entity)
            )

        if self.config.detect_inheritance:
            relationships.extend(
                self._detect_inheritance_relationships(tree, entities, entity_by_name)
            )

        if self.config.detect_contains:
            relationships.extend(
                self._detect_containment_relationships(tree, entities, entity_by_name, module_entity)
            )

        if self.config.detect_calls:
            relationships.extend(
                self._detect_call_relationships(tree, entities, entity_by_name)
            )

        if self.config.detect_decorators:
            relationships.extend(
                self._detect_decorator_relationships(tree, entities, entity_by_name)
            )

        if self.config.detect_uses:
            relationships.extend(
                self._detect_usage_relationships(tree, entities, entity_by_name)
            )

        if self.config.detect_instantiation:
            relationships.extend(
                self._detect_instantiation_relationships(tree, entities, entity_by_name)
            )

        return relationships

    def _detect_import_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
        module_entity: ModelEntity | None,
    ) -> list[ModelRelationship]:
        """Detect import relationships.

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name
            module_entity: The module entity

        Returns:
            List of import relationships
        """
        relationships: list[ModelRelationship] = []

        if not module_entity:
            return relationships

        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                # Get imported module names
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Find the dependency entity
                        dep_entity = entity_by_name.get(alias.name)
                        if dep_entity and dep_entity.entity_type.value == "DEPENDENCY":
                            relationships.append(
                                ModelRelationship(
                                    source_id=module_entity.entity_id,
                                    target_id=dep_entity.entity_id,
                                    relationship_type=EnumRelationshipType.IMPORTS,
                                    metadata={
                                        "import_type": "import",
                                        "alias": alias.asname,
                                        "line_number": node.lineno,
                                    },
                                )
                            )

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        # Construct full name
                        full_name = f"{module}.{alias.name}" if module else alias.name
                        dep_entity = entity_by_name.get(full_name)
                        if dep_entity and dep_entity.entity_type.value == "DEPENDENCY":
                            relationships.append(
                                ModelRelationship(
                                    source_id=module_entity.entity_id,
                                    target_id=dep_entity.entity_id,
                                    relationship_type=EnumRelationshipType.IMPORTS,
                                    metadata={
                                        "import_type": "from_import",
                                        "module": module,
                                        "imported_name": alias.name,
                                        "alias": alias.asname,
                                        "line_number": node.lineno,
                                    },
                                )
                            )

        return relationships

    def _detect_inheritance_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
    ) -> list[ModelRelationship]:
        """Detect class inheritance relationships.

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name

        Returns:
            List of inheritance relationships
        """
        relationships = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Find the class entity
                class_entity = entity_by_name.get(node.name)
                if not class_entity or class_entity.entity_type.value != "CLASS":
                    continue

                # Check base classes
                for base in node.bases:
                    # Try to get base class name
                    base_name = None
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        # Handle cases like module.ClassName
                        base_name = base.attr

                    if base_name:
                        # Look for the base class entity
                        base_entity = entity_by_name.get(base_name)
                        if base_entity and base_entity.entity_type.value == "CLASS":
                            relationships.append(
                                ModelRelationship(
                                    source_id=class_entity.entity_id,
                                    target_id=base_entity.entity_id,
                                    relationship_type=EnumRelationshipType.EXTENDS,
                                    metadata={
                                        "base_class": base_name,
                                        "line_number": node.lineno,
                                    },
                                )
                            )

        return relationships

    def _detect_containment_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
        module_entity: ModelEntity | None,
    ) -> list[ModelRelationship]:
        """Detect containment relationships (module contains class, class contains method).

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name
            module_entity: The module entity

        Returns:
            List of containment relationships
        """
        relationships = []

        # Build a map of AST nodes to their parent nodes
        parent_map: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent_map[child] = node

        for node in ast.walk(tree):
            # Class or function containment
            if isinstance(node, ast.ClassDef):
                class_entity = entity_by_name.get(node.name)
                if not class_entity:
                    continue

                # Check if class is at module level
                parent = parent_map.get(node)
                if isinstance(parent, ast.Module) and module_entity:
                    relationships.append(
                        ModelRelationship(
                            source_id=module_entity.entity_id,
                            target_id=class_entity.entity_id,
                            relationship_type=EnumRelationshipType.CONTAINS,
                            metadata={"type": "module_contains_class"},
                        )
                    )

                # Methods and attributes in class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        method_entity = entity_by_name.get(item.name)
                        if method_entity:
                            relationships.append(
                                ModelRelationship(
                                    source_id=class_entity.entity_id,
                                    target_id=method_entity.entity_id,
                                    relationship_type=EnumRelationshipType.CONTAINS,
                                    metadata={
                                        "type": "class_contains_method",
                                        "method_name": item.name,
                                    },
                                )
                            )

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                func_entity = entity_by_name.get(node.name)
                if not func_entity:
                    continue

                # Check if function is at module level
                parent = parent_map.get(node)
                if isinstance(parent, ast.Module) and module_entity:
                    relationships.append(
                        ModelRelationship(
                            source_id=module_entity.entity_id,
                            target_id=func_entity.entity_id,
                            relationship_type=EnumRelationshipType.CONTAINS,
                            metadata={"type": "module_contains_function"},
                        )
                    )

        return relationships

    def _detect_call_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
    ) -> list[ModelRelationship]:
        """Detect function call relationships.

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name

        Returns:
            List of call relationships
        """
        relationships: list[ModelRelationship] = []

        # Build context of which function we're currently in
        current_function_stack: list[str] = []

        class CallVisitor(ast.NodeVisitor):
            def __init__(self, visitor_self: "RelationshipDetectionCompute") -> None:
                self.visitor_self = visitor_self

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                current_function_stack.append(node.name)
                self.generic_visit(node)
                current_function_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                current_function_stack.append(node.name)
                self.generic_visit(node)
                current_function_stack.pop()

            def visit_Call(self, node: ast.Call) -> None:
                if current_function_stack:
                    caller_name = current_function_stack[-1]
                    caller_entity = entity_by_name.get(caller_name)

                    if caller_entity:
                        # Determine called function name
                        called_name = None
                        if isinstance(node.func, ast.Name):
                            called_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            called_name = node.func.attr

                        if called_name:
                            called_entity = entity_by_name.get(called_name)
                            if called_entity and called_entity.entity_type.value == "FUNCTION":
                                relationships.append(
                                    ModelRelationship(
                                        source_id=caller_entity.entity_id,
                                        target_id=called_entity.entity_id,
                                        relationship_type=EnumRelationshipType.CALLS,
                                        metadata={
                                            "caller": caller_name,
                                            "callee": called_name,
                                            "line_number": node.lineno,
                                        },
                                    )
                                )

                self.generic_visit(node)

        visitor = CallVisitor(self)
        visitor.visit(tree)

        return relationships

    def _detect_decorator_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
    ) -> list[ModelRelationship]:
        """Detect decorator application relationships.

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name

        Returns:
            List of decorator relationships
        """
        relationships = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                target_entity = entity_by_name.get(node.name)
                if not target_entity:
                    continue

                for decorator in node.decorator_list:
                    # Get decorator name
                    decorator_name = None
                    if isinstance(decorator, ast.Name):
                        decorator_name = decorator.id
                    elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                        decorator_name = decorator.func.id
                    elif isinstance(decorator, ast.Attribute):
                        decorator_name = decorator.attr

                    if decorator_name:
                        # Try to find decorator as a function entity
                        decorator_entity = entity_by_name.get(decorator_name)
                        if decorator_entity and decorator_entity.entity_type.value == "FUNCTION":
                            relationships.append(
                                ModelRelationship(
                                    source_id=decorator_entity.entity_id,
                                    target_id=target_entity.entity_id,
                                    relationship_type=EnumRelationshipType.REFERENCES,
                                    metadata={
                                        "relationship_subtype": "decorates",
                                        "decorator": decorator_name,
                                        "line_number": node.lineno,
                                    },
                                )
                            )

        return relationships

    def _detect_usage_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
    ) -> list[ModelRelationship]:
        """Detect variable/constant usage relationships.

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name

        Returns:
            List of usage relationships
        """
        relationships = []

        # Track which function we're in
        current_function_stack: list[str] = []

        class UsageVisitor(ast.NodeVisitor):
            def __init__(self, visitor_self: "RelationshipDetectionCompute") -> None:
                self.visitor_self = visitor_self

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                current_function_stack.append(node.name)
                self.generic_visit(node)
                current_function_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                current_function_stack.append(node.name)
                self.generic_visit(node)
                current_function_stack.pop()

            def visit_Name(self, node: ast.Name) -> None:
                # Only track variable loads (usage), not stores (definition)
                if isinstance(node.ctx, ast.Load) and current_function_stack:
                    user_func_name = current_function_stack[-1]
                    user_entity = entity_by_name.get(user_func_name)

                    if user_entity:
                        # Check if the name refers to a variable/constant entity
                        var_entity = entity_by_name.get(node.id)
                        if var_entity and var_entity.entity_type.value in ["VARIABLE", "CONSTANT"]:
                            relationships.append(
                                ModelRelationship(
                                    source_id=user_entity.entity_id,
                                    target_id=var_entity.entity_id,
                                    relationship_type=EnumRelationshipType.USES,
                                    metadata={
                                        "variable_name": node.id,
                                        "line_number": node.lineno,
                                    },
                                )
                            )

                self.generic_visit(node)

        visitor = UsageVisitor(self)
        visitor.visit(tree)

        return relationships

    def _detect_instantiation_relationships(
        self,
        tree: ast.AST,
        entities: list[ModelEntity],
        entity_by_name: dict[str, ModelEntity],
    ) -> list[ModelRelationship]:
        """Detect class instantiation relationships.

        Args:
            tree: AST tree
            entities: List of entities
            entity_by_name: Entity lookup by name

        Returns:
            List of instantiation relationships
        """
        relationships = []

        # Track which function we're in
        current_function_stack: list[str] = []

        class InstantiationVisitor(ast.NodeVisitor):
            def __init__(self, visitor_self: "RelationshipDetectionCompute") -> None:
                self.visitor_self = visitor_self

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                current_function_stack.append(node.name)
                self.generic_visit(node)
                current_function_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                current_function_stack.append(node.name)
                self.generic_visit(node)
                current_function_stack.pop()

            def visit_Call(self, node: ast.Call) -> None:
                if current_function_stack:
                    caller_name = current_function_stack[-1]
                    caller_entity = entity_by_name.get(caller_name)

                    if caller_entity:
                        # Check if calling a class (instantiation)
                        class_name = None
                        if isinstance(node.func, ast.Name):
                            class_name = node.func.id
                        elif isinstance(node.func, ast.Attribute):
                            class_name = node.func.attr

                        if class_name:
                            class_entity = entity_by_name.get(class_name)
                            if class_entity and class_entity.entity_type.value == "CLASS":
                                relationships.append(
                                    ModelRelationship(
                                        source_id=caller_entity.entity_id,
                                        target_id=class_entity.entity_id,
                                        relationship_type=EnumRelationshipType.REFERENCES,
                                        metadata={
                                            "relationship_subtype": "instantiates",
                                            "class_name": class_name,
                                            "line_number": node.lineno,
                                        },
                                    )
                                )

                self.generic_visit(node)

        visitor = InstantiationVisitor(self)
        visitor.visit(tree)

        return relationships
