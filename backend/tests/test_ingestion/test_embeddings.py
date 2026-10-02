"""
Tests for embedding service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.errors import EmbeddingError
from app.ingestion.embeddings import EmbeddingService


class TestEmbeddingService:
    """Test embedding service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = EmbeddingService()
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_single_text(self, mock_openai_class):
        """Test embedding single text."""
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock embedding response
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2, 0.3] + [0.0] * 1533)  # 1536 dimensions
        ]
        mock_response.usage.total_tokens = 10
        mock_client.embeddings.create.return_value = mock_response
        
        # Test single text embedding
        texts = ["This is a test document."]
        
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536  # OpenAI embedding dimension
        assert embeddings[0][0] == 0.1
        assert embeddings[0][1] == 0.2
        assert embeddings[0][2] == 0.3
        
        # Verify API call
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=texts,
            encoding_format="float"
        )
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_multiple_texts(self, mock_openai_class):
        """Test embedding multiple texts."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock embedding response for multiple texts
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
            MagicMock(embedding=[0.3] * 1536),
        ]
        mock_response.usage.total_tokens = 30
        mock_client.embeddings.create.return_value = mock_response
        
        texts = ["First document", "Second document", "Third document"]
        
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 3
        assert len(embeddings[0]) == 1536
        assert len(embeddings[1]) == 1536
        assert len(embeddings[2]) == 1536
        
        # Check that embeddings are different
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.2
        assert embeddings[2][0] == 0.3
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_large_batch(self, mock_openai_class):
        """Test embedding large batch with batching."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock response for batched requests
        def create_mock_response(texts_batch):
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[i * 0.1] * 1536) 
                for i in range(len(texts_batch))
            ]
            mock_response.usage.total_tokens = len(texts_batch) * 10
            return mock_response
        
        mock_client.embeddings.create.side_effect = lambda **kwargs: create_mock_response(kwargs['input'])
        
        # Create more texts than batch size (100)
        texts = [f"Document {i}" for i in range(150)]
        
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 150
        assert len(embeddings[0]) == 1536
        
        # Should have made 2 API calls (100 + 50)
        assert mock_client.embeddings.create.call_count == 2
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_with_retry(self, mock_openai_class):
        """Test embedding with retry on failure."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # First call fails, second succeeds
        success_response = MagicMock()
        success_response.data = [MagicMock(embedding=[0.1] * 1536)]
        success_response.usage.total_tokens = 10
        
        mock_client.embeddings.create.side_effect = [
            Exception("API Error"),  # First call fails
            success_response  # Second call succeeds
        ]
        
        texts = ["Test document"]
        
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536
        
        # Should have retried
        assert mock_client.embeddings.create.call_count == 2
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_max_retries_exceeded(self, mock_openai_class):
        """Test embedding fails after max retries."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # All calls fail
        mock_client.embeddings.create.side_effect = Exception("Persistent API Error")
        
        texts = ["Test document"]
        
        with pytest.raises(EmbeddingError):
            await self.service.embed_texts(texts)
    
    async def test_embed_empty_texts(self):
        """Test embedding empty text list."""
        texts = []
        
        embeddings = await self.service.embed_texts(texts)
        
        assert embeddings == []
    
    async def test_embed_none_texts(self):
        """Test embedding with None in texts."""
        with pytest.raises(ValueError):
            await self.service.embed_texts([None])
    
    async def test_embed_empty_string(self):
        """Test embedding empty string."""
        with pytest.raises(ValueError):
            await self.service.embed_texts([""])
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_special_characters(self, mock_openai_class):
        """Test embedding texts with special characters."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 15
        mock_client.embeddings.create.return_value = mock_response
        
        texts = ["Text with émojis 🚀 and spëcial châractërs!"]
        
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_embed_long_text(self, mock_openai_class):
        """Test embedding very long text."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 1000
        mock_client.embeddings.create.return_value = mock_response
        
        # Create very long text (over token limit)
        long_text = "This is a very long document. " * 1000  # ~30k chars
        texts = [long_text]
        
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_health_check_success(self, mock_openai_class):
        """Test health check success."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 5
        mock_client.embeddings.create.return_value = mock_response
        
        health = await self.service.health_check()
        
        assert health["status"] == "healthy"
        assert "response_time" in health
        assert health["model"] == "text-embedding-3-small"
        assert health["test_embedding_dimension"] == 1536
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_health_check_failure(self, mock_openai_class):
        """Test health check failure."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_client.embeddings.create.side_effect = Exception("Health check failed")
        
        health = await self.service.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "Health check failed" in health["error"]
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_rate_limiting_handling(self, mock_openai_class):
        """Test handling of rate limiting errors."""
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Simulate rate limiting error followed by success
        from openai import RateLimitError
        
        success_response = MagicMock()
        success_response.data = [MagicMock(embedding=[0.1] * 1536)]
        success_response.usage.total_tokens = 10
        
        mock_client.embeddings.create.side_effect = [
            RateLimitError("Rate limit exceeded", response=MagicMock(status_code=429), body={}),
            success_response
        ]
        
        texts = ["Test document"]
        
        # Should succeed after retry
        embeddings = await self.service.embed_texts(texts)
        
        assert len(embeddings) == 1
        assert mock_client.embeddings.create.call_count == 2
    
    async def test_close_service(self):
        """Test closing service."""
        # Should not raise an exception
        await self.service.close()
    
    @patch('app.ingestion.embeddings.AsyncOpenAI')
    async def test_concurrent_embedding_requests(self, mock_openai_class):
        """Test concurrent embedding requests."""
        import asyncio
        
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_response.usage.total_tokens = 10
        mock_client.embeddings.create.return_value = mock_response
        
        # Create multiple concurrent requests
        tasks = [
            self.service.embed_texts([f"Document {i}"]) 
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        for embeddings in results:
            assert len(embeddings) == 1
            assert len(embeddings[0]) == 1536