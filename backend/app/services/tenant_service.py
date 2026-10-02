"""
Tenant service for managing multi-tenant operations.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import (
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    QuotaExceededError,
)
from app.core.logging import get_logger
from app.core.security import generate_tenant_slug, hash_password
from app.db.models import APIKey, Chunk, Conversation, Document, Message, Tenant, User, UsageEvent
from app.schemas.tenant import TenantCreate, TenantLimits, TenantStats, TenantUpdate

logger = get_logger(__name__)


class TenantService:
    """Service for tenant management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_tenant(self, tenant_data: TenantCreate) -> tuple[Tenant, User]:
        """
        Create a new tenant with owner user.
        
        Args:
            tenant_data: Tenant creation data
            
        Returns:
            Tuple of (tenant, owner_user)
            
        Raises:
            ResourceAlreadyExistsError: If email already exists
        """
        # Check if user email already exists
        existing_user = await self.db.execute(
            select(User).where(User.email == tenant_data.owner_email)
        )
        if existing_user.scalar_one_or_none():
            raise ResourceAlreadyExistsError("User", tenant_data.owner_email)
        
        # Generate unique slug
        slug = generate_tenant_slug(tenant_data.name)
        
        # Generate Qdrant collection name
        qdrant_collection = f"{settings.QDRANT_COLLECTION_PREFIX}{slug.replace('-', '_')}"
        
        # Create tenant
        tenant = Tenant(
            name=tenant_data.name,
            slug=slug,
            qdrant_collection_name=qdrant_collection,
            widget_primary_color=tenant_data.widget_primary_color,
            widget_bot_name=tenant_data.widget_bot_name,
            widget_welcome_message=tenant_data.widget_welcome_message,
            handoff_email=tenant_data.handoff_email,
            handoff_webhook_url=tenant_data.handoff_webhook_url,
        )
        
        self.db.add(tenant)
        await self.db.flush()  # Get tenant ID
        
        # Create owner user
        owner = User(
            tenant_id=tenant.id,
            email=tenant_data.owner_email,
            password_hash=hash_password(tenant_data.owner_password),
            full_name=tenant_data.owner_full_name,
            role="owner",
        )
        
        self.db.add(owner)
        await self.db.commit()
        await self.db.refresh(tenant)
        await self.db.refresh(owner)
        
        logger.info(
            "Tenant created",
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            owner_email=tenant_data.owner_email,
        )
        
        return tenant, owner
    
    async def get_tenant_by_id(self, tenant_id: UUID) -> Tenant:
        """
        Get tenant by ID.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Tenant
            
        Raises:
            ResourceNotFoundError: If tenant not found
        """
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise ResourceNotFoundError("Tenant", str(tenant_id))
        
        return tenant
    
    async def get_tenant_by_slug(self, slug: str) -> Tenant:
        """
        Get tenant by slug.
        
        Args:
            slug: Tenant slug
            
        Returns:
            Tenant
            
        Raises:
            ResourceNotFoundError: If tenant not found
        """
        stmt = select(Tenant).where(Tenant.slug == slug)
        result = await self.db.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise ResourceNotFoundError("Tenant", slug)
        
        return tenant
    
    async def update_tenant(self, tenant: Tenant, update_data: TenantUpdate) -> Tenant:
        """
        Update tenant information.
        
        Args:
            tenant: Tenant to update
            update_data: Update data
            
        Returns:
            Updated tenant
        """
        # Update fields that are provided
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            setattr(tenant, field, value)
        
        tenant.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(tenant)
        
        logger.info("Tenant updated", tenant_id=str(tenant.id))
        return tenant
    
    async def get_tenant_stats(self, tenant: Tenant) -> TenantStats:
        """
        Get tenant usage statistics.
        
        Args:
            tenant: Tenant
            
        Returns:
            Tenant statistics
        """
        # Count documents
        doc_count = await self.db.execute(
            select(func.count(Document.id)).where(Document.tenant_id == tenant.id)
        )
        total_documents = doc_count.scalar() or 0
        
        # Count chunks
        chunk_count = await self.db.execute(
            select(func.count(Chunk.id)).where(Chunk.tenant_id == tenant.id)
        )
        total_chunks = chunk_count.scalar() or 0
        
        # Count conversations
        conv_count = await self.db.execute(
            select(func.count(Conversation.id)).where(Conversation.tenant_id == tenant.id)
        )
        total_conversations = conv_count.scalar() or 0
        
        # Count messages this month
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        msg_count = await self.db.execute(
            select(func.count(Message.id)).where(
                Message.tenant_id == tenant.id,
                Message.created_at >= month_start,
            )
        )
        messages_this_month = msg_count.scalar() or 0
        
        # Calculate storage usage (approximate)
        storage_result = await self.db.execute(
            select(func.sum(Document.file_size_bytes)).where(Document.tenant_id == tenant.id)
        )
        storage_bytes = storage_result.scalar() or 0
        storage_usage_mb = storage_bytes / (1024 * 1024)  # Convert to MB
        
        # Calculate usage percentages
        documents_used_percent = (total_documents / tenant.max_documents) * 100
        messages_used_percent = (messages_this_month / tenant.max_messages_per_month) * 100
        
        return TenantStats(
            total_documents=total_documents,
            total_chunks=total_chunks,
            total_conversations=total_conversations,
            messages_this_month=messages_this_month,
            storage_usage_mb=round(storage_usage_mb, 2),
            documents_limit=tenant.max_documents,
            messages_limit=tenant.max_messages_per_month,
            documents_used_percent=round(documents_used_percent, 1),
            messages_used_percent=round(messages_used_percent, 1),
        )
    
    async def check_tenant_limits(self, tenant: Tenant) -> TenantLimits:
        """
        Check tenant limits and current usage.
        
        Args:
            tenant: Tenant
            
        Returns:
            Tenant limits information
        """
        stats = await self.get_tenant_stats(tenant)
        
        # Check if tenant can add more documents
        can_add_document = stats.total_documents < tenant.max_documents
        documents_remaining = max(0, tenant.max_documents - stats.total_documents)
        
        # Check if tenant can send more messages this month
        can_send_message = stats.messages_this_month < tenant.max_messages_per_month
        messages_remaining = max(0, tenant.max_messages_per_month - stats.messages_this_month)
        
        return TenantLimits(
            can_add_document=can_add_document,
            can_send_message=can_send_message,
            documents_remaining=documents_remaining,
            messages_remaining=messages_remaining,
            current_documents=stats.total_documents,
            current_messages_this_month=stats.messages_this_month,
            max_documents=tenant.max_documents,
            max_messages_per_month=tenant.max_messages_per_month,
        )
    
    async def enforce_document_limit(self, tenant: Tenant) -> None:
        """
        Enforce document upload limits.
        
        Args:
            tenant: Tenant
            
        Raises:
            QuotaExceededError: If document limit exceeded
        """
        limits = await self.check_tenant_limits(tenant)
        
        if not limits.can_add_document:
            raise QuotaExceededError(
                resource="documents",
                limit=tenant.max_documents,
                current=limits.current_documents,
            )
    
    async def enforce_message_limit(self, tenant: Tenant) -> None:
        """
        Enforce message sending limits.
        
        Args:
            tenant: Tenant
            
        Raises:
            QuotaExceededError: If message limit exceeded
        """
        limits = await self.check_tenant_limits(tenant)
        
        if not limits.can_send_message:
            raise QuotaExceededError(
                resource="messages",
                limit=tenant.max_messages_per_month,
                current=limits.current_messages_this_month,
            )
    
    async def get_tenant_users(self, tenant: Tenant) -> list[User]:
        """
        Get all users for a tenant.
        
        Args:
            tenant: Tenant
            
        Returns:
            List of tenant users
        """
        stmt = (
            select(User)
            .where(User.tenant_id == tenant.id)
            .order_by(User.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def delete_tenant(self, tenant: Tenant) -> None:
        """
        Delete a tenant and all associated data.
        
        WARNING: This is destructive and will delete all tenant data.
        
        Args:
            tenant: Tenant to delete
        """
        logger.warning("Deleting tenant", tenant_id=str(tenant.id), tenant_slug=tenant.slug)
        
        # The database cascade will handle deleting related records
        await self.db.delete(tenant)
        await self.db.commit()
        
        logger.info("Tenant deleted", tenant_id=str(tenant.id))