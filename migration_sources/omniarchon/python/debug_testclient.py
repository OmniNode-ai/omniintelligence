"""Debug script to check TestClient creation."""

from unittest.mock import MagicMock, Mock, patch

from starlette.testclient import TestClient

# Mock database client
mock_database_client = Mock()
mock_database_client.table.return_value = mock_database_client
mock_database_client.select.return_value = mock_database_client
mock_database_client.execute.return_value = Mock(data=[])
mock_database_client.auth = MagicMock()
mock_database_client.auth.get_user.return_value = None
mock_database_client.storage = MagicMock()

with patch(
    "src.server.services.client_manager.create_client",
    return_value=mock_database_client,
):
    with patch(
        "src.server.services.credential_service.create_client",
        return_value=mock_database_client,
    ):
        with patch(
            "src.server.services.client_manager.get_database_client",
            return_value=mock_database_client,
        ):
            with patch("supabase.create_client", return_value=mock_database_client):
                from src.server.main import app

                print("App created successfully!")
                print(f"Middleware list: {app.user_middleware}")

                print("\nCreating TestClient...")
                try:
                    test_client = TestClient(app)
                    print("TestClient created successfully!")

                    # Try making a request
                    print("\nTrying to make a request...")
                    response = test_client.get("/health")
                    print(f"Response: {response.status_code}")
                except Exception as e:
                    print(f"Error creating TestClient or making request: {e}")
                    import traceback

                    traceback.print_exc()
