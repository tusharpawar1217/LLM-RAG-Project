"""
Tenant-related Pydantic schemas.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TenantBase(BaseModel):
    """Base tenant schema."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    
    # Branding
    widget_primary_color: str = Field(
        default="#3b82f6",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Widget primary color (hex)",
    )
    widget_bot_name: str = Field(
        default="Support Bot",
        min_length=1,
        max_length=100,
        description="Widget bot name",
    )
    widget_welcome_message: str | None = Field(
        default=None,
        max_length=500,
        description="Widget welcome message",
    )
    
    # Handoff
    handoff_email: str | None = Field(
        default=None,
        description="Email for human handoff notifications",
    )
    handoff_webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for handoff notifications",
    )


class TenantCreate(TenantBase):
    """Schema for creating a tenant."""
    
    # Owner user information
    owner_email: str = Field(..., description="Owner email address")
    owner_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Owner password (min 8 chars)",
    )
    owner_full_name: str | None = Field(
        default=None,
        max_length=255,
        description="Owner full name",
    )
    
    @field_validator("owner_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation."""
        if "@" not in v or "." not in v.split("@")[1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""
    
    name: str | None = Field(default=None, min_length=1, max_length=255)
    widget_primary_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )
    widget_bot_name: str | None = Field(default=None, min_length=1, max_length=100)
    widget_welcome_message: str | None = Field(default=None, max_length=500)
    handoff_email: str | None = None
    handoff_webhook_url: str | None = None


class TenantResponse(TenantBase):
    """Schema for tenant responses."""
    
    id: UUID
    slug: str
    
    # Subscription
    subscription_status: str
    subscription_tier: str
    
    # Limits
    max_documents: int
    max_messages_per_month: int
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class TenantStats(BaseModel):
    """Schema for tenant statistics."""
    
    total_documents: int
    total_chunks: int
    total_conversations: int
    messages_this_month: int
    storage_usage_mb: float
    
    # Usage limits
    documents_limit: int
    messages_limit: int
    documents_used_percent: float
    messages_used_percent: float


class TenantLimits(BaseModel):
    """Schema for tenant limits check."""
    
    can_add_document: bool
    can_send_message: bool
    documents_remaining: int
    messages_remaining: int
    
    # Current usage
    current_documents: int
    current_messages_this_month: int
    
    # Plan limits
    max_documents: int
    max_messages_per_month: int