"""
Main application entry point.

Imports models and utilities from the project structure.
"""

from src.models.user import User
from src.models.product import Product
from src.utils.helpers import format_output, validate_input


def main():
    """Main application function."""
    user = User(name="Test User", email="test@example.com")
    product = Product(name="Test Product", price=99.99)

    if validate_input(user.name):
        output = format_output(user, product)
        return output

    return None


if __name__ == "__main__":
    result = main()
    print(result)
