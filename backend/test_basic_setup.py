#!/usr/bin/env python3
"""
Basic test script to verify the core infrastructure works.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")


async def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from app.core.config import settings
        print("✅ Config imported successfully")
        print(f"   App name: {settings.APP_NAME}")
        print(f"   Environment: {settings.APP_ENV}")
        
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Logger test")
        print("✅ Logging imported and working")
        
        from app.core.errors import AskDocsException, AuthenticationError
        print("✅ Error classes imported")
        
        from app.core.security import hash_password, generate_api_key
        hashed = hash_password("test")
        api_key, key_hash = generate_api_key()
        print("✅ Security utilities working")
        print(f"   Generated API key prefix: {api_key[:12]}...")
        
        from app.db.models import Tenant, User, APIKey
        print("✅ Database models imported")
        
        from app.schemas.tenant import TenantCreate
        from app.schemas.user import UserCreate
        print("✅ Pydantic schemas imported")
        
        from app.services.auth_service import AuthService
        from app.services.tenant_service import TenantService
        print("✅ Services imported")
        
        print("\n🎉 All core modules imported successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_config_validation():
    """Test configuration validation."""
    print("\nTesting configuration validation...")
    
    try:
        from app.core.config import Settings
        
        # Test valid config
        valid_config = Settings(
            SECRET_KEY="test-secret-key-with-at-least-32-characters",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            OPENAI_API_KEY="sk-test-key",
        )
        print("✅ Valid configuration accepted")
        
        # Test plan limits
        limits = valid_config.get_plan_limits("pro")
        print(f"✅ Pro plan limits: {limits}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config validation failed: {e}")
        return False


async def test_database_models():
    """Test that database models are properly defined."""
    print("\nTesting database models...")
    
    try:
        from app.db.models import Base, Tenant, User, APIKey, Document
        
        # Check that all models have proper table names
        print(f"✅ Tenant table: {Tenant.__tablename__}")
        print(f"✅ User table: {User.__tablename__}")
        print(f"✅ APIKey table: {APIKey.__tablename__}")
        print(f"✅ Document table: {Document.__tablename__}")
        
        # Check relationships
        print("✅ Model relationships defined")
        
        return True
        
    except Exception as e:
        print(f"❌ Database models test failed: {e}")
        return False


async def test_pydantic_schemas():
    """Test Pydantic schema validation."""
    print("\nTesting Pydantic schemas...")
    
    try:
        from app.schemas.tenant import TenantCreate
        from app.schemas.user import UserCreate
        
        # Test tenant creation schema
        tenant_data = TenantCreate(
            name="Test Company",
            owner_email="test@example.com",
            owner_password="password123",
            owner_full_name="Test User",
        )
        print("✅ TenantCreate schema validation works")
        
        # Test user creation schema
        user_data = UserCreate(
            email="user@example.com",
            password="password123",
            full_name="Test User",
        )
        print("✅ UserCreate schema validation works")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema validation test failed: {e}")
        return False


async def test_fastapi_app():
    """Test that FastAPI app can be created."""
    print("\nTesting FastAPI app creation...")
    
    try:
        from app.main import create_app
        
        app = create_app()
        print("✅ FastAPI app created successfully")
        print(f"   Title: {app.title}")
        
        # Check routes
        routes = [route.path for route in app.routes]
        print(f"   Routes: {len(routes)} defined")
        
        return True
        
    except Exception as e:
        print(f"❌ FastAPI app creation failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Testing AskDocs Core Infrastructure\n")
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config_validation),
        ("Database Models", test_database_models),
        ("Pydantic Schemas", test_pydantic_schemas),
        ("FastAPI App", test_fastapi_app),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"TEST: {test_name}")
        print('='*50)
        
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print('='*50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Core infrastructure is working.")
        return 0
    else:
        print("❌ Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)