"""
Cost calculator for estimating API usage costs.
"""

from typing import Dict

from app.core.logging import get_logger

logger = get_logger(__name__)


class CostCalculator:
    """Calculator for estimating API usage costs."""
    
    def __init__(self):
        # OpenAI pricing (as of 2024, subject to change)
        self.openai_pricing = {
            # Embedding models (per 1M tokens)
            "text-embedding-3-small": 0.00002,  # $0.02 per 1M tokens
            "text-embedding-3-large": 0.00013,  # $0.13 per 1M tokens
            "text-embedding-ada-002": 0.00010,  # $0.10 per 1M tokens
            
            # Language models (per 1M tokens)
            "gpt-4o-mini": {
                "input": 0.00015,   # $0.15 per 1M input tokens
                "output": 0.0006,   # $0.60 per 1M output tokens
            },
            "gpt-4o": {
                "input": 0.005,     # $5.00 per 1M input tokens
                "output": 0.015,    # $15.00 per 1M output tokens
            },
            "gpt-3.5-turbo": {
                "input": 0.0005,    # $0.50 per 1M input tokens
                "output": 0.0015,   # $1.50 per 1M output tokens
            },
        }
    
    def calculate_embedding_cost(self, tokens: int, model: str) -> float:
        """
        Calculate cost for embedding generation.
        
        Args:
            tokens: Number of tokens processed
            model: Embedding model used
            
        Returns:
            Estimated cost in USD
        """
        if model not in self.openai_pricing:
            logger.warning(f"Unknown embedding model: {model}, using default pricing")
            price_per_million = 0.00002  # Default to text-embedding-3-small
        else:
            price_per_million = self.openai_pricing[model]
        
        cost = (tokens / 1_000_000) * price_per_million
        
        logger.debug(
            "Embedding cost calculated",
            tokens=tokens,
            model=model,
            cost_usd=cost,
        )
        
        return cost
    
    def calculate_llm_cost(
        self, 
        input_tokens: int, 
        output_tokens: int, 
        model: str
    ) -> float:
        """
        Calculate cost for LLM generation.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: LLM model used
            
        Returns:
            Estimated cost in USD
        """
        if model not in self.openai_pricing:
            logger.warning(f"Unknown LLM model: {model}, using default pricing")
            pricing = {"input": 0.00015, "output": 0.0006}  # Default to gpt-4o-mini
        else:
            pricing = self.openai_pricing[model]
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        logger.debug(
            "LLM cost calculated",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
        )
        
        return total_cost
    
    def estimate_monthly_cost(
        self,
        documents_per_month: int,
        avg_document_size_chars: int,
        queries_per_month: int,
        avg_query_response_tokens: int = 500,
    ) -> Dict[str, float]:
        """
        Estimate monthly costs for a tenant.
        
        Args:
            documents_per_month: Number of documents ingested per month
            avg_document_size_chars: Average document size in characters
            queries_per_month: Number of queries per month
            avg_query_response_tokens: Average response length in tokens
            
        Returns:
            Dictionary with cost breakdown
        """
        # Estimate tokens for document ingestion
        # Rough estimate: 4 characters = 1 token
        doc_tokens_per_month = documents_per_month * (avg_document_size_chars // 4)
        
        # Embedding cost for documents
        embedding_cost = self.calculate_embedding_cost(
            doc_tokens_per_month, 
            "text-embedding-3-small"
        )
        
        # Estimate query costs
        # Each query: ~50 tokens for query + retrieval context (~2000 tokens) + response
        query_input_tokens = queries_per_month * (50 + 2000)  # Query + context
        query_output_tokens = queries_per_month * avg_query_response_tokens
        
        llm_cost = self.calculate_llm_cost(
            query_input_tokens,
            query_output_tokens,
            "gpt-4o-mini"
        )
        
        # Query embedding costs (each query needs an embedding)
        query_embedding_tokens = queries_per_month * 12  # ~50 chars / 4
        query_embedding_cost = self.calculate_embedding_cost(
            query_embedding_tokens,
            "text-embedding-3-small"
        )
        
        total_cost = embedding_cost + llm_cost + query_embedding_cost
        
        cost_breakdown = {
            "document_embedding_cost": embedding_cost,
            "query_embedding_cost": query_embedding_cost,
            "llm_generation_cost": llm_cost,
            "total_monthly_cost": total_cost,
            "cost_per_document": embedding_cost / documents_per_month if documents_per_month > 0 else 0,
            "cost_per_query": (llm_cost + query_embedding_cost) / queries_per_month if queries_per_month > 0 else 0,
        }
        
        logger.info(
            "Monthly cost estimation",
            documents_per_month=documents_per_month,
            queries_per_month=queries_per_month,
            **cost_breakdown,
        )
        
        return cost_breakdown
    
    def get_pricing_info(self) -> Dict[str, any]:
        """
        Get current pricing information.
        
        Returns:
            Dictionary with pricing details
        """
        return {
            "embedding_models": {
                model: f"${price * 1000:.4f} per 1K tokens" 
                for model, price in self.openai_pricing.items() 
                if isinstance(price, (int, float))
            },
            "llm_models": {
                model: {
                    "input": f"${pricing['input'] * 1000:.4f} per 1K input tokens",
                    "output": f"${pricing['output'] * 1000:.4f} per 1K output tokens",
                }
                for model, pricing in self.openai_pricing.items()
                if isinstance(pricing, dict)
            },
            "note": "Prices are subject to change. Check OpenAI pricing page for latest rates.",
        }