"""
Tests for main application module.

Imports and tests main functionality.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import main
from src.models.user import User
from src.models.product import Product


def test_main_function():
    """Test main function execution."""
    result = main()
    assert result is not None
    assert "Test User" in result
    assert "Test Product" in result


def test_user_creation():
    """Test user creation."""
    user = User(name="John Doe", email="john@example.com")
    assert user.name == "John Doe"
    assert user.email == "john@example.com"
    assert user.active is True


def test_product_creation():
    """Test product creation."""
    product = Product(name="Widget", price=49.99)
    assert product.name == "Widget"
    assert product.price == 49.99
    assert product.available is True


if __name__ == "__main__":
    test_main_function()
    test_user_creation()
    test_product_creation()
    print("All tests passed!")
