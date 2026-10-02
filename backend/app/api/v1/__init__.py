"""API v1 package."""

from fastapi import APIRouter

from app.api.v1 import api_keys, auth, billing, documents, health, monitoring, query, tenants, users

router = APIRouter()

# Include routers
router.include_router(health.router, tags=["health"])
router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(query.router, prefix="/query", tags=["query"])
router.include_router(billing.router, prefix="/billing", tags=["billing"])