"""
User management endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminOrOwner, CurrentTenant, CurrentUser
from app.core.errors import AskDocsException
from app.db.base import get_db
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Create a new user in the tenant.
    
    Args:
        user_data: User creation data
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Created user information
    """
    try:
        user_service = UserService(db)
        user = await user_service.create_user(tenant, user_data, current_user)
        
        return UserResponse.model_validate(user)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """
    List all users in the tenant.
    
    Args:
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        include_inactive: Include inactive users
        db: Database session
        
    Returns:
        List of users
    """
    try:
        user_service = UserService(db)
        users = await user_service.list_tenant_users(
            tenant, current_user, include_inactive=include_inactive
        )
        
        return [UserResponse.model_validate(user) for user in users]
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Get user by ID.
    
    Args:
        user_id: User ID
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        User information
    """
    try:
        user_service = UserService(db)
        user = await user_service.get_user_by_id(tenant, user_id)
        
        return UserResponse.model_validate(user)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdate,
    tenant: CurrentTenant,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update user information.
    
    Users can update themselves, or admins/owners can update others.
    
    Args:
        user_id: User ID
        update_data: Update data
        tenant: Current tenant
        current_user: Current user
        db: Database session
        
    Returns:
        Updated user information
    """
    try:
        user_service = UserService(db)
        
        # Get the user to update
        user = await user_service.get_user_by_id(tenant, user_id)
        
        # Update the user
        updated_user = await user_service.update_user(user, update_data, current_user)
        
        return UserResponse.model_validate(updated_user)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: UUID,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Deactivate a user.
    
    Args:
        user_id: User ID
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Success message
    """
    try:
        user_service = UserService(db)
        
        # Get the user to deactivate
        user = await user_service.get_user_by_id(tenant, user_id)
        
        # Deactivate the user
        await user_service.deactivate_user(user, current_user)
        
        return {"message": "User deactivated successfully"}
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

