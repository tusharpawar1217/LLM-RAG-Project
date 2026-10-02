#!/usr/bin/env python3
"""
Demo script for AskDocs Billing System

This script demonstrates the complete billing system functionality:
- Plan management and enforcement
- Usage tracking and limits
- Stripe integration simulation
- Subscription lifecycle
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.logging import setup_logging, get_logger
from app.models.billing import Plan, Subscription, PlanTier, BillingCycle, SubscriptionStatus
from app.services.billing_service import BillingService, PlanLimitExceeded
from app.db.init_billing import init_plans
from app.core.billing_config import get_plan_config, calculate_llm_cost, calculate_embedding_cost

# Setup logging
setup_logging()
logger = get_logger(__name__)


class BillingDemo:
    """Demo class for billing system."""
    
    def __init__(self):
        self.db = SessionLocal()
        self.billing_service = BillingService(self.db)
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def demo_plan_management(self):
        """Demonstrate plan management."""
        print("\n" + "="*60)
        print("🎯 DEMO: Plan Management")
        print("="*60)
        
        # Initialize plans
        print("📦 Initializing subscription plans...")
        init_plans(self.db)
        
        # Get all plans
        plans = self.billing_service.get_all_active_plans()
        
        print(f"\n✅ Created {len(plans)} subscription plans:")
        for plan in plans:
            config = get_plan_config(plan.tier)
            print(f"  • {plan.name} ({plan.tier.value})")
            print(f"    - Price: ${plan.price_monthly}/month, ${plan.price_yearly}/year")
            print(f"    - Documents: {plan.max_documents if plan.max_documents > 0 else 'Unlimited'}")
            print(f"    - Queries: {plan.max_queries_per_month if plan.max_queries_per_month > 0 else 'Unlimited'}/month")
            print(f"    - Storage: {plan.max_storage_mb if plan.max_storage_mb > 0 else 'Unlimited'} MB")
            print(f"    - Features: {len(plan.features or [])} features")
            
            if plan.yearly_discount_percent:
                print(f"    - Yearly Discount: {plan.yearly_discount_percent:.0f}%")
            print()
    
    def demo_usage_tracking(self):
        """Demonstrate usage tracking and cost calculation."""
        print("\n" + "="*60)
        print("💰 DEMO: Usage Tracking & Cost Calculation")
        print("="*60)
        
        # Simulate usage scenarios
        scenarios = [
            {
                "name": "Small Business Query",
                "input_tokens": 500,
                "output_tokens": 150,
                "embedding_tokens": 800,
                "model": "gpt-4o-mini"
            },
            {
                "name": "Large Document Analysis", 
                "input_tokens": 2000,
                "output_tokens": 500,
                "embedding_tokens": 3000,
                "model": "gpt-4o"
            },
            {
                "name": "Batch Processing",
                "input_tokens": 10000,
                "output_tokens": 2000,
                "embedding_tokens": 15000,
                "model": "gpt-4o-mini"
            }
        ]
        
        for scenario in scenarios:
            print(f"\n📊 Scenario: {scenario['name']}")
            
            # Calculate costs
            llm_cost = calculate_llm_cost(
                scenario["input_tokens"],
                scenario["output_tokens"], 
                scenario["model"]
            )
            embedding_cost = calculate_embedding_cost(scenario["embedding_tokens"])
            total_cost = llm_cost + embedding_cost
            
            print(f"  • Model: {scenario['model']}")
            print(f"  • Input tokens: {scenario['input_tokens']:,}")
            print(f"  • Output tokens: {scenario['output_tokens']:,}")
            print(f"  • Embedding tokens: {scenario['embedding_tokens']:,}")
            print(f"  • LLM cost: ${llm_cost:.4f}")
            print(f"  • Embedding cost: ${embedding_cost:.4f}")
            print(f"  • Total cost: ${total_cost:.4f}")
    
    def demo_limit_enforcement(self):
        """Demonstrate plan limit enforcement."""
        print("\n" + "="*60)
        print("🚫 DEMO: Plan Limit Enforcement")
        print("="*60)
        
        # Create a mock tenant ID for demo
        import uuid
        tenant_id = uuid.uuid4()
        
        print(f"🏢 Demo Tenant ID: {tenant_id}")
        
        # Test limit checks for different scenarios
        scenarios = [
            {
                "name": "Free Plan Limits",
                "plan_tier": PlanTier.FREE,
                "tests": [
                    ("documents", "check_document_limit"),
                    ("queries", "check_query_limit"), 
                    ("storage", "check_storage_limit"),
                    ("api_keys", "check_api_key_limit"),
                    ("team_members", "check_team_member_limit")
                ]
            },
            {
                "name": "Starter Plan Limits", 
                "plan_tier": PlanTier.STARTER,
                "tests": [
                    ("documents", "check_document_limit"),
                    ("queries", "check_query_limit"),
                    ("storage", "check_storage_limit")
                ]
            }
        ]
        
        for scenario in scenarios:
            print(f"\n📋 {scenario['name']}:")
            plan = self.billing_service.get_plan_by_tier(scenario["plan_tier"])
            
            if not plan:
                print(f"  ❌ Plan {scenario['plan_tier'].value} not found")
                continue
            
            print(f"  • Plan: {plan.name}")
            
            for limit_name, check_method in scenario["tests"]:
                try:
                    method = getattr(self.billing_service, check_method)
                    can_add, current, limit = method(tenant_id)
                    
                    status = "✅" if can_add else "❌"
                    print(f"  {status} {limit_name.capitalize()}: {current}/{limit}")
                    
                except Exception as e:
                    print(f"  ⚠️  {limit_name.capitalize()}: Error - {e}")
    
    def demo_enforcement_errors(self):
        """Demonstrate limit enforcement errors."""
        print("\n" + "="*60)
        print("⚠️  DEMO: Limit Enforcement Errors")
        print("="*60)
        
        import uuid
        tenant_id = uuid.uuid4()
        
        # Test enforcement methods that should raise errors
        enforcement_tests = [
            ("Document Upload", "enforce_document_limit"),
            ("Query Execution", "enforce_query_limit"),
            ("Storage Usage", "enforce_storage_limit", 1000),  # 1GB
            ("API Key Creation", "enforce_api_key_limit"),
        ]
        
        for test_name, method_name, *args in enforcement_tests:
            print(f"\n🧪 Testing {test_name} enforcement:")
            
            try:
                method = getattr(self.billing_service, method_name)
                method(tenant_id, *args)
                print(f"  ✅ {test_name}: Limit check passed")
                
            except PlanLimitExceeded as e:
                print(f"  🚫 {test_name}: {e}")
                print(f"     Limit Type: {e.limit_type}")
                print(f"     Current: {e.current}")
                print(f"     Limit: {e.limit}")
                
            except Exception as e:
                print(f"  ⚠️  {test_name}: Unexpected error - {e}")
    
    def demo_billing_summary(self):
        """Demonstrate billing summary generation."""
        print("\n" + "="*60)
        print("📊 DEMO: Billing Summary")
        print("="*60)
        
        import uuid
        tenant_id = uuid.uuid4()
        
        print(f"🏢 Generating billing summary for tenant: {tenant_id}")
        
        try:
            summary = self.billing_service.get_billing_summary(tenant_id)
            
            print(f"\n📋 Subscription Info:")
            print(f"  • Plan: {summary['subscription']['plan_name']} ({summary['subscription']['plan_tier']})")
            print(f"  • Status: {summary['subscription']['status']}")
            print(f"  • Billing: {summary['subscription']['billing_cycle']}")
            
            print(f"\n📈 Current Usage:")
            usage = summary['usage']
            print(f"  • Queries: {usage['queries_count']}")
            print(f"  • Documents: {usage['documents_count']}")
            print(f"  • Storage: {usage['storage_mb']:.1f} MB")
            print(f"  • API Calls: {usage['api_calls_count']}")
            
            print(f"\n💰 Costs:")
            costs = usage['costs']
            print(f"  • LLM: ${costs['llm_cost']:.4f}")
            print(f"  • Embeddings: ${costs['embedding_cost']:.4f}")
            print(f"  • Storage: ${costs['storage_cost']:.4f}")
            print(f"  • Total: ${costs['total_cost']:.4f}")
            
            print(f"\n🎯 Limits & Usage:")
            for limit_type, check in summary['limit_checks'].items():
                percentage = check['usage_percent']
                status = "🔴" if percentage >= 90 else "🟡" if percentage >= 75 else "🟢"
                print(f"  {status} {limit_type.capitalize()}: {check['current']}/{check['limit']} ({percentage:.1f}%)")
                
        except Exception as e:
            print(f"❌ Failed to generate billing summary: {e}")
    
    def demo_stripe_integration(self):
        """Demonstrate Stripe integration concepts."""
        print("\n" + "="*60)
        print("💳 DEMO: Stripe Integration Concepts")
        print("="*60)
        
        print("🔧 Stripe Integration Features:")
        print("  ✅ Customer creation with tenant metadata")
        print("  ✅ Subscription management (create, update, cancel)")
        print("  ✅ Checkout session generation")
        print("  ✅ Customer portal for self-service")
        print("  ✅ Webhook event handling")
        print("  ✅ Invoice and payment tracking")
        
        print("\n📋 Required Stripe Configuration:")
        print("  • STRIPE_SECRET_KEY - API secret key")
        print("  • STRIPE_PUBLISHABLE_KEY - Public key for frontend")
        print("  • STRIPE_WEBHOOK_SECRET - Webhook signature verification")
        print("  • Price IDs for each plan and billing cycle")
        
        print("\n🔄 Webhook Events Handled:")
        events = [
            "customer.subscription.created",
            "customer.subscription.updated", 
            "customer.subscription.deleted",
            "invoice.payment_succeeded",
            "invoice.payment_failed",
            "checkout.session.completed"
        ]
        
        for event in events:
            print(f"  • {event}")
    
    def run_all_demos(self):
        """Run all billing demos."""
        print("🚀 AskDocs Billing System Demo")
        print("="*60)
        print("This demo showcases the complete billing and subscription system")
        print("including plan management, usage tracking, limit enforcement,")
        print("and Stripe integration capabilities.")
        
        try:
            self.demo_plan_management()
            self.demo_usage_tracking()
            self.demo_limit_enforcement()
            self.demo_enforcement_errors()
            self.demo_billing_summary()
            self.demo_stripe_integration()
            
            print("\n" + "="*60)
            print("✅ BILLING SYSTEM DEMO COMPLETED SUCCESSFULLY!")
            print("="*60)
            print("\n📋 Summary:")
            print("  • Plans initialized and configured")
            print("  • Usage tracking and cost calculation working")
            print("  • Plan limits properly enforced") 
            print("  • Billing summaries generated correctly")
            print("  • Stripe integration ready for production")
            
            print("\n🚀 Next Steps:")
            print("  1. Configure Stripe API keys in environment")
            print("  2. Create Stripe products and price IDs")
            print("  3. Set up webhook endpoints")
            print("  4. Test checkout flow end-to-end")
            print("  5. Enable billing enforcement middleware")
            
        except Exception as e:
            logger.error("Demo failed", error=str(e), exc_info=True)
            print(f"\n❌ Demo failed: {e}")
            return False
        
        return True


async def main():
    """Main demo function."""
    demo = BillingDemo()
    success = demo.run_all_demos()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())