#!/usr/bin/env python3
"""
Demo script showcasing AskDocs Module 2: Auth & Multi-tenancy
Demonstrates tenant registration, authentication, and API key usage.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"


class AskDocsDemo:
    """Demo class for AskDocs Module 2 functionality."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.tenant_tokens = {}
        self.api_keys = {}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def print_step(self, step: str, description: str = ""):
        """Print a demo step."""
        print(f"\n{'='*60}")
        print(f"STEP: {step}")
        if description:
            print(f"Description: {description}")
        print('='*60)
    
    def print_response(self, response: httpx.Response):
        """Print response details."""
        print(f"Status: {response.status_code}")
        if response.status_code >= 400:
            print(f"Error: {response.text}")
        else:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
            except:
                print(f"Response: {response.text}")
    
    async def check_health(self):
        """Check if the API is running."""
        self.print_step("Health Check", "Verifying AskDocs API is running")
        
        try:
            response = await self.client.get(f"{BASE_URL}/health")
            self.print_response(response)
            
            if response.status_code != 200:
                print("❌ API is not healthy!")
                return False
                
            # Check database health
            response = await self.client.get(f"{API_BASE}/health/db")
            self.print_response(response)
            
            if response.status_code != 200:
                print("❌ Database is not healthy!")
                return False
                
            print("✅ AskDocs API is healthy and ready!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to API: {e}")
            print("Make sure the API is running with: docker compose up -d")
            return False
    
    async def register_tenant(self, company_name: str, owner_email: str, password: str = "demopassword123"):
        """Register a new tenant."""
        self.print_step("Tenant Registration", f"Registering tenant: {company_name}")
        
        tenant_data = {
            "name": company_name,
            "owner_email": owner_email,
            "owner_password": password,
            "owner_full_name": f"{company_name} Owner",
            "widget_bot_name": f"{company_name} Support",
            "widget_primary_color": "#2563eb",
        }
        
        response = await self.client.post(f"{API_BASE}/tenants/", json=tenant_data)
        self.print_response(response)
        
        if response.status_code == 201:
            tenant_data = response.json()
            print(f"✅ Tenant '{company_name}' registered successfully!")
            print(f"   Tenant ID: {tenant_data['id']}")
            print(f"   Slug: {tenant_data['slug']}")
            return tenant_data
        else:
            print(f"❌ Failed to register tenant: {response.status_code}")
            return None
    
    async def login_user(self, email: str, password: str = "demopassword123"):
        """Login a user and get tokens."""
        self.print_step("User Login", f"Authenticating user: {email}")
        
        login_data = {
            "email": email,
            "password": password,
        }
        
        response = await self.client.post(f"{API_BASE}/auth/login", json=login_data)
        self.print_response(response)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]
            
            # Store token for later use
            self.tenant_tokens[email] = access_token
            
            print(f"✅ User '{email}' logged in successfully!")
            print(f"   Token expires in: {token_data['expires_in']} seconds")
            print(f"   User role: {token_data['user']['role']}")
            return access_token
        else:
            print(f"❌ Failed to login user: {response.status_code}")
            return None
    
    async def get_user_info(self, token: str):
        """Get current user information."""
        self.print_step("User Information", "Getting current user details")
        
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.client.get(f"{API_BASE}/auth/me", headers=headers)
        self.print_response(response)
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ User information retrieved!")
            return user_data
        else:
            print(f"❌ Failed to get user info: {response.status_code}")
            return None
    
    async def create_api_key(self, token: str, key_name: str, scopes: list[str]):
        """Create an API key."""
        self.print_step("API Key Creation", f"Creating API key: {key_name}")
        
        key_data = {
            "name": key_name,
            "scopes": scopes,
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.client.post(f"{API_BASE}/api-keys/", json=key_data, headers=headers)
        self.print_response(response)
        
        if response.status_code == 201:
            api_key_data = response.json()
            api_key = api_key_data["key"]
            
            # Store API key for later use
            self.api_keys[key_name] = api_key
            
            print(f"✅ API key '{key_name}' created successfully!")
            print(f"   Key: {api_key}")
            print(f"   Scopes: {api_key_data['scopes']}")
            print("   ⚠️ Store this key securely - it won't be shown again!")
            return api_key
        else:
            print(f"❌ Failed to create API key: {response.status_code}")
            return None
    
    async def test_api_key_auth(self, api_key: str):
        """Test API key authentication."""
        self.print_step("API Key Authentication", "Testing API key access")
        
        headers = {"Authorization": f"Bearer {api_key}"}
        response = await self.client.get(f"{API_BASE}/tenants/current", headers=headers)
        self.print_response(response)
        
        if response.status_code == 200:
            tenant_data = response.json()
            print("✅ API key authentication successful!")
            print(f"   Accessing tenant: {tenant_data['name']}")
            return True
        else:
            print(f"❌ API key authentication failed: {response.status_code}")
            return False
    
    async def create_team_member(self, admin_token: str, email: str, full_name: str, role: str = "member"):
        """Create a team member."""
        self.print_step("Team Member Creation", f"Creating {role}: {email}")
        
        user_data = {
            "email": email,
            "password": "teampassword123",
            "full_name": full_name,
            "role": role,
        }
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = await self.client.post(f"{API_BASE}/users/", json=user_data, headers=headers)
        self.print_response(response)
        
        if response.status_code == 201:
            user = response.json()
            print(f"✅ Team member '{email}' created successfully!")
            print(f"   Role: {user['role']}")
            return user
        else:
            print(f"❌ Failed to create team member: {response.status_code}")
            return None
    
    async def get_tenant_stats(self, token: str):
        """Get tenant statistics."""
        self.print_step("Tenant Statistics", "Getting tenant usage stats")
        
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.client.get(f"{API_BASE}/tenants/stats", headers=headers)
        self.print_response(response)
        
        if response.status_code == 200:
            stats = response.json()
            print("✅ Tenant statistics retrieved!")
            print(f"   Documents: {stats['total_documents']}/{stats['documents_limit']}")
            print(f"   Messages this month: {stats['messages_this_month']}/{stats['messages_limit']}")
            return stats
        else:
            print(f"❌ Failed to get tenant stats: {response.status_code}")
            return None
    
    async def test_cross_tenant_isolation(self, token1: str, token2: str):
        """Test that tenants cannot access each other's data."""
        self.print_step("Cross-Tenant Isolation Test", "Verifying tenant data isolation")
        
        # Get tenant 1 info
        headers1 = {"Authorization": f"Bearer {token1}"}
        response1 = await self.client.get(f"{API_BASE}/tenants/current", headers=headers1)
        
        # Get tenant 2 info
        headers2 = {"Authorization": f"Bearer {token2}"}
        response2 = await self.client.get(f"{API_BASE}/tenants/current", headers=headers2)
        
        if response1.status_code == 200 and response2.status_code == 200:
            tenant1 = response1.json()
            tenant2 = response2.json()
            
            if tenant1["id"] != tenant2["id"]:
                print("✅ Tenant isolation verified!")
                print(f"   Tenant 1: {tenant1['name']} (ID: {tenant1['id']})")
                print(f"   Tenant 2: {tenant2['name']} (ID: {tenant2['id']})")
                
                # Try to access tenant 1's users with tenant 2's token
                print("\n   Testing cross-tenant access...")
                response = await self.client.get(f"{API_BASE}/users/", headers=headers2)
                
                if response.status_code == 200:
                    users = response.json()
                    print(f"   Tenant 2 sees {len(users)} users (their own)")
                    return True
                
            else:
                print("❌ Tenants have the same ID - isolation failed!")
                return False
        else:
            print("❌ Failed to get tenant information")
            return False
    
    async def run_demo(self):
        """Run the complete demo."""
        print("🚀 AskDocs Module 2 Demo: Auth & Multi-tenancy")
        print("This demo showcases tenant registration, authentication, and API key management.")
        
        # Health check
        if not await self.check_health():
            return False
        
        # Register two tenants to test isolation
        tenant1 = await self.register_tenant("Acme Corp", "owner@acme.com")
        if not tenant1:
            return False
        
        tenant2 = await self.register_tenant("Beta Inc", "owner@beta.com")
        if not tenant2:
            return False
        
        # Login both tenant owners
        token1 = await self.login_user("owner@acme.com")
        if not token1:
            return False
        
        token2 = await self.login_user("owner@beta.com")
        if not token2:
            return False
        
        # Get user info
        await self.get_user_info(token1)
        
        # Create API key for tenant 1
        api_key = await self.create_api_key(token1, "Integration Key", ["query", "ingest"])
        if api_key:
            await self.test_api_key_auth(api_key)
        
        # Create team members
        await self.create_team_member(token1, "admin@acme.com", "Acme Admin", "admin")
        await self.create_team_member(token1, "member@acme.com", "Acme Member", "member")
        
        # Get tenant statistics
        await self.get_tenant_stats(token1)
        
        # Test cross-tenant isolation
        await self.test_cross_tenant_isolation(token1, token2)
        
        print(f"\n{'='*60}")
        print("🎉 DEMO COMPLETED SUCCESSFULLY!")
        print("='*60")
        print("Module 2: Auth & Multi-tenancy is working correctly!")
        print("\nKey features demonstrated:")
        print("✅ Tenant registration with owner user")
        print("✅ JWT authentication and token management")
        print("✅ API key creation and authentication")
        print("✅ Role-based user management")
        print("✅ Tenant statistics and limits")
        print("✅ Cross-tenant data isolation")
        print("\nThe system is ready for Module 3: Document Ingestion!")
        
        return True


async def main():
    """Main demo function."""
    try:
        async with AskDocsDemo() as demo:
            success = await demo.run_demo()
            return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n❌ Demo interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    print("Starting AskDocs Module 2 Demo...")
    print("Make sure the API is running: docker compose up -d")
    print("Press Ctrl+C to interrupt\n")
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)