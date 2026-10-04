"""
Document schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from app.db.models import DocumentStatus as DocumentStatusEnum


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    name: str = Field(..., min_length=1, max_length=255)
    document_type: str = Field(..., min_length=1, max_length=50)
    url: Optional[str] = Field(None, max_length=2048)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator('document_type')
    def validate_document_type(cls, v):
        """Validate document type is supported."""
        supported_types = ['pdf', 'docx', 'doc', 'md', 'markdown', 'txt', 'text', 'url']
        if v.lower() not in supported_types:
            raise ValueError(f'Unsupported document type: {v}')
        return v.lower()

    @validator('url')
    def validate_url(cls, v):
        """Validate URL format if provided."""
        if v is not None:
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(v):
                raise ValueError('Invalid URL format')
        
        return v


class DocumentUpdate(BaseModel):
    """Schema for updating document metadata."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    metadata: Optional[Dict[str, Any]] = None


class DocumentInDB(BaseModel):
    """Schema for document in database (API response)."""
    id: UUID
    tenant_id: UUID
    name: str
    document_type: str
    status: DocumentStatusEnum
    chunk_count: int = 0
    content_hash: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    """Schema for paginated document list."""
    items: List[DocumentInDB]
    total: int
    limit: int
    offset: int
    
    @property
    def has_more(self) -> bool:
        """Check if there are more items after current page."""
        return (self.offset + self.limit) < self.total


class JobStatus(BaseModel):
    """Schema for ARQ job status."""
    job_id: str
    status: str  # queued, running, completed, not_found
    enqueue_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    finish_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class VectorStoreStatus(BaseModel):
    """Schema for vector store status."""
    tenant_id: str
    collection_name: Optional[str] = None
    total_chunks: int = 0
    collection_status: str = "unknown"
    document_chunks: Optional[int] = None
    document_id: Optional[str] = None
    document_error: Optional[str] = None
    error: Optional[str] = None


class DocumentStatus(BaseModel):
    """Schema for detailed document processing status."""
    document_id: str
    name: str
    type: str
    status: str
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    job: Optional[JobStatus] = None
    vector_store: Optional[VectorStoreStatus] = None


class DocumentStatistics(BaseModel):
    """Schema for tenant document statistics."""
    tenant_id: str
    document_counts: Dict[str, int] = Field(default_factory=dict)
    total_chunks: int = 0
    document_types: Dict[str, int] = Field(default_factory=dict)
    vector_store: Dict[str, Any] = Field(default_factory=dict)


class ChunkInDB(BaseModel):
    """Schema for document chunk."""
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class BulkDocumentOperation(BaseModel):
    """Schema for bulk document operations."""
    document_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., regex=r'^(delete|reingest|process)$')
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BulkOperationResult(BaseModel):
    """Schema for bulk operation results."""
    operation: str
    total_requested: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, str]] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response."""
    document: DocumentInDB
    job_id: str
    message: str = "Document uploaded and queued for processing"


class IngestionConfig(BaseModel):
    """Schema for ingestion configuration."""
    chunk_size: int = Field(800, ge=100, le=4000)
    chunk_overlap: int = Field(200, ge=0, le=1000)
    chunking_strategy: str = Field('recursive', regex=r'^(recursive|markdown)$')
    embedding_model: str = Field('text-embedding-3-small')
    batch_size: int = Field(100, ge=1, le=1000)

    @validator('chunk_overlap')
    def validate_chunk_overlap(cls, v, values):
        """Ensure chunk overlap is less than chunk size."""
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('Chunk overlap must be less than chunk size')
        return v


class ProcessingMetrics(BaseModel):
    """Schema for processing metrics."""
    tenant_id: str
    time_period: str  # day, week, month
    documents_processed: int = 0
    chunks_created: int = 0
    embedding_tokens: int = 0
    processing_time_avg: float = 0.0  # seconds
    error_rate: float = 0.0  # percentage
    cost_estimate: float = 0.0  # USD


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""
    status: str  # healthy, degraded, unhealthy
    components: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

