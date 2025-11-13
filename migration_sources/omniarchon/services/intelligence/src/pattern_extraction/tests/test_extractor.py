"""
Unit Tests for Pattern Extraction Engine
==========================================

Comprehensive tests for AST-based pattern extraction.

Tests cover:
- AST parsing functionality
- Pattern classification
- Complexity metrics calculation
- End-to-end pattern extraction
"""

import sys
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pattern_extraction import (
    ASTParser,
    MetricsCalculator,
    PatternClassifier,
    PatternExtractor,
)
from pattern_extraction.classifier import PatternCategory, PatternType


class TestASTParser(unittest.TestCase):
    """Test cases for ASTParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = ASTParser()

    def test_parse_simple_function(self):
        """Test parsing a simple function."""
        source = """
def simple_function(x, y):
    '''Add two numbers.'''
    return x + y
"""
        self.parser.parse_source(source)
        functions = self.parser.extract_functions()

        self.assertEqual(len(functions), 1)
        func = functions[0]
        self.assertEqual(func.name, "simple_function")
        self.assertEqual(func.args, ["x", "y"])
        self.assertEqual(func.docstring, "Add two numbers.")
        self.assertFalse(func.is_async)

    def test_parse_async_function(self):
        """Test parsing an async function."""
        source = """
async def fetch_data(url):
    '''Fetch data from URL.'''
    return await http_client.get(url)
"""
        self.parser.parse_source(source)
        functions = self.parser.extract_functions()

        self.assertEqual(len(functions), 1)
        func = functions[0]
        self.assertEqual(func.name, "fetch_data")
        self.assertTrue(func.is_async)

    def test_parse_decorated_function(self):
        """Test parsing a function with decorators."""
        source = """
@property
@cache
def cached_property(self):
    return self._value
"""
        self.parser.parse_source(source)
        functions = self.parser.extract_functions()

        self.assertEqual(len(functions), 1)
        func = functions[0]
        self.assertEqual(func.name, "cached_property")
        self.assertIn("property", func.decorators)
        self.assertIn("cache", func.decorators)

    def test_parse_class(self):
        """Test parsing a class definition."""
        source = """
class MyRepository(BaseRepository):
    '''Repository for data access.'''

    def __init__(self):
        pass

    def get(self, id):
        pass

    def save(self, entity):
        pass
"""
        self.parser.parse_source(source)
        classes = self.parser.extract_classes()

        self.assertEqual(len(classes), 1)
        cls = classes[0]
        self.assertEqual(cls.name, "MyRepository")
        self.assertIn("BaseRepository", cls.bases)
        self.assertEqual(cls.docstring, "Repository for data access.")
        self.assertIn("__init__", cls.methods)
        self.assertIn("get", cls.methods)
        self.assertIn("save", cls.methods)

    def test_get_source_segment(self):
        """Test extracting source code segment."""
        source = """# line 1
# line 2
# line 3
# line 4
# line 5"""
        self.parser.parse_source(source)
        segment = self.parser.get_source_segment(2, 4)

        expected = "# line 2\n# line 3\n# line 4"
        self.assertEqual(segment, expected)


class TestPatternClassifier(unittest.TestCase):
    """Test cases for PatternClassifier."""

    def setUp(self):
        """Set up test fixtures."""
        self.classifier = PatternClassifier()
        self.parser = ASTParser()

    def test_classify_async_function(self):
        """Test classification of async function."""
        source = """
async def fetch_data(url):
    return await client.get(url)
"""
        self.parser.parse_source(source)
        functions = self.parser.extract_functions()
        func = functions[0]

        classification = self.classifier.classify_function(func)

        self.assertEqual(classification["pattern_type"], PatternType.FUNCTION_PATTERN)
        self.assertEqual(classification["category"], PatternCategory.ASYNC_OPERATION)
        self.assertIn("async", classification["tags"])

    def test_classify_database_function(self):
        """Test classification of database function."""
        source = """
async def execute_query(sql):
    '''Execute database query.'''
    async with transaction():
        return await session.execute(sql)
"""
        self.parser.parse_source(source)
        functions = self.parser.extract_functions()
        func = functions[0]

        classification = self.classifier.classify_function(func)

        self.assertEqual(classification["pattern_type"], PatternType.FUNCTION_PATTERN)
        self.assertIn("database", classification["tags"])

    def test_classify_factory_function(self):
        """Test classification of factory function."""
        source = """
def create_user(username, email):
    return User(username=username, email=email)
"""
        self.parser.parse_source(source)
        functions = self.parser.extract_functions()
        func = functions[0]

        classification = self.classifier.classify_function(func)

        self.assertEqual(classification["category"], PatternCategory.FACTORY_FUNCTION)
        self.assertIn("factory", classification["tags"])

    def test_classify_onex_node(self):
        """Test classification of ONEX node class."""
        source = """
class NodeDatabaseWriterEffect(NodeEffect):
    '''Effect node for database writes.'''

    async def execute_effect(self, contract):
        return await self._write_to_db(contract)
"""
        self.parser.parse_source(source)
        classes = self.parser.extract_classes()
        cls = classes[0]

        classification = self.classifier.classify_class(cls)

        self.assertEqual(classification["pattern_type"], PatternType.CLASS_PATTERN)
        self.assertEqual(classification["category"], PatternCategory.ONEX_NODE)
        self.assertIn("onex", classification["tags"])
        self.assertIn("effect", classification["tags"])

    def test_classify_repository(self):
        """Test classification of repository class."""
        source = """
class UserRepository:
    def get(self, id):
        pass

    def find(self, criteria):
        pass

    def save(self, entity):
        pass

    def delete(self, id):
        pass
"""
        self.parser.parse_source(source)
        classes = self.parser.extract_classes()
        cls = classes[0]

        classification = self.classifier.classify_class(cls)

        self.assertEqual(classification["category"], PatternCategory.REPOSITORY)
        self.assertIn("repository", classification["tags"])

    def test_classify_singleton(self):
        """Test classification of singleton class."""
        source = """
class ConfigurationManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
"""
        self.parser.parse_source(source)
        classes = self.parser.extract_classes()
        cls = classes[0]

        classification = self.classifier.classify_class(cls)

        self.assertEqual(classification["category"], PatternCategory.SINGLETON)
        self.assertIn("singleton", classification["tags"])


class TestMetricsCalculator(unittest.TestCase):
    """Test cases for MetricsCalculator."""

    def setUp(self):
        """Set up test fixtures."""
        try:
            self.calculator = MetricsCalculator()
        except ImportError:
            self.skipTest("radon library not installed")

    def test_simple_function_metrics(self):
        """Test metrics for simple function."""
        source = """
def add(x, y):
    return x + y
"""
        metrics = self.calculator.calculate_function_metrics(source, "add")

        self.assertEqual(metrics.cyclomatic_complexity, 1)
        self.assertEqual(metrics.complexity_grade, "A")

    def test_complex_function_metrics(self):
        """Test metrics for complex function."""
        source = """
def complex_function(x):
    if x > 0:
        if x > 10:
            return "high"
        else:
            return "medium"
    elif x < 0:
        if x < -10:
            return "very low"
        else:
            return "low"
    else:
        return "zero"
"""
        metrics = self.calculator.calculate_function_metrics(source, "complex_function")

        self.assertGreater(metrics.cyclomatic_complexity, 1)
        self.assertIsNotNone(metrics.maintainability_index)

    def test_class_metrics(self):
        """Test metrics for class."""
        source = """
class Calculator:
    def add(self, x, y):
        return x + y

    def subtract(self, x, y):
        return x - y

    def multiply(self, x, y):
        if x == 0 or y == 0:
            return 0
        return x * y
"""
        metrics = self.calculator.calculate_class_metrics(source, "Calculator")

        self.assertGreater(metrics.cyclomatic_complexity, 0)
        self.assertIsNotNone(metrics.maintainability_index)


class TestPatternExtractor(unittest.TestCase):
    """Test cases for PatternExtractor (end-to-end)."""

    def setUp(self):
        """Set up test fixtures."""
        try:
            self.extractor = PatternExtractor()
        except ImportError:
            self.skipTest("radon library not installed")

    def test_extract_from_simple_source(self):
        """Test extracting patterns from simple source."""
        source = """
def simple_function(x):
    '''Simple function.'''
    return x * 2

class SimpleClass:
    '''Simple class.'''
    def method(self):
        pass
"""
        patterns = self.extractor.extract_from_source(source)

        self.assertEqual(len(patterns), 3)  # 1 function + 1 class + 1 method

        # Find the function pattern
        func_patterns = [p for p in patterns if p["pattern_name"] == "simple_function"]
        self.assertEqual(len(func_patterns), 1)

        func_pattern = func_patterns[0]
        self.assertEqual(func_pattern["pattern_type"], "function_pattern")
        self.assertIn("implementation", func_pattern)
        self.assertIn("complexity", func_pattern)
        self.assertIn("tags", func_pattern)

    def test_extract_onex_pattern(self):
        """Test extracting ONEX node pattern."""
        source = """
class NodeDataProcessorCompute(NodeCompute):
    '''Compute node for data processing.'''

    async def execute_compute(self, contract):
        processed = await self._process(contract.data)
        return processed

    async def _process(self, data):
        return data.upper()
"""
        patterns = self.extractor.extract_from_source(source)

        # Find the class pattern
        class_patterns = [
            p for p in patterns if p["pattern_name"] == "NodeDataProcessorCompute"
        ]
        self.assertEqual(len(class_patterns), 1)

        cls_pattern = class_patterns[0]
        self.assertEqual(cls_pattern["category"], "onex_node")
        self.assertIn("onex", cls_pattern["tags"])
        self.assertIn("compute", cls_pattern["tags"])

    def test_pattern_summary(self):
        """Test generating pattern summary."""
        source = """
def func1():
    return 1

def func2():
    if True:
        return 2
    return 3

class MyClass:
    def method(self):
        pass
"""
        patterns = self.extractor.extract_from_source(source)
        summary = self.extractor.get_pattern_summary(patterns)

        self.assertGreater(summary["total_patterns"], 0)
        self.assertIn("by_type", summary)
        self.assertIn("by_category", summary)
        self.assertIn("avg_complexity", summary)

    def test_extract_repository_pattern(self):
        """Test extracting repository pattern."""
        source = """
class UserRepository:
    '''Repository for user data access.'''

    def get(self, user_id):
        return db.query(User).filter_by(id=user_id).first()

    def find_by_email(self, email):
        return db.query(User).filter_by(email=email).first()

    def save(self, user):
        db.session.add(user)
        db.session.commit()

    def delete(self, user_id):
        user = self.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
"""
        patterns = self.extractor.extract_from_source(source)

        # Find the repository class
        repo_patterns = [p for p in patterns if p["pattern_name"] == "UserRepository"]
        self.assertEqual(len(repo_patterns), 1)

        repo = repo_patterns[0]
        self.assertEqual(repo["category"], "repository")
        self.assertIn("repository", repo["tags"])
        self.assertIn("get", repo["methods"])
        self.assertIn("save", repo["methods"])


class TestComplexPatterns(unittest.TestCase):
    """Test cases for complex real-world patterns."""

    def setUp(self):
        """Set up test fixtures."""
        try:
            self.extractor = PatternExtractor()
        except ImportError:
            self.skipTest("radon library not installed")

    def test_async_database_transaction_pattern(self):
        """Test extracting async database transaction pattern."""
        source = """
async def execute_with_retry(operation, max_retries=3):
    '''Execute database operation with automatic retry on failure.'''
    for attempt in range(max_retries):
        try:
            async with transaction():
                result = await operation()
                await commit()
                return result
        except DatabaseError as e:
            if attempt == max_retries - 1:
                raise
            await rollback()
            await asyncio.sleep(2 ** attempt)
"""
        patterns = self.extractor.extract_from_source(source)

        func_patterns = [
            p for p in patterns if p["pattern_name"] == "execute_with_retry"
        ]
        self.assertEqual(len(func_patterns), 1)

        pattern = func_patterns[0]
        self.assertIn("async", pattern["tags"])
        self.assertIn("error_handling", pattern["tags"])
        self.assertGreater(pattern["complexity"], 1)

    def test_factory_with_registry_pattern(self):
        """Test extracting factory with registry pattern."""
        source = """
class NodeFactory:
    '''Factory for creating ONEX nodes with type registry.'''

    _registry = {}

    @classmethod
    def register(cls, node_type, node_class):
        cls._registry[node_type] = node_class

    @classmethod
    def create(cls, node_type, *args, **kwargs):
        if node_type not in cls._registry:
            raise ValueError(f"Unknown node type: {node_type}")
        node_class = cls._registry[node_type]
        return node_class(*args, **kwargs)
"""
        patterns = self.extractor.extract_from_source(source)

        factory_patterns = [p for p in patterns if p["pattern_name"] == "NodeFactory"]
        self.assertEqual(len(factory_patterns), 1)

        pattern = factory_patterns[0]
        self.assertEqual(pattern["category"], "factory")
        self.assertIn("factory", pattern["tags"])


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestASTParser))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternClassifier))
    suite.addTests(loader.loadTestsFromTestCase(TestMetricsCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestComplexPatterns))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()

    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
