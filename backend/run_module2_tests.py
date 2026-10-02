#!/usr/bin/env python3
"""
Module 2 Test Runner: Comprehensive validation of Auth & Multi-tenancy
This script runs all tests to validate Module 2 is production-ready.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"RUNNING: {description}")
    print('='*60)
    print(f"Command: {cmd}")
    print()
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=False, 
            check=True,
            text=True
        )
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Exit code: {e.returncode}")
        return False


def main():
    """Run all Module 2 validation tests."""
    print("🧪 AskDocs Module 2: Comprehensive Test Suite")
    print("Testing Auth & Multi-tenancy Implementation")
    print("="*60)
    
    # Change to backend directory
    original_dir = Path.cwd()
    backend_dir = Path(__file__).parent
    
    try:
        import os
        os.chdir(backend_dir)
        
        tests = [
            # Core functionality tests
            ("python test_basic_setup.py", "Core Infrastructure Setup"),
            
            # Authentication tests
            ("pytest tests/test_auth.py -v", "Authentication System"),
            
            # Tenant isolation tests (CRITICAL)
            ("pytest tests/test_tenant_isolation.py -v", "Tenant Isolation (CRITICAL)"),
            
            # API key tests
            ("pytest tests/test_api_keys.py -v", "API Key Management"),
            
            # User management tests
            ("pytest tests/test_user_management.py -v", "User Management"),
            
            # Tenant management tests
            ("pytest tests/test_tenant_management.py -v", "Tenant Management"),
            
            # Configuration tests
            ("pytest tests/test_config.py -v", "Configuration Validation"),
            
            # Health check tests
            ("pytest tests/test_health.py -v", "Health Check Endpoints"),
            
            # Full test suite with coverage
            ("pytest --cov=app --cov-report=term-missing --cov-fail-under=80", "Full Test Suite with Coverage"),
            
            # Code quality checks
            ("ruff check app", "Code Linting (Ruff)"),
            ("mypy app --ignore-missing-imports", "Type Checking (MyPy)"),
        ]
        
        passed = 0
        total = len(tests)
        failed_tests = []
        
        start_time = time.time()
        
        for cmd, description in tests:
            success = run_command(cmd, description)
            if success:
                passed += 1
            else:
                failed_tests.append(description)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print('='*60)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Duration: {duration:.2f} seconds")
        
        if failed_tests:
            print(f"\nFailed Tests:")
            for test in failed_tests:
                print(f"❌ {test}")
        
        print(f"\nOverall Result: {'✅ PASSED' if passed == total else '❌ FAILED'}")
        
        if passed == total:
            print("\n🎉 MODULE 2 VALIDATION SUCCESSFUL!")
            print("Auth & Multi-tenancy implementation is production-ready!")
            print("\nKey validations completed:")
            print("✅ Multi-tenant data isolation enforced")
            print("✅ JWT and API key authentication working")
            print("✅ Role-based access control implemented")
            print("✅ Tenant and user management functional")
            print("✅ Code quality standards met")
            print("✅ Test coverage above 80%")
            print("\n🚀 Ready to proceed to Module 3: Document Ingestion")
            return 0
        else:
            print("\n❌ MODULE 2 VALIDATION FAILED!")
            print("Please fix the failing tests before proceeding.")
            return 1
    
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)