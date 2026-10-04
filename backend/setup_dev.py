#!/usr/bin/env python3
"""
Development setup script for AskDocs backend.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and print output."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False, check=check)
    return result


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor < 11:
        print("❌ Python 3.11+ is required")
        return False
    
    print("✅ Python version is compatible")
    return True


def install_dependencies():
    """Install Python dependencies."""
    print("\n" + "="*50)
    print("INSTALLING DEPENDENCIES")
    print("="*50)
    
    # Install requirements
    try:
        run_command("pip install -r requirements.txt")
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def create_env_file():
    """Create .env file from template."""
    print("\n" + "="*50)
    print("CREATING ENVIRONMENT FILE")
    print("="*50)
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print(f"✅ {env_file} already exists")
        return True
    
    if not env_example.exists():
        print(f"❌ {env_example} not found")
        return False
    
    # Copy example to .env
    with open(env_example, 'r') as src, open(env_file, 'w') as dst:
        dst.write(src.read())
    
    print(f"✅ Created {env_file} from template")
    print("⚠️  Please edit .env with your actual configuration values")
    return True


def test_basic_setup():
    """Test basic setup."""
    print("\n" + "="*50)
    print("TESTING BASIC SETUP")
    print("="*50)
    
    try:
        result = run_command("python test_basic_setup.py", check=False)
        if result.returncode == 0:
            print("✅ Basic setup test passed")
            return True
        else:
            print("❌ Basic setup test failed")
            return False
    except Exception as e:
        print(f"❌ Could not run basic setup test: {e}")
        return False


def show_next_steps():
    """Show next steps."""
    print("\n" + "="*50)
    print("NEXT STEPS")
    print("="*50)
    
    print("1. Edit .env file with your configuration:")
    print("   - Set DATABASE_URL for your PostgreSQL database")
    print("   - Set REDIS_URL for your Redis instance")
    print("   - Set QDRANT_URL for your Qdrant instance")
    print("   - Set OPENAI_API_KEY for OpenAI access")
    print("   - Set SECRET_KEY (generate a secure 32+ character string)")
    
    print("\n2. Start services with Docker:")
    print("   docker compose up -d")
    
    print("\n3. Run database migrations:")
    print("   alembic upgrade head")
    
    print("\n4. Start the development server:")
    print("   make dev")
    print("   # or")
    print("   uvicorn app.main:app --reload")
    
    print("\n5. Test the API:")
    print("   curl http://localhost:8000/health")
    print("   curl http://localhost:8000/api/v1/health/db")
    
    print("\n6. Run the test suite:")
    print("   make test")
    print("   # or")
    print("   pytest")


def main():
    """Main setup function."""
    print("🚀 AskDocs Backend Development Setup")
    print("="*50)
    
    # Check Python version
    if not check_python_version():
        return 1
    
    steps = [
        ("Installing dependencies", install_dependencies),
        ("Creating environment file", create_env_file),
        ("Testing basic setup", test_basic_setup),
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔧 {step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            return 1
    
    print("\n🎉 Development setup completed successfully!")
    show_next_steps()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

