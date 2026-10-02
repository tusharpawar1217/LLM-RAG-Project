"""
Critical tests to ensure no cross-tenant data leakage.
These tests MUST pass to prove multi-tenant isolation.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core.security import create_access_token, generate_api_key
from app.db.models import APIKey, Document, Tenant, User
from app.services.tenant_service import TenantService
from app.schemas.tenant import TenantCreate


@pytest.fixture
async def tenant_a(db_session: AsyncSession) -> tuple[Tenant, User]:
    """Create tenant A with owner."""
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="Tenant A",
        owner_email="owner-a@example.com",
        owner_password="password123",
        owner_full_name="Owner A",
    )
    return await tenant_service.create_tenant(tenant_data)


@pytest.fixture
async def tenant_b(db_session: AsyncSession) -> tuple[Tenant, User]:
    """Create tenant B with owner."""
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="Tenant B",
        owner_email="owner-b@example.com",
        owner_password="password123",
        owner_full_name="Owner B",
    )
    return await tenant_service.create_tenant(tenant_data)


@pytest.fixture
async def tenant_a_token(tenant_a: tuple[Tenant, User]) -> str:
    """Create JWT token for tenant A owner."""
    tenant, user = tenant_a
    return create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )


@pytest.fixture
async def tenant_b_token(tenant_b: tuple[Tenant, User]) -> str:
    """Create JWT token for tenant B owner."""
    tenant, user = tenant_b
    return create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )


@pytest.fixture
async def tenant_a_api_key(db_session: AsyncSession, tenant_a: tuple[Tenant, User]) -> str:
    """Create API key for tenant A."""
    tenant, user = tenant_a
    
    full_key, key_hash = generate_api_key()
    api_key = APIKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        key_prefix=full_key[:8],
        name="Test Key",
        scopes=["query", "ingest"],
        created_by=user.id,
    )
    
    db_session.add(api_key)
    await db_session.commit()
    
    return full_key


@pytest.fixture
async def tenant_b_api_key(db_session: AsyncSession, tenant_b: tuple[Tenant, User]) -> str:
    """Create API key for tenant B."""
    tenant, user = tenant_b
    
    full_key, key_hash = generate_api_key()
    api_key = APIKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        key_prefix=full_key[:8],
        name="Test Key",
        scopes=["query", "ingest"],
        created_by=user.id,
    )
    
    db_session.add(api_key)
    await db_session.commit()
    
    return full_key


@pytest.mark.asyncio
async def test_jwt_token_tenant_isolation(
    client: AsyncClient,
    tenant_a_token: str,
    tenant_b_token: str,
):
    """Test that JWT tokens only access their own tenant data."""
    
    # Tenant A should see their own tenant info
    response = await client.get(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
    )
    assert response.status_code == 200
    tenant_a_data = response.json()
    
    # Tenant B should see their own tenant info
    response = await client.get(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
    )
    assert response.status_code == 200
    tenant_b_data = response.json()
    
    # They should be different tenants
    assert tenant_a_data["id"] != tenant_b_data["id"]
    assert tenant_a_data["name"] != tenant_b_data["name"]


@pytest.mark.asyncio
async def test_api_key_tenant_isolation(
    client: AsyncClient,
    tenant_a_api_key: str,
    tenant_b_api_key: str,
    tenant_a: tuple[Tenant, User],
    tenant_b: tuple[Tenant, User],
):
    """Test that API keys only access their own tenant data."""
    
    # This test will be expanded when we add document endpoints
    # For now, we test the authentication itself
    
    tenant_a_obj, _ = tenant_a
    tenant_b_obj, _ = tenant_b
    
    # Each API key should authenticate to the correct tenant
    # (We'll verify this through the tenant ID in response headers)
    
    # Note: We need endpoints that actually use API keys to test this properly
    # This will be completed in Module 3 when we add document endpoints


@pytest.mark.asyncio
async def test_user_access_isolation(
    client: AsyncClient,
    tenant_a_token: str,
    tenant_b_token: str,
):
    """Test that users can only see users in their own tenant."""
    
    # Tenant A should only see their users
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
    )
    assert response.status_code == 200
    tenant_a_users = response.json()
    
    # Tenant B should only see their users
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
    )
    assert response.status_code == 200
    tenant_b_users = response.json()
    
    # Should have exactly one user each (the owner)
    assert len(tenant_a_users) == 1
    assert len(tenant_b_users) == 1
    
    # Users should be different
    assert tenant_a_users[0]["id"] != tenant_b_users[0]["id"]
    assert tenant_a_users[0]["email"] != tenant_b_users[0]["email"]


@pytest.mark.asyncio
async def test_api_key_access_isolation(
    client: AsyncClient,
    tenant_a_token: str,
    tenant_b_token: str,
):
    """Test that API keys are isolated per tenant."""
    
    # Create API key for tenant A
    response = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
        json={
            "name": "Test Key A",
            "scopes": ["query"],
        },
    )
    assert response.status_code == 201
    api_key_a = response.json()
    
    # Create API key for tenant B
    response = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
        json={
            "name": "Test Key B",
            "scopes": ["query"],
        },
    )
    assert response.status_code == 201
    api_key_b = response.json()
    
    # Tenant A should only see their API key
    response = await client.get(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
    )
    assert response.status_code == 200
    tenant_a_keys = response.json()
    assert len(tenant_a_keys) == 1
    assert tenant_a_keys[0]["id"] == api_key_a["id"]
    
    # Tenant B should only see their API key
    response = await client.get(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
    )
    assert response.status_code == 200
    tenant_b_keys = response.json()
    assert len(tenant_b_keys) == 1
    assert tenant_b_keys[0]["id"] == api_key_b["id"]


@pytest.mark.asyncio
async def test_cross_tenant_resource_access_forbidden(
    client: AsyncClient,
    tenant_a_token: str,
    tenant_b_token: str,
):
    """Test that cross-tenant resource access is forbidden."""
    
    # Create API key for tenant A
    response = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
        json={"name": "Test Key", "scopes": ["query"]},
    )
    assert response.status_code == 201
    api_key_a = response.json()
    
    # Tenant B should NOT be able to access tenant A's API key
    response = await client.get(
        f"/api/v1/api-keys/{api_key_a['id']}",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
    )
    assert response.status_code == 404  # Should not find the resource
    
    # Tenant B should NOT be able to update tenant A's API key
    response = await client.put(
        f"/api/v1/api-keys/{api_key_a['id']}",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
        json={"name": "Hacked Key"},
    )
    assert response.status_code == 404  # Should not find the resource


@pytest.mark.asyncio
async def test_database_level_tenant_isolation(
    db_session: AsyncSession,
    tenant_a: tuple[Tenant, User],
    tenant_b: tuple[Tenant, User],
):
    """Test tenant isolation at the database level."""
    
    tenant_a_obj, user_a = tenant_a
    tenant_b_obj, user_b = tenant_b
    
    # Create some test documents for each tenant
    doc_a = Document(
        tenant_id=tenant_a_obj.id,
        filename="doc_a.pdf",
        source_type="upload",
        content_hash="hash_a",
        status="completed",
        file_size_bytes=1000,
    )
    doc_b = Document(
        tenant_id=tenant_b_obj.id,
        filename="doc_b.pdf",
        source_type="upload",
        content_hash="hash_b",
        status="completed",
        file_size_bytes=2000,
    )
    
    db_session.add(doc_a)
    db_session.add(doc_b)
    await db_session.commit()
    
    # Query documents with tenant isolation
    from sqlalchemy import select
    
    # Tenant A should only see their document
    tenant_a_docs = await db_session.execute(
        select(Document).where(Document.tenant_id == tenant_a_obj.id)
    )
    tenant_a_doc_list = list(tenant_a_docs.scalars().all())
    assert len(tenant_a_doc_list) == 1
    assert tenant_a_doc_list[0].filename == "doc_a.pdf"
    
    # Tenant B should only see their document  
    tenant_b_docs = await db_session.execute(
        select(Document).where(Document.tenant_id == tenant_b_obj.id)
    )
    tenant_b_doc_list = list(tenant_b_docs.scalars().all())
    assert len(tenant_b_doc_list) == 1
    assert tenant_b_doc_list[0].filename == "doc_b.pdf"
    
    # Cross-tenant query should return empty
    cross_tenant_docs = await db_session.execute(
        select(Document).where(Document.tenant_id == tenant_a_obj.id, Document.id == doc_b.id)
    )
    assert cross_tenant_docs.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_tenant_stats_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_a: tuple[Tenant, User],
    tenant_b: tuple[Tenant, User],
    tenant_a_token: str,
    tenant_b_token: str,
):
    """Test that tenant statistics don't leak across tenants."""
    
    tenant_a_obj, _ = tenant_a
    tenant_b_obj, _ = tenant_b
    
    # Create different numbers of documents for each tenant
    doc_a1 = Document(
        tenant_id=tenant_a_obj.id,
        filename="doc1_a.pdf",
        source_type="upload",
        content_hash="hash1_a",
        status="completed",
    )
    doc_a2 = Document(
        tenant_id=tenant_a_obj.id,
        filename="doc2_a.pdf",
        source_type="upload", 
        content_hash="hash2_a",
        status="completed",
    )
    doc_b1 = Document(
        tenant_id=tenant_b_obj.id,
        filename="doc1_b.pdf",
        source_type="upload",
        content_hash="hash1_b",
        status="completed",
    )
    
    db_session.add_all([doc_a1, doc_a2, doc_b1])
    await db_session.commit()
    
    # Get stats for tenant A
    response = await client.get(
        "/api/v1/tenants/stats",
        headers={"Authorization": f"Bearer {tenant_a_token}"},
    )
    assert response.status_code == 200
    stats_a = response.json()
    
    # Get stats for tenant B
    response = await client.get(
        "/api/v1/tenants/stats",
        headers={"Authorization": f"Bearer {tenant_b_token}"},
    )
    assert response.status_code == 200
    stats_b = response.json()
    
    # Tenant A should have 2 documents
    assert stats_a["total_documents"] == 2
    
    # Tenant B should have 1 document
    assert stats_b["total_documents"] == 1
    
    # Stats should be completely isolated
    assert stats_a != stats_b