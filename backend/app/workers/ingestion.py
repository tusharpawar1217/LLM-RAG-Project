"""
ARQ background workers for document ingestion.
"""

import asyncio
from pathlib import Path
from typing import Optional
from uuid import UUID

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_session
from app.core.logging import get_logger
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document, DocumentStatus
from app.models.tenant import Tenant

logger = get_logger(__name__)


async def ingest_document_task(
    ctx,
    tenant_id: str,
    document_id: str,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    force_reprocess: bool = False,
) -> dict:
    """
    ARQ task for ingesting a single document.
    
    Args:
        ctx: ARQ context
        tenant_id: UUID string of tenant
        document_id: UUID string of document  
        file_path: Optional path to document file
        url: Optional URL for web documents
        force_reprocess: Force reprocessing even if unchanged
        
    Returns:
        Result dictionary with status and metadata
    """
    logger.info(
        f"Starting document ingestion task",
        tenant_id=tenant_id,
        document_id=document_id,
        job_id=ctx.get('job_id'),
    )
    
    pipeline = None
    try:
        # Get tenant and document from database
        async with get_session() as session:
            # Get tenant
            tenant_result = await session.execute(
                select(Tenant).where(Tenant.id == UUID(tenant_id))
            )
            tenant = tenant_result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Get document
            document_result = await session.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            document = document_result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            # Check tenant ownership
            if document.tenant_id != tenant.id:
                raise ValueError(f"Document {document_id} does not belong to tenant {tenant_id}")
        
        # Initialize pipeline
        pipeline = IngestionPipeline()
        
        # Convert file path if provided
        file_path_obj = Path(file_path) if file_path else None
        
        # Process document
        result_document = await pipeline.ingest_document(
            tenant=tenant,
            document=document,
            file_path=file_path_obj,
            url=url,
            force_reprocess=force_reprocess,
        )
        
        result = {
            "status": "success",
            "document_id": str(result_document.id),
            "tenant_id": str(tenant.id),
            "document_status": result_document.status.value,
            "chunk_count": result_document.chunk_count,
            "content_hash": result_document.content_hash,
            "metadata": result_document.metadata,
        }
        
        logger.info(
            f"Document ingestion task completed successfully",
            result=result,
            job_id=ctx.get('job_id'),
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Document ingestion task failed: {e}",
            tenant_id=tenant_id,
            document_id=document_id,
            error=str(e),
            job_id=ctx.get('job_id'),
        )
        
        # Try to update document status to failed
        try:
            async with get_session() as session:
                document_result = await session.execute(
                    select(Document).where(Document.id == UUID(document_id))
                )
                document = document_result.scalar_one_or_none()
                if document:
                    document.status = DocumentStatus.FAILED
                    document.error_message = str(e)
                    session.add(document)
                    await session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update document status: {db_error}")
        
        return {
            "status": "error",
            "error": str(e),
            "document_id": document_id,
            "tenant_id": tenant_id,
        }
        
    finally:
        # Cleanup pipeline resources
        if pipeline:
            try:
                await pipeline.close()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up pipeline: {cleanup_error}")


async def reingest_document_task(
    ctx,
    tenant_id: str,
    document_id: str,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
) -> dict:
    """
    ARQ task for re-ingesting a document (removes old chunks first).
    
    Args:
        ctx: ARQ context
        tenant_id: UUID string of tenant
        document_id: UUID string of document
        file_path: Optional path to document file
        url: Optional URL for web documents
        
    Returns:
        Result dictionary with status and metadata
    """
    logger.info(
        f"Starting document re-ingestion task",
        tenant_id=tenant_id,
        document_id=document_id,
        job_id=ctx.get('job_id'),
    )
    
    pipeline = None
    try:
        # Get tenant and document from database
        async with get_session() as session:
            # Get tenant
            tenant_result = await session.execute(
                select(Tenant).where(Tenant.id == UUID(tenant_id))
            )
            tenant = tenant_result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # Get document
            document_result = await session.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            document = document_result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            # Check tenant ownership
            if document.tenant_id != tenant.id:
                raise ValueError(f"Document {document_id} does not belong to tenant {tenant_id}")
        
        # Initialize pipeline
        pipeline = IngestionPipeline()
        
        # Convert file path if provided
        file_path_obj = Path(file_path) if file_path else None
        
        # Re-process document
        result_document = await pipeline.reingest_document(
            tenant=tenant,
            document=document,
            file_path=file_path_obj,
            url=url,
        )
        
        result = {
            "status": "success",
            "document_id": str(result_document.id),
            "tenant_id": str(tenant.id),
            "document_status": result_document.status.value,
            "chunk_count": result_document.chunk_count,
            "content_hash": result_document.content_hash,
            "metadata": result_document.metadata,
            "operation": "reingest",
        }
        
        logger.info(
            f"Document re-ingestion task completed successfully",
            result=result,
            job_id=ctx.get('job_id'),
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Document re-ingestion task failed: {e}",
            tenant_id=tenant_id,
            document_id=document_id,
            error=str(e),
            job_id=ctx.get('job_id'),
        )
        
        # Try to update document status to failed
        try:
            async with get_session() as session:
                document_result = await session.execute(
                    select(Document).where(Document.id == UUID(document_id))
                )
                document = document_result.scalar_one_or_none()
                if document:
                    document.status = DocumentStatus.FAILED
                    document.error_message = str(e)
                    session.add(document)
                    await session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update document status: {db_error}")
        
        return {
            "status": "error",
            "error": str(e),
            "document_id": document_id,
            "tenant_id": tenant_id,
            "operation": "reingest",
        }
        
    finally:
        # Cleanup pipeline resources
        if pipeline:
            try:
                await pipeline.close()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up pipeline: {cleanup_error}")


async def cleanup_failed_documents_task(ctx) -> dict:
    """
    Periodic task to clean up documents stuck in processing status.
    Runs every hour to find documents that have been processing for too long.
    """
    logger.info("Starting cleanup of failed documents", job_id=ctx.get('job_id'))
    
    try:
        from datetime import datetime, timedelta
        
        # Documents processing for more than 1 hour are considered stuck
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        async with get_session() as session:
            # Find stuck documents
            result = await session.execute(
                select(Document).where(
                    Document.status == DocumentStatus.PROCESSING,
                    Document.updated_at < cutoff_time
                )
            )
            stuck_documents = result.scalars().all()
            
            cleaned_count = 0
            for document in stuck_documents:
                try:
                    document.status = DocumentStatus.FAILED
                    document.error_message = "Processing timeout - task may have failed"
                    session.add(document)
                    cleaned_count += 1
                    
                    logger.warning(
                        f"Marked stuck document as failed",
                        document_id=str(document.id),
                        tenant_id=str(document.tenant_id),
                        stuck_since=document.updated_at,
                    )
                    
                except Exception as doc_error:
                    logger.error(
                        f"Failed to cleanup document {document.id}: {doc_error}"
                    )
            
            if cleaned_count > 0:
                await session.commit()
                logger.info(f"Cleaned up {cleaned_count} stuck documents")
        
        return {
            "status": "success",
            "cleaned_count": cleaned_count,
            "cutoff_time": cutoff_time.isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


# ARQ worker configuration
class WorkerSettings:
    """ARQ worker settings."""
    
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        database=settings.REDIS_DB,
    )
    
    # Job queue settings
    queue_name = 'askdocs:ingestion'
    max_jobs = 10  # Maximum concurrent jobs
    job_timeout = 1800  # 30 minutes timeout
    keep_result = 3600  # Keep results for 1 hour
    
    # Cron jobs for maintenance
    cron_jobs = [
        cron(cleanup_failed_documents_task, hour={0, 6, 12, 18}, minute=0),  # Every 6 hours
    ]
    
    # Task functions
    functions = [
        ingest_document_task,
        reingest_document_task,
        cleanup_failed_documents_task,
    ]
    
    # Worker settings
    on_startup = None
    on_shutdown = None
    
    # Health check settings
    health_check_interval = 60  # seconds
    health_check_key = 'arq:health'


# Helper function to enqueue ingestion jobs
async def enqueue_document_ingestion(
    tenant_id: UUID,
    document_id: UUID,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    force_reprocess: bool = False,
    priority: int = 0,
) -> str:
    """
    Enqueue a document ingestion job.
    
    Args:
        tenant_id: Tenant UUID
        document_id: Document UUID
        file_path: Optional file path
        url: Optional URL
        force_reprocess: Force reprocessing
        priority: Job priority (higher = more important)
        
    Returns:
        Job ID string
    """
    from arq import create_pool
    
    redis = await create_pool(WorkerSettings.redis_settings)
    
    try:
        job = await redis.enqueue_job(
            'ingest_document_task',
            str(tenant_id),
            str(document_id),
            file_path,
            url,
            force_reprocess,
            _priority=priority,
        )
        
        logger.info(
            f"Enqueued document ingestion job",
            job_id=job.job_id,
            tenant_id=str(tenant_id),
            document_id=str(document_id),
        )
        
        return job.job_id
        
    finally:
        await redis.close()


async def enqueue_document_reingestion(
    tenant_id: UUID,
    document_id: UUID,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    priority: int = 0,
) -> str:
    """
    Enqueue a document re-ingestion job.
    
    Args:
        tenant_id: Tenant UUID
        document_id: Document UUID
        file_path: Optional file path
        url: Optional URL
        priority: Job priority (higher = more important)
        
    Returns:
        Job ID string
    """
    from arq import create_pool
    
    redis = await create_pool(WorkerSettings.redis_settings)
    
    try:
        job = await redis.enqueue_job(
            'reingest_document_task',
            str(tenant_id),
            str(document_id),
            file_path,
            url,
            _priority=priority,
        )
        
        logger.info(
            f"Enqueued document re-ingestion job",
            job_id=job.job_id,
            tenant_id=str(tenant_id),
            document_id=str(document_id),
        )
        
        return job.job_id
        
    finally:
        await redis.close()


async def get_job_status(job_id: str) -> dict:
    """
    Get status of an ARQ job.
    
    Args:
        job_id: Job ID to check
        
    Returns:
        Job status dictionary
    """
    from arq import create_pool
    from arq.jobs import JobStatus
    
    redis = await create_pool(WorkerSettings.redis_settings)
    
    try:
        job = await redis.get_job(job_id)
        
        if not job:
            return {
                "job_id": job_id,
                "status": "not_found",
                "error": "Job not found",
            }
        
        status_mapping = {
            JobStatus.deferred: "queued",
            JobStatus.queued: "queued", 
            JobStatus.in_progress: "running",
            JobStatus.complete: "completed",
            JobStatus.not_found: "not_found",
        }
        
        result = {
            "job_id": job_id,
            "status": status_mapping.get(job.status, "unknown"),
            "enqueue_time": job.enqueue_time.isoformat() if job.enqueue_time else None,
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "finish_time": job.finish_time.isoformat() if job.finish_time else None,
        }
        
        # Include result if job is complete
        if job.status == JobStatus.complete and job.result:
            result["result"] = job.result
            
        # Include error if job failed
        if hasattr(job, 'error') and job.error:
            result["error"] = str(job.error)
        
        return result
        
    finally:
        await redis.close()