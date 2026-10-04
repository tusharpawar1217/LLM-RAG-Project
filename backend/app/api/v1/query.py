"""
Query API endpoints for question answering.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_user, get_session
from app.core.logging import get_logger
from app.db.models import User
from app.services.query_service import QueryService

logger = get_logger(__name__)

router = APIRouter()


# Request/Response schemas
class QueryRequest(BaseModel):
    """Schema for query requests."""
    query: str = Field(..., min_length=1, max_length=1000, description="User question or query")
    document_ids: Optional[List[str]] = Field(None, description="Optional list of document IDs to search within")
    metadata_filter: Optional[dict] = Field(None, description="Optional metadata filter conditions")
    enable_verification: Optional[bool] = Field(None, description="Enable citation verification")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")


class QueryResponse(BaseModel):
    """Schema for query responses."""
    query: str
    answer: str
    citations: List[dict]
    retrieved_chunks: List[dict]
    confidence_score: float
    processing_time: float
    verification_results: List[dict]
    metadata: dict
    has_sufficient_context: bool
    requires_human_handoff: bool
    status: str


class QuerySuggestionsResponse(BaseModel):
    """Schema for query suggestions."""
    suggestions: List[str]
    document_count: int


class RetrievalStatsResponse(BaseModel):
    """Schema for retrieval statistics."""
    tenant_id: str
    retrieval: dict
    configuration: dict


@router.post("/", response_model=QueryResponse)
async def query_documents(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    request: QueryRequest
) -> QueryResponse:
    """
    Ask a question about the uploaded documents.
    Uses hybrid retrieval and LLM generation with citation verification.
    """
    try:
        query_service = QueryService()
        
        # Validate document_ids if provided
        validated_doc_ids = None
        if request.document_ids:
            # Here you could validate that the documents exist and belong to the tenant
            # For now, we'll pass them through
            validated_doc_ids = request.document_ids
        
        # Process the query
        result = await query_service.process_query(
            tenant=current_user.tenant,
            query=request.query,
            document_ids=validated_doc_ids,
            metadata_filter=request.metadata_filter,
            enable_verification=request.enable_verification,
            conversation_id=request.conversation_id
        )
        
        logger.info(
            f"Query processed via API",
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
            query_length=len(request.query),
            confidence_score=result.confidence_score,
            citations_count=len(result.citations),
            processing_time=result.processing_time
        )
        
        return QueryResponse(**result.to_dict())
        
    except Exception as e:
        logger.error(f"Query API failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process query. Please try again."
        )


@router.get("/suggestions", response_model=QuerySuggestionsResponse)
async def get_query_suggestions(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    document_ids: Optional[List[str]] = Query(None),
    limit: int = Query(5, ge=1, le=10)
) -> QuerySuggestionsResponse:
    """Get suggested queries based on document content."""
    try:
        query_service = QueryService()
        
        suggestions = await query_service.get_query_suggestions(
            tenant=current_user.tenant,
            document_ids=document_ids,
            limit=limit
        )
        
        # Get document count for reference
        # This could be enhanced to get actual document count
        document_count = len(document_ids) if document_ids else 0
        
        return QuerySuggestionsResponse(
            suggestions=suggestions,
            document_count=document_count
        )
        
    except Exception as e:
        logger.error(f"Query suggestions API failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get query suggestions"
        )


@router.get("/stats/retrieval", response_model=RetrievalStatsResponse)
async def get_retrieval_statistics(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user)
) -> RetrievalStatsResponse:
    """Get retrieval system statistics for the current tenant."""
    try:
        query_service = QueryService()
        
        stats = await query_service.get_retrieval_stats(current_user.tenant)
        
        return RetrievalStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Retrieval stats API failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get retrieval statistics"
        )


@router.post("/index/update")
async def update_search_index(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    operation: str = Query(..., regex="^(rebuild|remove_documents)$"),
    document_ids: Optional[List[str]] = Query(None)
) -> dict:
    """
    Update search indices after document changes.
    
    Operations:
    - rebuild: Rebuild the entire BM25 index  
    - remove_documents: Remove specific documents from index
    """
    try:
        query_service = QueryService()
        
        result = await query_service.update_bm25_index(
            tenant=current_user.tenant,
            operation=operation,
            document_ids=document_ids
        )
        
        logger.info(
            f"Search index updated via API",
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
            operation=operation,
            result=result
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Index update API failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update search index"
        )


@router.get("/health")
async def query_health_check(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user)
) -> dict:
    """Check health of query processing components."""
    try:
        query_service = QueryService()
        
        health = await query_service.health_check()
        
        return health
        
    except Exception as e:
        logger.error(f"Query health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


# Conversation endpoints (for future implementation)
@router.get("/conversations/{conversation_id}/history")
async def get_conversation_history(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    conversation_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> dict:
    """
    Get conversation history.
    Placeholder for future conversation tracking implementation.
    """
    try:
        # For now, return empty history
        # In production, you would fetch from conversation storage
        
        return {
            'conversation_id': conversation_id,
            'messages': [],
            'total': 0,
            'limit': limit,
            'offset': offset
        }
        
    except Exception as e:
        logger.error(f"Conversation history API failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation history"
        )


@router.post("/feedback")
async def submit_query_feedback(
    *,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_tenant_user),
    query: str = Field(..., description="Original query"),
    answer: str = Field(..., description="Generated answer"),
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5"),
    feedback: Optional[str] = Field(None, description="Optional feedback text"),
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
) -> dict:
    """
    Submit feedback on query results.
    Placeholder for future feedback collection implementation.
    """
    try:
        # For now, just log the feedback
        # In production, you would store this for analysis and improvement
        
        logger.info(
            f"Query feedback submitted",
            tenant_id=str(current_user.tenant.id),
            user_id=str(current_user.id),
            rating=rating,
            query_length=len(query),
            answer_length=len(answer),
            has_feedback_text=feedback is not None
        )
        
        return {
            'status': 'success',
            'message': 'Thank you for your feedback!'
        }
        
    except Exception as e:
        logger.error(f"Query feedback API failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )

