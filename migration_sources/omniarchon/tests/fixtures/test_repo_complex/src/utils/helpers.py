"""
Utility helper functions.

Provides formatting and validation utilities.
"""


def format_output(user, product):
    """Format user and product information for display."""
    return f"User: {user.name} | Product: {product.name} (${product.price:.2f})"


def validate_input(value: str) -> bool:
    """Validate input string is not empty."""
    return bool(value and value.strip())


def calculate_total(price: float, quantity: int, tax_rate: float = 0.0) -> float:
    """Calculate total price including tax."""
    subtotal = price * quantity
    tax = subtotal * tax_rate
    return subtotal + tax
