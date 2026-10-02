"""
API key management endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminOrOwner, CurrentTenant
from app.core.errors import AskDocsException
from app.db.base import get_db
from app.schemas.api_key import APIKeyCreate, APIKeyCreateResponse, APIKeyResponse, APIKeyUpdate
from app.services.api_key_service import APIKeyService

router = APIRouter()


@router.post("/", response_model=APIKeyCreateResponse, status_code=201)
async def create_api_key(
    key_data: APIKeyCreate,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreateResponse:
    """
    Create a new API key.
    
    Args:
        key_data: API key creation data
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Created API key with full key (shown only once)
    """
    try:
        api_key_service = APIKeyService(db)
        api_key, full_key = await api_key_service.create_api_key(
            tenant, key_data, current_user
        )
        
        # Create response with full key
        response_data = APIKeyResponse.model_validate(api_key).model_dump()
        response_data["key"] = full_key
        
        return APIKeyCreateResponse(**response_data)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/", response_model=list[APIKeyResponse])
async def list_api_keys(
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
    """
    List all API keys for the tenant.
    
    Args:
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        List of API keys (without full key values)
    """
    try:
        api_key_service = APIKeyService(db)
        api_keys = await api_key_service.list_api_keys(tenant, current_user)
        
        return [APIKeyResponse.model_validate(key) for key in api_keys]
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: UUID,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """
    Get API key by ID.
    
    Args:
        api_key_id: API key ID
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        API key information
    """
    try:
        api_key_service = APIKeyService(db)
        api_key = await api_key_service.get_api_key_by_id(tenant, api_key_id)
        
        return APIKeyResponse.model_validate(api_key)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/{api_key_id}", response_model=APIKeyResponse)
async def update_api_key(
    api_key_id: UUID,
    update_data: APIKeyUpdate,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """
    Update API key (name or revoke/activate).
    
    Args:
        api_key_id: API key ID
        update_data: Update data
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Updated API key information
    """
    try:
        api_key_service = APIKeyService(db)
        
        # Get the API key
        api_key = await api_key_service.get_api_key_by_id(tenant, api_key_id)
        
        # Update the API key
        updated_key = await api_key_service.update_api_key(api_key, update_data, current_user)
        
        return APIKeyResponse.model_validate(updated_key)
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: UUID,
    tenant: CurrentTenant,
    current_user: AdminOrOwner,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete an API key.
    
    Args:
        api_key_id: API key ID
        tenant: Current tenant
        current_user: Current user (admin or owner only)
        db: Database session
        
    Returns:
        Success message
    """
    try:
        api_key_service = APIKeyService(db)
        
        # Get the API key
        api_key = await api_key_service.get_api_key_by_id(tenant, api_key_id)
        
        # Delete the API key
        await api_key_service.delete_api_key(api_key, current_user)
        
        return {"message": "API key deleted successfully"}
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)