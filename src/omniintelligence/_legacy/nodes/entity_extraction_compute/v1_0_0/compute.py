"""
Entity Extraction Compute Node

Extracts code entities (functions, classes, variables, imports) from source code using AST.
"""

import ast
import uuid
from typing import Any

from omnibase_core.nodes import NodeCompute
from pydantic import BaseModel, Field

from omniintelligence._legacy.enums import EnumEntityType
from omniintelligence._legacy.models import ModelEntity


class ModelEntityExtractionInput(BaseModel):
    """Input model for entity extraction."""

    content: str = Field(..., description="Source code content to analyze")
    file_path: str = Field(..., description="Path to the source file")
    language: str = Field(default="python", description="Programming language")
    extract_docstrings: bool = Field(default=True, description="Extract docstrings")
    extract_decorators: bool = Field(default=True, description="Extract decorators")


class ModelEntityExtractionOutput(BaseModel):
    """Output model for entity extraction."""

    success: bool = Field(..., description="Whether extraction succeeded")
    entities: list[ModelEntity] = Field(default_factory=list, description="Extracted entities")
    parse_errors: list[str] = Field(default_factory=list, description="Parse errors encountered")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extraction metadata")


class ModelEntityExtractionConfig(BaseModel):
    """Configuration for entity extraction."""

    supported_languages: list[str] = Field(default_factory=lambda: ["python"])
    max_content_size: int = Field(default=1_000_000, description="Max content size in bytes")
    extract_module_level_vars: bool = Field(default=True)
    extract_private_members: bool = Field(default=True)


class EntityExtractionCompute(NodeCompute):
    """Compute node for extracting code entities."""

    def __init__(
        self,
        container: Any | None = None,
        config: ModelEntityExtractionConfig | None = None,
    ) -> None:
        """Initialize the entity extraction compute node.

        Args:
            container: Optional ONEX container for dependency injection (not used in standalone mode)
            config: Optional configuration for the node
        """
        # Only initialize base class with proper container (has compute_cache_config)
        # In standalone/test mode, container is None, so we skip super().__init__
        if container is not None and hasattr(container, "compute_cache_config"):
            super().__init__(container)

        self.config = config or ModelEntityExtractionConfig()

    async def process(
        self, input_data: ModelEntityExtractionInput
    ) -> ModelEntityExtractionOutput:
        """Extract entities from source code.

        Args:
            input_data: Input containing source code and extraction options

        Returns:
            ModelEntityExtractionOutput with extracted entities
        """
        if input_data.language != "python":
            return ModelEntityExtractionOutput(
                success=False,
                parse_errors=[f"Unsupported language: {input_data.language}"],
                metadata={"language": input_data.language},
            )

        if len(input_data.content) > self.config.max_content_size:
            return ModelEntityExtractionOutput(
                success=False,
                parse_errors=["Content exceeds maximum size"],
                metadata={"content_size": len(input_data.content)},
            )

        try:
            tree = ast.parse(input_data.content)
            entities = self._extract_entities(
                tree=tree,
                file_path=input_data.file_path,
                extract_docstrings=input_data.extract_docstrings,
                extract_decorators=input_data.extract_decorators,
            )

            return ModelEntityExtractionOutput(
                success=True,
                entities=entities,
                metadata={
                    "file_path": input_data.file_path,
                    "entity_count": len(entities),
                    "language": input_data.language,
                },
            )

        except SyntaxError as e:
            return ModelEntityExtractionOutput(
                success=False,
                parse_errors=[f"Syntax error at line {e.lineno}: {e.msg}"],
                metadata={"file_path": input_data.file_path},
            )
        except Exception as e:
            return ModelEntityExtractionOutput(
                success=False,
                parse_errors=[f"Unexpected error: {e!s}"],
                metadata={"file_path": input_data.file_path},
            )

    def _extract_entities(
        self,
        tree: ast.AST,
        file_path: str,
        extract_docstrings: bool,
        extract_decorators: bool,
    ) -> list[ModelEntity]:
        """Extract all entities from AST.

        Args:
            tree: Parsed AST tree
            file_path: Path to source file
            extract_docstrings: Whether to extract docstrings
            extract_decorators: Whether to extract decorators

        Returns:
            List of extracted entities
        """
        entities: list[ModelEntity] = []

        # Extract module-level entities
        module_entity = self._create_module_entity(tree, file_path)
        entities.append(module_entity)

        for node in ast.walk(tree):
            # Extract functions
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                entity = self._extract_function(
                    node, file_path, extract_docstrings, extract_decorators
                )
                entities.append(entity)

            # Extract classes
            elif isinstance(node, ast.ClassDef):
                entity = self._extract_class(
                    node, file_path, extract_docstrings, extract_decorators
                )
                entities.append(entity)

            # Extract imports
            elif isinstance(node, ast.Import | ast.ImportFrom):
                import_entities = self._extract_imports(node, file_path)
                entities.extend(import_entities)

            # Extract module-level variables
            elif isinstance(node, ast.Assign) and self.config.extract_module_level_vars:
                # Only top-level assignments (not inside functions/classes)
                if self._is_module_level(node, tree):
                    var_entities = self._extract_variables(node, file_path)
                    entities.extend(var_entities)

        return entities

    def _create_module_entity(self, tree: ast.AST, file_path: str) -> ModelEntity:
        """Create entity for the module itself.

        Args:
            tree: AST tree
            file_path: Path to source file

        Returns:
            Module entity
        """
        # Extract module docstring
        docstring = ""
        if isinstance(tree, ast.Module):
            docstring = ast.get_docstring(tree) or ""

        return ModelEntity(
            entity_id=f"module_{uuid.uuid4().hex[:8]}",
            entity_type=EnumEntityType.MODULE,
            name=file_path.split("/")[-1].replace(".py", ""),
            metadata={
                "file_path": file_path,
                "docstring": docstring,
                "line_start": 1,
                "line_end": self._get_last_line(tree),
            },
        )

    def _extract_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        extract_docstrings: bool,
        extract_decorators: bool,
    ) -> ModelEntity:
        """Extract function entity.

        Args:
            node: Function AST node
            file_path: Path to source file
            extract_docstrings: Whether to extract docstrings
            extract_decorators: Whether to extract decorators

        Returns:
            Function entity
        """
        is_async = isinstance(node, ast.AsyncFunctionDef)
        entity_type = EnumEntityType.FUNCTION

        # Get function signature
        args = [arg.arg for arg in node.args.args]
        returns = ast.unparse(node.returns) if node.returns else None

        # Get docstring
        docstring = ast.get_docstring(node) if extract_docstrings else None

        # Get decorators
        decorators = (
            [ast.unparse(dec) for dec in node.decorator_list]
            if extract_decorators
            else []
        )

        # Determine if private
        is_private = node.name.startswith("_") and not node.name.startswith("__")
        is_dunder = node.name.startswith("__") and node.name.endswith("__")

        metadata = {
            "file_path": file_path,
            "line_start": node.lineno,
            "line_end": node.end_lineno or node.lineno,
            "is_async": is_async,
            "arguments": args,
            "is_private": is_private,
            "is_dunder": is_dunder,
        }

        if docstring:
            metadata["docstring"] = docstring
        if returns:
            metadata["returns"] = returns
        if decorators:
            metadata["decorators"] = decorators

        return ModelEntity(
            entity_id=f"func_{uuid.uuid4().hex[:8]}",
            entity_type=entity_type,
            name=node.name,
            metadata=metadata,
        )

    def _extract_class(
        self,
        node: ast.ClassDef,
        file_path: str,
        extract_docstrings: bool,
        extract_decorators: bool,
    ) -> ModelEntity:
        """Extract class entity.

        Args:
            node: Class AST node
            file_path: Path to source file
            extract_docstrings: Whether to extract docstrings
            extract_decorators: Whether to extract decorators

        Returns:
            Class entity
        """
        # Get base classes
        bases = [ast.unparse(base) for base in node.bases]

        # Get docstring
        docstring = ast.get_docstring(node) if extract_docstrings else None

        # Get decorators
        decorators = (
            [ast.unparse(dec) for dec in node.decorator_list]
            if extract_decorators
            else []
        )

        # Extract methods and attributes
        methods = []
        attributes = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.append(item.name)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attributes.append(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)

        # Determine if private
        is_private = node.name.startswith("_") and not node.name.startswith("__")

        metadata = {
            "file_path": file_path,
            "line_start": node.lineno,
            "line_end": node.end_lineno or node.lineno,
            "bases": bases,
            "methods": methods,
            "attributes": attributes,
            "is_private": is_private,
        }

        if docstring:
            metadata["docstring"] = docstring
        if decorators:
            metadata["decorators"] = decorators

        return ModelEntity(
            entity_id=f"class_{uuid.uuid4().hex[:8]}",
            entity_type=EnumEntityType.CLASS,
            name=node.name,
            metadata=metadata,
        )

    def _extract_imports(
        self, node: ast.Import | ast.ImportFrom, file_path: str
    ) -> list[ModelEntity]:
        """Extract import entities.

        Args:
            node: Import AST node
            file_path: Path to source file

        Returns:
            List of import entities
        """
        entities = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                entity = ModelEntity(
                    entity_id=f"import_{uuid.uuid4().hex[:8]}",
                    entity_type=EnumEntityType.DEPENDENCY,
                    name=alias.name,
                    metadata={
                        "file_path": file_path,
                        "line_number": node.lineno,
                        "import_type": "import",
                        "alias": alias.asname if alias.asname else None,
                        "module": alias.name,
                    },
                )
                entities.append(entity)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                entity = ModelEntity(
                    entity_id=f"import_{uuid.uuid4().hex[:8]}",
                    entity_type=EnumEntityType.DEPENDENCY,
                    name=f"{module}.{alias.name}" if module else alias.name,
                    metadata={
                        "file_path": file_path,
                        "line_number": node.lineno,
                        "import_type": "from_import",
                        "module": module,
                        "imported_name": alias.name,
                        "alias": alias.asname if alias.asname else None,
                        "level": node.level,  # For relative imports
                    },
                )
                entities.append(entity)

        return entities

    def _extract_variables(
        self, node: ast.Assign, file_path: str
    ) -> list[ModelEntity]:
        """Extract variable entities.

        Args:
            node: Assignment AST node
            file_path: Path to source file

        Returns:
            List of variable entities
        """
        entities = []

        for target in node.targets:
            if isinstance(target, ast.Name):
                # Determine if constant (all uppercase)
                is_constant = target.id.isupper()
                entity_type = (
                    EnumEntityType.CONSTANT if is_constant else EnumEntityType.VARIABLE
                )

                # Try to get value representation
                try:
                    value_repr = ast.unparse(node.value)
                except Exception:
                    value_repr = None

                metadata = {
                    "file_path": file_path,
                    "line_number": node.lineno,
                    "is_constant": is_constant,
                }

                if value_repr:
                    metadata["value"] = value_repr

                entity = ModelEntity(
                    entity_id=f"var_{uuid.uuid4().hex[:8]}",
                    entity_type=entity_type,
                    name=target.id,
                    metadata=metadata,
                )
                entities.append(entity)

        return entities

    def _is_module_level(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if a node is at module level.

        Args:
            node: AST node to check
            tree: Root AST tree

        Returns:
            True if node is at module level
        """
        # Simple heuristic: check if node is directly in tree.body
        if hasattr(tree, "body"):
            return node in tree.body
        return False

    def _get_last_line(self, tree: ast.AST) -> int:
        """Get the last line number in the AST.

        Args:
            tree: AST tree

        Returns:
            Last line number
        """
        last_line = 1
        for node in ast.walk(tree):
            if hasattr(node, "end_lineno") and node.end_lineno:
                last_line = max(last_line, node.end_lineno)
        return last_line
