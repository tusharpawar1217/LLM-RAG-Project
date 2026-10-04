"""
Answer generator that combines retrieval with LLM generation.
Produces contextual answers with proper citations from retrieved chunks.
"""

import re
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.core.config import settings
from app.core.errors import GenerationError, InsufficientContextError
from app.core.logging import get_logger
from app.generation.llm import LLMService
from app.retrieval.hybrid import HybridRetriever, RetrievedChunk

logger = get_logger(__name__)


class Citation:
    """Container for citation with metadata."""
    
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        document_name: str,
        content: str,
        page_number: Optional[int] = None,
        section_heading: Optional[str] = None,
        metadata: Optional[Dict] = None,
        verified: bool = False
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_name = document_name
        self.content = content
        self.page_number = page_number
        self.section_heading = section_heading
        self.metadata = metadata or {}
        self.verified = verified
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'document_name': self.document_name,
            'content': self.content,
            'page_number': self.page_number,
            'section_heading': self.section_heading,
            'metadata': self.metadata,
            'verified': self.verified
        }
    
    def format_citation(self) -> str:
        """Format citation for display."""
        parts = [self.document_name]
        
        if self.page_number:
            parts.append(f"p.{self.page_number}")
        
        if self.section_heading:
            parts.append(f'"{self.section_heading}"')
        
        return f"[{', '.join(parts)}]"


class GeneratedAnswer:
    """Container for generated answer with citations and metadata."""
    
    def __init__(
        self,
        answer: str,
        citations: List[Citation],
        retrieved_chunks: List[RetrievedChunk],
        confidence_score: float = 0.0,
        has_sufficient_context: bool = True,
        llm_response_metadata: Optional[Dict] = None,
        processing_time: float = 0.0
    ):
        self.answer = answer
        self.citations = citations
        self.retrieved_chunks = retrieved_chunks
        self.confidence_score = confidence_score
        self.has_sufficient_context = has_sufficient_context
        self.llm_response_metadata = llm_response_metadata or {}
        self.processing_time = processing_time
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            'answer': self.answer,
            'citations': [citation.to_dict() for citation in self.citations],
            'retrieved_chunks': [chunk.to_dict() for chunk in self.retrieved_chunks],
            'confidence_score': self.confidence_score,
            'has_sufficient_context': self.has_sufficient_context,
            'llm_metadata': self.llm_response_metadata,
            'processing_time': self.processing_time,
            'num_citations': len(self.citations),
            'num_retrieved_chunks': len(self.retrieved_chunks)
        }


class AnswerGenerator:
    """Generates contextual answers from user queries using retrieval + LLM."""
    
    def __init__(self):
        self.retriever = HybridRetriever()
        self.llm_service = LLMService()
        
        # System prompt for answer generation
        self.system_prompt = self._build_system_prompt()
    
    async def generate_answer(
        self,
        tenant_id: UUID,
        query: str,
        document_ids: Optional[List[str]] = None,
        metadata_filter: Optional[Dict] = None,
        min_chunks: int = 1,
        max_chunks: int = 5
    ) -> GeneratedAnswer:
        """
        Generate an answer to a user query using retrieved context.
        
        Args:
            tenant_id: Tenant ID for data isolation
            query: User question/query
            document_ids: Optional list to filter by specific documents
            metadata_filter: Optional metadata filter conditions
            min_chunks: Minimum number of chunks needed for answer
            max_chunks: Maximum number of chunks to include in context
            
        Returns:
            GeneratedAnswer with response, citations, and metadata
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(
                f"Generating answer",
                tenant_id=str(tenant_id),
                query_length=len(query),
                document_filter=len(document_ids) if document_ids else 0
            )
            
            # Step 1: Retrieve relevant chunks
            retrieved_chunks = await self.retriever.retrieve(
                tenant_id=tenant_id,
                query=query,
                top_k=max_chunks,
                document_ids=document_ids,
                metadata_filter=metadata_filter,
                enable_reranking=settings.ENABLE_RERANKER
            )
            
            # Step 2: Check if we have sufficient context
            if len(retrieved_chunks) < min_chunks:
                processing_time = time.time() - start_time
                logger.warning(
                    f"Insufficient context for answer generation",
                    retrieved_chunks=len(retrieved_chunks),
                    min_required=min_chunks,
                    tenant_id=str(tenant_id)
                )
                
                return GeneratedAnswer(
                    answer="I don't have enough relevant information in the provided documents to answer your question. Please try rephrasing your question or check if the relevant documents have been uploaded.",
                    citations=[],
                    retrieved_chunks=retrieved_chunks,
                    confidence_score=0.0,
                    has_sufficient_context=False,
                    processing_time=processing_time
                )
            
            # Step 3: Build context from retrieved chunks
            context = self._build_context(retrieved_chunks, query)
            
            # Step 4: Generate answer using LLM
            prompt = self._build_prompt(query, context)
            
            llm_response = await self.llm_service.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS
            )
            
            # Step 5: Extract citations from answer
            citations = self._extract_citations(llm_response.content, retrieved_chunks)
            
            # Step 6: Calculate confidence score
            confidence_score = self._calculate_confidence(
                llm_response.content, retrieved_chunks, citations
            )
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Answer generation completed",
                answer_length=len(llm_response.content),
                num_citations=len(citations),
                confidence_score=confidence_score,
                processing_time=processing_time,
                tenant_id=str(tenant_id)
            )
            
            return GeneratedAnswer(
                answer=llm_response.content,
                citations=citations,
                retrieved_chunks=retrieved_chunks,
                confidence_score=confidence_score,
                has_sufficient_context=True,
                llm_response_metadata=llm_response.to_dict(),
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Answer generation failed: {e}")
            
            # Return error answer
            return GeneratedAnswer(
                answer="I encountered an error while processing your question. Please try again or contact support if the problem persists.",
                citations=[],
                retrieved_chunks=[],
                confidence_score=0.0,
                has_sufficient_context=False,
                processing_time=processing_time,
                llm_response_metadata={'error': str(e)}
            )
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for answer generation."""
        return """You are an expert assistant that answers questions based strictly on the provided context documents. Follow these guidelines:

1. ONLY use information from the provided context documents to answer questions
2. If the context doesn't contain enough information to answer the question, say "I don't have enough information in the provided documents to answer this question"
3. Include inline citations in your answer using the format [Doc_ID] where Doc_ID matches the chunk identifier from the context
4. Be accurate and specific - don't make up or hallucinate any information not present in the context
5. If multiple documents support the same point, cite all relevant sources
6. Structure your answer clearly with proper formatting when appropriate
7. If the question asks for information that's partially covered, answer what you can and clearly state what information is missing

Remember: Your credibility depends on only using the provided context and citing sources appropriately."""
    
    def _build_context(self, chunks: List[RetrievedChunk], query: str) -> str:
        """Build context string from retrieved chunks."""
        context_parts = []
        
        for i, chunk in enumerate(chunks):
            # Create chunk identifier for citations
            chunk_id = f"Doc_{i+1}"
            
            # Get document name from metadata
            doc_name = chunk.metadata.get('document_name', f"Document {chunk.document_id[:8]}")
            
            # Build context entry
            context_part = f"[{chunk_id}] Source: {doc_name}\n"
            
            # Add page/section info if available
            if chunk.metadata.get('page_number'):
                context_part += f"Page: {chunk.metadata['page_number']}\n"
            
            if chunk.metadata.get('section_heading'):
                context_part += f"Section: {chunk.metadata['section_heading']}\n"
            
            context_part += f"Content: {chunk.content}\n"
            
            context_parts.append(context_part)
        
        return "\n---\n".join(context_parts)
    
    def _build_prompt(self, query: str, context: str) -> str:
        """Build the complete prompt for answer generation."""
        return f"""Context Documents:
{context}

---

Question: {query}

Please provide a comprehensive answer based on the context documents above. Remember to cite your sources using the [Doc_ID] format."""
    
    def _extract_citations(
        self, answer: str, chunks: List[RetrievedChunk]
    ) -> List[Citation]:
        """Extract and validate citations from the generated answer."""
        citations = []
        
        # Find all citation patterns [Doc_X] in the answer
        citation_pattern = r'\[Doc_(\d+)\]'
        matches = re.findall(citation_pattern, answer)
        
        for match in matches:
            try:
                # Convert to 0-based index
                chunk_index = int(match) - 1
                
                if 0 <= chunk_index < len(chunks):
                    chunk = chunks[chunk_index]
                    
                    # Create citation
                    citation = Citation(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        document_name=chunk.metadata.get('document_name', f"Document {chunk.document_id[:8]}"),
                        content=chunk.content,
                        page_number=chunk.metadata.get('page_number'),
                        section_heading=chunk.metadata.get('section_heading'),
                        metadata=chunk.metadata,
                        verified=False  # Will be verified separately
                    )
                    
                    # Avoid duplicate citations
                    if not any(c.chunk_id == citation.chunk_id for c in citations):
                        citations.append(citation)
                        
            except ValueError:
                logger.warning(f"Invalid citation format: Doc_{match}")
                continue
        
        logger.debug(f"Extracted {len(citations)} citations from answer")
        return citations
    
    def _calculate_confidence(
        self,
        answer: str,
        chunks: List[RetrievedChunk],
        citations: List[Citation]
    ) -> float:
        """Calculate confidence score for the generated answer."""
        try:
            # Factors that influence confidence
            confidence_factors = []
            
            # 1. Citation coverage (how many chunks are cited)
            if chunks:
                citation_coverage = len(citations) / len(chunks)
                confidence_factors.append(min(citation_coverage, 1.0) * 0.3)
            
            # 2. Answer length (reasonable answers are usually substantial)
            answer_length_score = min(len(answer) / 500, 1.0) * 0.2  # Normalize to 500 chars
            confidence_factors.append(answer_length_score)
            
            # 3. Retrieval scores (average of top chunks)
            if chunks:
                avg_retrieval_score = sum(chunk.combined_score for chunk in chunks[:3]) / min(len(chunks), 3)
                # Normalize assuming max RRF score around 0.5
                retrieval_confidence = min(avg_retrieval_score * 2, 1.0) * 0.3
                confidence_factors.append(retrieval_confidence)
            
            # 4. "I don't know" detection (lower confidence if uncertain)
            uncertain_phrases = [
                "i don't have enough information",
                "i don't know",
                "not enough information",
                "insufficient information",
                "cannot determine",
                "unable to answer"
            ]
            
            answer_lower = answer.lower()
            has_uncertainty = any(phrase in answer_lower for phrase in uncertain_phrases)
            uncertainty_penalty = 0.5 if has_uncertainty else 1.0
            
            # 5. Base confidence (minimum threshold)
            confidence_factors.append(0.2)  # Base confidence
            
            # Calculate weighted average
            base_confidence = sum(confidence_factors)
            final_confidence = base_confidence * uncertainty_penalty
            
            # Ensure confidence is between 0 and 1
            final_confidence = max(0.0, min(1.0, final_confidence))
            
            logger.debug(
                f"Confidence calculation",
                factors=confidence_factors,
                uncertainty_penalty=uncertainty_penalty,
                final_confidence=final_confidence
            )
            
            return final_confidence
            
        except Exception as e:
            logger.warning(f"Confidence calculation failed: {e}")
            return 0.5  # Default moderate confidence
    
    async def health_check(self) -> Dict:
        """Check health of answer generation components."""
        try:
            # Check retriever health
            retriever_health = await self.retriever.health_check()
            
            # Check LLM service health
            llm_health = await self.llm_service.health_check()
            
            # Overall health
            components_healthy = (
                retriever_health.get('status') == 'healthy' and
                llm_health.get('status') == 'healthy'
            )
            
            return {
                'status': 'healthy' if components_healthy else 'unhealthy',
                'components': {
                    'retriever': retriever_health,
                    'llm_service': llm_health
                },
                'configuration': {
                    'min_context_threshold': settings.TOP_K_FINAL,
                    'citation_enabled': True,
                    'confidence_threshold': settings.CITATION_CONFIDENCE_THRESHOLD
                }
            }
            
        except Exception as e:
            logger.error(f"Answer generator health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def close(self):
        """Clean up answer generator resources."""
        try:
            await self.retriever.close()
            await self.llm_service.close()
            logger.info("Answer generator closed")
        except Exception as e:
            logger.warning(f"Error closing answer generator: {e}")

