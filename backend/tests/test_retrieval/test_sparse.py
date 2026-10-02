"""
Tests for BM25 sparse retrieval.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.ingestion.chunking import DocumentChunk
from app.retrieval.sparse import BM25Index, BM25Manager


class TestBM25Index:
    """Test BM25 index functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tenant_id = uuid4()
        
        # Use temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.core.config.settings.UPLOAD_DIR', temp_dir):
                self.index = BM25Index(self.tenant_id)
    
    def test_create_empty_index(self):
        """Test creating empty BM25 index."""
        assert self.index.tenant_id == self.tenant_id
        assert self.index.bm25 is None
        assert len(self.index.documents) == 0
        assert len(self.index.chunk_ids) == 0
    
    def test_add_chunks(self):
        """Test adding chunks to BM25 index."""
        # Create test chunks
        chunks = [
            DocumentChunk(
                id=uuid4(),
                chunk_index=0,
                content="The quick brown fox jumps over the lazy dog",
                token_count=9,
                metadata={'document_id': 'doc1', 'document_name': 'Test Doc 1'}
            ),
            DocumentChunk(
                id=uuid4(),
                chunk_index=1,
                content="Machine learning algorithms process large datasets efficiently",
                token_count=7,
                metadata={'document_id': 'doc2', 'document_name': 'Test Doc 2'}
            )
        ]
        
        self.index.add_chunks(chunks)
        
        assert self.index.bm25 is not None
        assert len(self.index.documents) == 2
        assert len(self.index.chunk_ids) == 2
        
        # Check document content
        assert self.index.documents[0]['content'] == chunks[0].content
        assert self.index.documents[1]['content'] == chunks[1].content
    
    def test_search_chunks(self):
        """Test searching BM25 index."""
        # Add test chunks
        chunks = [
            DocumentChunk(
                id=uuid4(),
                chunk_index=0,
                content="Python programming language for data science applications",
                token_count=8,
                metadata={'document_id': 'doc1'}
            ),
            DocumentChunk(
                id=uuid4(),
                chunk_index=1,
                content="Machine learning algorithms and neural networks",
                token_count=6,
                metadata={'document_id': 'doc2'}
            ),
            DocumentChunk(
                id=uuid4(),
                chunk_index=2,
                content="Web development using Python frameworks like Django",
                token_count=8,
                metadata={'document_id': 'doc3'}
            )
        ]
        
        self.index.add_chunks(chunks)
        
        # Search for Python-related content
        results = self.index.search("Python programming", top_k=2)
        
        assert len(results) >= 1
        assert len(results) <= 2
        
        # Check result format
        doc, score = results[0]
        assert 'content' in doc
        assert 'document_id' in doc
        assert isinstance(score, float)
        assert score > 0
        
        # First result should be most relevant (contains both "Python" and "programming")
        assert "Python programming" in doc['content']
    
    def test_search_empty_index(self):
        """Test searching empty BM25 index."""
        results = self.index.search("test query")
        assert results == []
    
    def test_search_empty_query(self):
        """Test searching with empty query."""
        # Add a test chunk
        chunk = DocumentChunk(
            id=uuid4(),
            chunk_index=0,
            content="Test content for empty query search",
            token_count=6,
            metadata={'document_id': 'doc1'}
        )
        
        self.index.add_chunks([chunk])
        
        results = self.index.search("")
        assert results == []
    
    def test_remove_chunks(self):
        """Test removing chunks from BM25 index."""
        # Add test chunks
        chunk1_id = str(uuid4())
        chunk2_id = str(uuid4())
        
        chunks = [
            DocumentChunk(
                id=chunk1_id,
                chunk_index=0,
                content="First document content",
                token_count=3,
                metadata={'document_id': 'doc1'}
            ),
            DocumentChunk(
                id=chunk2_id,
                chunk_index=1,
                content="Second document content",
                token_count=3,
                metadata={'document_id': 'doc2'}
            )
        ]
        
        self.index.add_chunks(chunks)
        assert len(self.index.documents) == 2
        
        # Remove one chunk
        removed_count = self.index.remove_chunks([chunk1_id])
        
        assert removed_count == 1
        assert len(self.index.documents) == 1
        assert len(self.index.chunk_ids) == 1
        
        # Verify the remaining chunk is the correct one
        assert self.index.documents[0]['document_id'] == 'doc2'
    
    def test_remove_document_chunks(self):
        """Test removing all chunks for a document."""
        chunks = [
            DocumentChunk(
                id=uuid4(),
                chunk_index=0,
                content="Content from document 1 chunk 1",
                token_count=5,
                metadata={'document_id': 'doc1'}
            ),
            DocumentChunk(
                id=uuid4(),
                chunk_index=1,
                content="Content from document 1 chunk 2",
                token_count=5,
                metadata={'document_id': 'doc1'}
            ),
            DocumentChunk(
                id=uuid4(),
                chunk_index=0,
                content="Content from document 2",
                token_count=4,
                metadata={'document_id': 'doc2'}
            )
        ]
        
        self.index.add_chunks(chunks)
        assert len(self.index.documents) == 3
        
        # Remove all chunks from doc1
        removed_count = self.index.remove_document_chunks('doc1')
        
        assert removed_count == 2
        assert len(self.index.documents) == 1
        assert self.index.documents[0]['document_id'] == 'doc2'
    
    def test_get_stats(self):
        """Test getting BM25 index statistics."""
        # Empty index stats
        empty_stats = self.index.get_stats()
        
        assert empty_stats['total_documents'] == 0
        assert empty_stats['total_tokens'] == 0
        assert empty_stats['average_doc_length'] == 0
        
        # Add chunks and check stats
        chunks = [
            DocumentChunk(
                id=uuid4(),
                chunk_index=0,
                content="Short content",
                token_count=2,
                metadata={'document_id': 'doc1'}
            ),
            DocumentChunk(
                id=uuid4(),
                chunk_index=1,
                content="Much longer content with many more words",
                token_count=8,
                metadata={'document_id': 'doc2'}
            )
        ]
        
        self.index.add_chunks(chunks)
        stats = self.index.get_stats()
        
        assert stats['total_documents'] == 2
        assert stats['total_tokens'] > 0
        assert stats['average_doc_length'] > 0
        assert 'vocabulary_size' in stats
    
    def test_tokenization(self):
        """Test text tokenization."""
        text = "Hello, world! This is a test. Numbers: 123, 456."
        tokens = self.index._tokenize(text)
        
        # Should contain words but not punctuation or very short tokens
        assert 'hello' in tokens
        assert 'world' in tokens
        assert 'test' in tokens
        assert '123' in tokens
        assert '456' in tokens
        
        # Should not contain punctuation or single characters
        assert ',' not in tokens
        assert '!' not in tokens
        assert '.' not in tokens
    
    def test_health_check(self):
        """Test BM25 index health check."""
        health = self.index.health_check()
        
        assert health['status'] in ['healthy', 'unhealthy']
        assert health['tenant_id'] == str(self.tenant_id)
        assert 'stats' in health
        assert 'index_loaded' in health


class TestBM25Manager:
    """Test BM25 manager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('app.core.config.settings.UPLOAD_DIR', temp_dir):
                self.manager = BM25Manager()
    
    def test_get_index(self):
        """Test getting BM25 index for tenant."""
        tenant_id = uuid4()
        
        # First call should create index
        index1 = self.manager.get_index(tenant_id)
        assert index1.tenant_id == tenant_id
        
        # Second call should return same index
        index2 = self.manager.get_index(tenant_id)
        assert index2 is index1
        
        # Different tenant should get different index
        other_tenant = uuid4()
        other_index = self.manager.get_index(other_tenant)
        assert other_index is not index1
        assert other_index.tenant_id == other_tenant
    
    def test_remove_tenant_index(self):
        """Test removing tenant index."""
        tenant_id = uuid4()
        
        # Create index
        index = self.manager.get_index(tenant_id)
        assert tenant_id in self.manager.indices
        
        # Remove index
        self.manager.remove_tenant_index(tenant_id)
        assert tenant_id not in self.manager.indices
    
    def test_get_all_stats(self):
        """Test getting stats for all tenant indices."""
        tenant1 = uuid4()
        tenant2 = uuid4()
        
        # Create indices
        self.manager.get_index(tenant1)
        self.manager.get_index(tenant2)
        
        # Get stats
        all_stats = self.manager.get_all_stats()
        
        assert str(tenant1) in all_stats
        assert str(tenant2) in all_stats
        assert all_stats[str(tenant1)]['total_documents'] == 0  # Empty indices
        assert all_stats[str(tenant2)]['total_documents'] == 0
    
    def test_health_check(self):
        """Test BM25 manager health check."""
        # Empty manager
        health = self.manager.health_check()
        assert health['status'] == 'healthy'  # No indices to fail
        assert health['total_tenants'] == 0
        
        # Add some indices
        tenant1 = uuid4()
        tenant2 = uuid4()
        self.manager.get_index(tenant1)
        self.manager.get_index(tenant2)
        
        health = self.manager.health_check()
        assert health['total_tenants'] == 2
        assert 'tenants' in health
        assert str(tenant1) in health['tenants']
        assert str(tenant2) in health['tenants']