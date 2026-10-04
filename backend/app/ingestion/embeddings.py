"""
Embedding service using OpenAI embeddings with batching and error handling.
"""

import asyncio
from typing import Any

import numpy as np
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.errors import ExternalServiceError, OpenAIError
from app.core.logging import get_logger
from app.ingestion.chunking import DocumentChunk
from app.utils.cost_calculator import CostCalculator

logger = get_logger(__name__)


class EmbeddingResult:
    """Result of embedding operation."""
    
    def __init__(
        self,
        chunk: DocumentChunk,
        embedding: list[float],
        tokens_used: int,
        embedding_model: str,
    ):
        self.chunk = chunk
        self.embedding = embedding
        self.tokens_used = tokens_used
        self.embedding_model = embedding_model
        self.embedding_dimensions = len(embedding)


class EmbeddingService:
    """Service for generating embeddings using OpenAI."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimensions = settings.OPENAI_EMBEDDING_DIMENSIONS
        self.batch_size = settings.OPENAI_EMBEDDING_BATCH_SIZE
        self.cost_calculator = CostCalculator()
    
    async def embed_chunks(self, chunks: list[DocumentChunk]) -> list[EmbeddingResult]:
        """
        Generate embeddings for a list of chunks with batching.
        
        Args:
            chunks: List of DocumentChunk objects to embed
            
        Returns:
            List of EmbeddingResult objects
            
        Raises:
            OpenAIError: If embedding generation fails
        """
        if not chunks:
            return []
        
        logger.info(
            "Starting embedding generation",
            chunks_count=len(chunks),
            model=self.model,
            batch_size=self.batch_size,
        )
        
        try:
            # Process chunks in batches
            all_results = []
            total_tokens = 0
            
            for batch_start in range(0, len(chunks), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(chunks))
                batch = chunks[batch_start:batch_end]
                
                logger.debug(f"Processing batch {batch_start//self.batch_size + 1} ({len(batch)} chunks)")
                
                batch_results = await self._embed_batch(batch)
                all_results.extend(batch_results)
                
                batch_tokens = sum(result.tokens_used for result in batch_results)
                total_tokens += batch_tokens
                
                # Small delay between batches to avoid rate limiting
                if batch_end < len(chunks):
                    await asyncio.sleep(0.1)
            
            # Calculate costs
            estimated_cost = self.cost_calculator.calculate_embedding_cost(
                total_tokens, self.model
            )
            
            logger.info(
                "Embedding generation completed",
                total_chunks=len(chunks),
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                avg_tokens_per_chunk=total_tokens // len(chunks) if chunks else 0,
            )
            
            return all_results
            
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise OpenAIError(f"Failed to generate embeddings: {str(e)}")
    
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def _embed_batch(self, chunks: list[DocumentChunk]) -> list[EmbeddingResult]:
        """Generate embeddings for a batch of chunks with retries."""
        try:
            # Prepare texts
            texts = [chunk.content for chunk in chunks]
            
            # Call OpenAI API
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )
            
            # Process response
            results = []
            for i, (chunk, embedding_data) in enumerate(zip(chunks, response.data)):
                result = EmbeddingResult(
                    chunk=chunk,
                    embedding=embedding_data.embedding,
                    tokens_used=response.usage.total_tokens // len(chunks),  # Approximate per chunk
                    embedding_model=self.model,
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error("Batch embedding failed", batch_size=len(chunks), error=str(e))
            
            # If batch fails, try individual chunks
            if len(chunks) > 1:
                logger.info("Retrying with individual chunks")
                individual_results = []
                
                for chunk in chunks:
                    try:
                        individual_result = await self._embed_single_chunk(chunk)
                        individual_results.append(individual_result)
                    except Exception as single_error:
                        logger.error(
                            "Individual chunk embedding failed",
                            chunk_index=chunk.chunk_index,
                            error=str(single_error)
                        )
                        raise
                
                return individual_results
            else:
                raise OpenAIError(f"Embedding API call failed: {str(e)}")
    
    async def _embed_single_chunk(self, chunk: DocumentChunk) -> EmbeddingResult:
        """Generate embedding for a single chunk."""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=chunk.content,
                dimensions=self.dimensions,
            )
            
            embedding_data = response.data[0]
            
            return EmbeddingResult(
                chunk=chunk,
                embedding=embedding_data.embedding,
                tokens_used=response.usage.total_tokens,
                embedding_model=self.model,
            )
            
        except Exception as e:
            logger.error("Single chunk embedding failed", chunk_index=chunk.chunk_index, error=str(e))
            raise OpenAIError(f"Failed to embed chunk: {str(e)}")
    
    async def embed_query(self, query_text: str) -> list[float]:
        """
        Generate embedding for a query string.
        
        Args:
            query_text: Query text to embed
            
        Returns:
            Embedding vector
            
        Raises:
            OpenAIError: If embedding generation fails
        """
        if not query_text.strip():
            raise ValueError("Query text cannot be empty")
        
        try:
            logger.debug("Generating query embedding", query_length=len(query_text))
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=query_text.strip(),
                dimensions=self.dimensions,
            )
            
            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens
            
            logger.debug(
                "Query embedding generated",
                tokens_used=tokens_used,
                embedding_dimensions=len(embedding),
            )
            
            return embedding
            
        except Exception as e:
            logger.error("Query embedding failed", error=str(e))
            raise OpenAIError(f"Failed to embed query: {str(e)}")
    
    def validate_embedding(self, embedding: list[float]) -> bool:
        """Validate that embedding has correct dimensions and values."""
        if not embedding:
            return False
        
        if len(embedding) != self.dimensions:
            logger.error(
                "Invalid embedding dimensions",
                expected=self.dimensions,
                actual=len(embedding),
            )
            return False
        
        # Check for NaN or infinite values
        embedding_array = np.array(embedding)
        if not np.isfinite(embedding_array).all():
            logger.error("Embedding contains invalid values (NaN or inf)")
            return False
        
        # Check magnitude (embeddings should be normalized-ish)
        magnitude = np.linalg.norm(embedding_array)
        if magnitude < 0.1 or magnitude > 2.0:
            logger.warning(f"Unusual embedding magnitude: {magnitude}")
        
        return True
    
    def calculate_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same dimensions")
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        magnitude1 = np.linalg.norm(vec1)
        magnitude2 = np.linalg.norm(vec2)
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        return float(similarity)
    
    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check of the embedding service.
        
        Returns:
            Health status information
        """
        try:
            # Test with a simple query
            test_text = "This is a test query for health checking."
            
            start_time = asyncio.get_event_loop().time()
            embedding = await self.embed_query(test_text)
            end_time = asyncio.get_event_loop().time()
            
            response_time = end_time - start_time
            
            is_valid = self.validate_embedding(embedding)
            
            return {
                "status": "healthy" if is_valid else "unhealthy",
                "model": self.model,
                "dimensions": self.dimensions,
                "response_time_ms": response_time * 1000,
                "test_embedding_valid": is_valid,
            }
            
        except Exception as e:
            logger.error("Embedding health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": self.model,
            }

