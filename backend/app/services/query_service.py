"""
Query service that orchestrates the complete RAG pipeline.
Handles question answering, citation verification, and response formatting.
"""

import asyncio
import time
from typing import Dict, List, Optional
from uuid import UUID

from app.core.config import settings
from app.core.errors import InsufficientContextError, RetrievalError
from app.core.logging import get_logger
from app.generation.generator import AnswerGenerator, GeneratedAnswer
from app.models.tenant import Tenant
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.sparse import bm25_manager
from app.verification.verifier import CitationVerifier

logger = get_logger(__name__)


class QueryResult:
    """Container for complete query processing result."""
    
    def __init__(
        self,
        query: str,
        answer: str,
        citations: List[Dict],
        retrieved_chunks: List[Dict],
        confidence_score: float,
        processing_time: float,
        verification_results: List[Dict] = None,
        metadata: Dict = None,
        has_sufficient_context: bool = True,
        requires_human_handoff: bool = False
    ):
        self.query = query
        self.answer = answer
        self.citations = citations
        self.retrieved_chunks = retrieved_chunks
        self.confidence_score = confidence_score
        self.processing_time = processing_time
        self.verification_results = verification_results or []
        self.metadata = metadata or {}
        self.has_sufficient_context = has_sufficient_context
        self.requires_human_handoff = requires_human_handoff
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            'query': self.query,
            'answer': self.answer,
            'citations': self.citations,
            'retrieved_chunks': self.retrieved_chunks,
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time,
            'verification_results': self.verification_results,
            'metadata': self.metadata,
            'has_sufficient_context': self.has_sufficient_context,
            'requires_human_handoff': self.requires_human_handoff,
            'status': 'success' if self.has_sufficient_context else 'insufficient_context'
        }


class QueryService:
    """Service for handling user queries through the complete RAG pipeline."""
    
    def __init__(self):
        self.answer_generator = AnswerGenerator()
        self.citation_verifier = CitationVerifier()
        
        # Configuration
        self.min_confidence_threshold = settings.CITATION_CONFIDENCE_THRESHOLD
        self.enable_verification = True
        self.enable_handoff_detection = True
    
    async def process_query(
        self,
        tenant: Tenant,
        query: str,
        document_ids: Optional[List[str]] = None,
        metadata_filter: Optional[Dict] = None,
        enable_verification: Optional[bool] = None,
        conversation_id: Optional[str] = None
    ) -> QueryResult:
        """
        Process a user query through the complete RAG pipeline.
        
        Args:
            tenant: Tenant making the query
            query: User question/query
            document_ids: Optional list to filter by specific documents  
            metadata_filter: Optional metadata filter conditions
            enable_verification: Whether to enable citation verification
            conversation_id: Optional conversation ID for context
            
        Returns:
            QueryResult with answer, citations, and metadata
        """
        start_time = time.time()
        
        try:
            logger.info(
                f"Processing query",
                tenant_id=str(tenant.id),
                query_length=len(query),
                document_filter=len(document_ids) if document_ids else 0,
                conversation_id=conversation_id
            )
            
            # Validate query
            if not query.strip():
                return self._create_error_result(
                    query, "Please provide a valid question.", start_time
                )
            
            if len(query) > 1000:  # Reasonable query length limit
                return self._create_error_result(
                    query, "Your question is too long. Please try a shorter version.", start_time
                )
            
            # Step 1: Generate answer using retrieval + LLM
            generated_answer = await self.answer_generator.generate_answer(
                tenant_id=tenant.id,
                query=query,
                document_ids=document_ids,
                metadata_filter=metadata_filter
            )
            
            # Step 2: Check if we have sufficient context
            if not generated_answer.has_sufficient_context:
                processing_time = time.time() - start_time
                
                logger.warning(
                    f"Insufficient context for query",
                    tenant_id=str(tenant.id),
                    query_preview=query[:100]
                )
                
                return QueryResult(
                    query=query,
                    answer=generated_answer.answer,
                    citations=[],
                    retrieved_chunks=[chunk.to_dict() for chunk in generated_answer.retrieved_chunks],
                    confidence_score=0.0,
                    processing_time=processing_time,
                    has_sufficient_context=False,
                    requires_human_handoff=self.enable_handoff_detection,
                    metadata={
                        'reason': 'insufficient_context',
                        'retrieved_chunks_count': len(generated_answer.retrieved_chunks)
                    }
                )
            
            # Step 3: Verify citations if enabled
            verification_results = []
            if (enable_verification is None and self.enable_verification) or enable_verification:
                try:
                    generated_answer, verification_results = await self.citation_verifier.verify_answer(
                        generated_answer, query
                    )
                except Exception as e:
                    logger.warning(f"Citation verification failed: {e}")
                    # Continue without verification
            
            # Step 4: Check if human handoff is needed
            requires_handoff = self._should_trigger_handoff(generated_answer, verification_results)
            
            processing_time = time.time() - start_time
            
            # Step 5: Create result
            result = QueryResult(
                query=query,
                answer=generated_answer.answer,
                citations=[citation.to_dict() for citation in generated_answer.citations],
                retrieved_chunks=[chunk.to_dict() for chunk in generated_answer.retrieved_chunks],
                confidence_score=generated_answer.confidence_score,
                processing_time=processing_time,
                verification_results=[vr.to_dict() for vr in verification_results],
                has_sufficient_context=generated_answer.has_sufficient_context,
                requires_human_handoff=requires_handoff,
                metadata={
                    'llm_provider': generated_answer.llm_response_metadata.get('provider'),
                    'llm_model': generated_answer.llm_response_metadata.get('model'),
                    'retrieval_strategy': 'hybrid',
                    'verification_enabled': bool(verification_results),
                    'conversation_id': conversation_id,
                    'tenant_id': str(tenant.id)
                }
            )
            
            logger.info(
                f"Query processing completed",
                tenant_id=str(tenant.id),
                answer_length=len(generated_answer.answer),
                citations_count=len(generated_answer.citations),
                confidence_score=generated_answer.confidence_score,
                processing_time=processing_time,
                requires_handoff=requires_handoff
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Query processing failed: {e}",
                tenant_id=str(tenant.id),
                query_preview=query[:100]
            )
            
            return self._create_error_result(
                query, 
                "I encountered an error while processing your question. Please try again or contact support if the problem persists.",
                start_time,
                error_details=str(e)
            )
    
    def _should_trigger_handoff(
        self,
        answer: GeneratedAnswer,
        verification_results: List
    ) -> bool:
        """Determine if human handoff should be triggered."""
        try:
            if not self.enable_handoff_detection:
                return False
            
            # Trigger handoff if confidence is too low
            if answer.confidence_score < self.min_confidence_threshold:
                return True
            
            # Trigger handoff if many citations are unverified
            if verification_results:
                verified_count = sum(1 for vr in verification_results if vr.citation.verified)
                verification_ratio = verified_count / len(verification_results)
                
                if verification_ratio < 0.5:  # Less than 50% verified
                    return True
            
            # Check for uncertainty phrases in answer
            uncertainty_phrases = [
                "i don't know",
                "i'm not sure",
                "i don't have enough information",
                "i cannot determine",
                "it's unclear",
                "i'm unable to answer"
            ]
            
            answer_lower = answer.answer.lower()
            if any(phrase in answer_lower for phrase in uncertainty_phrases):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Handoff detection failed: {e}")
            return False
    
    def _create_error_result(
        self,
        query: str,
        error_message: str,
        start_time: float,
        error_details: Optional[str] = None
    ) -> QueryResult:
        """Create error result for failed queries."""
        processing_time = time.time() - start_time
        
        metadata = {'error': True}
        if error_details:
            metadata['error_details'] = error_details
        
        return QueryResult(
            query=query,
            answer=error_message,
            citations=[],
            retrieved_chunks=[],
            confidence_score=0.0,
            processing_time=processing_time,
            has_sufficient_context=False,
            requires_human_handoff=self.enable_handoff_detection,
            metadata=metadata
        )
    
    async def get_query_suggestions(
        self,
        tenant: Tenant,
        document_ids: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[str]:
        """
        Generate query suggestions based on document content.
        This is a placeholder for future implementation.
        """
        try:
            # For now, return generic suggestions
            # In production, you could analyze document content to generate relevant questions
            
            generic_suggestions = [
                "What are the main topics covered in these documents?",
                "Can you summarize the key points?",
                "What are the important procedures mentioned?",
                "Are there any requirements I should be aware of?",
                "What are the contact details mentioned?"
            ]
            
            return generic_suggestions[:limit]
            
        except Exception as e:
            logger.warning(f"Query suggestion generation failed: {e}")
            return []
    
    async def get_conversation_context(
        self,
        tenant: Tenant,
        conversation_id: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get recent conversation history for context.
        This is a placeholder for future implementation.
        """
        try:
            # For now, return empty context
            # In production, you would fetch from conversation history storage
            
            return []
            
        except Exception as e:
            logger.warning(f"Conversation context retrieval failed: {e}")
            return []
    
    async def update_bm25_index(
        self,
        tenant: Tenant,
        operation: str,
        document_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        Update BM25 index after document changes.
        
        Args:
            tenant: Tenant whose index to update
            operation: 'rebuild' or 'remove_documents'
            document_ids: Document IDs for removal operation
            
        Returns:
            Operation result
        """
        try:
            bm25_index = bm25_manager.get_index(tenant.id)
            
            if operation == 'rebuild':
                bm25_index.rebuild_index()
                stats = bm25_index.get_stats()
                
                return {
                    'status': 'success',
                    'operation': 'rebuild',
                    'stats': stats
                }
                
            elif operation == 'remove_documents' and document_ids:
                total_removed = 0
                for doc_id in document_ids:
                    removed = bm25_index.remove_document_chunks(doc_id)
                    total_removed += removed
                
                return {
                    'status': 'success',
                    'operation': 'remove_documents',
                    'documents_removed': len(document_ids),
                    'chunks_removed': total_removed
                }
            
            else:
                return {
                    'status': 'error',
                    'error': f'Unknown operation: {operation}'
                }
                
        except Exception as e:
            logger.error(f"BM25 index update failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def get_retrieval_stats(self, tenant: Tenant) -> Dict:
        """Get comprehensive retrieval statistics for tenant."""
        try:
            # Get hybrid retriever stats
            retrieval_stats = await self.answer_generator.retriever.get_retrieval_stats(tenant.id)
            
            return {
                'tenant_id': str(tenant.id),
                'retrieval': retrieval_stats,
                'configuration': {
                    'confidence_threshold': self.min_confidence_threshold,
                    'verification_enabled': self.enable_verification,
                    'handoff_enabled': self.enable_handoff_detection
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get retrieval stats: {e}")
            return {
                'tenant_id': str(tenant.id),
                'error': str(e)
            }
    
    async def health_check(self) -> Dict:
        """Check health of query service components."""
        try:
            # Check answer generator
            generator_health = await self.answer_generator.health_check()
            
            # Check citation verifier
            verifier_health = await self.citation_verifier.health_check()
            
            # Overall health
            components_healthy = (
                generator_health.get('status') == 'healthy' and
                verifier_health.get('status') == 'healthy'
            )
            
            return {
                'status': 'healthy' if components_healthy else 'unhealthy',
                'components': {
                    'answer_generator': generator_health,
                    'citation_verifier': verifier_health
                },
                'configuration': {
                    'confidence_threshold': self.min_confidence_threshold,
                    'verification_enabled': self.enable_verification,
                    'handoff_detection_enabled': self.enable_handoff_detection
                }
            }
            
        except Exception as e:
            logger.error(f"Query service health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def close(self):
        """Clean up query service resources."""
        try:
            await self.answer_generator.close()
            await self.citation_verifier.close()
            logger.info("Query service closed")
        except Exception as e:
            logger.warning(f"Error closing query service: {e}")