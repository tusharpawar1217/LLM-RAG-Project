"""
Tenant management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminOrOwner, CurrentTenant, CurrentUser, OwnerOnly
from app.core.errors import AskDocsException
from app.db.base import get_db
from app.schemas.tenant import TenantCreate, TenantLimits, TenantResponse, TenantStats, TenantUpdate
from app.services.tenant_service import TenantService
from app.services.user_service import UserService

router = APIRouter()


@router.post("/", response_model=TenantResponse, status_code=201)
async def create_tenant(
    tenant_data: TenantCreate,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    Create a new tenant with owner user.
    
    This endpoint is public for tenant registration.
    
    Args:
        tenant_data: Tenant creation data
        db: Database session
        
    Returns:
        Created tenant information
    """
    try:
        tenant_service = TenantService(db)
        tenant, owner = await tenant_service.create_tenant(tenant_data)
        
        return TenantResponse.model_validate(tenant)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    tenant: CurrentTenant,
) -> TenantResponse:
    """
    Get current tenant information.
    
    Args:
        tenant: Current tenant from authentication
        
    Returns:
        Tenant information
    """
    return TenantResponse.model_validate(tenant)


@router.put("/current", response_model=TenantResponse)
async def update_current_tenant(
    update_data: TenantUpdate,
    tenant: CurrentTenant,
    user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    Update current tenant information.
    
    Args:
        update_data: Tenant update data
        tenant: Current tenant
        user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Updated tenant information
    """
    try:
        tenant_service = TenantService(db)
        updated_tenant = await tenant_service.update_tenant(tenant, update_data)
        
        return TenantResponse.model_validate(updated_tenant)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/stats", response_model=TenantStats)
async def get_tenant_stats(
    tenant: CurrentTenant,
    user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> TenantStats:
    """
    Get tenant usage statistics.
    
    Args:
        tenant: Current tenant
        user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Tenant usage statistics
    """
    try:
        tenant_service = TenantService(db)
        stats = await tenant_service.get_tenant_stats(tenant)
        
        return stats
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/limits", response_model=TenantLimits)
async def get_tenant_limits(
    tenant: CurrentTenant,
    user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> TenantLimits:
    """
    Get tenant limits and current usage.
    
    Args:
        tenant: Current tenant
        user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Tenant limits information
    """
    try:
        tenant_service = TenantService(db)
        limits = await tenant_service.check_tenant_limits(tenant)
        
        return limits
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/users")
async def get_tenant_users(
    tenant: CurrentTenant,
    user: AdminOrOwner,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all users in the tenant.
    
    Args:
        tenant: Current tenant
        user: Current user (admin or owner only)
        include_inactive: Include inactive users
        db: Database session
        
    Returns:
        List of tenant users
    """
    try:
        user_service = UserService(db)
        users = await user_service.list_tenant_users(
            tenant, user, include_inactive=include_inactive
        )
        
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at,
                "updated_at": u.updated_at,
            }
            for u in users
        ]
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/current")
async def delete_tenant(
    tenant: CurrentTenant,
    user: OwnerOnly,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete the current tenant and all associated data.
    
    WARNING: This is destructive and irreversible.
    
    Args:
        tenant: Current tenant
        user: Current user (owner only)
        db: Database session
        
    Returns:
        Success message
    """
    try:
        tenant_service = TenantService(db)
        await tenant_service.delete_tenant(tenant)
        
        return {"message": "Tenant deleted successfully"}
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

