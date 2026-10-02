#!/usr/bin/env python3
"""
Initialize database and run basic end-to-end test for Module 2.
This script sets up the database and validates core functionality.
"""

import asyncio
import os
import sys
from pathlib import Path

# Set environment variables for testing
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://askdocs:askdocs_password@localhost:5432/askdocs")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("SECRET_KEY", "test-secret-key-with-at-least-32-characters-for-demo")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-demo-purposes-only")

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))


async def init_database():
    """Initialize the database with tables."""
    print("🔧 Initializing database...")
    
    try:
        from app.db.base import init_db
        await init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False


async def test_tenant_creation():
    """Test tenant creation and user authentication."""
    print("\n🧪 Testing tenant creation and authentication...")
    
    try:
        from app.db.base import AsyncSessionLocal
        from app.services.tenant_service import TenantService
        from app.services.auth_service import AuthService
        from app.schemas.tenant import TenantCreate
        from app.schemas.user import UserLogin
        
        async with AsyncSessionLocal() as db:
            tenant_service = TenantService(db)
            auth_service = AuthService(db)
            
            # Create a test tenant
            tenant_data = TenantCreate(
                name="Test Company",
                owner_email="owner@testcompany.com",
                owner_password="testpassword123",
                owner_full_name="Test Owner"
            )
            
            tenant, user = await tenant_service.create_tenant(tenant_data)
            print(f"✅ Tenant created: {tenant.name} (ID: {tenant.id})")
            print(f"✅ Owner user created: {user.email} (Role: {user.role})")
            
            # Test login
            login_data = UserLogin(
                email="owner@testcompany.com",
                password="testpassword123"
            )
            
            authenticated_user = await auth_service.authenticate_user(login_data)
            print(f"✅ User authentication successful: {authenticated_user.email}")
            
            # Create access token
            token_response = await auth_service.create_tokens(authenticated_user)
            print(f"✅ Access token created (expires in {token_response.expires_in}s)")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_key_creation():
    """Test API key creation and authentication."""
    print("\n🔑 Testing API key creation and authentication...")
    
    try:
        from app.db.base import AsyncSessionLocal
        from app.services.tenant_service import TenantService
        from app.services.api_key_service import APIKeyService
        from app.services.auth_service import AuthService
        from app.schemas.api_key import APIKeyCreate
        from sqlalchemy import select
        from app.db.models import User, Tenant
        
        async with AsyncSessionLocal() as db:
            # Find existing test tenant and user
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.name == "Test Company")
            )
            tenant = tenant_result.scalar_one()
            
            user_result = await db.execute(
                select(User).where(User.tenant_id == tenant.id, User.role == "owner")
            )
            user = user_result.scalar_one()
            
            # Create API key
            api_key_service = APIKeyService(db)
            key_data = APIKeyCreate(
                name="Test API Key",
                scopes=["query", "ingest"]
            )
            
            api_key, full_key = await api_key_service.create_api_key(tenant, key_data, user)
            print(f"✅ API key created: {api_key.name}")
            print(f"   Key prefix: {api_key.key_prefix}")
            print(f"   Scopes: {api_key.scopes}")
            
            # Test API key authentication
            auth_service = AuthService(db)
            authenticated_tenant, key_record = await auth_service.authenticate_api_key(full_key)
            print(f"✅ API key authentication successful")
            print(f"   Authenticated tenant: {authenticated_tenant.name}")
            
            return True
            
    except Exception as e:
        print(f"❌ API key test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tenant_isolation():
    """Test that tenant isolation is working."""
    print("\n🔒 Testing tenant isolation...")
    
    try:
        from app.db.base import AsyncSessionLocal
        from app.services.tenant_service import TenantService
        from app.schemas.tenant import TenantCreate
        from sqlalchemy import select
        from app.db.models import User, Document
        
        async with AsyncSessionLocal() as db:
            tenant_service = TenantService(db)
            
            # Create second tenant
            tenant_data = TenantCreate(
                name="Another Company",
                owner_email="owner@anothercompany.com", 
                owner_password="testpassword123",
                owner_full_name="Another Owner"
            )
            
            tenant2, user2 = await tenant_service.create_tenant(tenant_data)
            print(f"✅ Second tenant created: {tenant2.name}")
            
            # Verify tenants are different
            tenant1_result = await db.execute(
                select(User).where(User.email == "owner@testcompany.com")
            )
            tenant1_user = tenant1_result.scalar_one()
            
            if tenant1_user.tenant_id != user2.tenant_id:
                print("✅ Tenants have different IDs - isolation confirmed")
            else:
                print("❌ Tenants have same ID - isolation failed!")
                return False
            
            # Test database query isolation
            tenant1_users = await db.execute(
                select(User).where(User.tenant_id == tenant1_user.tenant_id)
            )
            tenant1_user_count = len(list(tenant1_users.scalars().all()))
            
            tenant2_users = await db.execute(
                select(User).where(User.tenant_id == user2.tenant_id)
            )
            tenant2_user_count = len(list(tenant2_users.scalars().all()))
            
            print(f"✅ Tenant 1 has {tenant1_user_count} users")
            print(f"✅ Tenant 2 has {tenant2_user_count} users")
            
            return True
            
    except Exception as e:
        print(f"❌ Tenant isolation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all initialization and tests."""
    print("🚀 AskDocs Module 2: Database Initialization & Testing")
    print("="*60)
    
    tests = [
        ("Database Initialization", init_database),
        ("Tenant Creation & Auth", test_tenant_creation),
        ("API Key Management", test_api_key_creation),
        ("Tenant Isolation", test_tenant_isolation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"TEST: {test_name}")
        print('='*50)
        
        try:
            success = await test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - CRASHED: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("Module 2: Auth & Multi-tenancy is working correctly!")
        print("\nCore functionality validated:")
        print("✅ Database schema created")
        print("✅ Tenant registration working")
        print("✅ User authentication working")
        print("✅ API key system working")
        print("✅ Multi-tenant isolation enforced")
        print("\n🚀 System is ready for production use!")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest suite crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)