"""
Citation verification system to ensure answer accuracy and prevent hallucination.
Verifies that citations exist in retrieved chunks and claims are grounded.
"""

import asyncio
import re
from typing import Dict, List, Tuple
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.generation.generator import Citation, GeneratedAnswer
from app.generation.llm import LLMService

logger = get_logger(__name__)


class VerificationResult:
    """Container for citation verification results."""
    
    def __init__(
        self,
        citation: Citation,
        exists_in_context: bool = False,
        content_match_score: float = 0.0,
        semantic_match_score: float = 0.0,
        llm_verification_score: float = 0.0,
        overall_confidence: float = 0.0,
        verification_details: Dict = None
    ):
        self.citation = citation
        self.exists_in_context = exists_in_context
        self.content_match_score = content_match_score
        self.semantic_match_score = semantic_match_score
        self.llm_verification_score = llm_verification_score
        self.overall_confidence = overall_confidence
        self.verification_details = verification_details or {}
        
        # Mark citation as verified based on confidence threshold
        self.citation.verified = overall_confidence >= settings.CITATION_CONFIDENCE_THRESHOLD
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            'citation': self.citation.to_dict(),
            'verification': {
                'exists_in_context': self.exists_in_context,
                'content_match_score': self.content_match_score,
                'semantic_match_score': self.semantic_match_score,
                'llm_verification_score': self.llm_verification_score,
                'overall_confidence': self.overall_confidence,
                'verified': self.citation.verified,
                'details': self.verification_details
            }
        }


class CitationVerifier:
    """Verifies citations to ensure answer accuracy and prevent hallucination."""
    
    def __init__(self):
        self.llm_service = LLMService()
        
        # Verification thresholds
        self.confidence_threshold = settings.CITATION_CONFIDENCE_THRESHOLD
        self.use_llm_judge = settings.VERIFICATION_USE_LLM_JUDGE
    
    async def verify_answer(
        self,
        answer: GeneratedAnswer,
        original_query: str
    ) -> Tuple[GeneratedAnswer, List[VerificationResult]]:
        """
        Verify all citations in a generated answer.
        
        Args:
            answer: Generated answer with citations
            original_query: Original user query for context
            
        Returns:
            Tuple of (updated answer, verification results)
        """
        try:
            logger.info(
                f"Starting citation verification",
                num_citations=len(answer.citations),
                use_llm_judge=self.use_llm_judge
            )
            
            if not answer.citations:
                # No citations to verify
                return answer, []
            
            # Verify each citation
            verification_tasks = [
                self._verify_citation(citation, answer, original_query)
                for citation in answer.citations
            ]
            
            verification_results = await asyncio.gather(*verification_tasks, return_exceptions=True)
            
            # Handle any exceptions in verification
            valid_results = []
            for i, result in enumerate(verification_results):
                if isinstance(result, Exception):
                    logger.warning(f"Citation {i} verification failed: {result}")
                    # Create a failed verification result
                    valid_results.append(VerificationResult(
                        citation=answer.citations[i],
                        exists_in_context=False,
                        overall_confidence=0.0,
                        verification_details={'error': str(result)}
                    ))
                else:
                    valid_results.append(result)
            
            # Update answer confidence based on verification results
            updated_answer = self._update_answer_confidence(answer, valid_results)
            
            # Log verification summary
            verified_count = sum(1 for r in valid_results if r.citation.verified)
            avg_confidence = sum(r.overall_confidence for r in valid_results) / len(valid_results)
            
            logger.info(
                f"Citation verification completed",
                verified_citations=verified_count,
                total_citations=len(valid_results),
                avg_confidence=avg_confidence,
                answer_updated=updated_answer.confidence_score != answer.confidence_score
            )
            
            return updated_answer, valid_results
            
        except Exception as e:
            logger.error(f"Citation verification failed: {e}")
            # Return original answer with failed verification
            return answer, []
    
    async def _verify_citation(
        self,
        citation: Citation,
        answer: GeneratedAnswer,
        original_query: str
    ) -> VerificationResult:
        """Verify a single citation."""
        try:
            # Step 1: Check if citation exists in retrieved chunks
            exists_in_context = self._check_citation_exists(citation, answer.retrieved_chunks)
            
            if not exists_in_context:
                return VerificationResult(
                    citation=citation,
                    exists_in_context=False,
                    overall_confidence=0.0,
                    verification_details={'reason': 'Citation not found in retrieved context'}
                )
            
            # Step 2: Content matching (lexical overlap)
            content_match_score = self._calculate_content_match(citation, answer.answer)
            
            # Step 3: Semantic matching (optional, could use embeddings)
            semantic_match_score = await self._calculate_semantic_match(citation, answer.answer)
            
            # Step 4: LLM-based verification (if enabled)
            llm_verification_score = 0.0
            if self.use_llm_judge:
                llm_verification_score = await self._llm_verify_citation(
                    citation, answer.answer, original_query
                )
            
            # Step 5: Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(
                content_match_score, semantic_match_score, llm_verification_score
            )
            
            return VerificationResult(
                citation=citation,
                exists_in_context=exists_in_context,
                content_match_score=content_match_score,
                semantic_match_score=semantic_match_score,
                llm_verification_score=llm_verification_score,
                overall_confidence=overall_confidence,
                verification_details={
                    'content_overlap_words': self._count_overlapping_words(citation.content, answer.answer),
                    'citation_length': len(citation.content),
                    'llm_judge_used': self.use_llm_judge
                }
            )
            
        except Exception as e:
            logger.error(f"Single citation verification failed: {e}")
            return VerificationResult(
                citation=citation,
                exists_in_context=False,
                overall_confidence=0.0,
                verification_details={'error': str(e)}
            )
    
    def _check_citation_exists(self, citation: Citation, retrieved_chunks) -> bool:
        """Check if citation exists in retrieved chunks."""
        try:
            # Look for matching chunk ID or document ID + content
            for chunk in retrieved_chunks:
                if (chunk.id == citation.chunk_id or
                    chunk.document_id == citation.document_id):
                    
                    # Additional content verification
                    if self._text_similarity(citation.content, chunk.content) > 0.8:
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Citation existence check failed: {e}")
            return False
    
    def _calculate_content_match(self, citation: Citation, answer: str) -> float:
        """Calculate lexical content match between citation and answer."""
        try:
            # Extract key phrases from citation
            citation_words = set(self._extract_key_words(citation.content))
            answer_words = set(self._extract_key_words(answer))
            
            if not citation_words:
                return 0.0
            
            # Calculate overlap
            overlap = citation_words.intersection(answer_words)
            overlap_ratio = len(overlap) / len(citation_words)
            
            return min(overlap_ratio, 1.0)
            
        except Exception as e:
            logger.warning(f"Content match calculation failed: {e}")
            return 0.0
    
    async def _calculate_semantic_match(self, citation: Citation, answer: str) -> float:
        """Calculate semantic similarity between citation and answer."""
        try:
            # For now, use a simple heuristic based on sentence structure
            # In production, you could use sentence embeddings for better semantic matching
            
            citation_sentences = self._extract_sentences(citation.content)
            answer_sentences = self._extract_sentences(answer)
            
            max_similarity = 0.0
            for c_sent in citation_sentences:
                for a_sent in answer_sentences:
                    similarity = self._text_similarity(c_sent, a_sent)
                    max_similarity = max(max_similarity, similarity)
            
            return max_similarity
            
        except Exception as e:
            logger.warning(f"Semantic match calculation failed: {e}")
            return 0.0
    
    async def _llm_verify_citation(
        self,
        citation: Citation,
        answer: str,
        original_query: str
    ) -> float:
        """Use LLM to verify if citation supports claims in answer."""
        try:
            verification_prompt = f"""
Please verify if the following citation supports the claims made in the answer.

Original Question: {original_query}

Answer: {answer}

Citation Content: {citation.content}

Please analyze:
1. Does the citation content actually support the claims made in the answer?
2. Is the information in the citation relevant to the question?
3. Are there any contradictions between the citation and the answer?

Respond with a score from 0.0 to 1.0 where:
- 1.0 = Citation strongly supports the answer claims
- 0.8 = Citation generally supports the answer claims  
- 0.6 = Citation partially supports the answer claims
- 0.4 = Citation weakly supports the answer claims
- 0.2 = Citation barely supports the answer claims
- 0.0 = Citation does not support the answer claims

Score (number only):
"""
            
            response = await self.llm_service.generate(
                prompt=verification_prompt,
                temperature=0.1,  # Low temperature for consistent verification
                max_tokens=10
            )
            
            # Extract score from response
            score_match = re.search(r'(\d+\.?\d*)', response.content.strip())
            if score_match:
                score = float(score_match.group(1))
                return max(0.0, min(1.0, score))  # Clamp to [0,1]
            
            logger.warning(f"Could not parse LLM verification score: {response.content}")
            return 0.5  # Default middle score
            
        except Exception as e:
            logger.warning(f"LLM verification failed: {e}")
            return 0.5
    
    def _calculate_overall_confidence(
        self,
        content_match: float,
        semantic_match: float,
        llm_score: float
    ) -> float:
        """Calculate overall verification confidence."""
        try:
            # Weighted combination of scores
            weights = {
                'content': 0.4,
                'semantic': 0.3,
                'llm': 0.3 if self.use_llm_judge else 0.0
            }
            
            # Adjust weights if LLM judge is not used
            if not self.use_llm_judge:
                weights['content'] = 0.6
                weights['semantic'] = 0.4
            
            overall = (
                content_match * weights['content'] +
                semantic_match * weights['semantic'] +
                llm_score * weights['llm']
            )
            
            return max(0.0, min(1.0, overall))
            
        except Exception as e:
            logger.warning(f"Overall confidence calculation failed: {e}")
            return 0.0
    
    def _update_answer_confidence(
        self,
        answer: GeneratedAnswer,
        verification_results: List[VerificationResult]
    ) -> GeneratedAnswer:
        """Update answer confidence based on verification results."""
        try:
            if not verification_results:
                return answer
            
            # Calculate verification-adjusted confidence
            verified_count = sum(1 for r in verification_results if r.citation.verified)
            total_citations = len(verification_results)
            
            if total_citations == 0:
                citation_verification_score = 1.0  # No citations to verify
            else:
                citation_verification_score = verified_count / total_citations
            
            # Average verification confidence
            avg_verification_confidence = sum(
                r.overall_confidence for r in verification_results
            ) / len(verification_results)
            
            # Combine original confidence with verification results
            original_confidence = answer.confidence_score
            verification_weight = 0.6  # Give more weight to verification
            
            updated_confidence = (
                original_confidence * (1 - verification_weight) +
                avg_verification_confidence * verification_weight
            )
            
            # Apply penalty for unverified citations
            if citation_verification_score < 1.0:
                penalty = (1.0 - citation_verification_score) * 0.3
                updated_confidence *= (1.0 - penalty)
            
            # Update the answer
            answer.confidence_score = max(0.0, min(1.0, updated_confidence))
            
            # Update citation verification status
            for i, result in enumerate(verification_results):
                if i < len(answer.citations):
                    answer.citations[i].verified = result.citation.verified
            
            return answer
            
        except Exception as e:
            logger.warning(f"Answer confidence update failed: {e}")
            return answer
    
    # Utility methods
    def _extract_key_words(self, text: str) -> List[str]:
        """Extract key words from text, filtering out stop words."""
        import re
        
        # Simple stop words list
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'could', 'can', 'may', 'might', 'this', 'that', 'these', 'those'
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out stop words and short words
        key_words = [word for word in words if len(word) > 2 and word not in stop_words]
        
        return key_words
    
    def _extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text."""
        import re
        
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity based on word overlap."""
        try:
            words1 = set(self._extract_key_words(text1))
            words2 = set(self._extract_key_words(text2))
            
            if not words1 or not words2:
                return 0.0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
            
        except Exception:
            return 0.0
    
    def _count_overlapping_words(self, text1: str, text2: str) -> int:
        """Count overlapping words between two texts."""
        try:
            words1 = set(self._extract_key_words(text1))
            words2 = set(self._extract_key_words(text2))
            
            return len(words1.intersection(words2))
            
        except Exception:
            return 0
    
    async def health_check(self) -> Dict:
        """Check health of citation verifier."""
        try:
            # Check LLM service if used
            llm_health = {}
            if self.use_llm_judge:
                llm_health = await self.llm_service.health_check()
            
            return {
                'status': 'healthy',
                'configuration': {
                    'confidence_threshold': self.confidence_threshold,
                    'use_llm_judge': self.use_llm_judge,
                },
                'llm_service': llm_health if self.use_llm_judge else {'status': 'disabled'}
            }
            
        except Exception as e:
            logger.error(f"Citation verifier health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def close(self):
        """Clean up verifier resources."""
        try:
            if self.use_llm_judge:
                await self.llm_service.close()
            logger.info("Citation verifier closed")
        except Exception as e:
            logger.warning(f"Error closing citation verifier: {e}")