"""Debug script to check middleware configuration."""

import sys
from unittest.mock import Mock, patch

# Mock database client
mock_database_client = Mock()
mock_database_client.table.return_value = mock_database_client
mock_database_client.select.return_value = mock_database_client
mock_database_client.execute.return_value = Mock(data=[])

with patch(
    "src.server.utils.get_database_client",
    return_value=mock_database_client,
):
    with patch("supabase.create_client", return_value=mock_database_client):
        from src.server.main import app

        print("App created successfully!")
        print(f"Middleware list: {app.user_middleware}")
        print(f"Number of middleware: {len(app.user_middleware)}")
        print("\nMiddleware items:")
        for i, item in enumerate(app.user_middleware):
            print(
                f"{i}: {item} (type: {type(item)}, len: {len(item) if hasattr(item, '__len__') else 'N/A'})"
            )
            if hasattr(item, "__len__"):
                for j, subitem in enumerate(item):
                    print(f"  [{j}]: {subitem} (type: {type(subitem)})")
