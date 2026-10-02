"""Billing configuration and plan definitions."""

from typing import List, Dict, Any
from app.models.billing import PlanTier

# Plan configurations
PLAN_CONFIGS = {
    PlanTier.FREE: {
        "name": "Free",
        "description": "Perfect for trying out AskDocs",
        "price_monthly": 0,
        "price_yearly": 0,
        "max_documents": 10,
        "max_queries_per_month": 100,
        "max_storage_mb": 100,  # 100 MB
        "max_api_keys": 1,
        "max_team_members": 1,
        "features": [
            "Up to 10 documents",
            "100 queries per month", 
            "100MB storage",
            "Basic support"
        ],
        "is_popular": False,
        "sort_order": 0,
        "stripe_price_id": None
    },
    
    PlanTier.STARTER: {
        "name": "Starter",
        "description": "Great for small businesses getting started",
        "price_monthly": 29,
        "price_yearly": 290,  # ~17% discount
        "max_documents": 100,
        "max_queries_per_month": 1000,
        "max_storage_mb": 1024,  # 1 GB
        "max_api_keys": 3,
        "max_team_members": 3,
        "features": [
            "Up to 100 documents",
            "1,000 queries per month",
            "1GB storage",
            "3 team members",
            "3 API keys",
            "Email support",
            "Custom branding"
        ],
        "is_popular": False,
        "sort_order": 1,
        "stripe_price_id": "price_starter_monthly"  # Replace with actual Stripe price ID
    },
    
    PlanTier.PROFESSIONAL: {
        "name": "Professional", 
        "description": "Perfect for growing businesses with higher volume needs",
        "price_monthly": 99,
        "price_yearly": 990,  # ~17% discount
        "max_documents": 1000,
        "max_queries_per_month": 10000,
        "max_storage_mb": 10240,  # 10 GB
        "max_api_keys": 10,
        "max_team_members": 10,
        "features": [
            "Up to 1,000 documents",
            "10,000 queries per month",
            "10GB storage",
            "10 team members",
            "10 API keys",
            "Priority support",
            "Custom branding",
            "Advanced analytics",
            "API access",
            "SSO integration"
        ],
        "is_popular": True,
        "sort_order": 2,
        "stripe_price_id": "price_professional_monthly"  # Replace with actual Stripe price ID
    },
    
    PlanTier.ENTERPRISE: {
        "name": "Enterprise",
        "description": "For large organizations with custom requirements",
        "price_monthly": 299,
        "price_yearly": 2990,  # ~17% discount
        "max_documents": -1,  # Unlimited
        "max_queries_per_month": -1,  # Unlimited
        "max_storage_mb": -1,  # Unlimited
        "max_api_keys": -1,  # Unlimited
        "max_team_members": -1,  # Unlimited
        "features": [
            "Unlimited documents",
            "Unlimited queries",
            "Unlimited storage",
            "Unlimited team members",
            "Unlimited API keys",
            "Dedicated support",
            "Custom branding",
            "Advanced analytics",
            "API access",
            "SSO integration",
            "Custom integrations",
            "SLA guarantee",
            "On-premise deployment option"
        ],
        "is_popular": False,
        "sort_order": 3,
        "stripe_price_id": "price_enterprise_monthly"  # Replace with actual Stripe price ID
    }
}

# Feature flags by plan
PLAN_FEATURES = {
    PlanTier.FREE: {
        "custom_branding": False,
        "api_access": False,
        "advanced_analytics": False,
        "sso_integration": False,
        "priority_support": False,
        "dedicated_support": False,
        "white_label": False,
        "custom_integrations": False,
        "sla_guarantee": False,
        "on_premise": False
    },
    
    PlanTier.STARTER: {
        "custom_branding": True,
        "api_access": True,
        "advanced_analytics": False,
        "sso_integration": False,
        "priority_support": False,
        "dedicated_support": False,
        "white_label": False,
        "custom_integrations": False,
        "sla_guarantee": False,
        "on_premise": False
    },
    
    PlanTier.PROFESSIONAL: {
        "custom_branding": True,
        "api_access": True,
        "advanced_analytics": True,
        "sso_integration": True,
        "priority_support": True,
        "dedicated_support": False,
        "white_label": True,
        "custom_integrations": False,
        "sla_guarantee": False,
        "on_premise": False
    },
    
    PlanTier.ENTERPRISE: {
        "custom_branding": True,
        "api_access": True,
        "advanced_analytics": True,
        "sso_integration": True,
        "priority_support": True,
        "dedicated_support": True,
        "white_label": True,
        "custom_integrations": True,
        "sla_guarantee": True,
        "on_premise": True
    }
}

# Cost calculations (for usage tracking)
COST_RATES = {
    # OpenAI pricing (approximate, update with actual rates)
    "embedding_cost_per_1k_tokens": 0.0001,  # $0.0001 per 1K tokens
    "gpt4o_mini_cost_per_1k_input_tokens": 0.00015,  # $0.15 per 1M input tokens
    "gpt4o_mini_cost_per_1k_output_tokens": 0.0006,  # $0.60 per 1M output tokens
    "gpt4o_cost_per_1k_input_tokens": 0.005,  # $5.00 per 1M input tokens
    "gpt4o_cost_per_1k_output_tokens": 0.015,  # $15.00 per 1M output tokens
    
    # Storage costs (simplified)
    "storage_cost_per_mb_per_month": 0.001,  # $0.001 per MB per month
    
    # Qdrant vector database costs (estimated)
    "vector_storage_cost_per_1k_vectors": 0.0001,  # $0.0001 per 1K vectors
}

# Trial periods by plan
TRIAL_DAYS = {
    PlanTier.FREE: 0,  # No trial needed
    PlanTier.STARTER: 14,
    PlanTier.PROFESSIONAL: 14,
    PlanTier.ENTERPRISE: 30  # Longer trial for enterprise
}

# Billing intervals
BILLING_INTERVALS = {
    "monthly": {
        "stripe_interval": "month",
        "discount_percent": 0
    },
    "yearly": {
        "stripe_interval": "year", 
        "discount_percent": 17  # ~17% discount for yearly billing
    }
}

# Webhook events we care about
IMPORTANT_WEBHOOK_EVENTS = [
    "customer.subscription.created",
    "customer.subscription.updated", 
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "invoice.created",
    "invoice.finalized",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "checkout.session.completed",
    "customer.created",
    "customer.updated"
]

# Grace periods for overages
OVERAGE_GRACE_PERIODS = {
    "queries": 100,  # Allow 100 extra queries before hard limit
    "storage_mb": 50,  # Allow 50MB extra storage before hard limit
    "documents": 5,  # Allow 5 extra documents before hard limit
}

def get_plan_config(plan_tier: PlanTier) -> Dict[str, Any]:
    """Get configuration for a specific plan."""
    return PLAN_CONFIGS.get(plan_tier, {})

def get_plan_features(plan_tier: PlanTier) -> Dict[str, bool]:
    """Get feature flags for a specific plan."""
    return PLAN_FEATURES.get(plan_tier, {})

def has_feature(plan_tier: PlanTier, feature_name: str) -> bool:
    """Check if a plan has a specific feature."""
    features = get_plan_features(plan_tier)
    return features.get(feature_name, False)

def calculate_embedding_cost(token_count: int) -> float:
    """Calculate embedding cost based on token count."""
    return (token_count / 1000) * COST_RATES["embedding_cost_per_1k_tokens"]

def calculate_llm_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o-mini") -> float:
    """Calculate LLM cost based on token counts and model."""
    if model == "gpt-4o-mini":
        input_cost = (input_tokens / 1000) * COST_RATES["gpt4o_mini_cost_per_1k_input_tokens"]
        output_cost = (output_tokens / 1000) * COST_RATES["gpt4o_mini_cost_per_1k_output_tokens"]
    elif model == "gpt-4o":
        input_cost = (input_tokens / 1000) * COST_RATES["gpt4o_cost_per_1k_input_tokens"]
        output_cost = (output_tokens / 1000) * COST_RATES["gpt4o_cost_per_1k_output_tokens"]
    else:
        # Default to gpt-4o-mini rates
        input_cost = (input_tokens / 1000) * COST_RATES["gpt4o_mini_cost_per_1k_input_tokens"]
        output_cost = (output_tokens / 1000) * COST_RATES["gpt4o_mini_cost_per_1k_output_tokens"]
    
    return input_cost + output_cost

def calculate_storage_cost(size_mb: float) -> float:
    """Calculate storage cost per month."""
    return size_mb * COST_RATES["storage_cost_per_mb_per_month"]