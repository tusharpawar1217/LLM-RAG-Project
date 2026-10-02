"""
LLM service for generating answers using OpenAI and Anthropic APIs.
Supports multiple providers with fallback and configurable parameters.
"""

import asyncio
import json
from typing import Dict, List, Optional, Union

import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.errors import GenerationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMResponse:
    """Container for LLM response with metadata."""
    
    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        usage: Optional[Dict] = None,
        finish_reason: Optional[str] = None
    ):
        self.content = content
        self.provider = provider
        self.model = model
        self.usage = usage or {}
        self.finish_reason = finish_reason
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'content': self.content,
            'provider': self.provider,
            'model': self.model,
            'usage': self.usage,
            'finish_reason': self.finish_reason
        }


class LLMService:
    """Service for LLM-powered text generation with multiple provider support."""
    
    def __init__(self):
        # Initialize clients
        self.openai_client = None
        self.anthropic_client = None
        
        # Setup clients based on available API keys
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        # Configuration
        self.primary_provider = settings.PRIMARY_LLM_PROVIDER
        self.primary_model = settings.PRIMARY_LLM_MODEL
        self.fallback_provider = settings.FALLBACK_LLM_PROVIDER
        self.fallback_model = settings.FALLBACK_LLM_MODEL
        
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.timeout = settings.LLM_TIMEOUT
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_fallback: bool = False
    ) -> LLMResponse:
        """
        Generate text using LLM.
        
        Args:
            prompt: User prompt/question
            system_prompt: Optional system prompt for instructions
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            use_fallback: Whether to use fallback provider/model
            
        Returns:
            LLMResponse with generated content and metadata
        """
        try:
            # Determine provider and model
            if use_fallback:
                provider = self.fallback_provider
                model = self.fallback_model
            else:
                provider = self.primary_provider
                model = self.primary_model
            
            # Use provided parameters or defaults
            temp = temperature if temperature is not None else self.temperature
            max_tok = max_tokens if max_tokens is not None else self.max_tokens
            
            logger.info(
                f"Generating with LLM",
                provider=provider,
                model=model,
                temperature=temp,
                max_tokens=max_tok,
                prompt_length=len(prompt),
                has_system_prompt=system_prompt is not None
            )
            
            # Generate based on provider
            if provider == "openai":
                return await self._generate_openai(prompt, system_prompt, model, temp, max_tok)
            elif provider == "anthropic":
                return await self._generate_anthropic(prompt, system_prompt, model, temp, max_tok)
            else:
                raise GenerationError(f"Unknown LLM provider: {provider}")
            
        except Exception as e:
            # Try fallback if primary failed and fallback is available
            if not use_fallback and self.fallback_provider != self.primary_provider:
                logger.warning(f"Primary LLM failed, trying fallback: {e}")
                try:
                    return await self.generate(
                        prompt, system_prompt, temperature, max_tokens, use_fallback=True
                    )
                except Exception as fallback_error:
                    logger.error(f"Fallback LLM also failed: {fallback_error}")
                    raise GenerationError(f"Both primary and fallback LLM failed: {str(e)}")
            
            logger.error(f"LLM generation failed: {e}")
            raise GenerationError(f"LLM generation failed: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Generate using OpenAI API."""
        if not self.openai_client:
            raise GenerationError("OpenAI client not initialized")
        
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Make API call
            response = await asyncio.wait_for(
                self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=self.timeout
            )
            
            # Extract response
            choice = response.choices[0]
            content = choice.message.content or ""
            
            # Usage information
            usage = {}
            if response.usage:
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            
            logger.info(
                f"OpenAI generation completed",
                model=model,
                input_tokens=usage.get('prompt_tokens', 0),
                output_tokens=usage.get('completion_tokens', 0),
                finish_reason=choice.finish_reason
            )
            
            return LLMResponse(
                content=content,
                provider="openai",
                model=model,
                usage=usage,
                finish_reason=choice.finish_reason
            )
            
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded: {e}")
            raise GenerationError(f"Rate limit exceeded: {str(e)}")
        
        except openai.APITimeoutError as e:
            logger.warning(f"OpenAI API timeout: {e}")
            raise GenerationError(f"API timeout: {str(e)}")
        
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise GenerationError(f"OpenAI API error: {str(e)}")
        
        except asyncio.TimeoutError:
            logger.error("OpenAI request timeout")
            raise GenerationError("Request timeout")
        
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise GenerationError(f"OpenAI error: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Generate using Anthropic API."""
        if not self.anthropic_client:
            raise GenerationError("Anthropic client not initialized")
        
        try:
            # Make API call
            response = await asyncio.wait_for(
                self.anthropic_client.messages.create(
                    model=model,
                    system=system_prompt or "",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens
                ),
                timeout=self.timeout
            )
            
            # Extract content
            content = ""
            if response.content and len(response.content) > 0:
                content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
            
            # Usage information
            usage = {}
            if hasattr(response, 'usage'):
                usage = {
                    'prompt_tokens': getattr(response.usage, 'input_tokens', 0),
                    'completion_tokens': getattr(response.usage, 'output_tokens', 0),
                    'total_tokens': getattr(response.usage, 'input_tokens', 0) + getattr(response.usage, 'output_tokens', 0)
                }
            
            logger.info(
                f"Anthropic generation completed",
                model=model,
                input_tokens=usage.get('prompt_tokens', 0),
                output_tokens=usage.get('completion_tokens', 0),
                finish_reason=response.stop_reason
            )
            
            return LLMResponse(
                content=content,
                provider="anthropic",
                model=model,
                usage=usage,
                finish_reason=response.stop_reason
            )
            
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise GenerationError(f"Anthropic error: {str(e)}")
    
    async def generate_structured(
        self,
        prompt: str,
        schema: Dict,
        system_prompt: Optional[str] = None,
        max_attempts: int = 3
    ) -> Dict:
        """
        Generate structured JSON output that conforms to a schema.
        
        Args:
            prompt: User prompt
            schema: JSON schema for expected output format
            system_prompt: Optional system prompt
            max_attempts: Maximum attempts to get valid JSON
            
        Returns:
            Parsed JSON response
        """
        json_prompt = f"""
{system_prompt or ""}

Please respond with valid JSON that conforms to this schema:
{json.dumps(schema, indent=2)}

Question: {prompt}

Response (JSON only):
"""
        
        for attempt in range(max_attempts):
            try:
                response = await self.generate(
                    prompt=json_prompt,
                    temperature=0.1,  # Lower temperature for structured output
                    max_tokens=self.max_tokens
                )
                
                # Try to parse JSON
                try:
                    result = json.loads(response.content.strip())
                    logger.info(f"Structured generation successful on attempt {attempt + 1}")
                    return result
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed on attempt {attempt + 1}: {e}")
                    if attempt == max_attempts - 1:
                        raise GenerationError(f"Failed to generate valid JSON after {max_attempts} attempts")
                    
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise GenerationError(f"Structured generation failed: {str(e)}")
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
        
        raise GenerationError("Structured generation failed after all attempts")
    
    async def health_check(self) -> Dict:
        """Check health of LLM service."""
        try:
            health_info = {
                'status': 'healthy',
                'providers': {},
                'configuration': {
                    'primary_provider': self.primary_provider,
                    'primary_model': self.primary_model,
                    'fallback_provider': self.fallback_provider,
                    'fallback_model': self.fallback_model,
                    'temperature': self.temperature,
                    'max_tokens': self.max_tokens
                }
            }
            
            # Test OpenAI if available
            if self.openai_client:
                try:
                    test_response = await self._generate_openai(
                        prompt="Say 'OK' if you can respond.",
                        system_prompt=None,
                        model=self.primary_model if self.primary_provider == 'openai' else 'gpt-3.5-turbo',
                        temperature=0.0,
                        max_tokens=10
                    )
                    health_info['providers']['openai'] = {
                        'status': 'healthy',
                        'test_response_length': len(test_response.content)
                    }
                except Exception as e:
                    health_info['providers']['openai'] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
            
            # Test Anthropic if available
            if self.anthropic_client:
                try:
                    test_response = await self._generate_anthropic(
                        prompt="Say 'OK' if you can respond.",
                        system_prompt=None,
                        model=self.primary_model if self.primary_provider == 'anthropic' else 'claude-3-haiku-20240307',
                        temperature=0.0,
                        max_tokens=10
                    )
                    health_info['providers']['anthropic'] = {
                        'status': 'healthy',
                        'test_response_length': len(test_response.content)
                    }
                except Exception as e:
                    health_info['providers']['anthropic'] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
            
            # Overall health based on at least one working provider
            working_providers = [
                p for p in health_info['providers'].values()
                if p.get('status') == 'healthy'
            ]
            
            if not working_providers:
                health_info['status'] = 'unhealthy'
                health_info['error'] = 'No working LLM providers available'
            
            return health_info
            
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    async def close(self):
        """Clean up LLM service resources."""
        try:
            # Close clients if they have close methods
            if hasattr(self.openai_client, 'close'):
                await self.openai_client.close()
            
            if hasattr(self.anthropic_client, 'close'):
                await self.anthropic_client.close()
            
            logger.info("LLM service closed")
            
        except Exception as e:
            logger.warning(f"Error closing LLM service: {e}")