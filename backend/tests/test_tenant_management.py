"""
Test tenant management functionality.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models import Document, Tenant, User
from app.schemas.tenant import TenantCreate
from app.services.tenant_service import TenantService


@pytest.fixture
async def tenant_with_owner(db_session: AsyncSession) -> tuple[Tenant, User]:
    """Create tenant with owner user."""
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="Tenant Test Company",
        owner_email="owner@tenanttest.com",
        owner_password="password123",
        owner_full_name="Tenant Owner",
    )
    return await tenant_service.create_tenant(tenant_data)


@pytest.fixture
async def owner_token(tenant_with_owner: tuple[Tenant, User]) -> str:
    """Create JWT token for owner user."""
    tenant, user = tenant_with_owner
    return create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )


@pytest.mark.asyncio
async def test_get_current_tenant(
    client: AsyncClient,
    owner_token: str,
    tenant_with_owner: tuple[Tenant, User],
):
    """Test getting current tenant information."""
    tenant, _ = tenant_with_owner
    
    response = await client.get(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(tenant.id)
    assert data["name"] == "Tenant Test Company"
    assert data["subscription_status"] == "trial"
    assert data["subscription_tier"] == "starter"
    assert data["max_documents"] == 50
    assert data["max_messages_per_month"] == 1000


@pytest.mark.asyncio
async def test_update_tenant_branding(
    client: AsyncClient,
    owner_token: str,
):
    """Test updating tenant branding."""
    update_data = {
        "name": "Updated Company Name",
        "widget_primary_color": "#ff5733",
        "widget_bot_name": "Custom Support Bot",
        "widget_welcome_message": "Welcome to our support chat!",
    }
    
    response = await client.put(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=update_data,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "Updated Company Name"
    assert data["widget_primary_color"] == "#ff5733"
    assert data["widget_bot_name"] == "Custom Support Bot"
    assert data["widget_welcome_message"] == "Welcome to our support chat!"


@pytest.mark.asyncio
async def test_update_tenant_handoff_settings(
    client: AsyncClient,
    owner_token: str,
):
    """Test updating tenant handoff settings."""
    update_data = {
        "handoff_email": "support@company.com",
        "handoff_webhook_url": "https://company.com/webhook/handoff",
    }
    
    response = await client.put(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=update_data,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["handoff_email"] == "support@company.com"
    assert data["handoff_webhook_url"] == "https://company.com/webhook/handoff"


@pytest.mark.asyncio
async def test_get_tenant_stats_empty(
    client: AsyncClient,
    owner_token: str,
):
    """Test getting tenant stats with no data."""
    response = await client.get(
        "/api/v1/tenants/stats",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_documents"] == 0
    assert data["total_chunks"] == 0
    assert data["total_conversations"] == 0
    assert data["messages_this_month"] == 0
    assert data["storage_usage_mb"] == 0.0
    assert data["documents_limit"] == 50
    assert data["messages_limit"] == 1000
    assert data["documents_used_percent"] == 0.0
    assert data["messages_used_percent"] == 0.0


@pytest.mark.asyncio
async def test_get_tenant_stats_with_documents(
    client: AsyncClient,
    db_session: AsyncSession,
    owner_token: str,
    tenant_with_owner: tuple[Tenant, User],
):
    """Test getting tenant stats with documents."""
    tenant, _ = tenant_with_owner
    
    # Create test documents
    doc1 = Document(
        tenant_id=tenant.id,
        filename="doc1.pdf",
        source_type="upload",
        content_hash="hash1",
        status="completed",
        file_size_bytes=1024 * 1024,  # 1MB
    )
    doc2 = Document(
        tenant_id=tenant.id,
        filename="doc2.pdf",
        source_type="upload",
        content_hash="hash2",
        status="completed",
        file_size_bytes=2 * 1024 * 1024,  # 2MB
    )
    
    db_session.add_all([doc1, doc2])
    await db_session.commit()
    
    response = await client.get(
        "/api/v1/tenants/stats",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_documents"] == 2
    assert data["storage_usage_mb"] == 3.0  # 1MB + 2MB
    assert data["documents_used_percent"] == 4.0  # 2/50 * 100


@pytest.mark.asyncio
async def test_get_tenant_limits(
    client: AsyncClient,
    owner_token: str,
):
    """Test getting tenant limits."""
    response = await client.get(
        "/api/v1/tenants/limits",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["can_add_document"] == True
    assert data["can_send_message"] == True
    assert data["documents_remaining"] == 50
    assert data["messages_remaining"] == 1000
    assert data["current_documents"] == 0
    assert data["current_messages_this_month"] == 0
    assert data["max_documents"] == 50
    assert data["max_messages_per_month"] == 1000


@pytest.mark.asyncio
async def test_get_tenant_users_from_tenant_endpoint(
    client: AsyncClient,
    owner_token: str,
):
    """Test getting tenant users via tenant endpoint."""
    response = await client.get(
        "/api/v1/tenants/users",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have one user (the owner)
    assert len(data) == 1
    assert data[0]["email"] == "owner@tenanttest.com"
    assert data[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_tenant_slug_uniqueness(
    client: AsyncClient,
):
    """Test that tenant slugs are unique."""
    # Create first tenant
    tenant_data_1 = {
        "name": "Same Name Company",
        "owner_email": "owner1@example.com",
        "owner_password": "password123",
        "owner_full_name": "Owner One",
    }
    
    response1 = await client.post("/api/v1/tenants/", json=tenant_data_1)
    assert response1.status_code == 201
    slug1 = response1.json()["slug"]
    
    # Create second tenant with same name
    tenant_data_2 = {
        "name": "Same Name Company",
        "owner_email": "owner2@example.com",
        "owner_password": "password123",
        "owner_full_name": "Owner Two",
    }
    
    response2 = await client.post("/api/v1/tenants/", json=tenant_data_2)
    assert response2.status_code == 201
    slug2 = response2.json()["slug"]
    
    # Slugs should be different despite same name
    assert slug1 != slug2
    assert slug1.startswith("same-name-company")
    assert slug2.startswith("same-name-company")


@pytest.mark.asyncio
async def test_invalid_widget_color(
    client: AsyncClient,
    owner_token: str,
):
    """Test updating tenant with invalid widget color."""
    update_data = {
        "widget_primary_color": "invalid-color",
    }
    
    response = await client.put(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=update_data,
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_member_cannot_access_tenant_stats(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_owner: tuple[Tenant, User],
):
    """Test that members cannot access tenant stats."""
    tenant, owner = tenant_with_owner
    
    # Create a member user
    from app.core.security import hash_password
    member = User(
        tenant_id=tenant.id,
        email="member@tenanttest.com",
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
        "/api/v1/tenants/stats",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_member_cannot_update_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_owner: tuple[Tenant, User],
):
    """Test that members cannot update tenant settings."""
    tenant, owner = tenant_with_owner
    
    # Create a member user
    from app.core.security import hash_password
    member = User(
        tenant_id=tenant.id,
        email="member@tenanttest.com",
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
    
    update_data = {"name": "Unauthorized Update"}
    
    response = await client.put(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {member_token}"},
        json=update_data,
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_tenant_owner_only(
    client: AsyncClient,
    owner_token: str,
):
    """Test that only owners can delete tenants."""
    response = await client.delete(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Tenant deleted successfully"


@pytest.mark.asyncio
async def test_admin_cannot_delete_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_with_owner: tuple[Tenant, User],
):
    """Test that admins cannot delete tenants."""
    tenant, owner = tenant_with_owner
    
    # Create admin user
    from app.core.security import hash_password
    admin = User(
        tenant_id=tenant.id,
        email="admin@tenanttest.com",
        password_hash=hash_password("password123"),
        full_name="Admin User",
        role="admin",
    )
    db_session.add(admin)
    await db_session.commit()
    
    # Create token for admin
    admin_token = create_access_token(
        subject=str(admin.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": "admin",
            "email": admin.email,
        },
    )
    
    response = await client.delete(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]