"""
Content hashing utilities for idempotent operations.
"""

import hashlib
from typing import Union


def compute_content_hash(content: Union[str, bytes]) -> str:
    """
    Compute SHA256 hash of content for idempotency.
    
    Args:
        content: Content to hash (string or bytes)
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    if isinstance(content, str):
        content_bytes = content.encode('utf-8')
    else:
        content_bytes = content
    
    return hashlib.sha256(content_bytes).hexdigest()


def compute_file_hash(file_content: bytes, filename: str = "") -> str:
    """
    Compute hash of file content including filename for uniqueness.
    
    Args:
        file_content: Raw file bytes
        filename: Original filename (optional)
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    hasher = hashlib.sha256()
    hasher.update(file_content)
    
    if filename:
        hasher.update(filename.encode('utf-8'))
    
    return hasher.hexdigest()


def verify_content_integrity(content: str, expected_hash: str) -> bool:
    """
    Verify content integrity by comparing hashes.
    
    Args:
        content: Content to verify
        expected_hash: Expected hash value
        
    Returns:
        True if hashes match, False otherwise
    """
    actual_hash = compute_content_hash(content)
    return actual_hash == expected_hash