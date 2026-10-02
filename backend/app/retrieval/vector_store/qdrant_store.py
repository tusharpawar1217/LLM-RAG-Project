"""
Qdrant vector store implementation with per-tenant collections.
"""

import asyncio
from typing import Any, List, Optional
from uuid import UUID, uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.core.config import settings
from app.core.errors import QdrantError
from app.core.logging import get_logger
from app.ingestion.chunking import DocumentChunk
from app.retrieval.vector_store.base import BaseVectorStore, VectorSearchResult

logger = get_logger(__name__)


class QdrantVectorStore(BaseVectorStore):
    """Qdrant implementation of vector store."""
    
    def __init__(self):
        self.client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
        )
        self.embedding_size = settings.OPENAI_EMBEDDING_DIMENSIONS
    
    async def create_collection(self, collection_name: str) -> bool:
        """Create a new Qdrant collection for a tenant."""
        try:
            # Check if collection already exists
            if await self.collection_exists(collection_name):
                logger.info(f"Collection {collection_name} already exists")
                return False
            
            # Create collection with vector configuration
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.embedding_size,
                    distance=models.Distance.COSINE,
                ),
                optimizers_config=models.OptimizersConfig(
                    default_segment_number=2,
                    max_segment_size=None,
                    memmap_threshold=None,
                    indexing_threshold=20000,
                    flush_interval_sec=5,
                    max_optimization_threads=1,
                ),
                hnsw_config=models.HnswConfig(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                    max_indexing_threads=0,
                    on_disk=False,
                ),
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    )
                ),
            )
            
            logger.info(f"Created Qdrant collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise QdrantError(f"Failed to create collection: {str(e)}")
    
    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a Qdrant collection."""
        try:
            await self.client.delete_collection(collection_name)
            logger.info(f"Deleted Qdrant collection: {collection_name}")
            return True
            
        except ResponseHandlingException as e:
            if "Not found" in str(e):
                logger.info(f"Collection {collection_name} does not exist")
                return True
            else:
                logger.error(f"Failed to delete collection {collection_name}: {e}")
                raise QdrantError(f"Failed to delete collection: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            raise QdrantError(f"Failed to delete collection: {str(e)}")
    
    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in Qdrant."""
        try:
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            return collection_name in collection_names
            
        except Exception as e:
            logger.error(f"Failed to check collection existence: {e}")
            raise QdrantError(f"Failed to check collection existence: {str(e)}")
    
    async def upsert_chunks(
        self,
        collection_name: str,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> List[UUID]:
        """Insert or update chunks with embeddings in Qdrant."""
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        
        if not chunks:
            return []
        
        try:
            # Ensure collection exists
            if not await self.collection_exists(collection_name):
                await self.create_collection(collection_name)
            
            # Prepare points for upsert
            points = []
            chunk_ids = []
            
            for chunk, embedding in zip(chunks, embeddings):
                point_id = str(uuid4())  # Generate unique ID for Qdrant
                chunk_ids.append(UUID(point_id))
                
                # Prepare metadata
                payload = {
                    "chunk_id": str(chunk.chunk_index),  # Original chunk index
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "metadata": chunk.metadata,
                }
                
                # Add optional fields if present
                if chunk.page_number:
                    payload["page_number"] = chunk.page_number
                if chunk.section_heading:
                    payload["section_heading"] = chunk.section_heading
                
                point = models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
                points.append(point)
            
            # Perform batch upsert
            await self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            
            logger.info(
                f"Upserted {len(points)} chunks to collection {collection_name}",
                chunks=len(chunks),
                collection=collection_name,
            )
            
            return chunk_ids
            
        except Exception as e:
            logger.error(f"Failed to upsert chunks to {collection_name}: {e}")
            raise QdrantError(f"Failed to upsert chunks: {str(e)}")
    
    async def delete_chunks(
        self,
        collection_name: str,
        chunk_ids: List[UUID],
    ) -> int:
        """Delete chunks by ID from Qdrant."""
        if not chunk_ids:
            return 0
        
        try:
            # Convert UUIDs to strings
            point_ids = [str(chunk_id) for chunk_id in chunk_ids]
            
            # Delete points
            result = await self.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=point_ids,
                ),
            )
            
            deleted_count = len(point_ids)
            logger.info(f"Deleted {deleted_count} chunks from {collection_name}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete chunks from {collection_name}: {e}")
            raise QdrantError(f"Failed to delete chunks: {str(e)}")
    
    async def similarity_search(
        self,
        collection_name: str,
        query_embedding: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Perform similarity search in Qdrant."""
        try:
            # Build filter if provided
            query_filter = None
            if filter_conditions:
                must_conditions = []
                for key, value in filter_conditions.items():
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value),
                        )
                    )
                
                if must_conditions:
                    query_filter = models.Filter(must=must_conditions)
            
            # Perform search
            search_result = await self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False,  # Don't return vectors to save bandwidth
            )
            
            # Convert results
            results = []
            for hit in search_result:
                payload = hit.payload
                
                result = VectorSearchResult(
                    chunk_id=UUID(hit.id),
                    content=payload.get("content", ""),
                    score=hit.score,
                    metadata={
                        "chunk_index": payload.get("chunk_index"),
                        "page_number": payload.get("page_number"),
                        "section_heading": payload.get("section_heading"),
                        "token_count": payload.get("token_count"),
                        **payload.get("metadata", {}),
                    },
                )
                results.append(result)
            
            logger.debug(
                f"Similarity search in {collection_name} returned {len(results)} results",
                limit=limit,
                score_threshold=score_threshold,
                has_filter=filter_conditions is not None,
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed in {collection_name}: {e}")
            raise QdrantError(f"Similarity search failed: {str(e)}")
    
    async def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """Get information about a Qdrant collection."""
        try:
            collection_info = await self.client.get_collection(collection_name)
            
            info = {
                "name": collection_info.config.params.vectors.size,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "points_count": collection_info.points_count,
                "segments_count": collection_info.segments_count,
                "config": {
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": collection_info.config.params.vectors.distance.value,
                },
                "status": collection_info.status.value,
                "optimizer_status": collection_info.optimizer_status.value,
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get collection info for {collection_name}: {e}")
            raise QdrantError(f"Failed to get collection info: {str(e)}")
    
    async def health_check(self) -> dict[str, Any]:
        """Check Qdrant health."""
        try:
            # Get cluster info
            collections = await self.client.get_collections()
            
            # Test basic functionality with a simple operation
            test_collection = "health_check_test"
            test_successful = False
            
            try:
                # Try to create and delete a test collection
                if not await self.collection_exists(test_collection):
                    await self.create_collection(test_collection)
                    await self.delete_collection(test_collection)
                    test_successful = True
                else:
                    # Collection exists, just try to get info
                    await self.get_collection_info(test_collection)
                    test_successful = True
                    
            except Exception as test_e:
                logger.warning(f"Health check test failed: {test_e}")
            
            return {
                "status": "healthy" if test_successful else "degraded",
                "collections_count": len(collections.collections),
                "connection": "successful",
                "test_operation": "successful" if test_successful else "failed",
            }
            
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection": "failed",
            }
    
    async def get_chunks_by_document(
        self,
        collection_name: str,
        document_id: UUID,
    ) -> List[VectorSearchResult]:
        """Get all chunks for a specific document."""
        try:
            # Search for chunks with specific document_id in metadata
            filter_conditions = {"metadata.document_id": str(document_id)}
            
            # Use a high limit to get all chunks
            results = await self.similarity_search(
                collection_name=collection_name,
                query_embedding=[0] * self.embedding_size,  # Dummy vector
                limit=10000,  # High limit
                score_threshold=None,
                filter_conditions=filter_conditions,
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get chunks for document {document_id}: {e}")
            raise QdrantError(f"Failed to get document chunks: {str(e)}")
    
    async def delete_document_chunks(
        self,
        collection_name: str,
        document_id: UUID,
    ) -> int:
        """Delete all chunks for a specific document."""
        try:
            # First get all chunk IDs for the document
            chunks = await self.get_chunks_by_document(collection_name, document_id)
            
            if not chunks:
                return 0
            
            # Extract chunk IDs
            chunk_ids = [chunk.chunk_id for chunk in chunks]
            
            # Delete the chunks
            deleted_count = await self.delete_chunks(collection_name, chunk_ids)
            
            logger.info(
                f"Deleted {deleted_count} chunks for document {document_id}",
                collection=collection_name,
                document_id=str(document_id),
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete document chunks: {e}")
            raise QdrantError(f"Failed to delete document chunks: {str(e)}")
    
    async def close(self):
        """Close the Qdrant client."""
        try:
            await self.client.close()
            logger.info("Qdrant client closed")
        except Exception as e:
            logger.warning(f"Error closing Qdrant client: {e}")