"""
Tests for ingestion pipeline.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import IngestionError, ParsingError
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document, DocumentStatus
from app.models.tenant import Tenant


@pytest.fixture
def mock_tenant():
    """Create mock tenant."""
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid4()
    return tenant


@pytest.fixture
def mock_document():
    """Create mock document."""
    document = MagicMock(spec=Document)
    document.id = uuid4()
    document.name = "test-document.txt"
    document.document_type = "txt"
    document.status = DocumentStatus.PENDING
    document.metadata = {}
    document.content_hash = None
    document.chunk_count = 0
    return document


class TestIngestionPipeline:
    """Test ingestion pipeline."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = IngestionPipeline()
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_ingest_document_success(self, mock_get_session, mock_tenant, mock_document):
        """Test successful document ingestion."""
        # Mock database session
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock parsers
        self.pipeline.parsers['txt'] = AsyncMock()
        self.pipeline.parsers['txt'].parse_file.return_value = (
            "Test document content",
            {"file_size": 100, "line_count": 1}
        )
        
        # Mock chunking service
        self.pipeline.chunking_service = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.content = "Test document content"
        mock_chunk.token_count = 10
        mock_chunk.metadata = {}
        self.pipeline.chunking_service.chunk_document.return_value = [mock_chunk]
        
        # Mock embedding service
        self.pipeline.embedding_service = AsyncMock()
        self.pipeline.embedding_service.embed_texts.return_value = [[0.1] * 1536]
        
        # Mock vector store
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.create_collection.return_value = True
        self.pipeline.vector_store.upsert_chunks.return_value = [uuid4()]
        
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test document content")
            temp_path = Path(f.name)
        
        try:
            result = await self.pipeline.ingest_document(
                tenant=mock_tenant,
                document=mock_document,
                file_path=temp_path
            )
            
            # Verify result
            assert result == mock_document
            assert mock_document.status == DocumentStatus.COMPLETED
            assert mock_document.chunk_count == 1
            assert mock_document.content_hash is not None
            
            # Verify service calls
            self.pipeline.parsers['txt'].parse_file.assert_called_once_with(temp_path)
            self.pipeline.chunking_service.chunk_document.assert_called_once()
            self.pipeline.embedding_service.embed_texts.assert_called_once()
            self.pipeline.vector_store.upsert_chunks.assert_called_once()
            
        finally:
            temp_path.unlink()
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_ingest_document_parsing_failure(self, mock_get_session, mock_tenant, mock_document):
        """Test document ingestion with parsing failure."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock parser to raise exception
        self.pipeline.parsers['txt'] = AsyncMock()
        self.pipeline.parsers['txt'].parse_file.side_effect = Exception("Parse error")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(IngestionError):
                await self.pipeline.ingest_document(
                    tenant=mock_tenant,
                    document=mock_document,
                    file_path=temp_path
                )
            
            # Document should be marked as failed
            assert mock_document.status == DocumentStatus.FAILED
            assert "Parse error" in mock_document.error_message
            
        finally:
            temp_path.unlink()
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_ingest_document_idempotent(self, mock_get_session, mock_tenant, mock_document):
        """Test idempotent document ingestion."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock document as already processed with same content
        mock_document.content_hash = "existing-hash"
        mock_document.status = DocumentStatus.COMPLETED
        
        # Mock parser to return same content
        self.pipeline.parsers['txt'] = AsyncMock()
        self.pipeline.parsers['txt'].parse_file.return_value = (
            "Test content",
            {"file_size": 100}
        )
        
        # Mock hash calculation to return same hash
        with patch('app.ingestion.pipeline.calculate_content_hash') as mock_hash:
            mock_hash.return_value = "existing-hash"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("Test content")
                temp_path = Path(f.name)
            
            try:
                result = await self.pipeline.ingest_document(
                    tenant=mock_tenant,
                    document=mock_document,
                    file_path=temp_path
                )
                
                # Should return without reprocessing
                assert result == mock_document
                # Status should remain completed
                assert mock_document.status == DocumentStatus.COMPLETED
                
            finally:
                temp_path.unlink()
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_ingest_url_document(self, mock_get_session, mock_tenant, mock_document):
        """Test URL document ingestion."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Set document type to URL
        mock_document.document_type = "url"
        
        # Mock URL parser
        self.pipeline.parsers['url'] = AsyncMock()
        self.pipeline.parsers['url'].parse_url.return_value = (
            "Crawled web content",
            {"url": "https://example.com", "title": "Example"}
        )
        
        # Mock other services
        self.pipeline.chunking_service = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.content = "Crawled web content"
        mock_chunk.token_count = 15
        mock_chunk.metadata = {}
        self.pipeline.chunking_service.chunk_document.return_value = [mock_chunk]
        
        self.pipeline.embedding_service = AsyncMock()
        self.pipeline.embedding_service.embed_texts.return_value = [[0.2] * 1536]
        
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.create_collection.return_value = True
        self.pipeline.vector_store.upsert_chunks.return_value = [uuid4()]
        
        test_url = "https://example.com"
        
        result = await self.pipeline.ingest_document(
            tenant=mock_tenant,
            document=mock_document,
            url=test_url
        )
        
        assert result == mock_document
        assert mock_document.status == DocumentStatus.COMPLETED
        
        # Verify URL parser was called
        self.pipeline.parsers['url'].parse_url.assert_called_once_with(test_url)
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_reingest_document(self, mock_get_session, mock_tenant, mock_document):
        """Test document re-ingestion."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock vector store to return deleted count
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.delete_document_chunks.return_value = 3
        
        # Mock the ingestion pipeline
        with patch.object(self.pipeline, 'ingest_document') as mock_ingest:
            mock_ingest.return_value = mock_document
            
            result = await self.pipeline.reingest_document(
                tenant=mock_tenant,
                document=mock_document
            )
            
            assert result == mock_document
            
            # Verify old chunks were deleted
            self.pipeline.vector_store.delete_document_chunks.assert_called_once()
            
            # Verify re-ingestion was called with force_reprocess=True
            mock_ingest.assert_called_once()
            call_kwargs = mock_ingest.call_args[1]
            assert call_kwargs['force_reprocess'] is True
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_delete_document(self, mock_get_session, mock_tenant, mock_document):
        """Test document deletion."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock vector store
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.delete_document_chunks.return_value = 5
        
        deleted_count = await self.pipeline.delete_document(
            tenant=mock_tenant,
            document=mock_document
        )
        
        assert deleted_count == 5
        assert mock_document.status == DocumentStatus.DELETED
        
        # Verify chunks were deleted
        collection_name = f"tenant_{mock_tenant.id}"
        self.pipeline.vector_store.delete_document_chunks.assert_called_once_with(
            collection_name, mock_document.id
        )
    
    async def test_unsupported_document_type(self, mock_tenant, mock_document):
        """Test ingestion with unsupported document type."""
        mock_document.document_type = "unsupported"
        
        with pytest.raises(ParsingError, match="No parser available"):
            await self.pipeline.ingest_document(
                tenant=mock_tenant,
                document=mock_document
            )
    
    async def test_no_chunks_generated(self, mock_tenant, mock_document):
        """Test ingestion when no chunks are generated."""
        # Mock parser
        self.pipeline.parsers['txt'] = AsyncMock()
        self.pipeline.parsers['txt'].parse_file.return_value = (
            "Content",
            {"file_size": 100}
        )
        
        # Mock chunking service to return empty list
        self.pipeline.chunking_service = AsyncMock()
        self.pipeline.chunking_service.chunk_document.return_value = []
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Content")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(IngestionError, match="No chunks generated"):
                await self.pipeline.ingest_document(
                    tenant=mock_tenant,
                    document=mock_document,
                    file_path=temp_path
                )
        finally:
            temp_path.unlink()
    
    async def test_get_ingestion_status(self, mock_tenant):
        """Test getting ingestion status."""
        # Mock vector store
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.collection_exists.return_value = True
        self.pipeline.vector_store.get_collection_info.return_value = {
            "points_count": 100,
            "status": "green"
        }
        
        status = await self.pipeline.get_ingestion_status(mock_tenant)
        
        assert status["tenant_id"] == str(mock_tenant.id)
        assert status["total_chunks"] == 100
        assert status["collection_status"] == "green"
    
    async def test_get_ingestion_status_with_document_id(self, mock_tenant):
        """Test getting ingestion status for specific document."""
        document_id = uuid4()
        
        # Mock vector store
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.collection_exists.return_value = True
        self.pipeline.vector_store.get_collection_info.return_value = {
            "points_count": 100,
            "status": "green"
        }
        
        # Mock document chunks
        mock_chunks = [MagicMock(), MagicMock(), MagicMock()]
        self.pipeline.vector_store.get_chunks_by_document.return_value = mock_chunks
        
        status = await self.pipeline.get_ingestion_status(mock_tenant, document_id)
        
        assert status["document_chunks"] == 3
        assert status["document_id"] == str(document_id)
    
    async def test_health_check(self):
        """Test pipeline health check."""
        # Mock services
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.health_check.return_value = {"status": "healthy"}
        
        self.pipeline.embedding_service = AsyncMock()
        self.pipeline.embedding_service.health_check.return_value = {"status": "healthy"}
        
        health = await self.pipeline.health_check()
        
        assert health["status"] == "healthy"
        assert "components" in health
        assert "vector_store" in health["components"]
        assert "embedding_service" in health["components"]
        assert "parsers" in health["components"]
        assert health["components"]["parsers"]["count"] == len(self.pipeline.parsers)
    
    async def test_health_check_degraded(self):
        """Test pipeline health check with degraded service."""
        # Mock services - one unhealthy
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.health_check.return_value = {"status": "unhealthy"}
        
        self.pipeline.embedding_service = AsyncMock()
        self.pipeline.embedding_service.health_check.return_value = {"status": "healthy"}
        
        health = await self.pipeline.health_check()
        
        assert health["status"] == "unhealthy"
    
    async def test_close_pipeline(self):
        """Test closing pipeline."""
        # Mock services
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.embedding_service = AsyncMock()
        
        await self.pipeline.close()
        
        # Verify services were closed
        self.pipeline.vector_store.close.assert_called_once()
        self.pipeline.embedding_service.close.assert_called_once()
    
    @patch('app.ingestion.pipeline.get_session')
    async def test_chunk_content_markdown_strategy(self, mock_get_session, mock_tenant, mock_document):
        """Test chunking with markdown strategy."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Set document type to markdown
        mock_document.document_type = "markdown"
        
        # Mock parser
        self.pipeline.parsers['markdown'] = AsyncMock()
        self.pipeline.parsers['markdown'].parse_file.return_value = (
            "# Title\n\nContent here",
            {"file_size": 100, "headings": ["Title"]}
        )
        
        # Mock chunking service
        self.pipeline.chunking_service = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.content = "# Title\n\nContent here"
        mock_chunk.token_count = 10
        mock_chunk.metadata = {}
        self.pipeline.chunking_service.chunk_document.return_value = [mock_chunk]
        
        # Mock other services
        self.pipeline.embedding_service = AsyncMock()
        self.pipeline.embedding_service.embed_texts.return_value = [[0.1] * 1536]
        
        self.pipeline.vector_store = AsyncMock()
        self.pipeline.vector_store.create_collection.return_value = True
        self.pipeline.vector_store.upsert_chunks.return_value = [uuid4()]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Title\n\nContent here")
            temp_path = Path(f.name)
        
        try:
            await self.pipeline.ingest_document(
                tenant=mock_tenant,
                document=mock_document,
                file_path=temp_path
            )
            
            # Verify markdown strategy was used
            chunk_call = self.pipeline.chunking_service.chunk_document.call_args
            assert chunk_call[1]['strategy'] == 'markdown'
            
        finally:
            temp_path.unlink()