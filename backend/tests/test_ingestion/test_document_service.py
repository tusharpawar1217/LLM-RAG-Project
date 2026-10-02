"""
Tests for document service.
"""

import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import DocumentError
from app.models.document import DocumentStatus
from app.models.tenant import Tenant
from app.services.document import DocumentService


@pytest.fixture
def mock_tenant():
    """Create mock tenant."""
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid4()
    return tenant


@pytest.fixture
def mock_upload_file():
    """Create mock upload file."""
    file_content = b"Test document content"
    mock_file = MagicMock()
    mock_file.filename = "test.txt"
    mock_file.file = BytesIO(file_content)
    return mock_file


class TestDocumentService:
    """Test document service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = DocumentService()
        
        # Mock upload directory
        self.temp_dir = Path(tempfile.mkdtemp())
        self.service.upload_dir = self.temp_dir
    
    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.services.document.get_session')
    @patch('app.services.document.enqueue_document_ingestion')
    async def test_create_document_with_file(
        self, mock_enqueue, mock_get_session, mock_tenant, mock_upload_file
    ):
        """Test creating document with file upload."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock database query for duplicate check
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Mock enqueue function
        mock_enqueue.return_value = "job-123"
        
        document, job_id = await self.service.create_document(
            tenant=mock_tenant,
            name="Test Document",
            document_type="txt",
            file=mock_upload_file,
            metadata={"author": "test"}
        )
        
        assert document.name == "Test Document"
        assert document.document_type == "txt"
        assert document.tenant_id == mock_tenant.id
        assert document.status == DocumentStatus.PENDING
        assert document.metadata["author"] == "test"
        assert job_id == "job-123"
        
        # Verify file was saved
        tenant_dir = self.service.upload_dir / str(mock_tenant.id)
        assert tenant_dir.exists()
        assert any(tenant_dir.glob("*.txt"))
        
        # Verify database operations
        mock_session.add.assert_called()
        mock_session.commit.assert_called()
        
        # Verify ingestion was enqueued
        mock_enqueue.assert_called_once()
    
    @patch('app.services.document.get_session')
    @patch('app.services.document.enqueue_document_ingestion')
    async def test_create_document_with_url(
        self, mock_enqueue, mock_get_session, mock_tenant
    ):
        """Test creating document with URL."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock database query
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Mock enqueue function
        mock_enqueue.return_value = "job-456"
        
        test_url = "https://example.com/document"
        
        document, job_id = await self.service.create_document(
            tenant=mock_tenant,
            name="Web Document",
            document_type="url",
            url=test_url,
            metadata={"source": "web"}
        )
        
        assert document.name == "Web Document"
        assert document.document_type == "url"
        assert document.metadata["url"] == test_url
        assert document.metadata["source"] == "web"
        assert job_id == "job-456"
        
        # Verify no file was created
        tenant_dir = self.service.upload_dir / str(mock_tenant.id)
        assert not tenant_dir.exists() or not any(tenant_dir.iterdir())
    
    @patch('app.services.document.get_session')
    async def test_create_document_duplicate_name(
        self, mock_get_session, mock_tenant, mock_upload_file
    ):
        """Test creating document with duplicate name."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock existing document found
        mock_existing = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_existing
        
        with pytest.raises(DocumentError, match="already exists"):
            await self.service.create_document(
                tenant=mock_tenant,
                name="Existing Document",
                document_type="txt",
                file=mock_upload_file
            )
    
    async def test_create_document_no_file_or_url(self, mock_tenant):
        """Test creating document without file or URL."""
        with pytest.raises(ValueError, match="Either file or URL must be provided"):
            await self.service.create_document(
                tenant=mock_tenant,
                name="Invalid Document",
                document_type="txt"
            )
    
    async def test_create_document_both_file_and_url(self, mock_tenant, mock_upload_file):
        """Test creating document with both file and URL."""
        with pytest.raises(ValueError, match="Cannot provide both file and URL"):
            await self.service.create_document(
                tenant=mock_tenant,
                name="Invalid Document",
                document_type="txt",
                file=mock_upload_file,
                url="https://example.com"
            )
    
    @patch('app.services.document.get_session')
    async def test_get_document(self, mock_get_session, mock_tenant):
        """Test getting a document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock document found
        mock_document = MagicMock()
        mock_document.id = uuid4()
        mock_document.name = "Test Document"
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_document
        
        document = await self.service.get_document(mock_tenant, mock_document.id)
        
        assert document == mock_document
    
    @patch('app.services.document.get_session')
    async def test_get_document_not_found(self, mock_get_session, mock_tenant):
        """Test getting non-existent document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock no document found
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        document = await self.service.get_document(mock_tenant, uuid4())
        
        assert document is None
    
    @patch('app.services.document.get_session')
    async def test_list_documents(self, mock_get_session, mock_tenant):
        """Test listing documents."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock documents found
        mock_documents = [MagicMock(), MagicMock(), MagicMock()]
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=3)),  # Count query
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_documents))))  # List query
        ]
        
        documents, total = await self.service.list_documents(
            tenant=mock_tenant,
            limit=10,
            offset=0
        )
        
        assert len(documents) == 3
        assert total == 3
    
    @patch('app.services.document.get_session')
    async def test_update_document(self, mock_get_session, mock_tenant):
        """Test updating document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock document found
        mock_document = MagicMock()
        mock_document.id = uuid4()
        mock_document.name = "Old Name"
        mock_document.metadata = {"old_key": "old_value"}
        
        # Mock queries
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_document)),  # Get document
            MagicMock(scalar_one_or_none=MagicMock(return_value=None))  # Duplicate check
        ]
        
        updated_document = await self.service.update_document(
            tenant=mock_tenant,
            document_id=mock_document.id,
            name="New Name",
            metadata={"new_key": "new_value"}
        )
        
        assert updated_document == mock_document
        assert mock_document.name == "New Name"
        assert mock_document.metadata["old_key"] == "old_value"  # Preserved
        assert mock_document.metadata["new_key"] == "new_value"  # Added
    
    @patch('app.services.document.get_session')
    async def test_delete_document_soft(self, mock_get_session, mock_tenant):
        """Test soft delete document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock document found
        mock_document = MagicMock()
        mock_document.id = uuid4()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_document
        
        # Mock pipeline
        self.service.pipeline = AsyncMock()
        self.service.pipeline.delete_document.return_value = 5
        
        deleted = await self.service.delete_document(
            tenant=mock_tenant,
            document_id=mock_document.id,
            hard_delete=False
        )
        
        assert deleted is True
        assert mock_document.status == DocumentStatus.DELETED
        assert mock_document.metadata["deleted_chunks"] == 5
        
        # Verify document was not actually deleted from DB
        mock_session.delete.assert_not_called()
        mock_session.add.assert_called_with(mock_document)  # Updated instead
    
    @patch('app.services.document.get_session')
    async def test_delete_document_hard(self, mock_get_session, mock_tenant):
        """Test hard delete document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock document found
        mock_document = MagicMock()
        mock_document.id = uuid4()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_document
        
        # Mock pipeline
        self.service.pipeline = AsyncMock()
        self.service.pipeline.delete_document.return_value = 3
        
        deleted = await self.service.delete_document(
            tenant=mock_tenant,
            document_id=mock_document.id,
            hard_delete=True
        )
        
        assert deleted is True
        
        # Verify document was actually deleted from DB
        mock_session.delete.assert_called_with(mock_document)
        mock_session.add.assert_not_called()
    
    @patch('app.services.document.get_session')
    async def test_delete_document_not_found(self, mock_get_session, mock_tenant):
        """Test deleting non-existent document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock no document found
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        
        deleted = await self.service.delete_document(
            tenant=mock_tenant,
            document_id=uuid4()
        )
        
        assert deleted is False
    
    @patch('app.services.document.get_session')
    @patch('app.services.document.enqueue_document_reingestion')
    async def test_reingest_document(self, mock_enqueue, mock_get_session, mock_tenant):
        """Test re-ingesting document."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock document found
        mock_document = MagicMock()
        mock_document.id = uuid4()
        mock_document.name = "Test Document"
        mock_document.metadata = {}
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_document
        
        # Mock enqueue function
        mock_enqueue.return_value = "reingest-job-789"
        
        document, job_id = await self.service.reingest_document(
            tenant=mock_tenant,
            document_id=mock_document.id
        )
        
        assert document == mock_document
        assert job_id == "reingest-job-789"
        assert mock_document.status == DocumentStatus.PENDING
        assert mock_document.error_message is None
        assert mock_document.content_hash is None
        assert mock_document.chunk_count == 0
        assert "job_id" in mock_document.metadata
    
    @patch('app.services.document.get_job_status')
    async def test_get_document_status(self, mock_get_job_status, mock_tenant):
        """Test getting document status."""
        # Mock document
        mock_document = MagicMock()
        mock_document.id = uuid4()
        mock_document.name = "Test Document"
        mock_document.document_type = "txt"
        mock_document.status = DocumentStatus.COMPLETED
        mock_document.chunk_count = 5
        mock_document.content_hash = "abc123"
        mock_document.metadata = {"job_id": "job-123"}
        mock_document.error_message = None
        mock_document.created_at = MagicMock()
        mock_document.updated_at = MagicMock()
        mock_document.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_document.updated_at.isoformat.return_value = "2023-01-01T01:00:00"
        
        # Mock get_document
        with patch.object(self.service, 'get_document') as mock_get_document:
            mock_get_document.return_value = mock_document
            
            # Mock job status
            mock_get_job_status.return_value = {
                "job_id": "job-123",
                "status": "completed"
            }
            
            # Mock pipeline status
            self.service.pipeline = AsyncMock()
            self.service.pipeline.get_ingestion_status.return_value = {
                "total_chunks": 5,
                "collection_status": "ready"
            }
            
            status = await self.service.get_document_status(mock_tenant, mock_document.id)
            
            assert status["document_id"] == str(mock_document.id)
            assert status["name"] == "Test Document"
            assert status["status"] == "completed"
            assert status["chunk_count"] == 5
            assert status["job"]["status"] == "completed"
            assert status["vector_store"]["total_chunks"] == 5
    
    @patch('app.services.document.get_session')
    async def test_get_tenant_statistics(self, mock_get_session, mock_tenant):
        """Test getting tenant statistics."""
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock status counts
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=5)),   # Pending
            MagicMock(scalar=MagicMock(return_value=10)),  # Processing  
            MagicMock(scalar=MagicMock(return_value=25)),  # Completed
            MagicMock(scalar=MagicMock(return_value=2)),   # Failed
            MagicMock(scalar=MagicMock(return_value=150)), # Total chunks
            MagicMock(return_value=[("txt", 20), ("pdf", 15), ("docx", 7)])  # Type distribution
        ]
        
        # Mock pipeline status
        self.service.pipeline = AsyncMock()
        self.service.pipeline.get_ingestion_status.return_value = {
            "collection_status": "ready",
            "total_chunks": 150
        }
        
        stats = await self.service.get_tenant_statistics(mock_tenant)
        
        assert stats["tenant_id"] == str(mock_tenant.id)
        assert stats["document_counts"]["pending"] == 5
        assert stats["document_counts"]["completed"] == 25
        assert stats["total_chunks"] == 150
        assert stats["document_types"]["txt"] == 20
        assert stats["document_types"]["pdf"] == 15
    
    async def test_health_check(self):
        """Test service health check."""
        # Mock pipeline health
        self.service.pipeline = AsyncMock()
        self.service.pipeline.health_check.return_value = {"status": "healthy"}
        
        # Mock database session
        with patch('app.services.document.get_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_session.execute.return_value = None  # Successful query
            
            health = await self.service.health_check()
            
            assert health["status"] == "healthy"
            assert health["components"]["pipeline"]["status"] == "healthy"
            assert health["components"]["upload_directory"]["accessible"] is True
            assert health["components"]["database"]["status"] == "healthy"
    
    async def test_close_service(self):
        """Test closing service."""
        self.service.pipeline = AsyncMock()
        
        await self.service.close()
        
        self.service.pipeline.close.assert_called_once()