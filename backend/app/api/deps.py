"""
Dependency injection for FastAPI endpoints.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AskDocsException, AuthenticationError, AuthorizationError
from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.base import get_db
from app.db.models import APIKey, Tenant, User
from app.services.auth_service import AuthService
from app.services.tenant_service import TenantService

logger = get_logger(__name__)

# Security scheme for JWT tokens and API keys
security = HTTPBearer(auto_error=False)


async def get_current_user_from_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token
        db: Database session
        
    Returns:
        Authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    try:
        auth_service = AuthService(db)
        
        # Decode JWT token
        payload = decode_token(credentials.credentials)
        
        # Validate token type
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        # Get user ID from token
        user_id = UUID(payload["sub"])
        user = await auth_service.get_user_by_id(user_id)
        
        # Store in request state for middleware
        request.state.user_id = user.id
        request.state.tenant_id = user.tenant_id
        request.state.tenant = user.tenant
        
        return user
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error("Token authentication failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid authentication token")


async def get_current_tenant_from_user(
    user: User = Depends(get_current_user_from_token),
) -> Tenant:
    """
    Get current tenant from authenticated user.
    
    Args:
        user: Current authenticated user
        
    Returns:
        User's tenant
    """
    return user.tenant


async def get_tenant_from_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> tuple[Tenant, APIKey]:
    """
    Get tenant from API key authentication.
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer token (API key)
        db: Database session
        
    Returns:
        Tuple of (tenant, api_key)
        
    Raises:
        HTTPException: If API key authentication fails
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    try:
        auth_service = AuthService(db)
        tenant, api_key = await auth_service.authenticate_api_key(credentials.credentials)
        
        # Store in request state for middleware
        request.state.tenant_id = tenant.id
        request.state.tenant = tenant
        request.state.api_key = api_key
        
        return tenant, api_key
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error("API key authentication failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid API key")


async def get_tenant_from_api_key_only(
    tenant_and_key: tuple[Tenant, APIKey] = Depends(get_tenant_from_api_key),
) -> Tenant:
    """Extract just the tenant from API key authentication."""
    return tenant_and_key[0]


async def require_api_key_scope(required_scope: str):
    """
    Factory function to create dependency that requires specific API key scope.
    
    Args:
        required_scope: Required scope (query, ingest, admin)
        
    Returns:
        Dependency function
    """
    async def _check_scope(
        tenant_and_key: tuple[Tenant, APIKey] = Depends(get_tenant_from_api_key)
    ) -> tuple[Tenant, APIKey]:
        tenant, api_key = tenant_and_key
        
        if required_scope not in api_key.scopes:
            raise HTTPException(
                status_code=403,
                detail=f"API key missing required scope: {required_scope}"
            )
        
        return tenant, api_key
    
    return _check_scope


async def require_user_role(required_roles: list[str] | str):
    """
    Factory function to create dependency that requires specific user role.
    
    Args:
        required_roles: Required roles (owner, admin, member)
        
    Returns:
        Dependency function
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    
    async def _check_role(user: User = Depends(get_current_user_from_token)) -> User:
        if user.role not in required_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {', '.join(required_roles)}"
            )
        
        return user
    
    return _check_role


# Common dependency aliases for easy use
CurrentUser = Annotated[User, Depends(get_current_user_from_token)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant_from_user)]
TenantFromAPIKey = Annotated[Tenant, Depends(get_tenant_from_api_key_only)]

# Role-based dependencies
OwnerOnly = Annotated[User, Depends(require_user_role("owner"))]
AdminOrOwner = Annotated[User, Depends(require_user_role(["owner", "admin"]))]

# Scope-based dependencies
QueryAPIKey = Annotated[tuple[Tenant, APIKey], Depends(require_api_key_scope("query"))]
IngestAPIKey = Annotated[tuple[Tenant, APIKey], Depends(require_api_key_scope("ingest"))]
AdminAPIKey = Annotated[tuple[Tenant, APIKey], Depends(require_api_key_scope("admin"))]

