"""
Test authentication functionality.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.db.models import Tenant, User
from app.schemas.tenant import TenantCreate
from app.services.tenant_service import TenantService


@pytest.fixture
async def test_user_data():
    """Test user credentials."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    }


@pytest.fixture
async def test_tenant_with_user(db_session: AsyncSession, test_user_data) -> tuple[Tenant, User]:
    """Create a test tenant with user."""
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="Test Company",
        owner_email=test_user_data["email"],
        owner_password=test_user_data["password"],
        owner_full_name=test_user_data["full_name"],
    )
    return await tenant_service.create_tenant(tenant_data)


@pytest.mark.asyncio
async def test_tenant_registration(client: AsyncClient):
    """Test tenant registration endpoint."""
    tenant_data = {
        "name": "New Company",
        "owner_email": "owner@newcompany.com",
        "owner_password": "securepassword123",
        "owner_full_name": "Company Owner",
        "widget_bot_name": "Custom Bot",
        "widget_primary_color": "#ff5733",
    }
    
    response = await client.post("/api/v1/tenants/", json=tenant_data)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "New Company"
    assert data["widget_bot_name"] == "Custom Bot" 
    assert data["widget_primary_color"] == "#ff5733"
    assert data["subscription_status"] == "trial"
    assert data["subscription_tier"] == "starter"
    assert "slug" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_user_login_success(
    client: AsyncClient,
    test_tenant_with_user: tuple[Tenant, User],
    test_user_data: dict,
):
    """Test successful user login."""
    tenant, user = test_tenant_with_user
    
    login_data = {
        "email": test_user_data["email"],
        "password": test_user_data["password"],
    }
    
    response = await client.post("/api/v1/auth/login", json=login_data)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert "user" in data
    
    # Check user data
    user_data = data["user"]
    assert user_data["email"] == test_user_data["email"]
    assert user_data["full_name"] == test_user_data["full_name"]
    assert user_data["role"] == "owner"
    assert user_data["is_active"] == True


@pytest.mark.asyncio
async def test_user_login_invalid_email(client: AsyncClient):
    """Test login with invalid email."""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "password123",
    }
    
    response = await client.post("/api/v1/auth/login", json=login_data)
    
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_invalid_password(
    client: AsyncClient,
    test_tenant_with_user: tuple[Tenant, User],
    test_user_data: dict,
):
    """Test login with invalid password."""
    tenant, user = test_tenant_with_user
    
    login_data = {
        "email": test_user_data["email"],
        "password": "wrongpassword",
    }
    
    response = await client.post("/api/v1/auth/login", json=login_data)
    
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user_info(
    client: AsyncClient,
    test_tenant_with_user: tuple[Tenant, User],
):
    """Test getting current user info with JWT token."""
    tenant, user = test_tenant_with_user
    
    # Create access token
    token = create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )
    
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "user" in data
    assert "tenant" in data
    
    # Check user info
    user_info = data["user"]
    assert user_info["email"] == user.email
    assert user_info["role"] == "owner"
    
    # Check tenant info
    tenant_info = data["tenant"]
    assert tenant_info["name"] == tenant.name
    assert tenant_info["subscription_status"] == "trial"


@pytest.mark.asyncio
async def test_change_password_success(
    client: AsyncClient,
    test_tenant_with_user: tuple[Tenant, User],
    test_user_data: dict,
):
    """Test successful password change."""
    tenant, user = test_tenant_with_user
    
    # Create access token
    token = create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )
    
    password_data = {
        "current_password": test_user_data["password"],
        "new_password": "newpassword123",
    }
    
    response = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json=password_data,
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"
    
    # Try logging in with new password
    login_data = {
        "email": test_user_data["email"],
        "password": "newpassword123",
    }
    
    login_response = await client.post("/api/v1/auth/login", json=login_data)
    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current_password(
    client: AsyncClient,
    test_tenant_with_user: tuple[Tenant, User],
):
    """Test password change with wrong current password."""
    tenant, user = test_tenant_with_user
    
    # Create access token
    token = create_access_token(
        subject=str(user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
        },
    )
    
    password_data = {
        "current_password": "wrongpassword",
        "new_password": "newpassword123",
    }
    
    response = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json=password_data,
    )
    
    assert response.status_code == 401
    assert "Current password is incorrect" in response.json()["detail"]


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await client.get("/api/v1/auth/me")
    
    assert response.status_code == 401
    assert "Missing authentication token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_protected_endpoint_with_invalid_token(client: AsyncClient):
    """Test accessing protected endpoint with invalid token."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    
    assert response.status_code == 401
    assert "Invalid authentication token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tenant_registration_duplicate_email(
    client: AsyncClient,
    test_tenant_with_user: tuple[Tenant, User],
    test_user_data: dict,
):
    """Test tenant registration with duplicate email."""
    tenant_data = {
        "name": "Another Company",
        "owner_email": test_user_data["email"],  # Same email as existing user
        "owner_password": "password123",
        "owner_full_name": "Another Owner",
    }
    
    response = await client.post("/api/v1/tenants/", json=tenant_data)
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_with_inactive_subscription(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test login with inactive subscription."""
    # Create tenant with inactive subscription
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="Inactive Company",
        owner_email="inactive@example.com",
        owner_password="password123",
        owner_full_name="Inactive Owner",
    )
    tenant, user = await tenant_service.create_tenant(tenant_data)
    
    # Set subscription to inactive
    tenant.subscription_status = "canceled"
    await db_session.commit()
    
    login_data = {
        "email": "inactive@example.com",
        "password": "password123",
    }
    
    response = await client.post("/api/v1/auth/login", json=login_data)
    
    assert response.status_code == 401
    assert "subscription is inactive" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint."""
    response = await client.post("/api/v1/auth/logout")
    
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

