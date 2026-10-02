"""Billing service for plan enforcement and usage tracking."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.billing import (
    Plan, Subscription, UsageRecord, Invoice, Payment,
    PlanTier, SubscriptionStatus, BillingCycle
)
from app.models.tenant import Tenant
from app.models.document import Document, DocumentStatus
from app.services.stripe_service import stripe_service

logger = get_logger(__name__)


class PlanLimitExceeded(Exception):
    """Raised when tenant exceeds plan limits."""
    
    def __init__(self, limit_type: str, current: int, limit: int):
        self.limit_type = limit_type
        self.current = current
        self.limit = limit
        super().__init__(f"{limit_type} limit exceeded: {current}/{limit}")


class BillingService:
    """Service for billing operations and plan enforcement."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_tenant_subscription(self, tenant_id: UUID) -> Optional[Subscription]:
        """Get active subscription for tenant."""
        return (
            self.db.query(Subscription)
            .filter(
                Subscription.tenant_id == tenant_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING
                ])
            )
            .first()
        )
    
    def get_plan_by_tier(self, tier: PlanTier) -> Optional[Plan]:
        """Get plan by tier."""
        return (
            self.db.query(Plan)
            .filter(
                Plan.tier == tier,
                Plan.is_active == True
            )
            .first()
        )
    
    def get_all_active_plans(self) -> List[Plan]:
        """Get all active plans ordered by price."""
        return (
            self.db.query(Plan)
            .filter(Plan.is_active == True)
            .order_by(Plan.sort_order, Plan.price_monthly)
            .all()
        )
    
    def check_document_limit(self, tenant_id: UUID) -> Tuple[bool, int, int]:
        """Check if tenant can add more documents."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            # No subscription, use free tier limits
            plan = self.get_plan_by_tier(PlanTier.FREE)
            if not plan:
                return False, 0, 0
        else:
            plan = subscription.plan
        
        # Count current documents
        current_documents = (
            self.db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.status != DocumentStatus.ARCHIVED
            )
            .count()
        )
        
        can_add = current_documents < plan.max_documents
        return can_add, current_documents, plan.max_documents
    
    def check_query_limit(self, tenant_id: UUID) -> Tuple[bool, int, int]:
        """Check if tenant can make more queries this month."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            plan = self.get_plan_by_tier(PlanTier.FREE)
            if not plan:
                return False, 0, 0
        else:
            plan = subscription.plan
        
        # Get current month's usage
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        usage_record = (
            self.db.query(UsageRecord)
            .filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_start >= month_start
            )
            .first()
        )
        
        current_queries = usage_record.queries_count if usage_record else 0
        can_query = current_queries < plan.max_queries_per_month
        
        return can_query, current_queries, plan.max_queries_per_month
    
    def check_storage_limit(self, tenant_id: UUID, additional_mb: float = 0) -> Tuple[bool, float, int]:
        """Check if tenant has enough storage space."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            plan = self.get_plan_by_tier(PlanTier.FREE)
            if not plan:
                return False, 0, 0
        else:
            plan = subscription.plan
        
        # Calculate current storage usage
        total_bytes = (
            self.db.query(func.sum(Document.file_size))
            .filter(
                Document.tenant_id == tenant_id,
                Document.status != DocumentStatus.ARCHIVED
            )
            .scalar() or 0
        )
        
        current_mb = total_bytes / (1024 * 1024)
        can_store = (current_mb + additional_mb) <= plan.max_storage_mb
        
        return can_store, current_mb, plan.max_storage_mb
    
    def check_api_key_limit(self, tenant_id: UUID) -> Tuple[bool, int, int]:
        """Check if tenant can create more API keys."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            plan = self.get_plan_by_tier(PlanTier.FREE)
            if not plan:
                return False, 0, 0
        else:
            plan = subscription.plan
        
        # Count current API keys
        from app.models.api_key import APIKey
        current_keys = (
            self.db.query(APIKey)
            .filter(
                APIKey.tenant_id == tenant_id,
                APIKey.is_active == True
            )
            .count()
        )
        
        can_create = current_keys < plan.max_api_keys
        return can_create, current_keys, plan.max_api_keys
    
    def check_team_member_limit(self, tenant_id: UUID) -> Tuple[bool, int, int]:
        """Check if tenant can add more team members."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            plan = self.get_plan_by_tier(PlanTier.FREE)
            if not plan:
                return False, 0, 0
        else:
            plan = subscription.plan
        
        # Count current team members
        from app.models.user import User
        current_members = (
            self.db.query(User)
            .filter(
                User.tenant_id == tenant_id,
                User.is_active == True
            )
            .count()
        )
        
        can_add = current_members < plan.max_team_members
        return can_add, current_members, plan.max_team_members
    
    def enforce_document_limit(self, tenant_id: UUID) -> None:
        """Enforce document limit, raise exception if exceeded."""
        can_add, current, limit = self.check_document_limit(tenant_id)
        if not can_add:
            raise PlanLimitExceeded("documents", current, limit)
    
    def enforce_query_limit(self, tenant_id: UUID) -> None:
        """Enforce query limit, raise exception if exceeded."""
        can_query, current, limit = self.check_query_limit(tenant_id)
        if not can_query:
            raise PlanLimitExceeded("queries", current, limit)
    
    def enforce_storage_limit(self, tenant_id: UUID, additional_mb: float) -> None:
        """Enforce storage limit, raise exception if exceeded."""
        can_store, current, limit = self.check_storage_limit(tenant_id, additional_mb)
        if not can_store:
            raise PlanLimitExceeded("storage_mb", int(current + additional_mb), limit)
    
    def record_query_usage(self, tenant_id: UUID, cost_data: Optional[Dict[str, float]] = None) -> None:
        """Record a query usage event."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            logger.warning(f"No subscription found for tenant {tenant_id}")
            return
        
        # Get or create usage record for current month
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        usage_record = (
            self.db.query(UsageRecord)
            .filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.subscription_id == subscription.id,
                UsageRecord.period_start == month_start
            )
            .first()
        )
        
        if not usage_record:
            usage_record = UsageRecord(
                tenant_id=tenant_id,
                subscription_id=subscription.id,
                period_start=month_start,
                period_end=month_end,
                queries_count=0,
                documents_count=0,
                storage_mb=Decimal('0'),
                api_calls_count=0,
                embedding_cost=Decimal('0'),
                llm_cost=Decimal('0'),
                storage_cost=Decimal('0')
            )
            self.db.add(usage_record)
        
        # Increment usage
        usage_record.queries_count += 1
        usage_record.api_calls_count += 1
        
        # Add costs if provided
        if cost_data:
            usage_record.embedding_cost += Decimal(str(cost_data.get('embedding_cost', 0)))
            usage_record.llm_cost += Decimal(str(cost_data.get('llm_cost', 0)))
        
        self.db.commit()
        
        logger.debug(
            "Recorded query usage",
            tenant_id=str(tenant_id),
            queries_count=usage_record.queries_count
        )
    
    def record_document_usage(self, tenant_id: UUID, file_size_bytes: int) -> None:
        """Record document upload usage."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            logger.warning(f"No subscription found for tenant {tenant_id}")
            return
        
        # Get or create usage record for current month
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        
        usage_record = (
            self.db.query(UsageRecord)
            .filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.subscription_id == subscription.id,
                UsageRecord.period_start == month_start
            )
            .first()
        )
        
        if not usage_record:
            usage_record = UsageRecord(
                tenant_id=tenant_id,
                subscription_id=subscription.id,
                period_start=month_start,
                period_end=month_end,
                queries_count=0,
                documents_count=0,
                storage_mb=Decimal('0'),
                api_calls_count=0,
                embedding_cost=Decimal('0'),
                llm_cost=Decimal('0'),
                storage_cost=Decimal('0')
            )
            self.db.add(usage_record)
        
        # Update usage
        usage_record.documents_count += 1
        usage_record.storage_mb += Decimal(str(file_size_bytes / (1024 * 1024)))
        
        # Add storage cost (simplified calculation)
        storage_cost_per_mb = Decimal('0.001')  # $0.001 per MB per month
        usage_record.storage_cost += storage_cost_per_mb * Decimal(str(file_size_bytes / (1024 * 1024)))
        
        self.db.commit()
        
        logger.debug(
            "Recorded document usage",
            tenant_id=str(tenant_id),
            documents_count=usage_record.documents_count,
            storage_mb=float(usage_record.storage_mb)
        )
    
    def get_current_usage(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get current month usage for tenant."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            return {
                "queries_count": 0,
                "documents_count": 0,
                "storage_mb": 0,
                "api_calls_count": 0,
                "costs": {
                    "embedding_cost": 0,
                    "llm_cost": 0,
                    "storage_cost": 0,
                    "total_cost": 0
                }
            }
        
        # Get current month usage
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        usage_record = (
            self.db.query(UsageRecord)
            .filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_start == month_start
            )
            .first()
        )
        
        if not usage_record:
            return {
                "queries_count": 0,
                "documents_count": 0,
                "storage_mb": 0,
                "api_calls_count": 0,
                "costs": {
                    "embedding_cost": 0,
                    "llm_cost": 0,
                    "storage_cost": 0,
                    "total_cost": 0
                }
            }
        
        return {
            "queries_count": usage_record.queries_count,
            "documents_count": usage_record.documents_count,
            "storage_mb": float(usage_record.storage_mb),
            "api_calls_count": usage_record.api_calls_count,
            "costs": {
                "embedding_cost": float(usage_record.embedding_cost),
                "llm_cost": float(usage_record.llm_cost),
                "storage_cost": float(usage_record.storage_cost),
                "total_cost": float(usage_record.total_cost)
            }
        }
    
    def get_plan_limits(self, tenant_id: UUID) -> Dict[str, int]:
        """Get plan limits for tenant."""
        subscription = self.get_tenant_subscription(tenant_id)
        if not subscription:
            plan = self.get_plan_by_tier(PlanTier.FREE)
            if not plan:
                return {}
        else:
            plan = subscription.plan
        
        return {
            "max_documents": plan.max_documents,
            "max_queries_per_month": plan.max_queries_per_month,
            "max_storage_mb": plan.max_storage_mb,
            "max_api_keys": plan.max_api_keys,
            "max_team_members": plan.max_team_members
        }
    
    def get_billing_summary(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get comprehensive billing summary for tenant."""
        subscription = self.get_tenant_subscription(tenant_id)
        usage = self.get_current_usage(tenant_id)
        limits = self.get_plan_limits(tenant_id)
        
        # Check all limits
        can_add_docs, current_docs, doc_limit = self.check_document_limit(tenant_id)
        can_query, current_queries, query_limit = self.check_query_limit(tenant_id)
        can_store, current_storage, storage_limit = self.check_storage_limit(tenant_id)
        can_add_keys, current_keys, key_limit = self.check_api_key_limit(tenant_id)
        can_add_members, current_members, member_limit = self.check_team_member_limit(tenant_id)
        
        return {
            "subscription": {
                "plan_tier": subscription.plan.tier.value if subscription else "free",
                "plan_name": subscription.plan.name if subscription else "Free",
                "status": subscription.status.value if subscription else "active",
                "billing_cycle": subscription.billing_cycle.value if subscription else "monthly",
                "current_period_end": subscription.current_period_end.isoformat() if subscription else None,
                "is_trial": subscription.is_trial if subscription else False,
                "trial_end": subscription.trial_end.isoformat() if subscription and subscription.trial_end else None
            },
            "usage": usage,
            "limits": limits,
            "limit_checks": {
                "documents": {
                    "current": current_docs,
                    "limit": doc_limit,
                    "can_add": can_add_docs,
                    "usage_percent": (current_docs / doc_limit * 100) if doc_limit > 0 else 0
                },
                "queries": {
                    "current": current_queries,
                    "limit": query_limit,
                    "can_add": can_query,
                    "usage_percent": (current_queries / query_limit * 100) if query_limit > 0 else 0
                },
                "storage": {
                    "current": current_storage,
                    "limit": storage_limit,
                    "can_add": can_store,
                    "usage_percent": (current_storage / storage_limit * 100) if storage_limit > 0 else 0
                },
                "api_keys": {
                    "current": current_keys,
                    "limit": key_limit,
                    "can_add": can_add_keys,
                    "usage_percent": (current_keys / key_limit * 100) if key_limit > 0 else 0
                },
                "team_members": {
                    "current": current_members,
                    "limit": member_limit,
                    "can_add": can_add_members,
                    "usage_percent": (current_members / member_limit * 100) if member_limit > 0 else 0
                }
            }
        }


def get_billing_service(db: Session = next(get_db())) -> BillingService:
    """Get billing service instance."""
    return BillingService(db)