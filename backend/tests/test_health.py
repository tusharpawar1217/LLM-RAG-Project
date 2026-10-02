"""
Test health check endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test basic health check endpoint."""
    response = await client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["app"] == "AskDocs"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_database_health_check(client: AsyncClient):
    """Test database health check endpoint."""
    response = await client.get("/api/v1/health/db")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["app"] == "AskDocs"


@pytest.mark.asyncio
async def test_root_health_check(client: AsyncClient):
    """Test root health check endpoint."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["app"] == "AskDocs"