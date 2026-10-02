"""
Hybrid retrieval system combining dense vector search with sparse BM25 search.
Uses Reciprocal Rank Fusion (RRF) to merge results from both approaches.
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from app.core.config import settings
from app.core.errors import RetrievalError
from app.core.logging import get_logger
from app.ingestion.embeddings import EmbeddingService
from app.retrieval.sparse import bm25_manager
from app.retrieval.vector_store import QdrantVectorStore

logger = get_logger(__name__)


class RetrievedChunk:
    """Container for retrieved chunk with metadata and scores."""
    
    def __init__(
        self,
        id: str,
        document_id: str,
        content: str,
        metadata: Dict,
        dense_score: float = 0.0,
        sparse_score: float = 0.0,
        combined_score: float = 0.0,
        chunk_index: Optional[int] = None
    ):
        self.id = id
        self.document_id = document_id
        self.content = content
        self.metadata = metadata
        self.dense_score = dense_score
        self.sparse_score = sparse_score
        self.combined_score = combined_score
        self.chunk_index = chunk_index
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'content': self.content,
            'metadata': self.metadata,
            'scores': {
                'dense': self.dense_score,
                'sparse': self.sparse_score,
                'combined': self.combined_score
            },
            'chunk_index': self.chunk_index
        }


class HybridRetriever:
    """Hybrid retrieval system using dense + sparse search with RRF fusion."""
    
    def __init__(self):
        self.vector_store = QdrantVectorStore()
        self.embedding_service = EmbeddingService()
        
        # RRF parameters
        self.rrf_k = settings.RRF_K  # Controls the fusion weighting
        
        # Retrieval parameters
        self.top_k_dense = settings.TOP_K_DENSE
        self.top_k_sparse = settings.TOP_K_SPARSE
        self.top_k_final = settings.TOP_K_FINAL
    
    async def retrieve(
        self,
        tenant_id: UUID,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        metadata_filter: Optional[Dict] = None,
        enable_reranking: bool = False
    ) -> List[RetrievedChunk]:
        """
        Perform hybrid retrieval combining dense and sparse search.
        
        Args:
            tenant_id: Tenant ID for data isolation
            query: User query string
            top_k: Number of final results to return
            document_ids: Optional list to filter by specific documents
            metadata_filter: Optional metadata filter conditions
            enable_reranking: Whether to apply reranking (if configured)
            
        Returns:
            List of retrieved chunks sorted by relevance score
        """
        try:
            if top_k is None:
                top_k = self.top_k_final
            
            logger.info(
                f"Starting hybrid retrieval",
                tenant_id=str(tenant_id),
                query_length=len(query),
                top_k=top_k,
                document_filter=len(document_ids) if document_ids else 0
            )
            
            # Run dense and sparse retrieval in parallel
            dense_task = self._dense_retrieval(
                tenant_id, query, document_ids, metadata_filter
            )
            sparse_task = self._sparse_retrieval(
                tenant_id, query, document_ids
            )
            
            dense_results, sparse_results = await asyncio.gather(
                dense_task, sparse_task, return_exceptions=True
            )
            
            # Handle potential exceptions
            if isinstance(dense_results, Exception):
                logger.warning(f"Dense retrieval failed: {dense_results}")
                dense_results = []
            
            if isinstance(sparse_results, Exception):
                logger.warning(f"Sparse retrieval failed: {sparse_results}")
                sparse_results = []
            
            # Fuse results using RRF
            fused_results = self._reciprocal_rank_fusion(
                dense_results, sparse_results, top_k
            )
            
            # Apply reranking if enabled and configured
            if enable_reranking and settings.ENABLE_RERANKER:
                fused_results = await self._rerank_results(query, fused_results)
            
            # Final top-k selection
            final_results = fused_results[:top_k]
            
            logger.info(
                f"Hybrid retrieval completed",
                dense_results=len(dense_results) if isinstance(dense_results, list) else 0,
                sparse_results=len(sparse_results) if isinstance(sparse_results, list) else 0,
                fused_results=len(fused_results),
                final_results=len(final_results),
                tenant_id=str(tenant_id)
            )
            
            return final_results
            
        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            raise RetrievalError(f"Hybrid retrieval failed: {str(e)}")
    
    async def _dense_retrieval(
        self,
        tenant_id: UUID,
        query: str,
        document_ids: Optional[List[str]] = None,
        metadata_filter: Optional[Dict] = None
    ) -> List[Tuple[str, str, str, Dict, float]]:
        """Perform dense vector retrieval."""
        try:
            # Generate query embedding
            query_embeddings = await self.embedding_service.embed_texts([query])
            query_vector = query_embeddings[0]
            
            # Search vector store
            collection_name = f"tenant_{tenant_id}"
            
            # Build metadata filter
            search_filter = {}
            if document_ids:
                search_filter['document_id'] = {'$in': document_ids}
            
            if metadata_filter:
                search_filter.update(metadata_filter)
            
            # Perform vector search
            results = await self.vector_store.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=self.top_k_dense,
                filter_conditions=search_filter if search_filter else None
            )
            
            # Convert to standard format: (id, document_id, content, metadata, score)
            formatted_results = []
            for result in results:
                chunk_id = str(result.get('id', ''))
                payload = result.get('payload', {})
                
                formatted_results.append((
                    chunk_id,
                    payload.get('document_id', ''),
                    payload.get('content', ''),
                    payload.get('metadata', {}),
                    float(result.get('score', 0.0))
                ))
            
            logger.debug(
                f"Dense retrieval returned {len(formatted_results)} results",
                tenant_id=str(tenant_id),
                top_score=formatted_results[0][4] if formatted_results else 0
            )
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}")
            raise RetrievalError(f"Dense retrieval failed: {str(e)}")
    
    async def _sparse_retrieval(
        self,
        tenant_id: UUID,
        query: str,
        document_ids: Optional[List[str]] = None
    ) -> List[Tuple[str, str, str, Dict, float]]:
        """Perform sparse BM25 retrieval."""
        try:
            # Get BM25 index for tenant
            bm25_index = bm25_manager.get_index(tenant_id)
            
            # Search BM25 index
            bm25_results = bm25_index.search(query, top_k=self.top_k_sparse)
            
            # Filter by document_ids if specified
            if document_ids:
                bm25_results = [
                    (doc, score) for doc, score in bm25_results
                    if doc.get('document_id') in document_ids
                ]
            
            # Convert to standard format
            formatted_results = []
            for doc, score in bm25_results:
                chunk_id = doc.get('id', f"bm25_{doc.get('chunk_index', 0)}")
                
                formatted_results.append((
                    chunk_id,
                    doc.get('document_id', ''),
                    doc.get('content', ''),
                    doc.get('metadata', {}),
                    float(score)
                ))
            
            logger.debug(
                f"Sparse retrieval returned {len(formatted_results)} results",
                tenant_id=str(tenant_id),
                top_score=formatted_results[0][4] if formatted_results else 0
            )
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Sparse retrieval failed: {e}")
            raise RetrievalError(f"Sparse retrieval failed: {str(e)}")
    
    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Tuple[str, str, str, Dict, float]],
        sparse_results: List[Tuple[str, str, str, Dict, float]],
        top_k: int
    ) -> List[RetrievedChunk]:
        """
        Fuse dense and sparse results using Reciprocal Rank Fusion.
        
        RRF formula: score = 1 / (k + rank)
        where k is a parameter (typically 60) and rank is 1-indexed position
        """
        try:
            # Create dictionaries for efficient lookup by chunk ID
            dense_dict = {
                chunk_id: (doc_id, content, metadata, score, rank + 1)
                for rank, (chunk_id, doc_id, content, metadata, score) in enumerate(dense_results)
            }
            
            sparse_dict = {
                chunk_id: (doc_id, content, metadata, score, rank + 1)
                for rank, (chunk_id, doc_id, content, metadata, score) in enumerate(sparse_results)
            }
            
            # Collect all unique chunk IDs
            all_chunk_ids = set(dense_dict.keys()) | set(sparse_dict.keys())
            
            # Calculate RRF scores for each chunk
            fused_chunks = []
            
            for chunk_id in all_chunk_ids:
                dense_info = dense_dict.get(chunk_id)
                sparse_info = sparse_dict.get(chunk_id)
                
                # Calculate RRF scores
                dense_rrf_score = 0.0
                sparse_rrf_score = 0.0
                
                if dense_info:
                    doc_id, content, metadata, orig_score, rank = dense_info
                    dense_rrf_score = 1.0 / (self.rrf_k + rank)
                    dense_original_score = orig_score
                else:
                    # Use sparse info for missing fields
                    doc_id, content, metadata, _, _ = sparse_info
                    dense_original_score = 0.0
                
                if sparse_info:
                    # Update with sparse info if we only had dense
                    if not dense_info:
                        doc_id, content, metadata, orig_score, rank = sparse_info
                    else:
                        _, _, _, orig_score, rank = sparse_info
                    sparse_rrf_score = 1.0 / (self.rrf_k + rank)
                    sparse_original_score = orig_score
                else:
                    sparse_original_score = 0.0
                
                # Combined RRF score
                combined_score = dense_rrf_score + sparse_rrf_score
                
                # Create retrieved chunk
                retrieved_chunk = RetrievedChunk(
                    id=chunk_id,
                    document_id=doc_id,
                    content=content,
                    metadata=metadata,
                    dense_score=dense_original_score,
                    sparse_score=sparse_original_score,
                    combined_score=combined_score,
                    chunk_index=metadata.get('chunk_index')
                )
                
                fused_chunks.append(retrieved_chunk)
            
            # Sort by combined RRF score (descending)
            fused_chunks.sort(key=lambda x: x.combined_score, reverse=True)
            
            logger.debug(
                f"RRF fusion completed",
                dense_count=len(dense_results),
                sparse_count=len(sparse_results),
                unique_chunks=len(all_chunk_ids),
                fused_count=len(fused_chunks),
                top_combined_score=fused_chunks[0].combined_score if fused_chunks else 0
            )
            
            return fused_chunks[:top_k * 2]  # Return extra for potential reranking
            
        except Exception as e:
            logger.error(f"RRF fusion failed: {e}")
            raise RetrievalError(f"RRF fusion failed: {str(e)}")
    
    async def _rerank_results(
        self,
        query: str,
        results: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Apply reranking to fused results using cross-encoder or LLM-based scoring.
        This is a placeholder for reranking implementation.
        """
        try:
            if not settings.ENABLE_RERANKER:
                return results
            
            # TODO: Implement reranking using cross-encoder or LLM
            # For now, return original results
            
            logger.debug(f"Reranking applied to {len(results)} results")
            return results
            
        except Exception as e:
            logger.warning(f"Reranking failed, using original order: {e}")
            return results
    
    async def get_retrieval_stats(self, tenant_id: UUID) -> Dict:
        """Get retrieval statistics for a tenant."""
        try:
            # Vector store stats
            collection_name = f"tenant_{tenant_id}"
            vector_stats = {}
            
            try:
                if await self.vector_store.collection_exists(collection_name):
                    vector_info = await self.vector_store.get_collection_info(collection_name)
                    vector_stats = {
                        'points_count': vector_info.get('points_count', 0),
                        'status': vector_info.get('status', 'unknown')
                    }
            except Exception as e:
                vector_stats = {'error': str(e)}
            
            # BM25 stats
            bm25_index = bm25_manager.get_index(tenant_id)
            bm25_stats = bm25_index.get_stats()
            
            return {
                'tenant_id': str(tenant_id),
                'vector_store': vector_stats,
                'bm25_index': bm25_stats,
                'configuration': {
                    'top_k_dense': self.top_k_dense,
                    'top_k_sparse': self.top_k_sparse,
                    'top_k_final': self.top_k_final,
                    'rrf_k': self.rrf_k,
                    'reranking_enabled': settings.ENABLE_RERANKER
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get retrieval stats: {e}")
            return {
                'tenant_id': str(tenant_id),
                'error': str(e)
            }
    
    async def health_check(self) -> Dict:
        """Check health of all retrieval components."""
        try:
            # Check vector store
            vector_health = await self.vector_store.health_check()
            
            # Check embedding service
            embedding_health = await self.embedding_service.health_check()
            
            # Check BM25 manager
            bm25_health = bm25_manager.health_check()
            
            # Overall health
            components_healthy = (
                vector_health.get('status') == 'healthy' and
                embedding_health.get('status') == 'healthy' and
                bm25_health.get('status') in ['healthy', 'degraded']  # BM25 can be degraded
            )
            
            return {
                'status': 'healthy' if components_healthy else 'unhealthy',
                'components': {
                    'vector_store': vector_health,
                    'embedding_service': embedding_health,
                    'bm25_manager': bm25_health
                },
                'configuration': {
                    'hybrid_enabled': True,
                    'reranking_enabled': settings.ENABLE_RERANKER,
                    'rrf_k': self.rrf_k
                }
            }
            
        except Exception as e:
            logger.error(f"Retrieval health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def close(self):
        """Clean up retrieval resources."""
        try:
            await self.vector_store.close()
            await self.embedding_service.close()
            logger.info("Hybrid retriever closed")
        except Exception as e:
            logger.warning(f"Error closing hybrid retriever: {e}")