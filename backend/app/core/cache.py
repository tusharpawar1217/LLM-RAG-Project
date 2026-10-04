"""Advanced caching system with multiple backends."""

import json
import pickle
from typing import Optional, Any, Union, List, Dict
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import redis
import structlog

from app.core.monitoring import metrics

logger = structlog.get_logger(__name__)


@dataclass
class CacheKey:
    """Structured cache key."""
    namespace: str
    identifier: str
    tenant_id: Optional[str] = None
    version: Optional[str] = None
    
    def to_string(self) -> str:
        """Convert to cache key string."""
        parts = [self.namespace, self.identifier]
        
        if self.tenant_id:
            parts.insert(1, f"tenant:{self.tenant_id}")
        
        if self.version:
            parts.append(f"v:{self.version}")
        
        return ":".join(parts)
    
    @classmethod
    def from_string(cls, key_string: str) -> "CacheKey":
        """Create from cache key string."""
        parts = key_string.split(":")
        namespace = parts[0]
        identifier = parts[-1]
        
        tenant_id = None
        version = None
        
        for part in parts[1:-1]:
            if part.startswith("tenant:"):
                tenant_id = part[7:]
            elif part.startswith("v:"):
                version = part[2:]
        
        return cls(
            namespace=namespace,
            identifier=identifier,
            tenant_id=tenant_id,
            version=version
        )


class CacheBackend(ABC):
    """Abstract cache backend."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time."""
        pass
    
    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL."""
        pass


class RedisBackend(CacheBackend):
    """Redis cache backend."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def get(self, key: str) -> Optional[bytes]:
        """Get value from Redis."""
        try:
            value = await self.redis.get(key)
            return value
        except Exception as e:
            logger.error("Redis get failed", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> bool:
        """Set value in Redis."""
        try:
            if ttl:
                result = await self.redis.setex(key, ttl, value)
            else:
                result = await self.redis.set(key, value)
            return bool(result)
        except Exception as e:
            logger.error("Redis set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            result = await self.redis.delete(key)
            return bool(result)
        except Exception as e:
            logger.error("Redis delete failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error("Redis exists failed", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time in Redis."""
        try:
            result = await self.redis.expire(key, ttl)
            return bool(result)
        except Exception as e:
            logger.error("Redis expire failed", key=key, error=str(e))
            return False
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL from Redis."""
        try:
            ttl = await self.redis.ttl(key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.error("Redis TTL failed", key=key, error=str(e))
            return None


class InMemoryBackend(CacheBackend):
    """In-memory cache backend (for testing/development)."""
    
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
    
    async def get(self, key: str) -> Optional[bytes]:
        """Get value from memory."""
        if key not in self.store:
            return None
        
        entry = self.store[key]
        
        # Check expiration
        if entry["expires_at"] and datetime.utcnow() > entry["expires_at"]:
            del self.store[key]
            return None
        
        return entry["value"]
    
    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> bool:
        """Set value in memory."""
        expires_at = None
        if ttl:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        self.store[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.utcnow()
        }
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from memory."""
        if key in self.store:
            del self.store[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in memory."""
        if key not in self.store:
            return False
        
        entry = self.store[key]
        if entry["expires_at"] and datetime.utcnow() > entry["expires_at"]:
            del self.store[key]
            return False
        
        return True
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time in memory."""
        if key not in self.store:
            return False
        
        self.store[key]["expires_at"] = datetime.utcnow() + timedelta(seconds=ttl)
        return True
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL from memory."""
        if key not in self.store:
            return None
        
        entry = self.store[key]
        if not entry["expires_at"]:
            return -1  # No expiration
        
        remaining = (entry["expires_at"] - datetime.utcnow()).total_seconds()
        return int(remaining) if remaining > 0 else 0


class CacheSerializer:
    """Handle serialization/deserialization."""
    
    @staticmethod
    def serialize(value: Any) -> bytes:
        """Serialize value to bytes."""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return value.encode('utf-8')
        elif isinstance(value, (dict, list)):
            return json.dumps(value).encode('utf-8')
        else:
            return pickle.dumps(value)
    
    @staticmethod
    def deserialize(data: bytes, value_type: str = "auto") -> Any:
        """Deserialize bytes to value."""
        if value_type == "bytes":
            return data
        elif value_type == "str":
            return data.decode('utf-8')
        elif value_type == "json":
            return json.loads(data.decode('utf-8'))
        elif value_type == "pickle":
            return pickle.loads(data)
        else:  # auto
            try:
                # Try JSON first
                return json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                try:
                    # Try pickle
                    return pickle.loads(data)
                except Exception:
                    # Return as string
                    return data.decode('utf-8', errors='ignore')


class AdvancedCache:
    """Advanced caching system with multiple backends and features."""
    
    def __init__(self, backend: CacheBackend, default_ttl: int = 3600):
        self.backend = backend
        self.default_ttl = default_ttl
        self.serializer = CacheSerializer()
    
    def _create_key(self, key: Union[str, CacheKey]) -> str:
        """Create standardized cache key."""
        if isinstance(key, CacheKey):
            return key.to_string()
        return str(key)
    
    async def get(
        self, 
        key: Union[str, CacheKey], 
        value_type: str = "auto",
        tenant_id: Optional[str] = None
    ) -> Optional[Any]:
        """Get value from cache."""
        cache_key = self._create_key(key)
        
        try:
            data = await self.backend.get(cache_key)
            
            if data is None:
                metrics.record_cache_miss("advanced", tenant_id)
                return None
            
            metrics.record_cache_hit("advanced", tenant_id)
            return self.serializer.deserialize(data, value_type)
            
        except Exception as e:
            logger.error("Cache get failed", key=cache_key, error=str(e))
            metrics.record_cache_miss("advanced", tenant_id)
            return None
    
    async def set(
        self, 
        key: Union[str, CacheKey], 
        value: Any, 
        ttl: Optional[int] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Set value in cache."""
        cache_key = self._create_key(key)
        ttl = ttl or self.default_ttl
        
        try:
            data = self.serializer.serialize(value)
            result = await self.backend.set(cache_key, data, ttl)
            
            if result:
                logger.debug("Cache set successful", key=cache_key, ttl=ttl)
            else:
                logger.warning("Cache set failed", key=cache_key)
            
            return result
            
        except Exception as e:
            logger.error("Cache set failed", key=cache_key, error=str(e))
            return False
    
    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """Delete key from cache."""
        cache_key = self._create_key(key)
        
        try:
            result = await self.backend.delete(cache_key)
            logger.debug("Cache delete", key=cache_key, success=result)
            return result
            
        except Exception as e:
            logger.error("Cache delete failed", key=cache_key, error=str(e))
            return False
    
    async def get_or_set(
        self, 
        key: Union[str, CacheKey], 
        value_factory: callable, 
        ttl: Optional[int] = None,
        value_type: str = "auto",
        tenant_id: Optional[str] = None
    ) -> Any:
        """Get value from cache or set it using factory function."""
        # Try to get from cache first
        value = await self.get(key, value_type, tenant_id)
        
        if value is not None:
            return value
        
        # Generate value and cache it
        try:
            if asyncio.iscoroutinefunction(value_factory):
                value = await value_factory()
            else:
                value = value_factory()
            
            await self.set(key, value, ttl, tenant_id)
            return value
            
        except Exception as e:
            logger.error("Value factory failed", key=str(key), error=str(e))
            raise
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern (Redis only)."""
        if not isinstance(self.backend, RedisBackend):
            logger.warning("Pattern invalidation only supported with Redis backend")
            return 0
        
        try:
            # This would need Redis SCAN command implementation
            # For now, just log the pattern
            logger.info("Invalidating cache pattern", pattern=pattern)
            return 0
            
        except Exception as e:
            logger.error("Pattern invalidation failed", pattern=pattern, error=str(e))
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        # Basic stats - would need backend-specific implementation for detailed stats
        return {
            "backend_type": type(self.backend).__name__,
            "default_ttl": self.default_ttl
        }


# Cache instances for different use cases
query_cache: Optional[AdvancedCache] = None
document_cache: Optional[AdvancedCache] = None
embedding_cache: Optional[AdvancedCache] = None
general_cache: Optional[AdvancedCache] = None


def init_cache_system(redis_client: redis.Redis = None):
    """Initialize cache system."""
    global query_cache, document_cache, embedding_cache, general_cache
    
    if redis_client:
        backend = RedisBackend(redis_client)
        logger.info("Using Redis cache backend")
    else:
        backend = InMemoryBackend()
        logger.info("Using in-memory cache backend")
    
    # Different caches with different TTLs
    query_cache = AdvancedCache(backend, default_ttl=1800)  # 30 minutes
    document_cache = AdvancedCache(backend, default_ttl=3600)  # 1 hour
    embedding_cache = AdvancedCache(backend, default_ttl=86400)  # 24 hours
    general_cache = AdvancedCache(backend, default_ttl=3600)  # 1 hour
    
    logger.info("Cache system initialized")


# Utility functions for common caching patterns
async def cache_query_result(
    query_text: str, 
    tenant_id: str, 
    result: Any, 
    ttl: int = 1800
) -> bool:
    """Cache query result."""
    if not query_cache:
        return False
    
    # Create hash of query for consistent key
    query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
    
    key = CacheKey(
        namespace="query_result",
        identifier=query_hash,
        tenant_id=tenant_id
    )
    
    return await query_cache.set(key, result, ttl, tenant_id)


async def get_cached_query_result(
    query_text: str, 
    tenant_id: str
) -> Optional[Any]:
    """Get cached query result."""
    if not query_cache:
        return None
    
    query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
    
    key = CacheKey(
        namespace="query_result",
        identifier=query_hash,
        tenant_id=tenant_id
    )
    
    return await query_cache.get(key, tenant_id=tenant_id)


async def cache_document_embeddings(
    document_id: str, 
    embeddings: List[List[float]], 
    ttl: int = 86400
) -> bool:
    """Cache document embeddings."""
    if not embedding_cache:
        return False
    
    key = CacheKey(
        namespace="doc_embeddings",
        identifier=document_id
    )
    
    return await embedding_cache.set(key, embeddings, ttl)


async def get_cached_document_embeddings(
    document_id: str
) -> Optional[List[List[float]]]:
    """Get cached document embeddings."""
    if not embedding_cache:
        return None
    
    key = CacheKey(
        namespace="doc_embeddings",
        identifier=document_id
    )
    
    return await embedding_cache.get(key)

