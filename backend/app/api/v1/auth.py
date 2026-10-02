"""
Authentication endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.errors import AskDocsException
from app.db.base import get_db
from app.schemas.user import TokenResponse, UserChangePassword, UserLogin
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user and return access tokens.
    
    Args:
        credentials: User login credentials
        db: Database session
        
    Returns:
        Token response with access and refresh tokens
    """
    try:
        auth_service = AuthService(db)
        
        # Authenticate user
        user = await auth_service.authenticate_user(credentials)
        
        # Create tokens
        token_response = await auth_service.create_tokens(user)
        
        return token_response
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Valid refresh token
        db: Database session
        
    Returns:
        New token response
    """
    try:
        auth_service = AuthService(db)
        token_response = await auth_service.refresh_access_token(refresh_token)
        return token_response
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/me")
async def get_current_user_info(
    current_user: CurrentUser,
) -> dict:
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User information and tenant details
    """
    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at,
        },
        "tenant": {
            "id": str(current_user.tenant.id),
            "name": current_user.tenant.name,
            "slug": current_user.tenant.slug,
            "subscription_status": current_user.tenant.subscription_status,
            "subscription_tier": current_user.tenant.subscription_tier,
        },
    }


@router.post("/change-password")
async def change_password(
    password_data: UserChangePassword,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Change current user's password.
    
    Args:
        password_data: Current and new password
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    try:
        auth_service = AuthService(db)
        await auth_service.change_user_password(
            current_user,
            password_data.current_password,
            password_data.new_password,
        )
        
        return {"message": "Password changed successfully"}
        
    except AskDocsException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/logout")
async def logout():
    """
    Logout user (client-side token removal).
    
    Note: Since we're using JWTs, actual logout is handled client-side
    by removing the tokens. Server-side blacklisting could be added later.
    
    Returns:
        Success message
    """
    return {"message": "Logged out successfully"}