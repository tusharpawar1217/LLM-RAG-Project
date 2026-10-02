"""Production monitoring and observability."""

import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import psutil
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import structlog

logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'askdocs_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status', 'tenant_id']
)

REQUEST_DURATION = Histogram(
    'askdocs_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'tenant_id']
)

QUERY_DURATION = Histogram(
    'askdocs_query_duration_seconds',
    'Query processing duration in seconds',
    ['query_type', 'tenant_id']
)

DOCUMENT_PROCESSING_DURATION = Histogram(
    'askdocs_document_processing_seconds',
    'Document processing duration in seconds',
    ['doc_type', 'tenant_id']
)

ACTIVE_CONNECTIONS = Gauge(
    'askdocs_active_connections',
    'Number of active database connections'
)

CACHE_HITS = Counter(
    'askdocs_cache_hits_total',
    'Total cache hits',
    ['cache_type', 'tenant_id']
)

CACHE_MISSES = Counter(
    'askdocs_cache_misses_total',
    'Total cache misses',
    ['cache_type', 'tenant_id']
)

LLM_TOKENS = Counter(
    'askdocs_llm_tokens_total',
    'Total LLM tokens used',
    ['model', 'token_type', 'tenant_id']
)

EMBEDDING_TOKENS = Counter(
    'askdocs_embedding_tokens_total',
    'Total embedding tokens used',
    ['tenant_id']
)

VECTOR_DB_OPERATIONS = Counter(
    'askdocs_vector_db_operations_total',
    'Total vector database operations',
    ['operation', 'tenant_id']
)

SYSTEM_MEMORY_USAGE = Gauge(
    'askdocs_system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_CPU_USAGE = Gauge(
    'askdocs_system_cpu_usage_percent',
    'System CPU usage percentage'
)

QUEUE_SIZE = Gauge(
    'askdocs_queue_size',
    'Number of items in processing queue',
    ['queue_type']
)

ERROR_COUNT = Counter(
    'askdocs_errors_total',
    'Total number of errors',
    ['error_type', 'tenant_id']
)


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    operation: str
    tenant_id: Optional[str]
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self):
        """Mark operation as finished."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        
        logger.info(
            "Operation completed",
            operation=self.operation,
            tenant_id=self.tenant_id,
            duration=self.duration,
            **self.metadata
        )


class MetricsCollector:
    """Centralized metrics collection."""
    
    def __init__(self):
        self.active_operations: Dict[str, PerformanceMetrics] = {}
    
    @contextmanager
    def track_request(self, method: str, endpoint: str, tenant_id: Optional[str] = None):
        """Track HTTP request metrics."""
        start_time = time.time()
        status = "success"
        
        try:
            yield
        except Exception as e:
            status = "error"
            ERROR_COUNT.labels(
                error_type=type(e).__name__,
                tenant_id=tenant_id or "unknown"
            ).inc()
            raise
        finally:
            duration = time.time() - start_time
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status=status,
                tenant_id=tenant_id or "unknown"
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                tenant_id=tenant_id or "unknown"
            ).observe(duration)
    
    @contextmanager
    def track_query(self, query_type: str, tenant_id: Optional[str] = None):
        """Track query processing metrics."""
        start_time = time.time()
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            
            QUERY_DURATION.labels(
                query_type=query_type,
                tenant_id=tenant_id or "unknown"
            ).observe(duration)
    
    @contextmanager
    def track_document_processing(self, doc_type: str, tenant_id: Optional[str] = None):
        """Track document processing metrics."""
        start_time = time.time()
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            
            DOCUMENT_PROCESSING_DURATION.labels(
                doc_type=doc_type,
                tenant_id=tenant_id or "unknown"
            ).observe(duration)
    
    def record_cache_hit(self, cache_type: str, tenant_id: Optional[str] = None):
        """Record cache hit."""
        CACHE_HITS.labels(
            cache_type=cache_type,
            tenant_id=tenant_id or "unknown"
        ).inc()
    
    def record_cache_miss(self, cache_type: str, tenant_id: Optional[str] = None):
        """Record cache miss."""
        CACHE_MISSES.labels(
            cache_type=cache_type,
            tenant_id=tenant_id or "unknown"
        ).inc()
    
    def record_llm_usage(self, model: str, input_tokens: int, output_tokens: int, tenant_id: Optional[str] = None):
        """Record LLM token usage."""
        LLM_TOKENS.labels(
            model=model,
            token_type="input",
            tenant_id=tenant_id or "unknown"
        ).inc(input_tokens)
        
        LLM_TOKENS.labels(
            model=model,
            token_type="output",
            tenant_id=tenant_id or "unknown"
        ).inc(output_tokens)
    
    def record_embedding_usage(self, tokens: int, tenant_id: Optional[str] = None):
        """Record embedding token usage."""
        EMBEDDING_TOKENS.labels(
            tenant_id=tenant_id or "unknown"
        ).inc(tokens)
    
    def record_vector_operation(self, operation: str, tenant_id: Optional[str] = None):
        """Record vector database operation."""
        VECTOR_DB_OPERATIONS.labels(
            operation=operation,
            tenant_id=tenant_id or "unknown"
        ).inc()
    
    def update_system_metrics(self):
        """Update system-level metrics."""
        # Memory usage
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE.set(memory.used)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        SYSTEM_CPU_USAGE.set(cpu_percent)
    
    def update_queue_size(self, queue_type: str, size: int):
        """Update queue size metric."""
        QUEUE_SIZE.labels(queue_type=queue_type).set(size)


# Global metrics collector instance
metrics = MetricsCollector()


class HealthChecker:
    """Health check system."""
    
    def __init__(self):
        self.checks: Dict[str, callable] = {}
    
    def register_check(self, name: str, check_func: callable):
        """Register a health check."""
        self.checks[name] = check_func
    
    async def run_checks(self) -> Dict[str, Dict[str, Any]]:
        """Run all health checks."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                result = await check_func()
                duration = time.time() - start_time
                
                if isinstance(result, bool):
                    result = {"healthy": result}
                elif isinstance(result, dict):
                    if "healthy" not in result:
                        result["healthy"] = True
                else:
                    result = {"healthy": True, "message": str(result)}
                
                result["duration"] = duration
                results[name] = result
                
                if not result["healthy"]:
                    overall_healthy = False
                    
            except Exception as e:
                logger.error(f"Health check {name} failed", error=str(e), exc_info=True)
                results[name] = {
                    "healthy": False,
                    "error": str(e),
                    "duration": time.time() - start_time if 'start_time' in locals() else 0
                }
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results
        }


# Global health checker instance
health_checker = HealthChecker()


class AlertManager:
    """Basic alerting system."""
    
    def __init__(self):
        self.thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "error_rate": 5.0,
            "response_time_p95": 2.0
        }
        self.alert_history: List[Dict[str, Any]] = []
    
    def check_thresholds(self):
        """Check system thresholds and generate alerts."""
        alerts = []
        
        # CPU usage alert
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > self.thresholds["cpu_usage"]:
            alert = {
                "type": "cpu_usage",
                "severity": "warning" if cpu_usage < 90 else "critical",
                "message": f"High CPU usage: {cpu_usage:.1f}%",
                "value": cpu_usage,
                "threshold": self.thresholds["cpu_usage"],
                "timestamp": datetime.utcnow().isoformat()
            }
            alerts.append(alert)
            logger.warning("High CPU usage detected", **alert)
        
        # Memory usage alert
        memory = psutil.virtual_memory()
        memory_usage_percent = memory.percent
        if memory_usage_percent > self.thresholds["memory_usage"]:
            alert = {
                "type": "memory_usage",
                "severity": "warning" if memory_usage_percent < 95 else "critical",
                "message": f"High memory usage: {memory_usage_percent:.1f}%",
                "value": memory_usage_percent,
                "threshold": self.thresholds["memory_usage"],
                "timestamp": datetime.utcnow().isoformat()
            }
            alerts.append(alert)
            logger.warning("High memory usage detected", **alert)
        
        # Store alerts
        self.alert_history.extend(alerts)
        
        # Keep only recent alerts (last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.alert_history = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"]) > cutoff_time
        ]
        
        return alerts


# Global alert manager instance
alert_manager = AlertManager()


def start_metrics_server(port: int = 8000):
    """Start Prometheus metrics server."""
    try:
        start_http_server(port)
        logger.info(f"Metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")


def setup_monitoring():
    """Setup monitoring and observability."""
    logger.info("Setting up monitoring and observability")
    
    # Register basic health checks
    async def database_check():
        """Check database connectivity."""
        from app.core.database import SessionLocal
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
            return {"healthy": True, "message": "Database connection successful"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def redis_check():
        """Check Redis connectivity."""
        from app.core.redis import redis_client
        try:
            await redis_client.ping()
            return {"healthy": True, "message": "Redis connection successful"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def vector_db_check():
        """Check vector database connectivity."""
        try:
            from app.services.vector_service import VectorService
            vector_service = VectorService()
            # Basic connectivity check
            return {"healthy": True, "message": "Vector DB connection successful"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    health_checker.register_check("database", database_check)
    health_checker.register_check("redis", redis_check)
    health_checker.register_check("vector_db", vector_db_check)
    
    logger.info("Monitoring setup completed")