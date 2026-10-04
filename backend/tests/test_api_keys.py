"""
Test API key functionality.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core.security import create_access_token, generate_api_key
from app.db.models import APIKey, Tenant, User
from app.schemas.tenant import TenantCreate
from app.services.auth_service import AuthService
from app.services.tenant_service import TenantService


@pytest.fixture
async def tenant_with_admin(db_session: AsyncSession) -> tuple[Tenant, User]:
    """Create tenant with admin user."""
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="API Test Company",
        owner_email="admin@apitest.com",
        owner_password="password123",
        owner_full_name="Admin User",
    )
    return await tenant_service.create_tenant(tenant_data)


@pytest.fixture
async def admin_token(tenant_with_admin: tuple[Tenant, User]) -> str:
    """Create JWT token for admin user."""
    tenant, user = tenant_with_admin
    return create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )


@pytest.fixture
async def test_api_key(
    db_session: AsyncSession,
    tenant_with_admin: tuple[Tenant, User],
) -> tuple[str, APIKey]:
    """Create a test API key."""
    tenant, user = tenant_with_admin
    
    full_key, key_hash = generate_api_key()
    api_key = APIKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        key_prefix=full_key[:8],
        name="Test API Key",
        scopes=["query", "ingest"],
        created_by=user.id,
    )
    
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    
    return full_key, api_key


@pytest.mark.asyncio
async def test_create_api_key(
    client: AsyncClient,
    admin_token: str,
):
    """Test creating an API key."""
    key_data = {
        "name": "My API Key",
        "scopes": ["query", "ingest"],
    }
    
    response = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=key_data,
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "My API Key"
    assert set(data["scopes"]) == {"query", "ingest"}
    assert "key" in data  # Full key should be present
    assert data["key"].startswith("ask_")  # Should have correct prefix
    assert "key_prefix" in data
    assert "id" in data
    assert data["created_by"] is not None


@pytest.mark.asyncio
async def test_create_api_key_admin_scope_requires_admin(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_admin: tuple[Tenant, User],
):
    """Test that creating admin-scoped API key requires admin role."""
    tenant, owner = tenant_with_admin
    
    # Create a regular member user
    from app.core.security import hash_password
    member = User(
        tenant_id=tenant.id,
        email="member@apitest.com",
        password_hash=hash_password("password123"),
        full_name="Member User",
        role="member",
    )
    db_session.add(member)
    await db_session.commit()
    
    # Create token for member
    member_token = create_access_token(
        subject=str(member.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": "member",
            "email": member.email,
        },
    )
    
    key_data = {
        "name": "Admin Key",
        "scopes": ["admin"],
    }
    
    response = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {member_token}"},
        json=key_data,
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_api_keys(
    client: AsyncClient,
    admin_token: str,
    test_api_key: tuple[str, APIKey],
):
    """Test listing API keys."""
    full_key, api_key = test_api_key
    
    response = await client.get(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    key_info = data[0]
    
    assert key_info["id"] == str(api_key.id)
    assert key_info["name"] == "Test API Key"
    assert set(key_info["scopes"]) == {"query", "ingest"}
    assert key_info["key_prefix"] == full_key[:8]
    assert "key" not in key_info  # Full key should NOT be in list response


@pytest.mark.asyncio
async def test_get_api_key_by_id(
    client: AsyncClient,
    admin_token: str,
    test_api_key: tuple[str, APIKey],
):
    """Test getting API key by ID."""
    full_key, api_key = test_api_key
    
    response = await client.get(
        f"/api/v1/api-keys/{api_key.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(api_key.id)
    assert data["name"] == "Test API Key"
    assert set(data["scopes"]) == {"query", "ingest"}


@pytest.mark.asyncio
async def test_update_api_key_name(
    client: AsyncClient,
    admin_token: str,
    test_api_key: tuple[str, APIKey],
):
    """Test updating API key name."""
    full_key, api_key = test_api_key
    
    update_data = {"name": "Updated API Key"}
    
    response = await client.put(
        f"/api/v1/api-keys/{api_key.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=update_data,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "Updated API Key"
    assert data["id"] == str(api_key.id)


@pytest.mark.asyncio
async def test_revoke_api_key(
    client: AsyncClient,
    admin_token: str,
    test_api_key: tuple[str, APIKey],
):
    """Test revoking an API key."""
    full_key, api_key = test_api_key
    
    update_data = {"is_active": False}
    
    response = await client.put(
        f"/api/v1/api-keys/{api_key.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=update_data,
    )
    
    assert response.status_code == 200
    
    # Verify the key is revoked by checking expiration
    response = await client.get(
        f"/api/v1/api-keys/{api_key.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["expires_at"] is not None  # Should have expiration set


@pytest.mark.asyncio
async def test_delete_api_key(
    client: AsyncClient,
    admin_token: str,
    test_api_key: tuple[str, APIKey],
):
    """Test deleting an API key."""
    full_key, api_key = test_api_key
    
    response = await client.delete(
        f"/api/v1/api-keys/{api_key.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "API key deleted successfully"
    
    # Verify the key is deleted
    response = await client.get(
        f"/api/v1/api-keys/{api_key.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_key_authentication(
    client: AsyncClient,
    db_session: AsyncSession,
    test_api_key: tuple[str, APIKey],
):
    """Test API key authentication."""
    full_key, api_key = test_api_key
    
    # Test authentication with the API key
    auth_service = AuthService(db_session)
    tenant, key_record = await auth_service.authenticate_api_key(full_key)
    
    assert tenant.id == api_key.tenant_id
    assert key_record.id == api_key.id
    assert key_record.last_used_at is not None  # Should update last used


@pytest.mark.asyncio
async def test_invalid_api_key_authentication(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test authentication with invalid API key."""
    auth_service = AuthService(db_session)
    
    with pytest.raises(Exception):  # Should raise AuthenticationError
        await auth_service.authenticate_api_key("ask_invalid_key_123456789")


@pytest.mark.asyncio
async def test_member_cannot_list_api_keys(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_admin: tuple[Tenant, User],
):
    """Test that members cannot list API keys."""
    tenant, owner = tenant_with_admin
    
    # Create a member user
    from app.core.security import hash_password
    member = User(
        tenant_id=tenant.id,
        email="member@apitest.com",
        password_hash=hash_password("password123"),
        full_name="Member User",
        role="member",
    )
    db_session.add(member)
    await db_session.commit()
    
    # Create token for member
    member_token = create_access_token(
        subject=str(member.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": "member",
            "email": member.email,
        },
    )
    
    response = await client.get(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_key_scopes_validation(
    client: AsyncClient,
    admin_token: str,
):
    """Test API key scope validation."""
    # Test invalid scope
    key_data = {
        "name": "Invalid Scope Key",
        "scopes": ["invalid_scope"],
    }
    
    response = await client.post(
        "/api/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=key_data,
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_expired_api_key(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_admin: tuple[Tenant, User],
):
    """Test expired API key authentication."""
    tenant, user = tenant_with_admin
    
    # Create expired API key
    from datetime import datetime, timedelta
    full_key, key_hash = generate_api_key()
    expired_key = APIKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        key_prefix=full_key[:8],
        name="Expired Key",
        scopes=["query"],
        expires_at=datetime.utcnow() - timedelta(days=1),  # Expired yesterday
        created_by=user.id,
    )
    
    db_session.add(expired_key)
    await db_session.commit()
    
    # Try to authenticate with expired key
    auth_service = AuthService(db_session)
    
    with pytest.raises(Exception):  # Should raise AuthenticationError
        await auth_service.authenticate_api_key(full_key)

