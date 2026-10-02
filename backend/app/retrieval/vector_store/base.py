"""
Abstract vector store interface for swappable implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple
from uuid import UUID

from app.ingestion.chunking import DocumentChunk


class VectorSearchResult:
    """Result from vector similarity search."""
    
    def __init__(
        self,
        chunk_id: UUID,
        content: str,
        score: float,
        metadata: dict[str, Any],
    ):
        self.chunk_id = chunk_id
        self.content = content
        self.score = score
        self.metadata = metadata
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": str(self.chunk_id),
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""
    
    @abstractmethod
    async def create_collection(self, collection_name: str) -> bool:
        """
        Create a new collection.
        
        Args:
            collection_name: Name of the collection to create
            
        Returns:
            True if created successfully, False if already exists
        """
        pass
    
    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection and all its data.
        
        Args:
            collection_name: Name of the collection to delete
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            True if collection exists
        """
        pass
    
    @abstractmethod
    async def upsert_chunks(
        self,
        collection_name: str,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> List[UUID]:
        """
        Insert or update chunks with embeddings.
        
        Args:
            collection_name: Target collection
            chunks: List of document chunks
            embeddings: Corresponding embeddings
            
        Returns:
            List of chunk IDs that were inserted/updated
        """
        pass
    
    @abstractmethod
    async def delete_chunks(
        self,
        collection_name: str,
        chunk_ids: List[UUID],
    ) -> int:
        """
        Delete chunks by ID.
        
        Args:
            collection_name: Target collection
            chunk_ids: List of chunk IDs to delete
            
        Returns:
            Number of chunks deleted
        """
        pass
    
    @abstractmethod
    async def similarity_search(
        self,
        collection_name: str,
        query_embedding: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Perform similarity search.
        
        Args:
            collection_name: Target collection
            query_embedding: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_conditions: Optional metadata filters
            
        Returns:
            List of search results ordered by similarity score
        """
        pass
    
    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            collection_name: Collection name
            
        Returns:
            Dictionary with collection metadata
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Check the health of the vector store.
        
        Returns:
            Dictionary with health status information
        """
        pass