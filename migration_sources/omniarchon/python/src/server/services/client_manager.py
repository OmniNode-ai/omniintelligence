"""
Client Manager Service

Manages database and API client connections.
"""

import os
import re

from server.config.logfire_config import search_logger
from supabase import Client, create_client


def get_database_client() -> Client:
    """
    Get a database client instance.

    Returns:
        Database client instance
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
        )

    try:
        # Let database handle connection pooling internally
        client = create_client(url, key)

        # Extract project ID from URL for logging purposes only
        match = re.match(r"https://([^.]+)\.supabase\.co", url)
        if match:
            project_id = match.group(1)
            search_logger.info(f"Database client initialized - project_id={project_id}")

        return client
    except Exception as e:
        search_logger.error(f"Failed to create database client: {e}")
        raise
