"""
AST Parser Module
=================

Low-level Python AST parsing and node extraction.

This module provides functionality to:
- Parse Python source code into AST
- Extract function definitions (sync and async)
- Extract class definitions
- Extract decorators and context managers
- Extract docstrings and metadata
"""

import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FunctionNode:
    """
    Represents a function definition in the AST.

    Attributes:
        name: Function name
        line_start: Starting line number
        line_end: Ending line number
        is_async: Whether function is async
        decorators: List of decorator names
        args: Function arguments
        returns: Return type annotation (if any)
        docstring: Function docstring (if any)
        body: AST nodes in function body
    """

    name: str
    line_start: int
    line_end: int
    is_async: bool
    decorators: List[str]
    args: List[str]
    returns: Optional[str]
    docstring: Optional[str]
    body: List[ast.AST]


@dataclass
class ClassNode:
    """
    Represents a class definition in the AST.

    Attributes:
        name: Class name
        line_start: Starting line number
        line_end: Ending line number
        bases: Base classes
        decorators: List of decorator names
        methods: List of method names
        docstring: Class docstring (if any)
        body: AST nodes in class body
    """

    name: str
    line_start: int
    line_end: int
    bases: List[str]
    decorators: List[str]
    methods: List[str]
    docstring: Optional[str]
    body: List[ast.AST]


class ASTParser:
    """
    Python AST parser for extracting code patterns.

    Parses Python source code and extracts structured information about
    functions, classes, and other code constructs.
    """

    def __init__(self):
        """Initialize AST parser."""
        self.tree: Optional[ast.AST] = None
        self.source_lines: List[str] = []

    def parse_file(self, file_path: str) -> ast.AST:
        """
        Parse Python file into AST.

        Args:
            file_path: Path to Python source file

        Returns:
            AST tree of the file

        Raises:
            SyntaxError: If file contains invalid Python syntax
            FileNotFoundError: If file does not exist
        """
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
            self.source_lines = source_code.splitlines()

        self.tree = ast.parse(source_code, filename=file_path)
        return self.tree

    def parse_source(self, source_code: str) -> ast.AST:
        """
        Parse Python source code into AST.

        Args:
            source_code: Python source code string

        Returns:
            AST tree of the source code

        Raises:
            SyntaxError: If source contains invalid Python syntax
        """
        self.source_lines = source_code.splitlines()
        self.tree = ast.parse(source_code)
        return self.tree

    def extract_functions(self) -> List[FunctionNode]:
        """
        Extract all function definitions from parsed AST.

        Returns:
            List of FunctionNode objects

        Raises:
            ValueError: If no AST has been parsed yet
        """
        if self.tree is None:
            raise ValueError(
                "No AST parsed. Call parse_file() or parse_source() first."
            )

        functions = []

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_node = self._extract_function_node(node)
                functions.append(function_node)

        return functions

    def extract_classes(self) -> List[ClassNode]:
        """
        Extract all class definitions from parsed AST.

        Returns:
            List of ClassNode objects

        Raises:
            ValueError: If no AST has been parsed yet
        """
        if self.tree is None:
            raise ValueError(
                "No AST parsed. Call parse_file() or parse_source() first."
            )

        classes = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                class_node = self._extract_class_node(node)
                classes.append(class_node)

        return classes

    def get_source_segment(self, line_start: int, line_end: int) -> str:
        """
        Get source code segment by line range.

        Args:
            line_start: Starting line number (1-indexed)
            line_end: Ending line number (1-indexed)

        Returns:
            Source code segment as string
        """
        # Convert to 0-indexed
        start_idx = max(0, line_start - 1)
        end_idx = min(len(self.source_lines), line_end)

        return "\n".join(self.source_lines[start_idx:end_idx])

    def _extract_function_node(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> FunctionNode:
        """
        Extract FunctionNode from AST function definition.

        Args:
            node: AST FunctionDef or AsyncFunctionDef node

        Returns:
            FunctionNode with extracted metadata
        """
        # Extract decorators
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]

        # Extract arguments
        args = [arg.arg for arg in node.args.args]

        # Extract return type annotation
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Get line numbers
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        return FunctionNode(
            name=node.name,
            line_start=line_start,
            line_end=line_end,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
            args=args,
            returns=returns,
            docstring=docstring,
            body=node.body,
        )

    def _extract_class_node(self, node: ast.ClassDef) -> ClassNode:
        """
        Extract ClassNode from AST class definition.

        Args:
            node: AST ClassDef node

        Returns:
            ClassNode with extracted metadata
        """
        # Extract base classes
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))

        # Extract decorators
        decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]

        # Extract methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Get line numbers
        line_start = node.lineno
        line_end = node.end_lineno or line_start

        return ClassNode(
            name=node.name,
            line_start=line_start,
            line_end=line_end,
            bases=bases,
            decorators=decorators,
            methods=methods,
            docstring=docstring,
            body=node.body,
        )

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """
        Extract decorator name from AST node.

        Args:
            decorator: AST decorator node

        Returns:
            Decorator name as string
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return ast.unparse(decorator.func)
        elif isinstance(decorator, ast.Attribute):
            return ast.unparse(decorator)

        return ast.unparse(decorator)

    def find_context_managers(self) -> List[Tuple[int, str]]:
        """
        Find context manager usage (with statements).

        Returns:
            List of (line_number, context_manager_name) tuples
        """
        if self.tree is None:
            raise ValueError(
                "No AST parsed. Call parse_file() or parse_source() first."
            )

        context_managers = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    cm_name = ast.unparse(item.context_expr)
                    context_managers.append((node.lineno, cm_name))

        return context_managers

    def find_decorators(self, decorator_name: str) -> List[str]:
        """
        Find all functions/classes with a specific decorator.

        Args:
            decorator_name: Name of decorator to search for

        Returns:
            List of function/class names with the decorator
        """
        if self.tree is None:
            raise ValueError(
                "No AST parsed. Call parse_file() or parse_source() first."
            )

        results = []

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                decorators = [
                    self._get_decorator_name(dec) for dec in node.decorator_list
                ]
                if decorator_name in decorators:
                    results.append(node.name)

        return results
