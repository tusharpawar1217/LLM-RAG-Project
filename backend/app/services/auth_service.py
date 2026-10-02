"""
Authentication service for handling login, tokens, and password management.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AuthenticationError, ResourceNotFoundError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_api_key,
    verify_password,
)
from app.db.models import APIKey, Tenant, User
from app.schemas.user import TokenResponse, UserLogin, UserResponse

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def authenticate_user(self, credentials: UserLogin) -> User:
        """
        Authenticate user with email and password.
        
        Args:
            credentials: User login credentials
            
        Returns:
            Authenticated user
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Find user by email
        stmt = (
            select(User)
            .options(selectinload(User.tenant))
            .where(User.email == credentials.email, User.is_active == True)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("Authentication failed: user not found", email=credentials.email)
            raise AuthenticationError("Invalid email or password")
        
        # Verify password
        if not verify_password(credentials.password, user.password_hash):
            logger.warning("Authentication failed: invalid password", user_id=str(user.id))
            raise AuthenticationError("Invalid email or password")
        
        # Check if tenant is active
        if user.tenant.subscription_status not in ("trial", "active"):
            logger.warning(
                "Authentication failed: inactive subscription",
                user_id=str(user.id),
                tenant_id=str(user.tenant_id),
                subscription_status=user.tenant.subscription_status,
            )
            raise AuthenticationError("Account subscription is inactive")
        
        logger.info("User authenticated successfully", user_id=str(user.id))
        return user
    
    async def create_tokens(self, user: User) -> TokenResponse:
        """
        Create access and refresh tokens for user.
        
        Args:
            user: Authenticated user
            
        Returns:
            Token response with access and refresh tokens
        """
        # Create access token
        access_token = create_access_token(
            subject=str(user.id),
            additional_claims={
                "tenant_id": str(user.tenant_id),
                "role": user.role,
                "email": user.email,
            }
        )
        
        # Create refresh token
        refresh_token = create_refresh_token(subject=str(user.id))
        
        # Convert user to response schema
        user_response = UserResponse.model_validate(user)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
        )
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Create new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token response
            
        Raises:
            AuthenticationError: If refresh token is invalid
        """
        try:
            # Decode refresh token
            payload = decode_token(refresh_token)
            
            # Validate token type
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            
            # Get user
            user_id = UUID(payload["sub"])
            user = await self.get_user_by_id(user_id)
            
            # Create new tokens
            return await self.create_tokens(user)
            
        except Exception as e:
            logger.warning("Refresh token failed", error=str(e))
            raise AuthenticationError("Invalid refresh token")
    
    async def get_user_by_id(self, user_id: UUID) -> User:
        """
        Get user by ID with tenant information.
        
        Args:
            user_id: User ID
            
        Returns:
            User with tenant
            
        Raises:
            ResourceNotFoundError: If user not found
        """
        stmt = (
            select(User)
            .options(selectinload(User.tenant))
            .where(User.id == user_id, User.is_active == True)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise ResourceNotFoundError("User", str(user_id))
        
        return user
    
    async def authenticate_api_key(self, api_key: str) -> tuple[Tenant, APIKey]:
        """
        Authenticate request using API key.
        
        Args:
            api_key: API key from request
            
        Returns:
            Tuple of (tenant, api_key_record)
            
        Raises:
            AuthenticationError: If API key is invalid
        """
        # Query all API keys (we need to check hashes)
        stmt = (
            select(APIKey)
            .options(selectinload(APIKey.tenant))
            .where(APIKey.expires_at.is_(None) | (APIKey.expires_at > datetime.utcnow()))
        )
        result = await self.db.execute(stmt)
        api_keys = result.scalars().all()
        
        # Check each API key hash
        for key_record in api_keys:
            if verify_api_key(api_key, key_record.key_hash):
                # Check if tenant subscription is active
                if key_record.tenant.subscription_status not in ("trial", "active"):
                    logger.warning(
                        "API key authentication failed: inactive subscription",
                        tenant_id=str(key_record.tenant_id),
                        subscription_status=key_record.tenant.subscription_status,
                    )
                    raise AuthenticationError("Account subscription is inactive")
                
                # Update last used timestamp
                key_record.last_used_at = datetime.utcnow()
                await self.db.commit()
                
                logger.info(
                    "API key authenticated",
                    tenant_id=str(key_record.tenant_id),
                    api_key_id=str(key_record.id),
                )
                return key_record.tenant, key_record
        
        logger.warning("API key authentication failed: invalid key")
        raise AuthenticationError("Invalid API key")
    
    async def change_user_password(
        self, 
        user: User, 
        current_password: str, 
        new_password: str
    ) -> None:
        """
        Change user password.
        
        Args:
            user: User to change password for
            current_password: Current password for verification
            new_password: New password
            
        Raises:
            AuthenticationError: If current password is incorrect
        """
        # Verify current password
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        
        # Update password
        user.password_hash = hash_password(new_password)
        await self.db.commit()
        
        logger.info("Password changed", user_id=str(user.id))