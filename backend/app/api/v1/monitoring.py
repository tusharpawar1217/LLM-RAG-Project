"""Monitoring and health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Dict, Any, Optional
import json

from app.core.monitoring import health_checker, metrics, alert_manager
from app.core.security import get_current_user_optional
from app.models.auth import User

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Comprehensive health check endpoint.
    Returns the overall health status and individual check results.
    """
    try:
        health_data = await health_checker.run_checks()
        
        status_code = (
            status.HTTP_200_OK 
            if health_data["status"] == "healthy" 
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        
        return JSONResponse(
            status_code=status_code,
            content=health_data
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "message": f"Health check failed: {str(e)}"
            }
        )


@router.get("/health/ready")
async def readiness_check() -> JSONResponse:
    """
    Kubernetes-style readiness probe.
    Returns 200 if the service is ready to serve traffic.
    """
    try:
        health_data = await health_checker.run_checks()
        
        # Check critical services
        critical_services = ["database", "redis", "vector_db"]
        for service in critical_services:
            if service in health_data["checks"]:
                if not health_data["checks"][service].get("healthy", False):
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"ready": False, "reason": f"{service} not healthy"}
                    )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"ready": True}
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False, "reason": str(e)}
        )


@router.get("/health/live")
async def liveness_check() -> JSONResponse:
    """
    Kubernetes-style liveness probe.
    Returns 200 if the service is alive (basic functionality).
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"alive": True}
    )


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus format.
    """
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        
        # Update system metrics before returning
        metrics.update_system_metrics()
        
        # Generate Prometheus format
        metrics_data = generate_latest()
        
        return PlainTextResponse(
            content=metrics_data.decode('utf-8'),
            media_type=CONTENT_TYPE_LATEST
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate metrics: {str(e)}"
        )


@router.get("/alerts")
async def get_alerts(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Get system alerts.
    Requires authentication for detailed alerts.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Check current thresholds
        current_alerts = alert_manager.check_thresholds()
        
        # Get alert history
        recent_alerts = alert_manager.alert_history[-50:]  # Last 50 alerts
        
        return {
            "current_alerts": current_alerts,
            "recent_alerts": recent_alerts,
            "alert_count": {
                "critical": len([a for a in current_alerts if a.get("severity") == "critical"]),
                "warning": len([a for a in current_alerts if a.get("severity") == "warning"]),
                "total": len(current_alerts)
            },
            "thresholds": alert_manager.thresholds
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alerts: {str(e)}"
        )


@router.get("/stats")
async def get_system_stats(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Get detailed system statistics.
    Requires authentication.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        import psutil
        from datetime import datetime
        
        # System information
        system_stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu": {
                    "usage_percent": psutil.cpu_percent(interval=1),
                    "count": psutil.cpu_count(),
                    "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "used": psutil.virtual_memory().used,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            }
        }
        
        # Database connection info
        try:
            from app.db.base import engine
            pool = engine.pool
            system_stats["database"] = {
                "pool_size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "checked_in": pool.checkedin()
            }
        except Exception:
            system_stats["database"] = {"error": "Unable to get database stats"}
        
        return system_stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system stats: {str(e)}"
        )


@router.post("/alerts/acknowledge/{alert_id}")
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Acknowledge an alert.
    Requires authentication.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Find and acknowledge alert
        # In a real implementation, you'd store alert acknowledgments
        return {
            "alert_id": alert_id,
            "acknowledged": True,
            "acknowledged_by": current_user.email,
            "acknowledged_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert: {str(e)}"
        )

