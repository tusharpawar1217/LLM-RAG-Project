"""Billing and subscription models."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Numeric, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.base import Base


class PlanTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status values."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    PAUSED = "paused"


class BillingCycle(str, Enum):
    """Billing cycle types."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


class PaymentStatus(str, Enum):
    """Payment status values."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Plan(Base):
    """Subscription plans definition."""
    
    __tablename__ = "plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Plan identification
    name = Column(String(100), nullable=False)
    tier = Column(sa.Enum(PlanTier), nullable=False, index=True)
    stripe_price_id = Column(String(100), nullable=True)  # Stripe Price ID
    
    # Pricing
    price_monthly = Column(Numeric(10, 2), nullable=False, default=0)
    price_yearly = Column(Numeric(10, 2), nullable=False, default=0)
    
    # Limits
    max_documents = Column(Integer, nullable=False, default=10)
    max_queries_per_month = Column(Integer, nullable=False, default=100)
    max_storage_mb = Column(Integer, nullable=False, default=100)
    max_api_keys = Column(Integer, nullable=False, default=1)
    max_team_members = Column(Integer, nullable=False, default=1)
    
    # Features
    features = Column(JSON, nullable=False, default=list)  # List of feature names
    
    # Metadata
    description = Column(Text, nullable=True)
    is_popular = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")
    
    @hybrid_property
    def yearly_discount_percent(self) -> Optional[float]:
        """Calculate yearly discount percentage."""
        if self.price_monthly <= 0 or self.price_yearly <= 0:
            return None
        
        monthly_yearly = float(self.price_monthly) * 12
        yearly = float(self.price_yearly)
        
        if monthly_yearly <= yearly:
            return None
            
        return ((monthly_yearly - yearly) / monthly_yearly) * 100
    
    def __repr__(self) -> str:
        return f"<Plan(tier='{self.tier}', name='{self.name}')>"


class Subscription(Base):
    """Tenant subscription information."""
    
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Relationships
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    
    # Stripe integration
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    stripe_customer_id = Column(String(100), nullable=True)
    
    # Subscription details
    status = Column(sa.Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    billing_cycle = Column(sa.Enum(BillingCycle), nullable=False, default=BillingCycle.MONTHLY)
    
    # Dates
    current_period_start = Column(DateTime, nullable=False, default=datetime.utcnow)
    current_period_end = Column(DateTime, nullable=False)
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    
    # Metadata
    subscription_metadata = Column("metadata", JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription")
    usage_records = relationship("UsageRecord", back_populates="subscription")
    
    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        if not self.trial_end:
            return False
        return datetime.utcnow() <= self.trial_end
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    @property
    def days_until_renewal(self) -> int:
        """Days until next billing cycle."""
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)
    
    def __repr__(self) -> str:
        return f"<Subscription(tenant_id='{self.tenant_id}', plan='{self.plan.tier if self.plan else None}')>"


class Invoice(Base):
    """Billing invoices."""
    
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Relationships
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    
    # Stripe integration
    stripe_invoice_id = Column(String(100), nullable=True, unique=True)
    
    # Invoice details
    invoice_number = Column(String(50), nullable=False, unique=True)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(10, 2), nullable=False, default=0)
    
    # Status and dates
    status = Column(sa.Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    due_date = Column(DateTime, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    
    # Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Details
    description = Column(Text, nullable=True)
    line_items = Column(JSON, nullable=False, default=list)  # Invoice line items
    invoice_metadata = Column("metadata", JSON, nullable=False, default=dict)
    
    # URLs
    hosted_invoice_url = Column(String(500), nullable=True)  # Stripe hosted URL
    invoice_pdf_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    subscription = relationship("Subscription", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
    
    @property
    def is_paid(self) -> bool:
        """Check if invoice is fully paid."""
        return self.status == PaymentStatus.SUCCEEDED
    
    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        return (
            not self.is_paid and 
            self.due_date < datetime.utcnow() and
            self.status != PaymentStatus.FAILED
        )
    
    def __repr__(self) -> str:
        return f"<Invoice(number='{self.invoice_number}', amount={self.amount_due})>"


class Payment(Base):
    """Payment records."""
    
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Relationships
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    
    # Stripe integration
    stripe_payment_intent_id = Column(String(100), nullable=True, unique=True)
    stripe_charge_id = Column(String(100), nullable=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(sa.Enum(PaymentStatus), nullable=False)
    
    # Payment method
    payment_method_type = Column(String(50), nullable=True)  # card, bank_account, etc.
    last_four = Column(String(4), nullable=True)  # Last 4 digits
    brand = Column(String(50), nullable=True)  # visa, mastercard, etc.
    
    # Dates
    processed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    # Details
    description = Column(Text, nullable=True)
    failure_reason = Column(String(500), nullable=True)
    payment_metadata = Column("metadata", JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    invoice = relationship("Invoice", back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment(amount={self.amount}, status='{self.status}')>"


class UsageRecord(Base):
    """Usage tracking for billing."""
    
    __tablename__ = "usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Relationships
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)
    
    # Usage metrics
    queries_count = Column(Integer, nullable=False, default=0)
    documents_count = Column(Integer, nullable=False, default=0)
    storage_mb = Column(Numeric(10, 2), nullable=False, default=0)
    api_calls_count = Column(Integer, nullable=False, default=0)
    
    # Costs (for tracking, not billing)
    embedding_cost = Column(Numeric(10, 4), nullable=False, default=0)
    llm_cost = Column(Numeric(10, 4), nullable=False, default=0)
    storage_cost = Column(Numeric(10, 4), nullable=False, default=0)
    
    # Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Metadata
    usage_metadata = Column("metadata", JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    subscription = relationship("Subscription", back_populates="usage_records")
    
    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost for the period."""
        return self.embedding_cost + self.llm_cost + self.storage_cost
    
    def __repr__(self) -> str:
        return f"<UsageRecord(tenant_id='{self.tenant_id}', queries={self.queries_count})>"

