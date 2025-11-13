"""
API package for Archon - modular FastAPI endpoints

This package organizes the API into logical modules:
- settings_api: Settings and credentials management
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
- tests_api: Test execution and streaming with real-time output
"""

from server.api_routes.agent_chat_api import router as agent_chat_router
from server.api_routes.internal_api import router as internal_router
from server.api_routes.knowledge_api import router as knowledge_router

# REMOVED: MCP API router - MCP support has been removed
# from server.api_routes.mcp_api import router as mcp_router
from server.api_routes.projects_api import router as projects_router
from server.api_routes.settings_api import router as settings_router
from server.api_routes.tests_api import router as tests_router

__all__ = [
    "settings_router",
    # "mcp_router",  # REMOVED
    "knowledge_router",
    "projects_router",
    "tests_router",
    "agent_chat_router",
    "internal_router",
]
