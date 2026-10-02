"""
Security utilities for password hashing, API key generation, and JWT tokens.
"""

import secrets
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import AuthenticationError

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_hash) where:
        - full_key: The complete key to show to the user once
        - key_hash: Hashed version to store in database
    """
    # Generate random key
    raw_key = secrets.token_urlsafe(settings.API_KEY_LENGTH)
    full_key = f"{settings.API_KEY_PREFIX}{raw_key}"
    
    # Hash for storage
    key_hash = pwd_context.hash(full_key)
    
    return full_key, key_hash


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return pwd_context.verify(plain_key, hashed_key)


def get_key_prefix(full_key: str) -> str:
    """Extract display prefix from API key (first 8 characters)."""
    return full_key[:min(8, len(full_key))]


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        subject: The subject of the token (usually user_id)
        expires_delta: Optional expiration time delta
        additional_claims: Optional additional claims to include
        
    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
    }
    
    if additional_claims:
        to_encode.update(additional_claims)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_refresh_token(subject: str) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        subject: The subject of the token (usually user_id)
        
    Returns:
        Encoded JWT refresh token
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token to decode
        
    Returns:
        Decoded token payload
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def get_token_subject(token: str) -> str:
    """
    Extract subject from JWT token.
    
    Args:
        token: The JWT token
        
    Returns:
        Token subject (user_id)
        
    Raises:
        AuthenticationError: If token is invalid
    """
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Token missing subject")
    return subject


def generate_tenant_slug(name: str) -> str:
    """
    Generate a URL-safe slug from tenant name.
    
    Args:
        name: Tenant name
        
    Returns:
        URL-safe slug
    """
    # Convert to lowercase and replace spaces/special chars
    slug = name.lower().strip()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)
    
    # Remove consecutive dashes
    while "--" in slug:
        slug = slug.replace("--", "-")
    
    # Remove leading/trailing dashes
    slug = slug.strip("-")
    
    # Add random suffix to ensure uniqueness
    random_suffix = secrets.token_hex(4)
    return f"{slug}-{random_suffix}"


def generate_external_id() -> str:
    """Generate a unique external ID for conversations/resources."""
    return secrets.token_urlsafe(16)
