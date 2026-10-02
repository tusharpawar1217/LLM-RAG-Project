"""
API Key-related Pydantic schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class APIKeyBase(BaseModel):
    """Base API key schema."""
    
    name: str | None = Field(default=None, max_length=255, description="API key name")
    scopes: list[str] = Field(
        default=["query"],
        description="API key scopes",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="API key expiration (optional)",
    )
    
    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Validate API key scopes."""
        allowed_scopes = {"query", "ingest", "admin"}
        for scope in v:
            if scope not in allowed_scopes:
                raise ValueError(f"Invalid scope: {scope}. Allowed: {', '.join(allowed_scopes)}")
        return list(set(v))  # Remove duplicates


class APIKeyCreate(APIKeyBase):
    """Schema for creating an API key."""
    pass


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    
    name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = Field(default=None, description="Revoke/activate key")


class APIKeyResponse(BaseModel):
    """Schema for API key responses."""
    
    id: UUID
    key_prefix: str
    name: str | None
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    created_by: UUID | None
    
    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    """Schema for API key creation response (includes full key)."""
    
    key: str = Field(..., description="Full API key (shown only once)")


class APIKeyUsage(BaseModel):
    """Schema for API key usage statistics."""
    
    total_requests: int
    requests_last_30_days: int
    last_used_at: datetime | None
    most_used_endpoint: str | None