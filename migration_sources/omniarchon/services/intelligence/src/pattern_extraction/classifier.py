"""
Pattern Classifier Module
==========================

Classifies extracted code patterns into categories and types.

This module identifies:
- Function patterns (async, decorators, error handlers, factories)
- Class patterns (Singleton, Factory, Repository, ONEX nodes)
- Design patterns (Observer, Strategy, Context managers)
- Architectural patterns (MVC, Repository, Service)
"""

import ast
from enum import Enum
from typing import Dict, List, Optional, Set

from pattern_extraction.ast_parser import ClassNode, FunctionNode


class PatternType(Enum):
    """Pattern type enumeration."""

    FUNCTION_PATTERN = "function_pattern"
    CLASS_PATTERN = "class_pattern"
    DESIGN_PATTERN = "design_pattern"
    ARCHITECTURAL_PATTERN = "architectural_pattern"


class PatternCategory(Enum):
    """Pattern category enumeration."""

    # Function categories
    ASYNC_OPERATION = "async_operation"
    ERROR_HANDLER = "error_handler"
    DECORATOR_PATTERN = "decorator_pattern"
    FACTORY_FUNCTION = "factory_function"
    CONTEXT_MANAGER = "context_manager"
    DATABASE_OPERATION = "database_operation"
    API_ENDPOINT = "api_endpoint"

    # Class categories
    SINGLETON = "singleton"
    FACTORY = "factory"
    REPOSITORY = "repository"
    SERVICE = "service"
    ONEX_NODE = "onex_node"
    DATA_MODEL = "data_model"
    OBSERVER = "observer"
    STRATEGY = "strategy"

    # Architectural categories
    MVC_CONTROLLER = "mvc_controller"
    MVC_MODEL = "mvc_model"
    MVC_VIEW = "mvc_view"

    # Generic
    UTILITY = "utility"
    UNKNOWN = "unknown"


class PatternClassifier:
    """
    Classifies code patterns into types and categories.

    Uses heuristics based on:
    - Naming conventions
    - Base classes
    - Decorators
    - Method signatures
    - Code structure
    """

    # ONEX node type suffixes
    ONEX_NODE_TYPES = {"Effect", "Compute", "Reducer", "Orchestrator"}

    # Common design pattern indicators
    SINGLETON_INDICATORS = {"__instance", "_instance", "instance", "get_instance"}
    FACTORY_INDICATORS = {"create", "build", "make", "factory"}
    REPOSITORY_INDICATORS = {"repository", "repo", "get", "find", "save", "delete"}
    SERVICE_INDICATORS = {"service", "manager", "handler", "processor"}

    # Function pattern indicators
    ASYNC_KEYWORDS = {"async", "await"}
    ERROR_HANDLER_INDICATORS = {"try", "except", "raise", "error", "exception"}
    DATABASE_INDICATORS = {
        "query",
        "execute",
        "transaction",
        "commit",
        "rollback",
        "session",
    }
    API_INDICATORS = {"get", "post", "put", "delete", "patch", "route", "endpoint"}

    def __init__(self):
        """Initialize pattern classifier."""
        pass

    def classify_function(self, func: FunctionNode) -> Dict[str, any]:
        """
        Classify a function pattern.

        Args:
            func: FunctionNode to classify

        Returns:
            Dictionary with:
                - pattern_type: PatternType enum value
                - category: PatternCategory enum value
                - tags: List of descriptive tags
                - confidence: Classification confidence (0.0-1.0)
        """
        tags = []
        categories = []

        # Check if async
        if func.is_async:
            tags.append("async")
            categories.append(PatternCategory.ASYNC_OPERATION)

        # Check decorators
        decorator_tags = self._analyze_decorators(func.decorators)
        tags.extend(decorator_tags)

        # Analyze function name
        name_lower = func.name.lower()

        # Check for factory pattern
        if any(indicator in name_lower for indicator in self.FACTORY_INDICATORS):
            categories.append(PatternCategory.FACTORY_FUNCTION)
            tags.append("factory")

        # Check for database operations
        if any(indicator in name_lower for indicator in self.DATABASE_INDICATORS):
            categories.append(PatternCategory.DATABASE_OPERATION)
            tags.append("database")

        # Check for API endpoints
        if any(indicator in name_lower for indicator in self.API_INDICATORS):
            categories.append(PatternCategory.API_ENDPOINT)
            tags.append("api")

        # Check for error handling in body
        if self._has_error_handling(func.body):
            categories.append(PatternCategory.ERROR_HANDLER)
            tags.append("error_handling")

        # Check for context manager
        if self._is_context_manager(func):
            categories.append(PatternCategory.CONTEXT_MANAGER)
            tags.append("context_manager")

        # Determine primary category
        primary_category = categories[0] if categories else PatternCategory.UTILITY

        # Calculate confidence based on number of indicators
        confidence = min(1.0, len(tags) * 0.25 + 0.3)

        return {
            "pattern_type": PatternType.FUNCTION_PATTERN,
            "category": primary_category,
            "tags": list(set(tags)),  # Remove duplicates
            "confidence": confidence,
        }

    def classify_class(self, cls: ClassNode) -> Dict[str, any]:
        """
        Classify a class pattern.

        Args:
            cls: ClassNode to classify

        Returns:
            Dictionary with:
                - pattern_type: PatternType enum value
                - category: PatternCategory enum value
                - tags: List of descriptive tags
                - confidence: Classification confidence (0.0-1.0)
        """
        tags = []
        categories = []

        # Check for ONEX node pattern
        if self._is_onex_node(cls):
            categories.append(PatternCategory.ONEX_NODE)
            tags.append("onex")
            tags.append(self._get_onex_node_type(cls.name))

        # Check for Singleton pattern
        if self._is_singleton(cls):
            categories.append(PatternCategory.SINGLETON)
            tags.append("singleton")

        # Check for Factory pattern
        if self._is_factory(cls):
            categories.append(PatternCategory.FACTORY)
            tags.append("factory")

        # Check for Repository pattern
        if self._is_repository(cls):
            categories.append(PatternCategory.REPOSITORY)
            tags.append("repository")

        # Check for Service pattern
        if self._is_service(cls):
            categories.append(PatternCategory.SERVICE)
            tags.append("service")

        # Check for Data Model
        if self._is_data_model(cls):
            categories.append(PatternCategory.DATA_MODEL)
            tags.append("model")

        # Check for Observer pattern
        if self._is_observer(cls):
            categories.append(PatternCategory.OBSERVER)
            tags.append("observer")

        # Determine primary category
        primary_category = categories[0] if categories else PatternCategory.UNKNOWN

        # Calculate confidence
        confidence = min(1.0, len(categories) * 0.3 + 0.4)

        return {
            "pattern_type": PatternType.CLASS_PATTERN,
            "category": primary_category,
            "tags": list(set(tags)),
            "confidence": confidence,
        }

    def _analyze_decorators(self, decorators: List[str]) -> List[str]:
        """
        Analyze decorators and return relevant tags.

        Args:
            decorators: List of decorator names

        Returns:
            List of tags based on decorators
        """
        tags = []

        for dec in decorators:
            dec_lower = dec.lower()

            if "property" in dec_lower:
                tags.append("property")
            elif "staticmethod" in dec_lower:
                tags.append("static")
            elif "classmethod" in dec_lower:
                tags.append("classmethod")
            elif "dataclass" in dec_lower:
                tags.append("dataclass")
            elif any(
                http in dec_lower for http in ["get", "post", "put", "delete", "patch"]
            ):
                tags.append("http_endpoint")
            elif "cache" in dec_lower:
                tags.append("cached")
            elif "retry" in dec_lower:
                tags.append("retry")

        return tags

    def _has_error_handling(self, body: List[ast.AST]) -> bool:
        """
        Check if function body contains error handling.

        Args:
            body: List of AST nodes in function body

        Returns:
            True if error handling found
        """
        for node in ast.walk(ast.Module(body=body)):
            if isinstance(node, (ast.Try, ast.Raise, ast.ExceptHandler)):
                return True
        return False

    def _is_context_manager(self, func: FunctionNode) -> bool:
        """
        Check if function is a context manager.

        Args:
            func: FunctionNode to check

        Returns:
            True if function is a context manager
        """
        # Check for @contextmanager decorator
        return any("contextmanager" in dec.lower() for dec in func.decorators)

    def _is_onex_node(self, cls: ClassNode) -> bool:
        """
        Check if class is an ONEX node.

        Args:
            cls: ClassNode to check

        Returns:
            True if class is an ONEX node
        """
        # Check if class name ends with ONEX node type
        return any(cls.name.endswith(node_type) for node_type in self.ONEX_NODE_TYPES)

    def _get_onex_node_type(self, class_name: str) -> str:
        """
        Get ONEX node type from class name.

        Args:
            class_name: Name of the class

        Returns:
            ONEX node type (effect, compute, reducer, orchestrator) or empty string
        """
        for node_type in self.ONEX_NODE_TYPES:
            if class_name.endswith(node_type):
                return node_type.lower()
        return ""

    def _is_singleton(self, cls: ClassNode) -> bool:
        """
        Check if class implements Singleton pattern.

        Args:
            cls: ClassNode to check

        Returns:
            True if Singleton pattern detected
        """
        # Check for singleton indicators in method names
        method_names = {m.lower() for m in cls.methods}
        return bool(self.SINGLETON_INDICATORS & method_names)

    def _is_factory(self, cls: ClassNode) -> bool:
        """
        Check if class implements Factory pattern.

        Args:
            cls: ClassNode to check

        Returns:
            True if Factory pattern detected
        """
        name_lower = cls.name.lower()
        method_names = {m.lower() for m in cls.methods}

        return "factory" in name_lower or bool(self.FACTORY_INDICATORS & method_names)

    def _is_repository(self, cls: ClassNode) -> bool:
        """
        Check if class implements Repository pattern.

        Args:
            cls: ClassNode to check

        Returns:
            True if Repository pattern detected
        """
        name_lower = cls.name.lower()
        method_names = {m.lower() for m in cls.methods}

        return "repository" in name_lower or bool(
            self.REPOSITORY_INDICATORS & method_names
        )

    def _is_service(self, cls: ClassNode) -> bool:
        """
        Check if class implements Service pattern.

        Args:
            cls: ClassNode to check

        Returns:
            True if Service pattern detected
        """
        name_lower = cls.name.lower()
        return any(indicator in name_lower for indicator in self.SERVICE_INDICATORS)

    def _is_data_model(self, cls: ClassNode) -> bool:
        """
        Check if class is a data model.

        Args:
            cls: ClassNode to check

        Returns:
            True if data model detected
        """
        # Check for dataclass decorator or BaseModel inheritance
        dataclass_indicators = ["dataclass", "basemodel", "model"]

        has_dataclass_decorator = any(
            indicator in dec.lower()
            for dec in cls.decorators
            for indicator in dataclass_indicators
        )

        has_model_base = any("model" in base.lower() for base in cls.bases)

        return has_dataclass_decorator or has_model_base

    def _is_observer(self, cls: ClassNode) -> bool:
        """
        Check if class implements Observer pattern.

        Args:
            cls: ClassNode to check

        Returns:
            True if Observer pattern detected
        """
        observer_methods = {"subscribe", "unsubscribe", "notify", "update"}
        method_names = {m.lower() for m in cls.methods}

        return bool(observer_methods & method_names)
