"""
Document ingestion pipeline orchestrator.
Coordinates parsing, chunking, embedding, and vector store operations.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import IngestionError, ParsingError
from app.core.logging import get_logger
from app.ingestion.chunking import ChunkingService, DocumentChunk
from app.ingestion.embeddings import EmbeddingService
from app.ingestion.parsers.base import BaseParser
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.markdown import MarkdownParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.parsers.url_crawler import URLCrawler
from app.models.document import Document, DocumentStatus
from app.models.tenant import Tenant
from app.retrieval.vector_store import QdrantVectorStore
from app.utils.cost_calculator import calculate_embedding_cost
from app.utils.hashing import calculate_content_hash

logger = get_logger(__name__)


class IngestionPipeline:
    """Main document ingestion pipeline."""
    
    def __init__(self):
        self.parsers: Dict[str, BaseParser] = {
            'pdf': PDFParser(),
            'docx': DOCXParser(), 
            'doc': DOCXParser(),
            'md': MarkdownParser(),
            'markdown': MarkdownParser(),
            'txt': TXTParser(),
            'text': TXTParser(),
            'url': URLCrawler(),
        }
        self.chunking_service = ChunkingService()
        self.embedding_service = EmbeddingService()
        self.vector_store = QdrantVectorStore()
    
    async def ingest_document(
        self,
        tenant: Tenant,
        document: Document,
        file_path: Optional[Path] = None,
        url: Optional[str] = None,
        force_reprocess: bool = False,
    ) -> Document:
        """
        Ingest a single document through the full pipeline.
        
        Args:
            tenant: Tenant owning the document
            document: Document model instance
            file_path: Path to document file (for file uploads)
            url: URL to crawl (for URL documents)
            force_reprocess: Force reprocessing even if document unchanged
            
        Returns:
            Updated document with ingestion status
        """
        logger.info(
            f"Starting document ingestion for tenant {tenant.id}",
            document_id=str(document.id),
            document_name=document.name,
            document_type=document.document_type,
        )
        
        try:
            # Update document status
            document.status = DocumentStatus.PROCESSING
            await self._update_document(document)
            
            # Step 1: Parse document content
            content, metadata = await self._parse_document(
                document, file_path, url
            )
            
            # Step 2: Check if content changed (idempotent processing)
            content_hash = calculate_content_hash(content)
            if (not force_reprocess and 
                document.content_hash == content_hash and
                document.status == DocumentStatus.COMPLETED):
                logger.info(f"Document {document.id} unchanged, skipping processing")
                return document
            
            # Step 3: Chunk the content
            chunks = await self._chunk_content(
                content, metadata, document
            )
            
            if not chunks:
                raise IngestionError("No chunks generated from document")
            
            # Step 4: Generate embeddings
            embeddings, embedding_cost = await self._generate_embeddings(chunks)
            
            # Step 5: Store in vector database
            await self._store_vectors(tenant, document, chunks, embeddings)
            
            # Step 6: Update document with results
            document.content_hash = content_hash
            document.chunk_count = len(chunks)
            document.status = DocumentStatus.COMPLETED
            document.metadata = {
                **document.metadata,
                **metadata,
                'embedding_cost': embedding_cost,
                'processing_version': '1.0',
            }
            document.error_message = None
            
            await self._update_document(document)
            
            logger.info(
                f"Successfully ingested document {document.id}",
                chunks_created=len(chunks),
                embedding_cost=embedding_cost,
                tenant_id=str(tenant.id),
            )
            
            return document
            
        except Exception as e:
            # Update document with error status
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            await self._update_document(document)
            
            logger.error(
                f"Failed to ingest document {document.id}: {e}",
                document_name=document.name,
                tenant_id=str(tenant.id),
                error=str(e),
            )
            raise IngestionError(f"Document ingestion failed: {str(e)}")
    
    async def reingest_document(
        self,
        tenant: Tenant,
        document: Document,
        file_path: Optional[Path] = None,
        url: Optional[str] = None,
    ) -> Document:
        """
        Re-ingest a document, removing old chunks first.
        """
        logger.info(f"Re-ingesting document {document.id}")
        
        try:
            # Remove existing chunks from vector store
            collection_name = f"tenant_{tenant.id}"
            deleted_count = await self.vector_store.delete_document_chunks(
                collection_name, document.id
            )
            
            logger.info(
                f"Removed {deleted_count} existing chunks for document {document.id}"
            )
            
            # Process with force reprocess
            return await self.ingest_document(
                tenant, document, file_path, url, force_reprocess=True
            )
            
        except Exception as e:
            logger.error(f"Failed to re-ingest document {document.id}: {e}")
            raise IngestionError(f"Document re-ingestion failed: {str(e)}")
    
    async def delete_document(
        self,
        tenant: Tenant,
        document: Document,
    ) -> int:
        """
        Delete a document and all its chunks from vector store.
        
        Returns:
            Number of chunks deleted
        """
        logger.info(f"Deleting document {document.id} and its chunks")
        
        try:
            collection_name = f"tenant_{tenant.id}"
            deleted_count = await self.vector_store.delete_document_chunks(
                collection_name, document.id
            )
            
            # Update document status
            document.status = DocumentStatus.DELETED
            await self._update_document(document)
            
            logger.info(
                f"Deleted {deleted_count} chunks for document {document.id}",
                tenant_id=str(tenant.id),
            )
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete document {document.id}: {e}")
            raise IngestionError(f"Document deletion failed: {str(e)}")
    
    async def _parse_document(
        self,
        document: Document,
        file_path: Optional[Path] = None,
        url: Optional[str] = None,
    ) -> tuple[str, dict]:
        """Parse document content using appropriate parser."""
        parser_type = document.document_type.lower()
        
        if parser_type not in self.parsers:
            raise ParsingError(f"No parser available for type: {parser_type}")
        
        parser = self.parsers[parser_type]
        
        try:
            if parser_type == 'url' and url:
                content, metadata = await parser.parse_url(url)
            elif file_path:
                content, metadata = await parser.parse_file(file_path)
            else:
                raise ParsingError("Neither file_path nor URL provided for parsing")
            
            # Add document metadata
            metadata['document_id'] = str(document.id)
            metadata['document_name'] = document.name
            metadata['document_type'] = document.document_type
            
            return content, metadata
            
        except Exception as e:
            logger.error(f"Parsing failed for document {document.id}: {e}")
            raise ParsingError(f"Failed to parse document: {str(e)}")
    
    async def _chunk_content(
        self,
        content: str,
        metadata: dict,
        document: Document,
    ) -> List[DocumentChunk]:
        """Chunk document content."""
        try:
            # Choose chunking strategy based on document type
            strategy = "markdown" if document.document_type.lower() in ['md', 'markdown'] else "recursive"
            
            chunks = await self.chunking_service.chunk_document(
                content=content,
                metadata=metadata,
                strategy=strategy,
            )
            
            logger.info(
                f"Generated {len(chunks)} chunks for document {document.id}",
                strategy=strategy,
                avg_chunk_size=sum(chunk.token_count for chunk in chunks) // len(chunks) if chunks else 0,
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Chunking failed for document {document.id}: {e}")
            raise IngestionError(f"Failed to chunk document: {str(e)}")
    
    async def _generate_embeddings(
        self,
        chunks: List[DocumentChunk],
    ) -> tuple[List[List[float]], float]:
        """Generate embeddings for chunks."""
        try:
            # Extract content for embedding
            texts = [chunk.content for chunk in chunks]
            
            # Generate embeddings with batching
            embeddings = await self.embedding_service.embed_texts(texts)
            
            # Calculate cost
            total_tokens = sum(chunk.token_count for chunk in chunks)
            cost = calculate_embedding_cost(total_tokens)
            
            logger.info(
                f"Generated {len(embeddings)} embeddings",
                total_tokens=total_tokens,
                estimated_cost=cost,
            )
            
            return embeddings, cost
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise IngestionError(f"Failed to generate embeddings: {str(e)}")
    
    async def _store_vectors(
        self,
        tenant: Tenant,
        document: Document,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> List[UUID]:
        """Store chunks and embeddings in vector database."""
        try:
            collection_name = f"tenant_{tenant.id}"
            
            # Ensure collection exists
            await self.vector_store.create_collection(collection_name)
            
            # Add document metadata to chunks
            for chunk in chunks:
                chunk.metadata['document_id'] = str(document.id)
                chunk.metadata['tenant_id'] = str(tenant.id)
            
            # Store vectors
            chunk_ids = await self.vector_store.upsert_chunks(
                collection_name, chunks, embeddings
            )
            
            logger.info(
                f"Stored {len(chunk_ids)} chunks in vector database",
                collection=collection_name,
                document_id=str(document.id),
            )
            
            return chunk_ids
            
        except Exception as e:
            logger.error(f"Vector storage failed: {e}")
            raise IngestionError(f"Failed to store vectors: {str(e)}")
    
    async def _update_document(self, document: Document) -> None:
        """Update document in database."""
        try:
            async with get_session() as session:
                session.add(document)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update document {document.id}: {e}")
            raise IngestionError(f"Database update failed: {str(e)}")
    
    async def get_ingestion_status(
        self,
        tenant: Tenant,
        document_id: Optional[UUID] = None,
    ) -> dict:
        """Get ingestion status for tenant or specific document."""
        try:
            collection_name = f"tenant_{tenant.id}"
            
            # Get collection info
            if await self.vector_store.collection_exists(collection_name):
                collection_info = await self.vector_store.get_collection_info(collection_name)
            else:
                collection_info = {"points_count": 0, "status": "not_created"}
            
            status = {
                "tenant_id": str(tenant.id),
                "collection_name": collection_name,
                "total_chunks": collection_info.get("points_count", 0),
                "collection_status": collection_info.get("status", "unknown"),
            }
            
            if document_id:
                # Get document-specific chunks
                try:
                    chunks = await self.vector_store.get_chunks_by_document(
                        collection_name, document_id
                    )
                    status["document_chunks"] = len(chunks)
                    status["document_id"] = str(document_id)
                except Exception:
                    status["document_chunks"] = 0
                    status["document_error"] = "Failed to fetch document chunks"
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get ingestion status: {e}")
            return {
                "tenant_id": str(tenant.id),
                "error": str(e),
                "status": "error"
            }
    
    async def health_check(self) -> dict:
        """Check health of ingestion pipeline components."""
        try:
            # Check vector store health
            vector_store_health = await self.vector_store.health_check()
            
            # Check embedding service health
            embedding_health = await self.embedding_service.health_check()
            
            # Overall health
            overall_healthy = (
                vector_store_health.get("status") == "healthy" and
                embedding_health.get("status") == "healthy"
            )
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "components": {
                    "vector_store": vector_store_health,
                    "embedding_service": embedding_health,
                    "parsers": {
                        "available": list(self.parsers.keys()),
                        "count": len(self.parsers),
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    async def close(self):
        """Cleanup pipeline resources."""
        try:
            await self.vector_store.close()
            await self.embedding_service.close()
            logger.info("Ingestion pipeline closed")
        except Exception as e:
            logger.warning(f"Error closing ingestion pipeline: {e}")