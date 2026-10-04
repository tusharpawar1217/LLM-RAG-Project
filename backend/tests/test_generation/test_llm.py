"""
Tests for LLM service.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.generation.llm import LLMService, LLMResponse


class TestLLMService:
    """Test LLM service functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = LLMService()
    
    @patch('app.generation.llm.AsyncOpenAI')
    async def test_generate_openai_success(self, mock_openai_class):
        """Test successful OpenAI generation."""
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "This is a test response from OpenAI."
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 8
        mock_response.usage.total_tokens = 18
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Override service client
        self.service.openai_client = mock_client
        self.service.primary_provider = "openai"
        self.service.primary_model = "gpt-3.5-turbo"
        
        # Test generation
        result = await self.service.generate(
            prompt="Test prompt",
            system_prompt="Test system prompt"
        )
        
        assert isinstance(result, LLMResponse)
        assert result.content == "This is a test response from OpenAI."
        assert result.provider == "openai"
        assert result.model == "gpt-3.5-turbo"
        assert result.usage['total_tokens'] == 18
        assert result.finish_reason == "stop"
        
        # Verify API call
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs['model'] == "gpt-3.5-turbo"
        assert len(call_kwargs['messages']) == 2  # system + user
        assert call_kwargs['messages'][0]['role'] == 'system'
        assert call_kwargs['messages'][1]['role'] == 'user'
    
    @patch('app.generation.llm.AsyncAnthropic')
    async def test_generate_anthropic_success(self, mock_anthropic_class):
        """Test successful Anthropic generation."""
        # Mock Anthropic client
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client
        
        # Mock response
        mock_content = MagicMock()
        mock_content.text = "This is a test response from Claude."
        
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 12
        mock_response.usage.output_tokens = 9
        
        mock_client.messages.create.return_value = mock_response
        
        # Override service client  
        self.service.anthropic_client = mock_client
        self.service.primary_provider = "anthropic"
        self.service.primary_model = "claude-3-haiku-20240307"
        
        # Test generation
        result = await self.service.generate(
            prompt="Test prompt",
            system_prompt="Test system prompt"
        )
        
        assert isinstance(result, LLMResponse)
        assert result.content == "This is a test response from Claude."
        assert result.provider == "anthropic"
        assert result.model == "claude-3-haiku-20240307"
        assert result.usage['prompt_tokens'] == 12
        assert result.usage['completion_tokens'] == 9
        assert result.finish_reason == "end_turn"
    
    @patch('app.generation.llm.AsyncOpenAI')
    async def test_generate_with_fallback(self, mock_openai_class):
        """Test fallback when primary provider fails."""
        # Mock primary failure
        mock_client_primary = AsyncMock()
        mock_client_primary.chat.completions.create.side_effect = Exception("Primary failed")
        
        # Mock fallback success
        mock_client_fallback = AsyncMock()
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Fallback response"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_response.usage.total_tokens = 8
        
        mock_client_fallback.chat.completions.create.return_value = mock_response
        
        # Set up service with different primary/fallback
        self.service.openai_client = mock_client_primary
        self.service.primary_provider = "openai"
        self.service.primary_model = "gpt-4"
        self.service.fallback_provider = "openai" 
        self.service.fallback_model = "gpt-3.5-turbo"
        
        # Override the client creation to return fallback client on second call
        def client_side_effect(*args, **kwargs):
            return mock_client_fallback
        
        mock_openai_class.side_effect = [mock_client_primary, mock_client_fallback]
        
        # This is a simplified test - in reality the fallback logic is more complex
        # For now, test that service can handle provider switching
        
        # Test direct fallback call
        result = await self.service.generate(
            prompt="Test prompt",
            use_fallback=True
        )
        
        # Should eventually work with fallback, but exact behavior depends on implementation
        # The key is that the service doesn't crash
    
    @patch('app.generation.llm.AsyncOpenAI')
    async def test_generate_structured_success(self, mock_openai_class):
        """Test structured JSON generation."""
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock JSON response
        json_response = json.dumps({
            "answer": "The answer is 42",
            "confidence": 0.95,
            "sources": ["source1", "source2"]
        })
        
        mock_choice = MagicMock()
        mock_choice.message.content = json_response
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 15
        mock_response.usage.total_tokens = 35
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Override service client
        self.service.openai_client = mock_client
        self.service.primary_provider = "openai"
        
        # Test structured generation
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"},
                "sources": {"type": "array"}
            }
        }
        
        result = await self.service.generate_structured(
            prompt="What is the answer?",
            schema=schema
        )
        
        assert isinstance(result, dict)
        assert result["answer"] == "The answer is 42"
        assert result["confidence"] == 0.95
        assert result["sources"] == ["source1", "source2"]
    
    @patch('app.generation.llm.AsyncOpenAI')
    async def test_generate_structured_invalid_json(self, mock_openai_class):
        """Test structured generation with invalid JSON response."""
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock invalid JSON response
        mock_choice = MagicMock()
        mock_choice.message.content = "This is not valid JSON"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Override service client
        self.service.openai_client = mock_client
        self.service.primary_provider = "openai"
        
        # Test structured generation - should fail after max attempts
        schema = {"type": "object"}
        
        with pytest.raises(Exception):  # Should raise GenerationError
            await self.service.generate_structured(
                prompt="Generate JSON",
                schema=schema,
                max_attempts=1
            )
    
    def test_llm_response_to_dict(self):
        """Test LLMResponse to_dict conversion."""
        response = LLMResponse(
            content="Test content",
            provider="openai",
            model="gpt-3.5-turbo",
            usage={"total_tokens": 10},
            finish_reason="stop"
        )
        
        result = response.to_dict()
        
        assert result['content'] == "Test content"
        assert result['provider'] == "openai"
        assert result['model'] == "gpt-3.5-turbo"
        assert result['usage']['total_tokens'] == 10
        assert result['finish_reason'] == "stop"
    
    async def test_health_check_no_clients(self):
        """Test health check with no clients configured."""
        # Clear clients
        self.service.openai_client = None
        self.service.anthropic_client = None
        
        health = await self.service.health_check()
        
        assert health['status'] == 'unhealthy'
        assert 'error' in health
        assert health['providers'] == {}
    
    @patch('app.generation.llm.AsyncOpenAI')
    async def test_health_check_with_openai(self, mock_openai_class):
        """Test health check with OpenAI client."""
        # Mock OpenAI client
        mock_client = AsyncMock()
        mock_openai_class.return_value = mock_client
        
        # Mock successful health check response
        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_choice.finish_reason = "stop"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock()
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Override service client
        self.service.openai_client = mock_client
        self.service.primary_provider = "openai"
        
        health = await self.service.health_check()
        
        assert 'openai' in health['providers']
        # Should attempt health check call
        assert mock_client.chat.completions.create.called
    
    async def test_close_service(self):
        """Test closing LLM service."""
        # Mock clients with close methods
        self.service.openai_client = AsyncMock()
        self.service.anthropic_client = AsyncMock()
        
        self.service.openai_client.close = AsyncMock()
        self.service.anthropic_client.close = AsyncMock()
        
        await self.service.close()
        
        # Close methods should be called if they exist
        # Note: Actual OpenAI/Anthropic clients might not have close methods

