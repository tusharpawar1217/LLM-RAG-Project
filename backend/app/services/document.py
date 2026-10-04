"""
Document service for managing document operations and ingestion.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.base import get_db as get_session
from app.core.errors import DocumentError, ValidationError
from app.core.logging import get_logger
from app.ingestion.pipeline import IngestionPipeline
from app.db.models import Document, DocumentStatus
from app.db.models import Tenant
from app.utils.hashing import compute_file_hash
from app.workers.ingestion import enqueue_document_ingestion, enqueue_document_reingestion, get_job_status

logger = get_logger(__name__)


class DocumentService:
    """Service for managing documents and their ingestion."""
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = IngestionPipeline()
    
    async def create_document(
        self,
        tenant: Tenant,
        name: str,
        document_type: str,
        file: Optional[UploadFile] = None,
        url: Optional[str] = None,
        metadata: Optional[dict] = None,
        enqueue_processing: bool = True,
    ) -> tuple[Document, str]:
        """
        Create a new document and optionally enqueue for processing.
        
        Args:
            tenant: Tenant owning the document
            name: Document name
            document_type: Type of document (pdf, docx, etc.)
            file: Uploaded file (for file uploads)
            url: URL (for web documents)
            metadata: Additional metadata
            enqueue_processing: Whether to enqueue for background processing
            
        Returns:
            Tuple of (Document, job_id)
        """
        if not file and not url:
            raise ValidationError("Either file or URL must be provided")
        
        if file and url:
            raise ValidationError("Cannot provide both file and URL")
        
        async with get_session() as session:
            # Check for duplicate by name within tenant
            existing = await session.execute(
                select(Document).where(
                    and_(
                        Document.tenant_id == tenant.id,
                        Document.name == name,
                        Document.status != DocumentStatus.DELETED
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                raise DocumentError(f"Document with name '{name}' already exists")
            
            # Create document record
            document = Document(
                id=uuid4(),
                tenant_id=tenant.id,
                name=name,
                document_type=document_type.lower(),
                status=DocumentStatus.PENDING,
                metadata=metadata or {},
            )
            
            file_path = None
            
            try:
                # Handle file upload
                if file:
                    # Generate unique filename
                    file_extension = Path(file.filename or '').suffix
                    if not file_extension:
                        file_extension = f'.{document_type.lower()}'
                    
                    filename = f"{document.id}{file_extension}"
                    file_path = self.upload_dir / str(tenant.id) / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Save file
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    
                    # Calculate file hash
                    file_hash = compute_file_hash(file_path)
                    document.metadata['file_hash'] = file_hash
                    document.metadata['file_size'] = file_path.stat().st_size
                    document.metadata['original_filename'] = file.filename
                
                # Handle URL
                if url:
                    document.metadata['url'] = url
                
                # Save document
                session.add(document)
                await session.commit()
                await session.refresh(document)
                
                logger.info(
                    f"Created document {document.id}",
                    document_name=name,
                    document_type=document_type,
                    tenant_id=str(tenant.id),
                    has_file=file is not None,
                    has_url=url is not None,
                )
                
                # Enqueue processing if requested
                job_id = ""
                if enqueue_processing:
                    job_id = await enqueue_document_ingestion(
                        tenant_id=tenant.id,
                        document_id=document.id,
                        file_path=str(file_path) if file_path else None,
                        url=url,
                    )
                    
                    # Update document with job ID
                    document.metadata['job_id'] = job_id
                    session.add(document)
                    await session.commit()
                
                return document, job_id
                
            except Exception as e:
                # Clean up file if created
                if file_path and file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup file {file_path}: {cleanup_error}")
                
                logger.error(f"Failed to create document: {e}")
                raise DocumentError(f"Failed to create document: {str(e)}")
    
    async def get_document(
        self,
        tenant: Tenant,
        document_id: UUID,
        include_chunks: bool = False,
    ) -> Optional[Document]:
        """Get a document by ID."""
        async with get_session() as session:
            query = select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.tenant_id == tenant.id,
                    Document.status != DocumentStatus.DELETED
                )
            )
            
            if include_chunks:
                query = query.options(selectinload(Document.chunks))
            
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def list_documents(
        self,
        tenant: Tenant,
        status: Optional[DocumentStatus] = None,
        document_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Document], int]:
        """List documents for a tenant with optional filtering."""
        async with get_session() as session:
            # Base query
            query = select(Document).where(
                and_(
                    Document.tenant_id == tenant.id,
                    Document.status != DocumentStatus.DELETED
                )
            )
            
            # Apply filters
            if status:
                query = query.where(Document.status == status)
            
            if document_type:
                query = query.where(Document.document_type == document_type.lower())
            
            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination and ordering
            query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            documents = result.scalars().all()
            
            return list(documents), total
    
    async def update_document(
        self,
        tenant: Tenant,
        document_id: UUID,
        name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Document]:
        """Update document metadata."""
        async with get_session() as session:
            # Get document
            result = await session.execute(
                select(Document).where(
                    and_(
                        Document.id == document_id,
                        Document.tenant_id == tenant.id,
                        Document.status != DocumentStatus.DELETED
                    )
                )
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return None
            
            # Update fields
            if name is not None:
                # Check for duplicate name
                existing = await session.execute(
                    select(Document).where(
                        and_(
                            Document.tenant_id == tenant.id,
                            Document.name == name,
                            Document.id != document_id,
                            Document.status != DocumentStatus.DELETED
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    raise DocumentError(f"Document with name '{name}' already exists")
                
                document.name = name
            
            if metadata is not None:
                # Merge with existing metadata
                document.metadata = {**document.metadata, **metadata}
            
            session.add(document)
            await session.commit()
            await session.refresh(document)
            
            logger.info(
                f"Updated document {document.id}",
                tenant_id=str(tenant.id),
                updated_name=name is not None,
                updated_metadata=metadata is not None,
            )
            
            return document
    
    async def delete_document(
        self,
        tenant: Tenant,
        document_id: UUID,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete a document and its chunks.
        
        Args:
            tenant: Tenant owning the document
            document_id: Document ID to delete
            hard_delete: If True, permanently delete from DB. If False, mark as deleted.
            
        Returns:
            True if document was deleted, False if not found
        """
        async with get_session() as session:
            # Get document
            result = await session.execute(
                select(Document).where(
                    and_(
                        Document.id == document_id,
                        Document.tenant_id == tenant.id
                    )
                )
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return False
            
            try:
                # Delete chunks from vector store
                deleted_chunks = await self.pipeline.delete_document(tenant, document)
                
                if hard_delete:
                    # Permanently delete from database
                    await session.delete(document)
                    operation = "hard_deleted"
                else:
                    # Soft delete (mark as deleted)
                    document.status = DocumentStatus.DELETED
                    document.metadata['deleted_chunks'] = deleted_chunks
                    session.add(document)
                    operation = "soft_deleted"
                
                await session.commit()
                
                # Clean up uploaded file if exists
                await self._cleanup_document_file(tenant, document)
                
                logger.info(
                    f"Document {document_id} {operation}",
                    tenant_id=str(tenant.id),
                    deleted_chunks=deleted_chunks,
                )
                
                return True
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete document {document_id}: {e}")
                raise DocumentError(f"Failed to delete document: {str(e)}")
    
    async def reingest_document(
        self,
        tenant: Tenant,
        document_id: UUID,
        file: Optional[UploadFile] = None,
        url: Optional[str] = None,
    ) -> tuple[Document, str]:
        """
        Re-ingest a document with optional new content.
        
        Args:
            tenant: Tenant owning the document
            document_id: Document ID to re-ingest
            file: Optional new file to upload
            url: Optional new URL
            
        Returns:
            Tuple of (Document, job_id)
        """
        async with get_session() as session:
            # Get document
            result = await session.execute(
                select(Document).where(
                    and_(
                        Document.id == document_id,
                        Document.tenant_id == tenant.id,
                        Document.status != DocumentStatus.DELETED
                    )
                )
            )
            document = result.scalar_one_or_none()
            
            if not document:
                raise DocumentError(f"Document {document_id} not found")
            
            file_path = None
            
            try:
                # Handle new file upload
                if file:
                    # Clean up old file
                    await self._cleanup_document_file(tenant, document)
                    
                    # Upload new file
                    file_extension = Path(file.filename or '').suffix
                    if not file_extension:
                        file_extension = f'.{document.document_type}'
                    
                    filename = f"{document.id}{file_extension}"
                    file_path = self.upload_dir / str(tenant.id) / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    
                    # Update metadata
                    file_hash = compute_file_hash(file_path)
                    document.metadata.update({
                        'file_hash': file_hash,
                        'file_size': file_path.stat().st_size,
                        'original_filename': file.filename,
                    })
                
                # Handle new URL
                if url:
                    document.metadata['url'] = url
                
                # Update status and clear old processing data
                document.status = DocumentStatus.PENDING
                document.error_message = None
                document.content_hash = None
                document.chunk_count = 0
                
                # Remove old job ID from metadata
                if 'job_id' in document.metadata:
                    del document.metadata['job_id']
                
                session.add(document)
                await session.commit()
                
                # Enqueue re-ingestion
                job_id = await enqueue_document_reingestion(
                    tenant_id=tenant.id,
                    document_id=document.id,
                    file_path=str(file_path) if file_path else None,
                    url=url,
                )
                
                # Update with new job ID
                document.metadata['job_id'] = job_id
                session.add(document)
                await session.commit()
                await session.refresh(document)
                
                logger.info(
                    f"Enqueued document re-ingestion {document.id}",
                    tenant_id=str(tenant.id),
                    job_id=job_id,
                    has_new_file=file is not None,
                    has_new_url=url is not None,
                )
                
                return document, job_id
                
            except Exception as e:
                logger.error(f"Failed to re-ingest document {document_id}: {e}")
                raise DocumentError(f"Failed to re-ingest document: {str(e)}")
    
    async def get_document_status(
        self,
        tenant: Tenant,
        document_id: UUID,
    ) -> dict:
        """Get detailed status of document processing."""
        document = await self.get_document(tenant, document_id)
        
        if not document:
            return {
                "document_id": str(document_id),
                "status": "not_found",
                "error": "Document not found"
            }
        
        status_info = {
            "document_id": str(document.id),
            "name": document.name,
            "type": document.document_type,
            "status": document.status.value,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "chunk_count": document.chunk_count,
            "content_hash": document.content_hash,
            "metadata": document.metadata,
        }
        
        if document.error_message:
            status_info["error"] = document.error_message
        
        # Get job status if available
        job_id = document.metadata.get('job_id')
        if job_id:
            try:
                job_status = await get_job_status(job_id)
                status_info["job"] = job_status
            except Exception as e:
                logger.warning(f"Failed to get job status for {job_id}: {e}")
                status_info["job"] = {"error": "Failed to get job status"}
        
        # Get vector store status
        try:
            ingestion_status = await self.pipeline.get_ingestion_status(
                tenant, document_id
            )
            status_info["vector_store"] = ingestion_status
        except Exception as e:
            logger.warning(f"Failed to get vector store status: {e}")
            status_info["vector_store"] = {"error": "Failed to get vector store status"}
        
        return status_info
    
    async def get_tenant_statistics(self, tenant: Tenant) -> dict:
        """Get document statistics for a tenant."""
        async with get_session() as session:
            # Document counts by status
            status_counts = {}
            for status in DocumentStatus:
                if status == DocumentStatus.DELETED:
                    continue  # Skip deleted documents
                
                result = await session.execute(
                    select(func.count()).where(
                        and_(
                            Document.tenant_id == tenant.id,
                            Document.status == status
                        )
                    )
                )
                status_counts[status.value] = result.scalar()
            
            # Total chunks across all documents
            chunk_result = await session.execute(
                select(func.sum(Document.chunk_count)).where(
                    and_(
                        Document.tenant_id == tenant.id,
                        Document.status != DocumentStatus.DELETED
                    )
                )
            )
            total_chunks = chunk_result.scalar() or 0
            
            # Document type distribution
            type_result = await session.execute(
                select(Document.document_type, func.count()).where(
                    and_(
                        Document.tenant_id == tenant.id,
                        Document.status != DocumentStatus.DELETED
                    )
                ).group_by(Document.document_type)
            )
            type_distribution = {row[0]: row[1] for row in type_result}
            
            # Vector store status
            try:
                vector_status = await self.pipeline.get_ingestion_status(tenant)
            except Exception as e:
                vector_status = {"error": str(e)}
        
        return {
            "tenant_id": str(tenant.id),
            "document_counts": status_counts,
            "total_chunks": total_chunks,
            "document_types": type_distribution,
            "vector_store": vector_status,
        }
    
    async def _cleanup_document_file(
        self,
        tenant: Tenant,
        document: Document,
    ) -> None:
        """Clean up uploaded file for a document."""
        try:
            # Look for file in upload directory
            tenant_dir = self.upload_dir / str(tenant.id)
            if tenant_dir.exists():
                # Try different file extensions
                possible_files = list(tenant_dir.glob(f"{document.id}.*"))
                
                for file_path in possible_files:
                    try:
                        file_path.unlink()
                        logger.info(f"Cleaned up file {file_path}")
                    except Exception as file_error:
                        logger.warning(f"Failed to delete file {file_path}: {file_error}")
                        
        except Exception as e:
            logger.warning(f"Error during file cleanup for document {document.id}: {e}")
    
    async def health_check(self) -> dict:
        """Check health of document service."""
        try:
            # Check pipeline health
            pipeline_health = await self.pipeline.health_check()
            
            # Check upload directory
            upload_dir_accessible = self.upload_dir.exists() and self.upload_dir.is_dir()
            
            # Check database connectivity
            db_healthy = False
            try:
                async with get_session() as session:
                    await session.execute(select(1))
                    db_healthy = True
            except Exception as db_error:
                logger.error(f"Database health check failed: {db_error}")
            
            overall_healthy = (
                pipeline_health.get("status") == "healthy" and
                upload_dir_accessible and
                db_healthy
            )
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "components": {
                    "pipeline": pipeline_health,
                    "upload_directory": {
                        "accessible": upload_dir_accessible,
                        "path": str(self.upload_dir),
                    },
                    "database": {
                        "status": "healthy" if db_healthy else "unhealthy",
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Document service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    async def close(self):
        """Cleanup service resources."""
        try:
            await self.pipeline.close()
            logger.info("Document service closed")
        except Exception as e:
            logger.warning(f"Error closing document service: {e}")



