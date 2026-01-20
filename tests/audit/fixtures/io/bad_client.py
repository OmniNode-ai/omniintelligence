"""A node with forbidden client import violations.

This fixture demonstrates forbidden patterns:
- confluent_kafka imports
- qdrant_client imports
- neo4j imports
- asyncpg imports
- httpx imports
- aiofiles imports

NOTE: This file intentionally contains violations for testing.
"""

# ruff: noqa: F401

# VIOLATION: confluent_kafka import
from confluent_kafka import Consumer, Producer

# VIOLATION: qdrant_client import
from qdrant_client import QdrantClient

# VIOLATION: neo4j import
from neo4j import GraphDatabase

# VIOLATION: asyncpg import
import asyncpg

# VIOLATION: httpx import
import httpx

# VIOLATION: httpx submodule import
from httpx import AsyncClient

# VIOLATION: aiofiles import
import aiofiles


async def connect_to_kafka() -> Producer:
    """BAD: Creates Kafka producer directly in node."""
    return Producer({"bootstrap.servers": "localhost:9092"})


async def connect_to_qdrant() -> QdrantClient:
    """BAD: Creates Qdrant client directly in node."""
    return QdrantClient(host="localhost", port=6333)


async def connect_to_neo4j():
    """BAD: Creates Neo4j driver directly in node."""
    return GraphDatabase.driver("bolt://localhost:7687")


async def connect_to_postgres():
    """BAD: Creates asyncpg connection directly in node."""
    return await asyncpg.connect("postgresql://localhost/db")


async def make_http_request(url: str) -> str:
    """BAD: Makes HTTP request directly in node."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text


async def read_file_async(path: str) -> str:
    """BAD: Reads file asynchronously in node."""
    async with aiofiles.open(path) as f:
        return await f.read()


# =========================================================================
# Aliased Import Violations
# =========================================================================

# VIOLATION: httpx import with alias
import httpx as http_client

# VIOLATION: confluent_kafka with alias
import confluent_kafka as ck


async def make_aliased_http_request(url: str) -> str:
    """BAD: Makes HTTP request using aliased import."""
    # VIOLATION: Using aliased httpx import
    http_client.get(url)  # Should be detected
    return "response"


def create_aliased_kafka_producer() -> None:
    """BAD: Creates Kafka producer using aliased import."""
    # VIOLATION: Using aliased confluent_kafka import
    ck.Producer({"bootstrap.servers": "localhost:9092"})  # Should be detected
