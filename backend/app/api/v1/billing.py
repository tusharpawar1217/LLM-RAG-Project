"""Billing and subscription API endpoints."""

from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.deps import get_current_tenant, get_current_user
from app.core.logging import get_logger
from app.models.billing import PlanTier, BillingCycle
from app.db.models import Tenant
from app.db.models import User
from app.services.billing_service import BillingService, PlanLimitExceeded
from app.services.stripe_service import stripe_service

logger = get_logger(__name__)
router = APIRouter()


# Pydantic Models
class PlanResponse(BaseModel):
    id: str
    name: str
    tier: str
    description: Optional[str]
    price_monthly: float
    price_yearly: float
    yearly_discount_percent: Optional[float]
    max_documents: int
    max_queries_per_month: int
    max_storage_mb: int
    max_api_keys: int
    max_team_members: int
    features: List[str]
    is_popular: bool
    
    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    plan_tier: str
    plan_name: str
    status: str
    billing_cycle: str
    current_period_end: Optional[str]
    is_trial: bool
    trial_end: Optional[str]
    cancel_at_period_end: bool = False
    days_until_renewal: int = 0


class UsageResponse(BaseModel):
    queries_count: int
    documents_count: int
    storage_mb: float
    api_calls_count: int
    costs: Dict[str, float]


class LimitCheckResponse(BaseModel):
    current: int
    limit: int
    can_add: bool
    usage_percent: float


class BillingSummaryResponse(BaseModel):
    subscription: SubscriptionResponse
    usage: UsageResponse
    limits: Dict[str, int]
    limit_checks: Dict[str, LimitCheckResponse]


class CheckoutSessionRequest(BaseModel):
    plan_tier: PlanTier
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class CustomerPortalResponse(BaseModel):
    portal_url: str


class WebhookEvent(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]


# API Endpoints
@router.get("/plans", response_model=List[PlanResponse])
async def get_plans(
    db: Session = Depends(get_db)
) -> List[PlanResponse]:
    """Get all available subscription plans."""
    billing_service = BillingService(db)
    plans = billing_service.get_all_active_plans()
    
    return [
        PlanResponse(
            id=str(plan.id),
            name=plan.name,
            tier=plan.tier.value,
            description=plan.description,
            price_monthly=float(plan.price_monthly),
            price_yearly=float(plan.price_yearly),
            yearly_discount_percent=plan.yearly_discount_percent,
            max_documents=plan.max_documents,
            max_queries_per_month=plan.max_queries_per_month,
            max_storage_mb=plan.max_storage_mb,
            max_api_keys=plan.max_api_keys,
            max_team_members=plan.max_team_members,
            features=plan.features or [],
            is_popular=plan.is_popular
        )
        for plan in plans
    ]


@router.get("/subscription", response_model=BillingSummaryResponse)
async def get_subscription(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> BillingSummaryResponse:
    """Get tenant's subscription and billing information."""
    billing_service = BillingService(db)
    summary = billing_service.get_billing_summary(tenant.id)
    
    return BillingSummaryResponse(**summary)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> UsageResponse:
    """Get current month usage for tenant."""
    billing_service = BillingService(db)
    usage = billing_service.get_current_usage(tenant.id)
    
    return UsageResponse(**usage)


@router.get("/limits", response_model=Dict[str, int])
async def get_limits(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> Dict[str, int]:
    """Get plan limits for tenant."""
    billing_service = BillingService(db)
    return billing_service.get_plan_limits(tenant.id)


@router.get("/limits/check")
async def check_limits(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> Dict[str, LimitCheckResponse]:
    """Check current usage against plan limits."""
    billing_service = BillingService(db)
    
    # Check all limits
    can_add_docs, current_docs, doc_limit = billing_service.check_document_limit(tenant.id)
    can_query, current_queries, query_limit = billing_service.check_query_limit(tenant.id)
    can_store, current_storage, storage_limit = billing_service.check_storage_limit(tenant.id)
    can_add_keys, current_keys, key_limit = billing_service.check_api_key_limit(tenant.id)
    can_add_members, current_members, member_limit = billing_service.check_team_member_limit(tenant.id)
    
    return {
        "documents": LimitCheckResponse(
            current=current_docs,
            limit=doc_limit,
            can_add=can_add_docs,
            usage_percent=(current_docs / doc_limit * 100) if doc_limit > 0 else 0
        ),
        "queries": LimitCheckResponse(
            current=current_queries,
            limit=query_limit,
            can_add=can_query,
            usage_percent=(current_queries / query_limit * 100) if query_limit > 0 else 0
        ),
        "storage": LimitCheckResponse(
            current=int(current_storage),
            limit=storage_limit,
            can_add=can_store,
            usage_percent=(current_storage / storage_limit * 100) if storage_limit > 0 else 0
        ),
        "api_keys": LimitCheckResponse(
            current=current_keys,
            limit=key_limit,
            can_add=can_add_keys,
            usage_percent=(current_keys / key_limit * 100) if key_limit > 0 else 0
        ),
        "team_members": LimitCheckResponse(
            current=current_members,
            limit=member_limit,
            can_add=can_add_members,
            usage_percent=(current_members / member_limit * 100) if member_limit > 0 else 0
        )
    }


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> CheckoutSessionResponse:
    """Create Stripe checkout session for subscription."""
    billing_service = BillingService(db)
    
    # Get the plan
    plan = billing_service.get_plan_by_tier(request.plan_tier)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {request.plan_tier.value} not found"
        )
    
    try:
        # Get or create Stripe customer
        subscription = billing_service.get_tenant_subscription(tenant.id)
        if subscription and subscription.stripe_customer_id:
            customer_id = subscription.stripe_customer_id
        else:
            customer_id = await stripe_service.create_customer(tenant)
        
        # Create checkout session
        checkout_url = await stripe_service.create_checkout_session(
            customer_id=customer_id,
            plan=plan,
            billing_cycle=request.billing_cycle,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            trial_days=14 if plan.tier != PlanTier.FREE else None
        )
        
        logger.info(
            "Created checkout session",
            tenant_id=str(tenant.id),
            plan_tier=plan.tier.value,
            billing_cycle=request.billing_cycle.value
        )
        
        return CheckoutSessionResponse(checkout_url=checkout_url)
        
    except Exception as e:
        logger.error(
            "Failed to create checkout session",
            error=str(e),
            tenant_id=str(tenant.id),
            plan_tier=request.plan_tier.value
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.post("/customer-portal", response_model=CustomerPortalResponse)
async def create_customer_portal_session(
    return_url: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> CustomerPortalResponse:
    """Create Stripe customer portal session."""
    billing_service = BillingService(db)
    
    # Get subscription
    subscription = billing_service.get_tenant_subscription(tenant.id)
    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found"
        )
    
    try:
        portal_url = await stripe_service.create_customer_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=return_url
        )
        
        logger.info(
            "Created customer portal session",
            tenant_id=str(tenant.id),
            customer_id=subscription.stripe_customer_id
        )
        
        return CustomerPortalResponse(portal_url=portal_url)
        
    except Exception as e:
        logger.error(
            "Failed to create customer portal session",
            error=str(e),
            tenant_id=str(tenant.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create customer portal session"
        )


@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events."""
    try:
        # Get raw body
        body = await request.body()
        
        # Verify webhook signature (in production)
        sig_header = request.headers.get('stripe-signature')
        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature"
            )
        
        # TODO: Verify signature in production
        # event = stripe.Webhook.construct_event(
        #     body, sig_header, settings.STRIPE_WEBHOOK_SECRET
        # )
        
        # For now, parse JSON directly
        import json
        event = json.loads(body)
        
        # Handle the event
        await stripe_service.handle_webhook_event(event)
        
        logger.info(
            "Handled Stripe webhook",
            event_type=event.get("type"),
            event_id=event.get("id")
        )
        
        return {"status": "success"}
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    except Exception as e:
        logger.error(
            "Failed to handle webhook",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


@router.get("/invoices")
async def get_invoices(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get tenant's invoices."""
    from app.models.billing import Invoice
    
    invoices = (
        db.query(Invoice)
        .filter(Invoice.tenant_id == tenant.id)
        .order_by(Invoice.created_at.desc())
        .limit(50)
        .all()
    )
    
    return [
        {
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "amount_due": float(invoice.amount_due),
            "amount_paid": float(invoice.amount_paid),
            "status": invoice.status.value,
            "due_date": invoice.due_date.isoformat(),
            "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
            "period_start": invoice.period_start.isoformat(),
            "period_end": invoice.period_end.isoformat(),
            "description": invoice.description,
            "hosted_invoice_url": invoice.hosted_invoice_url,
            "invoice_pdf_url": invoice.invoice_pdf_url,
            "is_paid": invoice.is_paid,
            "is_overdue": invoice.is_overdue,
            "created_at": invoice.created_at.isoformat()
        }
        for invoice in invoices
    ]


# Error Handlers
@router.exception_handler(PlanLimitExceeded)
async def plan_limit_exceeded_handler(request: Request, exc: PlanLimitExceeded):
    """Handle plan limit exceeded errors."""
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "error": "Plan limit exceeded",
            "limit_type": exc.limit_type,
            "current": exc.current,
            "limit": exc.limit,
            "message": str(exc)
        }
    )

