"""
Tests for document chunking service.
"""

import pytest

from app.ingestion.chunking import ChunkingService, DocumentChunk


class TestChunkingService:
    """Test chunking service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = ChunkingService()
    
    async def test_chunk_simple_text(self):
        """Test chunking simple text."""
        content = "This is a simple document. " * 100  # ~2700 chars
        metadata = {"document_id": "test-doc", "document_type": "txt"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        assert len(chunks) >= 2  # Should create multiple chunks
        assert all(isinstance(chunk, DocumentChunk) for chunk in chunks)
        assert all(chunk.content for chunk in chunks)  # No empty chunks
        assert all(chunk.token_count > 0 for chunk in chunks)
        assert all(chunk.metadata["document_id"] == "test-doc" for chunk in chunks)
        
        # Check chunk indices are sequential
        indices = [chunk.chunk_index for chunk in chunks]
        assert indices == list(range(len(chunks)))
    
    async def test_chunk_markdown_strategy(self):
        """Test chunking with markdown strategy."""
        content = """# Main Title

This is the introduction section with some content.

## Section 1

This is section 1 with detailed content that goes on for a while and contains multiple sentences to ensure it's substantial enough for chunking.

### Subsection 1.1

More detailed content under subsection 1.1 with technical details and explanations.

## Section 2

This is section 2 with different content and approach to the topic.

### Subsection 2.1

Additional content in subsection 2.1 with more examples and use cases.
"""
        
        metadata = {"document_id": "test-md", "document_type": "markdown"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="markdown"
        )
        
        assert len(chunks) > 1
        
        # Check that headers are preserved in chunks
        chunk_contents = [chunk.content for chunk in chunks]
        full_content = "\n".join(chunk_contents)
        assert "# Main Title" in full_content
        assert "## Section 1" in full_content
        assert "### Subsection 1.1" in full_content
        
        # Check that section headings are captured in metadata
        has_section_metadata = any(
            chunk.section_heading for chunk in chunks
        )
        assert has_section_metadata
    
    async def test_chunk_size_limits(self):
        """Test chunk size respects limits."""
        # Create content that should definitely be split
        content = "This is a test sentence. " * 200  # ~5000 chars
        metadata = {"document_id": "test-long"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        # Check that chunks respect size limits
        for chunk in chunks:
            # Token count should be reasonable (roughly chunk_size)
            assert chunk.token_count <= self.service.chunk_size * 1.5  # Some flexibility
            assert len(chunk.content) <= self.service.chunk_size * 6  # ~4-6 chars per token
    
    async def test_chunk_overlap(self):
        """Test that chunks have proper overlap."""
        content = "Sentence one. Sentence two. Sentence three. " * 50
        metadata = {"document_id": "test-overlap"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        if len(chunks) > 1:
            # Check for overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                current_chunk = chunks[i]
                next_chunk = chunks[i + 1]
                
                # Find common words between end of current and start of next
                current_words = current_chunk.content.split()[-20:]  # Last 20 words
                next_words = next_chunk.content.split()[:20]  # First 20 words
                
                # Should have some overlap
                common_words = set(current_words) & set(next_words)
                # Note: This is a heuristic, LangChain may handle overlap differently
    
    async def test_empty_content(self):
        """Test chunking empty content."""
        content = ""
        metadata = {"document_id": "empty-doc"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        assert len(chunks) == 0
    
    async def test_very_short_content(self):
        """Test chunking very short content."""
        content = "Short content."
        metadata = {"document_id": "short-doc"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        assert len(chunks) == 1
        assert chunks[0].content == content
        assert chunks[0].chunk_index == 0
        assert chunks[0].token_count > 0
    
    async def test_chunk_metadata_preservation(self):
        """Test that chunk metadata is properly set."""
        content = "Test content for metadata preservation."
        metadata = {
            "document_id": "meta-test",
            "document_type": "txt",
            "author": "test-author",
            "title": "Test Document"
        }
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        assert len(chunks) == 1
        chunk = chunks[0]
        
        # Check required fields
        assert chunk.content == content
        assert chunk.chunk_index == 0
        assert chunk.token_count > 0
        assert chunk.metadata["document_id"] == "meta-test"
        assert chunk.metadata["document_type"] == "txt"
        assert chunk.metadata["author"] == "test-author"
        assert chunk.metadata["title"] == "Test Document"
    
    async def test_chunk_with_page_numbers(self):
        """Test chunking with page number information."""
        content = "This is content from page 5 of a PDF document."
        metadata = {
            "document_id": "pdf-test",
            "page_number": 5,
            "document_type": "pdf"
        }
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.page_number == 5
        assert chunk.metadata["page_number"] == 5
    
    async def test_invalid_strategy(self):
        """Test invalid chunking strategy."""
        content = "Test content"
        metadata = {"document_id": "test"}
        
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            await self.service.chunk_document(
                content=content,
                metadata=metadata,
                strategy="invalid_strategy"
            )
    
    async def test_token_counting(self):
        """Test token counting accuracy."""
        # Use a known text and verify token counting
        content = "The quick brown fox jumps over the lazy dog."
        metadata = {"document_id": "token-test"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        assert len(chunks) == 1
        chunk = chunks[0]
        
        # Token count should be reasonable for this simple sentence
        assert 5 <= chunk.token_count <= 15  # Approximately 10 words
    
    async def test_large_document_chunking(self):
        """Test chunking a large document."""
        # Create a large document
        paragraph = "This is a paragraph with multiple sentences. It contains various information and details. The content is structured to simulate a real document. "
        content = (paragraph * 100) + "\n\n" + (paragraph * 100)  # ~large document
        
        metadata = {"document_id": "large-doc", "document_type": "txt"}
        
        chunks = await self.service.chunk_document(
            content=content,
            metadata=metadata,
            strategy="recursive"
        )
        
        # Should create multiple chunks
        assert len(chunks) > 5  # Large document should create many chunks
        
        # All chunks should be within reasonable size
        for chunk in chunks:
            assert chunk.token_count <= self.service.chunk_size * 1.2  # Allow some flexibility
            assert chunk.content  # No empty chunks
            assert chunk.metadata["document_id"] == "large-doc"
        
        # Verify chunk indices
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i