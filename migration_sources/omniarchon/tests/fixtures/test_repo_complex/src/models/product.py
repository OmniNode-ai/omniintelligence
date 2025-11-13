"""
Product model definition.

Defines the Product entity with pricing logic.
"""


class Product:
    """Product entity representing a purchasable item."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price
        self.available = True

    def apply_discount(self, percentage: float):
        """Apply a discount percentage to the product price."""
        if 0 <= percentage <= 100:
            self.price = self.price * (1 - percentage / 100)

    def __repr__(self):
        return f"Product(name={self.name}, price={self.price:.2f}, available={self.available})"
