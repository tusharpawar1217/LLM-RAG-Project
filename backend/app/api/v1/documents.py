"""
Document management API endpoints.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_user, get_session
from app.core.errors import DocumentError, ValidationError
from app.core.logging import get_logger
from app.models.document import DocumentStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.document import (
    DocumentCreate,
    DocumentInDB,
    DocumentList,
    DocumentStatus as DocumentStatusResponse,
    DocumentUpdate,
)
from app.services.document import DocumentService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=DocumentInDB, status_code=status.HTTP_201_CREATED)
async def create_document(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    file: Optional[UploadFile] = File(None),
    name: str = Form(...),
    document_type: str = Form(...),
    url: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),  # JSON string
) -> DocumentInDB:
    """
    Create a new document.
    Upload a file or provide a URL for ingestion.
    """
    try:
        # Parse metadata if provided
        parsed_metadata = {}
        if metadata:
            import json
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid metadata JSON format"
                )
        
        # Validate document type
        supported_types = ['pdf', 'docx', 'doc', 'md', 'markdown', 'txt', 'text', 'url']
        if document_type.lower() not in supported_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported document type. Supported: {', '.join(supported_types)}"
            )
        
        # Validate file vs URL
        if not file and not url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either file or URL must be provided"
            )
        
        if file and url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot provide both file and URL"
            )
        
        # For URL type, URL is required
        if document_type.lower() == 'url' and not url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL is required for URL document type"
            )
        
        # For file types, file is required
        if document_type.lower() != 'url' and not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is required for non-URL document types"
            )
        
        # Create document
        document_service = DocumentService()
        
        document, job_id = await document_service.create_document(
            tenant=current_user.tenant,
            name=name,
            document_type=document_type,
            file=file,
            url=url,
            metadata=parsed_metadata,
            enqueue_processing=True,
        )
        
        logger.info(
            f"Created document via API",
            document_id=str(document.id),
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
            job_id=job_id,
        )
        
        return DocumentInDB.model_validate(document)
        
    except DocumentError as e:
        logger.error(f"Document creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error creating document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/", response_model=DocumentList)
async def list_documents(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    document_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> DocumentList:
    """List documents for the current tenant."""
    try:
        document_service = DocumentService()
        
        documents, total = await document_service.list_documents(
            tenant=current_user.tenant,
            status=status_filter,
            document_type=document_type,
            limit=limit,
            offset=offset,
        )
        
        return DocumentList(
            items=[DocumentInDB.model_validate(doc) for doc in documents],
            total=total,
            limit=limit,
            offset=offset,
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{document_id}", response_model=DocumentInDB)
async def get_document(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    document_id: UUID,
) -> DocumentInDB:
    """Get a specific document by ID."""
    try:
        document_service = DocumentService()
        
        document = await document_service.get_document(
            tenant=current_user.tenant,
            document_id=document_id,
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentInDB.model_validate(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put("/{document_id}", response_model=DocumentInDB)
async def update_document(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    document_id: UUID,
    document_update: DocumentUpdate,
) -> DocumentInDB:
    """Update document metadata."""
    try:
        document_service = DocumentService()
        
        document = await document_service.update_document(
            tenant=current_user.tenant,
            document_id=document_id,
            name=document_update.name,
            metadata=document_update.metadata,
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        logger.info(
            f"Updated document via API",
            document_id=str(document_id),
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
        )
        
        return DocumentInDB.model_validate(document)
        
    except DocumentError as e:
        logger.error(f"Document update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{document_id}")
async def delete_document(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    document_id: UUID,
    hard_delete: bool = Query(False),
) -> dict:
    """Delete a document and its chunks."""
    try:
        document_service = DocumentService()
        
        deleted = await document_service.delete_document(
            tenant=current_user.tenant,
            document_id=document_id,
            hard_delete=hard_delete,
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        logger.info(
            f"Deleted document via API",
            document_id=str(document_id),
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
            hard_delete=hard_delete,
        )
        
        return {
            "message": "Document deleted successfully",
            "document_id": str(document_id),
            "hard_delete": hard_delete,
        }
        
    except DocumentError as e:
        logger.error(f"Document deletion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/{document_id}/reingest", response_model=DocumentInDB)
async def reingest_document(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    document_id: UUID,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
) -> DocumentInDB:
    """Re-ingest a document with optional new content."""
    try:
        document_service = DocumentService()
        
        document, job_id = await document_service.reingest_document(
            tenant=current_user.tenant,
            document_id=document_id,
            file=file,
            url=url,
        )
        
        logger.info(
            f"Re-ingested document via API",
            document_id=str(document_id),
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
            job_id=job_id,
        )
        
        return DocumentInDB.model_validate(document)
        
    except DocumentError as e:
        logger.error(f"Document re-ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to re-ingest document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    document_id: UUID,
) -> DocumentStatusResponse:
    """Get detailed processing status for a document."""
    try:
        document_service = DocumentService()
        
        status_info = await document_service.get_document_status(
            tenant=current_user.tenant,
            document_id=document_id,
        )
        
        if status_info.get("status") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentStatusResponse(**status_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document status {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats/tenant")
async def get_tenant_document_statistics(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
) -> dict:
    """Get document statistics for the current tenant."""
    try:
        document_service = DocumentService()
        
        stats = await document_service.get_tenant_statistics(
            tenant=current_user.tenant
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get tenant statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )