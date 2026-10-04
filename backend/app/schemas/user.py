"""
User-related Pydantic schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UserBase(BaseModel):
    """Base user schema."""
    
    email: str = Field(..., description="User email address")
    full_name: str | None = Field(default=None, max_length=255, description="User full name")
    role: str = Field(default="member", description="User role in tenant")
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        if "@" not in v or "." not in v.split("@")[1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate user role."""
        allowed_roles = {"owner", "admin", "member"}
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class UserCreate(UserBase):
    """Schema for creating a user."""
    
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (min 8 chars)",
    )


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    full_name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        """Validate user role."""
        if v is None:
            return v
        allowed_roles = {"owner", "admin", "member"}
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class UserResponse(UserBase):
    """Schema for user responses."""
    
    id: UUID
    tenant_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    """Schema for user login."""
    
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        return v.lower().strip()


class UserChangePassword(BaseModel):
    """Schema for changing password."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (min 8 chars)",
    )


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse

