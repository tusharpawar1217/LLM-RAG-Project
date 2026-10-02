"""Initialize billing plans in database."""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.billing_config import PLAN_CONFIGS
from app.models.billing import Plan, PlanTier
from app.core.logging import get_logger

logger = get_logger(__name__)


def init_plans(db: Session) -> None:
    """Initialize subscription plans in database."""
    
    for plan_tier, config in PLAN_CONFIGS.items():
        # Check if plan already exists
        existing_plan = db.query(Plan).filter(Plan.tier == plan_tier).first()
        
        if existing_plan:
            # Update existing plan
            existing_plan.name = config["name"]
            existing_plan.description = config.get("description")
            existing_plan.price_monthly = config["price_monthly"]
            existing_plan.price_yearly = config["price_yearly"]
            existing_plan.max_documents = config["max_documents"]
            existing_plan.max_queries_per_month = config["max_queries_per_month"]
            existing_plan.max_storage_mb = config["max_storage_mb"]
            existing_plan.max_api_keys = config["max_api_keys"]
            existing_plan.max_team_members = config["max_team_members"]
            existing_plan.features = config["features"]
            existing_plan.is_popular = config["is_popular"]
            existing_plan.sort_order = config["sort_order"]
            existing_plan.stripe_price_id = config.get("stripe_price_id")
            existing_plan.is_active = True
            
            logger.info(f"Updated plan: {plan_tier.value}")
        else:
            # Create new plan
            new_plan = Plan(
                tier=plan_tier,
                name=config["name"],
                description=config.get("description"),
                price_monthly=config["price_monthly"],
                price_yearly=config["price_yearly"],
                max_documents=config["max_documents"],
                max_queries_per_month=config["max_queries_per_month"],
                max_storage_mb=config["max_storage_mb"],
                max_api_keys=config["max_api_keys"],
                max_team_members=config["max_team_members"],
                features=config["features"],
                is_popular=config["is_popular"],
                sort_order=config["sort_order"],
                stripe_price_id=config.get("stripe_price_id"),
                is_active=True
            )
            
            db.add(new_plan)
            logger.info(f"Created plan: {plan_tier.value}")
    
    db.commit()
    logger.info("Billing plans initialized successfully")


def main():
    """Main function to initialize plans."""
    db = SessionLocal()
    try:
        init_plans(db)
        print("✅ Billing plans initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize billing plans: {e}")
        logger.error(f"Failed to initialize billing plans: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()