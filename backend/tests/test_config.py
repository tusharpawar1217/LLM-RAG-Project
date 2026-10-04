"""
Test configuration management.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_validation():
    """Test settings validation."""
    # Test valid configuration
    settings = Settings(
        SECRET_KEY="a-secret-key-with-at-least-32-characters",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        OPENAI_API_KEY="sk-test-key",
    )
    
    assert settings.APP_NAME == "AskDocs"
    assert settings.API_VERSION == "v1"
    assert settings.SECRET_KEY == "a-secret-key-with-at-least-32-characters"


def test_secret_key_validation():
    """Test secret key length validation."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            SECRET_KEY="short",  # Too short
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            OPENAI_API_KEY="sk-test-key",
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert "SECRET_KEY" in str(errors)


def test_database_url_validation():
    """Test database URL validation."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            SECRET_KEY="a-secret-key-with-at-least-32-characters",
            DATABASE_URL="invalid-url",  # Invalid URL
            OPENAI_API_KEY="sk-test-key",
        )
    
    errors = exc_info.value.errors()
    assert len(errors) > 0


def test_cors_origins_parsing():
    """Test CORS origins parsing from string."""
    settings = Settings(
        SECRET_KEY="a-secret-key-with-at-least-32-characters",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        OPENAI_API_KEY="sk-test-key",
        CORS_ORIGINS="http://localhost:3000,https://app.example.com",
    )
    
    expected = ["http://localhost:3000", "https://app.example.com"]
    assert settings.CORS_ORIGINS == expected


def test_plan_limits():
    """Test plan limits getter."""
    settings = Settings(
        SECRET_KEY="a-secret-key-with-at-least-32-characters",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
        OPENAI_API_KEY="sk-test-key",
    )
    
    starter_limits = settings.get_plan_limits("starter")
    assert starter_limits["max_documents"] == 50
    assert starter_limits["max_messages"] == 1000
    
    pro_limits = settings.get_plan_limits("pro")
    assert pro_limits["max_documents"] == 500
    assert pro_limits["max_messages"] == 10000
    
    # Unknown tier should return starter limits
    unknown_limits = settings.get_plan_limits("unknown")
    assert unknown_limits == starter_limits

