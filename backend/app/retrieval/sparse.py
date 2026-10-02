"""
Sparse retrieval using BM25 for keyword-based document search.
Complements dense vector search with lexical matching.
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import UUID

from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.core.errors import RetrievalError
from app.core.logging import get_logger
from app.ingestion.chunking import DocumentChunk

logger = get_logger(__name__)


class BM25Index:
    """BM25 sparse retrieval index for keyword-based search."""
    
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.index_path = Path(settings.UPLOAD_DIR) / "bm25_indices" / str(tenant_id)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # BM25 parameters
        self.k1 = 1.2  # Controls term frequency normalization
        self.b = 0.75  # Controls length normalization
        
        # Index components
        self.bm25: BM25Okapi = None
        self.documents: List[Dict] = []
        self.chunk_ids: List[str] = []
        
        # Load existing index if available
        self._load_index()
    
    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Add chunks to the BM25 index."""
        try:
            # Tokenize chunk content
            tokenized_chunks = []
            new_documents = []
            new_chunk_ids = []
            
            for chunk in chunks:
                # Simple tokenization - split on whitespace and punctuation
                tokens = self._tokenize(chunk.content)
                tokenized_chunks.append(tokens)
                
                # Store chunk metadata
                doc_info = {
                    'id': str(chunk.id) if hasattr(chunk, 'id') else None,
                    'document_id': chunk.metadata.get('document_id'),
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'token_count': chunk.token_count,
                    'metadata': chunk.metadata
                }
                
                new_documents.append(doc_info)
                new_chunk_ids.append(str(chunk.id) if hasattr(chunk, 'id') else f"chunk_{len(self.chunk_ids)}")
            
            # Update internal storage
            self.documents.extend(new_documents)
            self.chunk_ids.extend(new_chunk_ids)
            
            # Rebuild BM25 index with all documents
            all_tokenized = []
            for doc in self.documents:
                tokens = self._tokenize(doc['content'])
                all_tokenized.append(tokens)
            
            self.bm25 = BM25Okapi(all_tokenized, k1=self.k1, b=self.b)
            
            # Save updated index
            self._save_index()
            
            logger.info(
                f"Added {len(chunks)} chunks to BM25 index",
                tenant_id=str(self.tenant_id),
                total_documents=len(self.documents)
            )
            
        except Exception as e:
            logger.error(f"Failed to add chunks to BM25 index: {e}")
            raise RetrievalError(f"BM25 indexing failed: {str(e)}")
    
    def remove_chunks(self, chunk_ids_to_remove: List[str]) -> int:
        """Remove chunks from the BM25 index."""
        try:
            # Find indices to remove
            indices_to_remove = []
            for i, chunk_id in enumerate(self.chunk_ids):
                if chunk_id in chunk_ids_to_remove:
                    indices_to_remove.append(i)
            
            if not indices_to_remove:
                return 0
            
            # Remove in reverse order to maintain indices
            for i in sorted(indices_to_remove, reverse=True):
                del self.documents[i]
                del self.chunk_ids[i]
            
            # Rebuild BM25 index if documents remain
            if self.documents:
                all_tokenized = []
                for doc in self.documents:
                    tokens = self._tokenize(doc['content'])
                    all_tokenized.append(tokens)
                
                self.bm25 = BM25Okapi(all_tokenized, k1=self.k1, b=self.b)
            else:
                self.bm25 = None
            
            # Save updated index
            self._save_index()
            
            removed_count = len(indices_to_remove)
            logger.info(
                f"Removed {removed_count} chunks from BM25 index",
                tenant_id=str(self.tenant_id),
                remaining_documents=len(self.documents)
            )
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to remove chunks from BM25 index: {e}")
            raise RetrievalError(f"BM25 chunk removal failed: {str(e)}")
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        """
        Search the BM25 index for relevant chunks.
        
        Args:
            query: Search query string
            top_k: Number of top results to return
            
        Returns:
            List of (document_dict, score) tuples sorted by relevance
        """
        try:
            if not self.bm25 or not self.documents:
                return []
            
            # Tokenize query
            query_tokens = self._tokenize(query)
            
            if not query_tokens:
                return []
            
            # Get BM25 scores
            scores = self.bm25.get_scores(query_tokens)
            
            # Get top-k results
            top_indices = scores.argsort()[-top_k:][::-1]  # Sort descending
            
            results = []
            for idx in top_indices:
                if idx < len(self.documents) and scores[idx] > 0:
                    doc = self.documents[idx]
                    score = float(scores[idx])
                    results.append((doc, score))
            
            logger.debug(
                f"BM25 search returned {len(results)} results",
                query_length=len(query_tokens),
                top_score=results[0][1] if results else 0,
                tenant_id=str(self.tenant_id)
            )
            
            return results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            raise RetrievalError(f"BM25 search failed: {str(e)}")
    
    def remove_document_chunks(self, document_id: str) -> int:
        """Remove all chunks for a specific document."""
        try:
            chunk_ids_to_remove = [
                chunk_id for i, chunk_id in enumerate(self.chunk_ids)
                if self.documents[i]['document_id'] == document_id
            ]
            
            if chunk_ids_to_remove:
                return self.remove_chunks(chunk_ids_to_remove)
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to remove document chunks from BM25: {e}")
            raise RetrievalError(f"Document removal failed: {str(e)}")
    
    def get_stats(self) -> Dict:
        """Get statistics about the BM25 index."""
        try:
            if not self.bm25:
                return {
                    'total_documents': 0,
                    'total_tokens': 0,
                    'average_doc_length': 0,
                    'vocabulary_size': 0
                }
            
            total_tokens = sum(len(self._tokenize(doc['content'])) for doc in self.documents)
            avg_doc_length = total_tokens / len(self.documents) if self.documents else 0
            
            return {
                'total_documents': len(self.documents),
                'total_tokens': total_tokens,
                'average_doc_length': avg_doc_length,
                'vocabulary_size': len(self.bm25.idf) if hasattr(self.bm25, 'idf') else 0,
                'index_size_mb': self._get_index_size_mb()
            }
            
        except Exception as e:
            logger.error(f"Failed to get BM25 stats: {e}")
            return {'error': str(e)}
    
    def rebuild_index(self) -> None:
        """Rebuild the entire BM25 index from stored documents."""
        try:
            if not self.documents:
                self.bm25 = None
                return
            
            # Retokenize all documents
            all_tokenized = []
            for doc in self.documents:
                tokens = self._tokenize(doc['content'])
                all_tokenized.append(tokens)
            
            # Rebuild index
            self.bm25 = BM25Okapi(all_tokenized, k1=self.k1, b=self.b)
            
            # Save rebuilt index
            self._save_index()
            
            logger.info(
                f"Rebuilt BM25 index",
                tenant_id=str(self.tenant_id),
                documents=len(self.documents)
            )
            
        except Exception as e:
            logger.error(f"Failed to rebuild BM25 index: {e}")
            raise RetrievalError(f"Index rebuild failed: {str(e)}")
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25."""
        import re
        
        # Convert to lowercase and split on whitespace/punctuation
        text = text.lower()
        # Keep alphanumeric and basic punctuation, split on everything else
        tokens = re.findall(r'\b\w+\b', text)
        
        # Filter out very short tokens
        tokens = [token for token in tokens if len(token) > 1]
        
        return tokens
    
    def _save_index(self) -> None:
        """Save BM25 index to disk."""
        try:
            index_file = self.index_path / "bm25_index.pkl"
            metadata_file = self.index_path / "bm25_metadata.json"
            
            # Save BM25 index
            if self.bm25:
                with open(index_file, 'wb') as f:
                    pickle.dump(self.bm25, f)
            
            # Save metadata
            metadata = {
                'documents': self.documents,
                'chunk_ids': self.chunk_ids,
                'k1': self.k1,
                'b': self.b,
                'tenant_id': str(self.tenant_id)
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)
            
        except Exception as e:
            logger.warning(f"Failed to save BM25 index: {e}")
    
    def _load_index(self) -> None:
        """Load BM25 index from disk."""
        try:
            index_file = self.index_path / "bm25_index.pkl"
            metadata_file = self.index_path / "bm25_metadata.json"
            
            if not metadata_file.exists():
                return
            
            # Load metadata
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            self.documents = metadata.get('documents', [])
            self.chunk_ids = metadata.get('chunk_ids', [])
            self.k1 = metadata.get('k1', 1.2)
            self.b = metadata.get('b', 0.75)
            
            # Load BM25 index if it exists
            if index_file.exists() and self.documents:
                with open(index_file, 'rb') as f:
                    self.bm25 = pickle.load(f)
            
            if self.documents:
                logger.info(
                    f"Loaded BM25 index",
                    tenant_id=str(self.tenant_id),
                    documents=len(self.documents)
                )
            
        except Exception as e:
            logger.warning(f"Failed to load BM25 index: {e}")
            # Reset to empty state on load failure
            self.documents = []
            self.chunk_ids = []
            self.bm25 = None
    
    def _get_index_size_mb(self) -> float:
        """Calculate index size in MB."""
        try:
            index_file = self.index_path / "bm25_index.pkl"
            metadata_file = self.index_path / "bm25_metadata.json"
            
            total_size = 0
            if index_file.exists():
                total_size += index_file.stat().st_size
            if metadata_file.exists():
                total_size += metadata_file.stat().st_size
            
            return total_size / (1024 * 1024)
            
        except Exception:
            return 0.0
    
    def health_check(self) -> Dict:
        """Check health of BM25 index."""
        try:
            stats = self.get_stats()
            
            # Basic health checks
            is_healthy = (
                isinstance(stats.get('total_documents'), int) and
                stats.get('total_documents', 0) >= 0
            )
            
            return {
                'status': 'healthy' if is_healthy else 'unhealthy',
                'tenant_id': str(self.tenant_id),
                'stats': stats,
                'index_loaded': self.bm25 is not None,
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'tenant_id': str(self.tenant_id)
            }


class BM25Manager:
    """Manager for tenant-specific BM25 indices."""
    
    def __init__(self):
        self.indices: Dict[UUID, BM25Index] = {}
    
    def get_index(self, tenant_id: UUID) -> BM25Index:
        """Get or create BM25 index for a tenant."""
        if tenant_id not in self.indices:
            self.indices[tenant_id] = BM25Index(tenant_id)
        
        return self.indices[tenant_id]
    
    def remove_tenant_index(self, tenant_id: UUID) -> None:
        """Remove and cleanup tenant's BM25 index."""
        if tenant_id in self.indices:
            del self.indices[tenant_id]
        
        # Cleanup files
        try:
            index_path = Path(settings.UPLOAD_DIR) / "bm25_indices" / str(tenant_id)
            if index_path.exists():
                import shutil
                shutil.rmtree(index_path)
                
            logger.info(f"Removed BM25 index for tenant {tenant_id}")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup BM25 index files: {e}")
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all tenant indices."""
        return {
            str(tenant_id): index.get_stats()
            for tenant_id, index in self.indices.items()
        }
    
    def health_check(self) -> Dict:
        """Health check for all BM25 indices."""
        try:
            tenant_health = {}
            overall_healthy = True
            
            for tenant_id, index in self.indices.items():
                health = index.health_check()
                tenant_health[str(tenant_id)] = health
                
                if health.get('status') != 'healthy':
                    overall_healthy = False
            
            return {
                'status': 'healthy' if overall_healthy else 'degraded',
                'total_tenants': len(self.indices),
                'tenants': tenant_health
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }


# Global BM25 manager instance
bm25_manager = BM25Manager()