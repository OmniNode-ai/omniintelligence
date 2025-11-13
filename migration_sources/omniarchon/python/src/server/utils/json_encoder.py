"""
Custom JSON encoder for handling datetime and other non-serializable objects.

This module provides a custom JSON encoder that can handle datetime objects
and other types that are not natively JSON serializable.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles datetime objects and other common types.

    This encoder ensures that datetime objects are properly converted to ISO format strings,
    preventing "Object of type datetime is not JSON serializable" errors.
    """

    def default(self, obj: Any) -> Any:
        """Convert non-serializable objects to JSON-serializable types."""
        if isinstance(obj, datetime | date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, UUID):
            return str(obj)
        elif hasattr(obj, "__dict__"):
            # Handle custom objects by converting to dict
            return obj.__dict__

        # Let the base class handle any other type
        return super().default(obj)


def json_dumps(obj: Any, **kwargs) -> str:
    """
    JSON dumps function using the custom encoder.

    Args:
        obj: Object to serialize
        **kwargs: Additional arguments for json.dumps

    Returns:
        JSON string representation of the object
    """
    # Ensure we use our custom encoder
    kwargs["cls"] = CustomJSONEncoder
    return json.dumps(obj, **kwargs)


def safe_json_response(data: Any) -> dict:
    """
    Safely convert data to JSON-serializable format.

    This function recursively processes the data to ensure all datetime
    objects and other non-serializable types are converted.

    Args:
        data: Data to convert

    Returns:
        JSON-serializable version of the data
    """
    if isinstance(data, datetime | date):
        return data.isoformat()
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, UUID):
        return str(data)
    elif isinstance(data, dict):
        return {key: safe_json_response(value) for key, value in data.items()}
    elif isinstance(data, list | tuple):
        return [safe_json_response(item) for item in data]
    elif hasattr(data, "__dict__"):
        return safe_json_response(data.__dict__)
    else:
        return data
