"""
API Key service for managing API key operations.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthorizationError, ResourceNotFoundError
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_key_prefix
from app.db.models import APIKey, Tenant, User
from app.schemas.api_key import APIKeyCreate, APIKeyUpdate

logger = get_logger(__name__)


class APIKeyService:
    """Service for API key management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_api_key(
        self, 
        tenant: Tenant, 
        key_data: APIKeyCreate, 
        created_by: User
    ) -> tuple[APIKey, str]:
        """
        Create a new API key for a tenant.
        
        Args:
            tenant: Tenant to create API key for
            key_data: API key creation data
            created_by: User creating the API key
            
        Returns:
            Tuple of (api_key_record, full_key_string)
            
        Raises:
            AuthorizationError: If creator lacks permission
        """
        # Check permissions
        if created_by.role not in ("owner", "admin") and "admin" in key_data.scopes:
            raise AuthorizationError("Insufficient permissions to create admin-scoped API keys")
        
        # Generate API key
        full_key, key_hash = generate_api_key()
        key_prefix = get_key_prefix(full_key)
        
        # Create API key record
        api_key = APIKey(
            tenant_id=tenant.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=key_data.name,
            scopes=key_data.scopes,
            expires_at=key_data.expires_at,
            created_by=created_by.id,
        )
        
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        
        logger.info(
            "API key created",
            api_key_id=str(api_key.id),
            tenant_id=str(tenant.id),
            scopes=key_data.scopes,
            created_by=str(created_by.id),
        )
        
        return api_key, full_key
    
    async def get_api_key_by_id(self, tenant: Tenant, api_key_id: UUID) -> APIKey:
        """
        Get API key by ID within tenant.
        
        Args:
            tenant: Tenant context
            api_key_id: API key ID
            
        Returns:
            API key
            
        Raises:
            ResourceNotFoundError: If API key not found
        """
        stmt = select(APIKey).where(
            APIKey.id == api_key_id,
            APIKey.tenant_id == tenant.id,  # Enforce tenant isolation
        )
        result = await self.db.execute(stmt)
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ResourceNotFoundError("API Key", str(api_key_id))
        
        return api_key
    
    async def list_api_keys(self, tenant: Tenant, requesting_user: User) -> list[APIKey]:
        """
        List all API keys for a tenant.
        
        Args:
            tenant: Tenant
            requesting_user: User making the request
            
        Returns:
            List of API keys
            
        Raises:
            AuthorizationError: If user lacks permission
        """
        # Check permissions
        if requesting_user.role not in ("owner", "admin"):
            raise AuthorizationError("Insufficient permissions to list API keys")
        
        stmt = (
            select(APIKey)
            .where(APIKey.tenant_id == tenant.id)
            .order_by(APIKey.created_at.desc())
        )
        result = await self.db.execute(stmt)
        
        return list(result.scalars().all())
    
    async def update_api_key(
        self, 
        api_key: APIKey, 
        update_data: APIKeyUpdate, 
        updated_by: User
    ) -> APIKey:
        """
        Update API key information.
        
        Args:
            api_key: API key to update
            update_data: Update data
            updated_by: User performing the update
            
        Returns:
            Updated API key
            
        Raises:
            AuthorizationError: If updater lacks permission
        """
        # Check permissions
        if updated_by.role not in ("owner", "admin"):
            raise AuthorizationError("Insufficient permissions to update API keys")
        
        # Update fields
        if update_data.name is not None:
            api_key.name = update_data.name
        
        # Handle revocation/activation
        if update_data.is_active is not None:
            if not update_data.is_active:
                # Revoke by setting expiration to now
                api_key.expires_at = datetime.utcnow()
            else:
                # Reactivate by removing expiration (if it was set for revocation)
                if api_key.expires_at and api_key.expires_at <= datetime.utcnow():
                    api_key.expires_at = None
        
        await self.db.commit()
        await self.db.refresh(api_key)
        
        action = "revoked" if (update_data.is_active is False) else "updated"
        logger.info(
            f"API key {action}",
            api_key_id=str(api_key.id),
            updated_by=str(updated_by.id),
        )
        
        return api_key
    
    async def delete_api_key(self, api_key: APIKey, deleted_by: User) -> None:
        """
        Delete an API key.
        
        Args:
            api_key: API key to delete
            deleted_by: User performing the deletion
            
        Raises:
            AuthorizationError: If deleter lacks permission
        """
        # Check permissions
        if deleted_by.role not in ("owner", "admin"):
            raise AuthorizationError("Insufficient permissions to delete API keys")
        
        await self.db.delete(api_key)
        await self.db.commit()
        
        logger.info(
            "API key deleted",
            api_key_id=str(api_key.id),
            deleted_by=str(deleted_by.id),
        )
    
    async def is_api_key_valid(self, api_key: APIKey) -> bool:
        """
        Check if API key is valid (not expired).
        
        Args:
            api_key: API key to check
            
        Returns:
            True if valid, False otherwise
        """
        if api_key.expires_at is None:
            return True
        
        return api_key.expires_at > datetime.utcnow()
    
    async def get_api_key_scopes(self, api_key: APIKey) -> list[str]:
        """
        Get scopes for an API key.
        
        Args:
            api_key: API key
            
        Returns:
            List of scopes
        """
        return api_key.scopes or ["query"]  # Default to query scope