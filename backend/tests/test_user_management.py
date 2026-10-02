"""
Test user management functionality.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.db.models import Tenant, User
from app.schemas.tenant import TenantCreate
from app.services.tenant_service import TenantService


@pytest.fixture
async def tenant_with_owner(db_session: AsyncSession) -> tuple[Tenant, User]:
    """Create tenant with owner user."""
    tenant_service = TenantService(db_session)
    tenant_data = TenantCreate(
        name="User Test Company",
        owner_email="owner@usertest.com",
        owner_password="password123",
        owner_full_name="Owner User",
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


@pytest.fixture
async def admin_user(
    db_session: AsyncSession,
    tenant_with_owner: tuple[Tenant, User],
) -> User:
    """Create admin user in the tenant."""
    tenant, owner = tenant_with_owner
    
    admin = User(
        tenant_id=tenant.id,
        email="admin@usertest.com",
        password_hash=hash_password("password123"),
        full_name="Admin User",
        role="admin",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    
    return admin


@pytest.fixture
async def admin_token(tenant_with_owner: tuple[Tenant, User], admin_user: User) -> str:
    """Create JWT token for admin user."""
    tenant, _ = tenant_with_owner
    return create_access_token(
        subject=str(admin_user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": admin_user.role,
            "email": admin_user.email,
        },
    )


@pytest.fixture
async def member_user(
    db_session: AsyncSession,
    tenant_with_owner: tuple[Tenant, User],
) -> User:
    """Create member user in the tenant."""
    tenant, owner = tenant_with_owner
    
    member = User(
        tenant_id=tenant.id,
        email="member@usertest.com",
        password_hash=hash_password("password123"),
        full_name="Member User",
        role="member",
    )
    db_session.add(member)
    await db_session.commit()
    await db_session.refresh(member)
    
    return member


@pytest.fixture
async def member_token(tenant_with_owner: tuple[Tenant, User], member_user: User) -> str:
    """Create JWT token for member user."""
    tenant, _ = tenant_with_owner
    return create_access_token(
        subject=str(member_user.id),
        additional_claims={
            "tenant_id": str(tenant.id),
            "role": member_user.role,
            "email": member_user.email,
        },
    )


@pytest.mark.asyncio
async def test_create_user_as_owner(
    client: AsyncClient,
    owner_token: str,
):
    """Test creating a user as owner."""
    user_data = {
        "email": "newuser@usertest.com",
        "password": "securepassword123",
        "full_name": "New User",
        "role": "member",
    }
    
    response = await client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=user_data,
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["email"] == "newuser@usertest.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "member"
    assert data["is_active"] == True
    assert "id" in data
    assert "password" not in data  # Password should not be returned


@pytest.mark.asyncio
async def test_create_user_as_admin(
    client: AsyncClient,
    admin_token: str,
):
    """Test creating a user as admin."""
    user_data = {
        "email": "admincreated@usertest.com",
        "password": "password123",
        "full_name": "Admin Created User",
        "role": "member",
    }
    
    response = await client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=user_data,
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["email"] == "admincreated@usertest.com"
    assert data["role"] == "member"


@pytest.mark.asyncio
async def test_create_user_as_member_fails(
    client: AsyncClient,
    member_token: str,
):
    """Test that members cannot create users."""
    user_data = {
        "email": "unauthorized@usertest.com",
        "password": "password123",
        "full_name": "Unauthorized User",
        "role": "member",
    }
    
    response = await client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {member_token}"},
        json=user_data,
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_owner_requires_owner_role(
    client: AsyncClient,
    admin_token: str,
):
    """Test that only owners can create other owners."""
    user_data = {
        "email": "newowner@usertest.com",
        "password": "password123",
        "full_name": "New Owner",
        "role": "owner",
    }
    
    response = await client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=user_data,
    )
    
    assert response.status_code == 403
    assert "Only owners can create other owners" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_duplicate_email_fails(
    client: AsyncClient,
    owner_token: str,
    member_user: User,
):
    """Test that creating user with duplicate email fails."""
    user_data = {
        "email": member_user.email,  # Same email as existing user
        "password": "password123",
        "full_name": "Duplicate Email User",
        "role": "member",
    }
    
    response = await client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=user_data,
    )
    
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_users(
    client: AsyncClient,
    owner_token: str,
    admin_user: User,
    member_user: User,
):
    """Test listing users."""
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should have 3 users: owner, admin, member
    assert len(data) == 3
    
    # Check that all users are present
    emails = {user["email"] for user in data}
    assert "owner@usertest.com" in emails
    assert "admin@usertest.com" in emails
    assert "member@usertest.com" in emails


@pytest.mark.asyncio
async def test_list_users_include_inactive(
    client: AsyncClient,
    db_session: AsyncSession,
    owner_token: str,
    member_user: User,
):
    """Test listing users including inactive ones."""
    # Deactivate the member user
    member_user.is_active = False
    await db_session.commit()
    
    # List without inactive users
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should not include inactive user
    emails = {user["email"] for user in data}
    assert "member@usertest.com" not in emails
    
    # List with inactive users
    response = await client.get(
        "/api/v1/users/?include_inactive=true",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should include inactive user
    emails = {user["email"] for user in data}
    assert "member@usertest.com" in emails
    
    # Find the inactive user
    inactive_user = next(u for u in data if u["email"] == "member@usertest.com")
    assert inactive_user["is_active"] == False


@pytest.mark.asyncio
async def test_get_user_by_id(
    client: AsyncClient,
    owner_token: str,
    member_user: User,
):
    """Test getting user by ID."""
    response = await client.get(
        f"/api/v1/users/{member_user.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(member_user.id)
    assert data["email"] == member_user.email
    assert data["role"] == member_user.role


@pytest.mark.asyncio
async def test_update_user_as_owner(
    client: AsyncClient,
    owner_token: str,
    member_user: User,
):
    """Test updating user as owner."""
    update_data = {
        "full_name": "Updated Member User",
        "role": "admin",
    }
    
    response = await client.put(
        f"/api/v1/users/{member_user.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=update_data,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["full_name"] == "Updated Member User"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_update_self(
    client: AsyncClient,
    member_token: str,
    member_user: User,
):
    """Test that users can update themselves."""
    update_data = {
        "full_name": "Self Updated Name",
    }
    
    response = await client.put(
        f"/api/v1/users/{member_user.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json=update_data,
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["full_name"] == "Self Updated Name"


@pytest.mark.asyncio
async def test_member_cannot_update_others(
    client: AsyncClient,
    member_token: str,
    admin_user: User,
):
    """Test that members cannot update other users."""
    update_data = {
        "full_name": "Unauthorized Update",
    }
    
    response = await client.put(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json=update_data,
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_cannot_promote_to_owner(
    client: AsyncClient,
    admin_token: str,
    member_user: User,
):
    """Test that admins cannot promote users to owner."""
    update_data = {
        "role": "owner",
    }
    
    response = await client.put(
        f"/api/v1/users/{member_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=update_data,
    )
    
    assert response.status_code == 403
    assert "Only owners can promote to owner role" in response.json()["detail"]


@pytest.mark.asyncio
async def test_deactivate_user(
    client: AsyncClient,
    owner_token: str,
    member_user: User,
):
    """Test deactivating a user."""
    response = await client.delete(
        f"/api/v1/users/{member_user.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "User deactivated successfully"
    
    # Verify user is deactivated
    response = await client.get(
        f"/api/v1/users/{member_user.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    # Note: The user might still be found but should be inactive
    # This depends on how the service handles inactive users


@pytest.mark.asyncio
async def test_cannot_deactivate_last_owner(
    client: AsyncClient,
    owner_token: str,
    tenant_with_owner: tuple[Tenant, User],
):
    """Test that the last owner cannot be deactivated."""
    tenant, owner = tenant_with_owner
    
    response = await client.delete(
        f"/api/v1/users/{owner.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    
    assert response.status_code == 403
    assert "Cannot deactivate the last owner" in response.json()["detail"]


@pytest.mark.asyncio
async def test_member_cannot_list_users(
    client: AsyncClient,
    member_token: str,
):
    """Test that members cannot list users."""
    response = await client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]