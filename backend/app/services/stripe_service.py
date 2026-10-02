"""Stripe integration service."""

import stripe
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.models.billing import (
    Subscription, Invoice, Payment, Plan, 
    SubscriptionStatus, PaymentStatus, BillingCycle
)
from app.models.tenant import Tenant

logger = get_logger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for Stripe integration."""
    
    def __init__(self):
        self.api_key = settings.STRIPE_SECRET_KEY
        if not self.api_key:
            logger.warning("Stripe API key not configured")
    
    async def create_customer(self, tenant: Tenant, payment_method_id: Optional[str] = None) -> str:
        """Create a Stripe customer for tenant."""
        try:
            customer_data = {
                "name": tenant.name,
                "email": tenant.owner_email,
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "tenant_slug": tenant.slug,
                }
            }
            
            if payment_method_id:
                customer_data["payment_method"] = payment_method_id
                customer_data["invoice_settings"] = {
                    "default_payment_method": payment_method_id
                }
            
            customer = stripe.Customer.create(**customer_data)
            
            logger.info(
                "Created Stripe customer",
                customer_id=customer.id,
                tenant_id=str(tenant.id)
            )
            
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe customer",
                error=str(e),
                tenant_id=str(tenant.id)
            )
            raise
    
    async def create_subscription(
        self, 
        customer_id: str, 
        plan: Plan, 
        billing_cycle: BillingCycle = BillingCycle.MONTHLY,
        trial_days: Optional[int] = None
    ) -> str:
        """Create a Stripe subscription."""
        try:
            # Get the correct price ID based on billing cycle
            price_id = self.get_price_id_for_plan(plan, billing_cycle)
            
            subscription_data = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "metadata": {
                    "plan_id": str(plan.id),
                    "plan_tier": plan.tier.value,
                    "billing_cycle": billing_cycle.value,
                }
            }
            
            if trial_days and trial_days > 0:
                subscription_data["trial_period_days"] = trial_days
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            logger.info(
                "Created Stripe subscription",
                subscription_id=subscription.id,
                customer_id=customer_id,
                plan_tier=plan.tier.value
            )
            
            return subscription.id
            
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe subscription",
                error=str(e),
                customer_id=customer_id,
                plan_id=str(plan.id)
            )
            raise
    
    async def cancel_subscription(
        self, 
        subscription_id: str, 
        cancel_at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a Stripe subscription."""
        try:
            if cancel_at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.cancel(subscription_id)
            
            logger.info(
                "Canceled Stripe subscription",
                subscription_id=subscription_id,
                cancel_at_period_end=cancel_at_period_end
            )
            
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to cancel Stripe subscription",
                error=str(e),
                subscription_id=subscription_id
            )
            raise
    
    async def update_subscription(
        self,
        subscription_id: str,
        new_plan: Plan,
        billing_cycle: Optional[BillingCycle] = None
    ) -> Dict[str, Any]:
        """Update a Stripe subscription to new plan."""
        try:
            # Get current subscription
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Determine billing cycle
            if not billing_cycle:
                # Try to infer from current subscription
                current_price_id = subscription["items"]["data"][0]["price"]["id"]
                billing_cycle = self.infer_billing_cycle_from_price(current_price_id)
            
            # Get new price ID
            new_price_id = self.get_price_id_for_plan(new_plan, billing_cycle)
            
            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    "id": subscription["items"]["data"][0]["id"],
                    "price": new_price_id,
                }],
                metadata={
                    "plan_id": str(new_plan.id),
                    "plan_tier": new_plan.tier.value,
                    "billing_cycle": billing_cycle.value,
                }
            )
            
            logger.info(
                "Updated Stripe subscription",
                subscription_id=subscription_id,
                new_plan_tier=new_plan.tier.value
            )
            
            return updated_subscription
            
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to update Stripe subscription",
                error=str(e),
                subscription_id=subscription_id
            )
            raise
    
    async def create_checkout_session(
        self,
        customer_id: str,
        plan: Plan,
        billing_cycle: BillingCycle,
        success_url: str,
        cancel_url: str,
        trial_days: Optional[int] = None
    ) -> str:
        """Create a Stripe Checkout session."""
        try:
            price_id = self.get_price_id_for_plan(plan, billing_cycle)
            
            session_data = {
                "customer": customer_id,
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": price_id,
                    "quantity": 1,
                }],
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "plan_id": str(plan.id),
                    "plan_tier": plan.tier.value,
                    "billing_cycle": billing_cycle.value,
                }
            }
            
            if trial_days and trial_days > 0:
                session_data["subscription_data"] = {
                    "trial_period_days": trial_days
                }
            
            session = stripe.checkout.Session.create(**session_data)
            
            logger.info(
                "Created Stripe checkout session",
                session_id=session.id,
                customer_id=customer_id,
                plan_tier=plan.tier.value
            )
            
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create checkout session",
                error=str(e),
                customer_id=customer_id
            )
            raise
    
    async def create_customer_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> str:
        """Create a Stripe customer portal session."""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            
            logger.info(
                "Created customer portal session",
                session_id=session.id,
                customer_id=customer_id
            )
            
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create customer portal session",
                error=str(e),
                customer_id=customer_id
            )
            raise
    
    async def retrieve_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retrieve a Stripe invoice."""
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
            return invoice
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to retrieve invoice",
                error=str(e),
                invoice_id=invoice_id
            )
            raise
    
    async def handle_webhook_event(self, event: Dict[str, Any]) -> None:
        """Handle Stripe webhook events."""
        event_type = event.get("type")
        
        logger.info(
            "Handling Stripe webhook",
            event_type=event_type,
            event_id=event.get("id")
        )
        
        try:
            if event_type == "customer.subscription.created":
                await self._handle_subscription_created(event["data"]["object"])
            elif event_type == "customer.subscription.updated":
                await self._handle_subscription_updated(event["data"]["object"])
            elif event_type == "customer.subscription.deleted":
                await self._handle_subscription_deleted(event["data"]["object"])
            elif event_type == "invoice.payment_succeeded":
                await self._handle_payment_succeeded(event["data"]["object"])
            elif event_type == "invoice.payment_failed":
                await self._handle_payment_failed(event["data"]["object"])
            elif event_type.startswith("payment_intent."):
                await self._handle_payment_intent_event(event_type, event["data"]["object"])
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                
        except Exception as e:
            logger.error(
                "Failed to handle webhook event",
                error=str(e),
                event_type=event_type,
                event_id=event.get("id"),
                exc_info=True
            )
            raise
    
    def get_price_id_for_plan(self, plan: Plan, billing_cycle: BillingCycle) -> str:
        """Get Stripe price ID for plan and billing cycle."""
        # This would typically be stored in the database or config
        # For now, we'll construct it based on conventions
        
        if not plan.stripe_price_id:
            raise ValueError(f"No Stripe price ID configured for plan {plan.tier}")
        
        # If plan has specific price IDs for different cycles, return appropriate one
        # For now, assume single price ID
        return plan.stripe_price_id
    
    def infer_billing_cycle_from_price(self, price_id: str) -> BillingCycle:
        """Infer billing cycle from Stripe price ID."""
        # This is a simple heuristic - in practice, you'd store this mapping
        if "monthly" in price_id.lower() or "month" in price_id.lower():
            return BillingCycle.MONTHLY
        elif "yearly" in price_id.lower() or "year" in price_id.lower() or "annual" in price_id.lower():
            return BillingCycle.YEARLY
        else:
            # Default to monthly
            return BillingCycle.MONTHLY
    
    # Private webhook handlers
    async def _handle_subscription_created(self, subscription_data: Dict[str, Any]) -> None:
        """Handle subscription created webhook."""
        # Implementation would update database subscription record
        pass
    
    async def _handle_subscription_updated(self, subscription_data: Dict[str, Any]) -> None:
        """Handle subscription updated webhook."""
        # Implementation would update database subscription record
        pass
    
    async def _handle_subscription_deleted(self, subscription_data: Dict[str, Any]) -> None:
        """Handle subscription deleted webhook."""
        # Implementation would update database subscription record
        pass
    
    async def _handle_payment_succeeded(self, invoice_data: Dict[str, Any]) -> None:
        """Handle successful payment webhook."""
        # Implementation would update database invoice and payment records
        pass
    
    async def _handle_payment_failed(self, invoice_data: Dict[str, Any]) -> None:
        """Handle failed payment webhook."""
        # Implementation would update database invoice and payment records
        pass
    
    async def _handle_payment_intent_event(self, event_type: str, payment_intent_data: Dict[str, Any]) -> None:
        """Handle payment intent events."""
        # Implementation would update database payment records
        pass


# Singleton instance
stripe_service = StripeService()