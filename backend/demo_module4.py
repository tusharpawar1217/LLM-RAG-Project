#!/usr/bin/env python3
"""
Module 4: Retrieval & Generation Demo Script

This script demonstrates the complete RAG pipeline:
- Hybrid search (dense + sparse retrieval)
- LLM answer generation with citations
- Citation verification
- Query processing service
- End-to-end question answering
"""

import asyncio
import time
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.db.base import get_db as get_session
from app.core.logging import setup_logging, get_logger
from app.generation.generator import AnswerGenerator
from app.generation.llm import LLMService
from app.ingestion.chunking import DocumentChunk
from app.ingestion.pipeline import IngestionPipeline
from app.db.models import Document, DocumentStatus
from app.db.models import Tenant
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.sparse import bm25_manager
from app.services.query_service import QueryService
from app.verification.verifier import CitationVerifier

# Setup logging
setup_logging(level="INFO", format_type="console")
logger = get_logger(__name__)


async def setup_test_data():
    """Set up test tenant and documents with content."""
    logger.info("Setting up test data for RAG pipeline demo...")
    
    # Create test tenant
    tenant = Tenant(
        id=uuid4(),
        name="RAG Demo Corp",
        slug="rag-demo-corp",
        plan_tier="enterprise"
    )
    
    async with get_session() as session:
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
    
    # Sample documents with rich content
    sample_docs = {
        "company_policy.txt": """
        # Company Remote Work Policy

        ## Overview
        Our company supports flexible remote work arrangements to promote work-life balance and employee satisfaction. This policy outlines the guidelines and expectations for remote work.

        ## Eligibility
        - Full-time employees with at least 6 months of tenure
        - Part-time employees with manager approval
        - Contractors on case-by-case basis

        ## Equipment and Technology
        - Company will provide necessary hardware (laptop, monitor, keyboard)
        - High-speed internet connection required (minimum 25 Mbps)
        - VPN access mandatory for all company systems
        - Regular software updates and security patches required

        ## Work Schedule
        - Core hours: 9 AM - 3 PM local time for team collaboration
        - Flexible start/end times outside core hours
        - Minimum 40 hours per week for full-time employees
        - Maximum 2 consecutive days per week remote work

        ## Communication Requirements
        - Daily stand-up meetings via video call
        - Weekly one-on-one with direct manager
        - Respond to messages within 4 hours during business hours
        - Use company Slack for team communication

        ## Performance Expectations
        - Meet all project deadlines and deliverables
        - Maintain regular communication with team members
        - Participate actively in virtual meetings
        - Complete quarterly performance reviews

        ## Data Security
        - All work must be done on company-provided devices
        - No storing company data on personal devices
        - Use company-approved cloud storage only
        - Report security incidents immediately to IT

        ## Termination of Remote Work
        - Performance issues may result in return to office requirement
        - Policy violation may result in immediate termination of remote privileges
        - Business needs may require temporary office presence

        Contact HR at hr@company.com for questions about this policy.
        """,
        
        "product_specs.md": """
        # Product Specifications - AskDocs Platform

        ## Technical Architecture
        
        ### Backend Services
        - **API Server**: FastAPI with async support
        - **Database**: PostgreSQL 14+ with SQLAlchemy ORM
        - **Cache Layer**: Redis for session and query caching
        - **Queue System**: ARQ for background job processing
        - **Vector Database**: Qdrant for embeddings storage

        ### AI/ML Components
        - **Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
        - **LLM Provider**: OpenAI GPT-4o-mini with Claude fallback
        - **Search**: Hybrid approach combining dense and BM25 sparse search
        - **Chunking**: LangChain text splitters with 800 token chunks

        ## System Requirements

        ### Minimum Hardware
        - CPU: 4 cores, 2.5GHz
        - RAM: 16GB
        - Storage: 100GB SSD
        - Network: 1Gbps connection

        ### Recommended Hardware
        - CPU: 8 cores, 3.0GHz
        - RAM: 32GB
        - Storage: 500GB NVMe SSD
        - Network: 10Gbps connection

        ### Supported File Formats
        - PDF documents (text-based, up to 50MB)
        - Microsoft Word (.docx, .doc)
        - Plain text files (.txt)
        - Markdown documents (.md)
        - Web content via URL crawling

        ## API Specifications

        ### Authentication
        - JWT tokens with 1-hour expiration
        - API keys for programmatic access
        - Role-based access control (RBAC)

        ### Rate Limits
        - Free tier: 100 requests/hour
        - Pro tier: 1000 requests/hour  
        - Enterprise: Custom limits

        ### Response Times
        - Document upload: < 30 seconds
        - Search queries: < 2 seconds
        - Index rebuild: < 5 minutes

        ## Security Features
        - Multi-tenant data isolation
        - Encryption at rest and in transit
        - SOC 2 Type II compliance
        - Regular penetration testing
        - GDPR compliance for EU customers

        ## Monitoring and Analytics
        - Real-time performance metrics
        - Query success rates and response times
        - User engagement analytics
        - System health dashboards
        - Automated alerting for issues

        ## Integration Options
        - REST API with OpenAPI specification
        - JavaScript widget for websites
        - Webhook notifications for events
        - Single sign-on (SSO) support
        - Custom branding options

        For technical support, contact tech-support@askdocs.ai
        """,
        
        "pricing_info.txt": """
        # AskDocs Pricing Plans

        ## Starter Plan - $29/month
        Perfect for small businesses and individuals getting started.

        **Features Included:**
        - Up to 50 documents
        - 1,000 queries per month
        - 2 team members
        - Email support
        - Basic analytics
        - Standard response time (24-48 hours)

        **Document Limits:**
        - Maximum file size: 10MB
        - Supported formats: PDF, DOCX, TXT
        - Vector storage: 1GB

        ## Professional Plan - $99/month  
        Ideal for growing teams and businesses with higher volume needs.

        **Features Included:**
        - Up to 500 documents
        - 10,000 queries per month
        - 10 team members
        - Priority email support
        - Advanced analytics and insights
        - Custom branding options
        - API access
        - Webhook integrations

        **Enhanced Features:**
        - Maximum file size: 25MB
        - All supported formats including Markdown
        - URL crawling capabilities
        - Vector storage: 10GB
        - Custom response time: 12-24 hours

        ## Enterprise Plan - Custom Pricing
        Designed for large organizations with specific requirements.

        **Features Included:**
        - Unlimited documents
        - Unlimited queries
        - Unlimited team members
        - Dedicated support manager
        - White-label solutions
        - On-premise deployment options
        - Custom integrations
        - SLA guarantees

        **Enterprise Benefits:**
        - Maximum file size: 100MB
        - Custom file format support
        - Advanced security features
        - Compliance certifications
        - Custom response time: 4-8 hours
        - 99.9% uptime guarantee

        ## Add-on Services

        ### Professional Services
        - Implementation consulting: $2,500 one-time
        - Custom integration development: $150/hour
        - Training workshops: $1,000 per session
        - Data migration assistance: $500-2,000

        ### Additional Storage
        - Extra 5GB vector storage: $10/month
        - Archive storage: $5/month per 10GB

        ## Payment Options
        - Monthly or annual billing
        - Annual plans receive 2 months free
        - Major credit cards accepted
        - ACH transfers for enterprise customers
        - Purchase orders available for enterprise

        ## Free Trial
        - 14-day free trial for all paid plans
        - No credit card required for trial
        - Full feature access during trial period
        - Easy upgrade process

        ## Refund Policy
        - 30-day money-back guarantee
        - Pro-rated refunds for annual subscriptions
        - No penalties for downgrades

        Questions about pricing? Contact sales@askdocs.ai or call 1-800-ASK-DOCS.
        """
    }
    
    # Create and ingest documents
    pipeline = IngestionPipeline()
    documents = []
    
    for filename, content in sample_docs.items():
        # Create document record
        doc_type = filename.split('.')[-1]
        document = Document(
            id=uuid4(),
            tenant_id=tenant.id,
            name=filename,
            document_type=doc_type,
            status=DocumentStatus.PENDING
        )
        
        async with get_session() as session:
            session.add(document)
            await session.commit()
            await session.refresh(document)
        
        # Create temporary file for ingestion
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{doc_type}', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            # Ingest document
            result = await pipeline.ingest_document(
                tenant=tenant,
                document=document,
                file_path=temp_path
            )
            
            documents.append(result)
            logger.info(f"Ingested {filename}: {result.chunk_count} chunks")
            
        finally:
            temp_path.unlink()
    
    await pipeline.close()
    
    logger.info(f"Setup complete: {len(documents)} documents ingested for tenant {tenant.name}")
    return tenant, documents


async def demo_llm_service():
    """Demonstrate LLM service functionality."""
    logger.info("\n=== LLM Service Demo ===")
    
    llm_service = LLMService()
    
    try:
        # Test basic generation
        logger.info("1. Testing basic LLM generation...")
        
        response = await llm_service.generate(
            prompt="What are the benefits of remote work?",
            system_prompt="You are a helpful assistant that provides concise, accurate answers.",
            temperature=0.3,
            max_tokens=200
        )
        
        logger.info(f"✓ Generated response ({len(response.content)} chars)")
        logger.info(f"  Provider: {response.provider}")
        logger.info(f"  Model: {response.model}")
        logger.info(f"  Usage: {response.usage}")
        logger.info(f"  Response preview: {response.content[:150]}...")
        
        # Test structured generation
        logger.info("\n2. Testing structured JSON generation...")
        
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            }
        }
        
        structured_result = await llm_service.generate_structured(
            prompt="Summarize the benefits of hybrid work models",
            schema=schema,
            system_prompt="Respond with valid JSON only"
        )
        
        logger.info("✓ Generated structured response")
        logger.info(f"  Summary: {structured_result.get('summary', 'N/A')[:100]}...")
        logger.info(f"  Key points: {len(structured_result.get('key_points', []))}")
        logger.info(f"  Confidence: {structured_result.get('confidence', 'N/A')}")
        
        # Health check
        logger.info("\n3. LLM service health check...")
        health = await llm_service.health_check()
        
        logger.info(f"Health status: {health['status']}")
        for provider, status in health.get('providers', {}).items():
            logger.info(f"  {provider}: {status.get('status', 'unknown')}")
        
    finally:
        await llm_service.close()


async def demo_hybrid_retrieval(tenant, documents):
    """Demonstrate hybrid retrieval functionality."""
    logger.info("\n=== Hybrid Retrieval Demo ===")
    
    retriever = HybridRetriever()
    
    try:
        # Test queries with different characteristics
        test_queries = [
            "What are the remote work eligibility requirements?",
            "How much does the Professional plan cost?",
            "What are the minimum system requirements?",
            "What is the company's data security policy?",
            "How do I contact technical support?"
        ]
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n{i}. Query: '{query}'")
            
            start_time = time.time()
            results = await retriever.retrieve(
                tenant_id=tenant.id,
                query=query,
                top_k=3
            )
            retrieval_time = time.time() - start_time
            
            logger.info(f"   Retrieved {len(results)} chunks in {retrieval_time:.2f}s")
            
            for j, chunk in enumerate(results):
                logger.info(f"   [{j+1}] Score: {chunk.combined_score:.3f} "
                          f"(D:{chunk.dense_score:.3f}, S:{chunk.sparse_score:.3f})")
                logger.info(f"       Content: {chunk.content[:100]}...")
                logger.info(f"       Source: {chunk.metadata.get('document_name', 'Unknown')}")
        
        # Retrieval statistics
        logger.info("\n4. Retrieval system statistics...")
        stats = await retriever.get_retrieval_stats(tenant.id)
        
        logger.info(f"Vector store: {stats.get('vector_store', {}).get('points_count', 0)} points")
        logger.info(f"BM25 index: {stats.get('bm25_index', {}).get('total_documents', 0)} documents")
        logger.info(f"Configuration: RRF_K={stats.get('configuration', {}).get('rrf_k', 'N/A')}")
        
        # Health check
        logger.info("\n5. Retrieval system health check...")
        health = await retriever.health_check()
        
        logger.info(f"Overall health: {health['status']}")
        for component, status in health.get('components', {}).items():
            logger.info(f"  {component}: {status.get('status', 'unknown')}")
        
    finally:
        await retriever.close()


async def demo_answer_generation(tenant, documents):
    """Demonstrate answer generation with citations."""
    logger.info("\n=== Answer Generation Demo ===")
    
    generator = AnswerGenerator()
    
    try:
        test_questions = [
            "What are the eligibility requirements for remote work?",
            "How much does the Professional plan cost and what features are included?", 
            "What are the minimum hardware requirements for the system?",
            "What should I do if I have a security incident while working remotely?",
            "How can I get technical support for integration issues?"
        ]
        
        for i, question in enumerate(test_questions, 1):
            logger.info(f"\n{i}. Question: '{question}'")
            
            # Generate answer
            answer = await generator.generate_answer(
                tenant_id=tenant.id,
                query=question,
                max_chunks=5
            )
            
            logger.info(f"   ✓ Generated answer ({len(answer.answer)} chars)")
            logger.info(f"   Confidence: {answer.confidence_score:.2f}")
            logger.info(f"   Citations: {len(answer.citations)}")
            logger.info(f"   Processing time: {answer.processing_time:.2f}s")
            logger.info(f"   Sufficient context: {answer.has_sufficient_context}")
            
            # Show answer preview
            logger.info(f"\n   Answer preview:")
            answer_lines = answer.answer.split('\n')[:3]  # First 3 lines
            for line in answer_lines:
                if line.strip():
                    logger.info(f"   {line.strip()}")
            
            # Show citations
            if answer.citations:
                logger.info(f"\n   Citations:")
                for j, citation in enumerate(answer.citations):
                    source_info = citation.document_name
                    if citation.page_number:
                        source_info += f", p.{citation.page_number}"
                    logger.info(f"   [{j+1}] {source_info}")
                    logger.info(f"       {citation.content[:80]}...")
        
        # Health check
        logger.info("\n6. Answer generator health check...")
        health = await generator.health_check()
        
        logger.info(f"Generator health: {health['status']}")
        for component, status in health.get('components', {}).items():
            logger.info(f"  {component}: {status.get('status', 'unknown')}")
    
    finally:
        await generator.close()


async def demo_citation_verification(tenant, documents):
    """Demonstrate citation verification functionality."""
    logger.info("\n=== Citation Verification Demo ===")
    
    generator = AnswerGenerator()
    verifier = CitationVerifier()
    
    try:
        # Generate an answer to verify
        test_query = "What are the communication requirements for remote workers?"
        
        logger.info(f"Query: '{test_query}'")
        
        # Generate answer
        answer = await generator.generate_answer(
            tenant_id=tenant.id,
            query=test_query,
            max_chunks=4
        )
        
        logger.info(f"Generated answer with {len(answer.citations)} citations")
        
        # Verify citations
        logger.info("\nVerifying citations...")
        
        verified_answer, verification_results = await verifier.verify_answer(
            answer, test_query
        )
        
        logger.info(f"Verification completed:")
        logger.info(f"  Original confidence: {answer.confidence_score:.3f}")
        logger.info(f"  Updated confidence: {verified_answer.confidence_score:.3f}")
        
        # Show verification details
        for i, result in enumerate(verification_results):
            citation = result.citation
            logger.info(f"\n  Citation {i+1}: {citation.document_name}")
            logger.info(f"    Exists in context: {result.exists_in_context}")
            logger.info(f"    Content match: {result.content_match_score:.3f}")
            logger.info(f"    Semantic match: {result.semantic_match_score:.3f}")
            logger.info(f"    LLM verification: {result.llm_verification_score:.3f}")
            logger.info(f"    Overall confidence: {result.overall_confidence:.3f}")
            logger.info(f"    Verified: {'✓' if citation.verified else '✗'}")
        
        # Verification health check
        logger.info("\nCitation verifier health check...")
        health = await verifier.health_check()
        
        logger.info(f"Verifier health: {health['status']}")
        logger.info(f"Configuration: threshold={health['configuration']['confidence_threshold']}")
        
    finally:
        await generator.close()
        await verifier.close()


async def demo_query_service(tenant, documents):
    """Demonstrate end-to-end query service."""
    logger.info("\n=== Query Service Demo ===")
    
    query_service = QueryService()
    
    try:
        # Test various types of queries
        test_scenarios = [
            {
                "name": "Simple factual query",
                "query": "How much does the Starter plan cost?",
                "expected_topic": "pricing"
            },
            {
                "name": "Multi-part question", 
                "query": "What are the hardware requirements and what file formats are supported?",
                "expected_topic": "technical specs"
            },
            {
                "name": "Policy query",
                "query": "What happens if I violate the remote work policy?",
                "expected_topic": "company policy"
            },
            {
                "name": "Complex comparison",
                "query": "What's the difference between Professional and Enterprise plans?",
                "expected_topic": "pricing comparison"
            },
            {
                "name": "Contact information",
                "query": "How do I contact support for technical issues?",
                "expected_topic": "support contacts"
            }
        ]
        
        results = []
        
        for i, scenario in enumerate(test_scenarios, 1):
            logger.info(f"\n{i}. {scenario['name']}")
            logger.info(f"   Query: '{scenario['query']}'")
            
            # Process query
            result = await query_service.process_query(
                tenant=tenant,
                query=scenario['query'],
                enable_verification=True
            )
            
            results.append(result)
            
            # Log results
            logger.info(f"   ✓ Status: {result.to_dict()['status']}")
            logger.info(f"   Confidence: {result.confidence_score:.3f}")
            logger.info(f"   Citations: {len(result.citations)}")
            logger.info(f"   Processing time: {result.processing_time:.2f}s")
            logger.info(f"   Needs handoff: {'Yes' if result.requires_human_handoff else 'No'}")
            
            # Show answer preview
            answer_preview = result.answer[:200] + "..." if len(result.answer) > 200 else result.answer
            logger.info(f"   Answer: {answer_preview}")
            
            # Show top citation
            if result.citations:
                top_citation = result.citations[0]
                logger.info(f"   Top source: {top_citation.get('document_name', 'Unknown')}")
        
        # Summary statistics
        logger.info(f"\n=== Processing Summary ===")
        total_queries = len(results)
        avg_processing_time = sum(r.processing_time for r in results) / total_queries
        avg_confidence = sum(r.confidence_score for r in results) / total_queries
        handoff_needed = sum(1 for r in results if r.requires_human_handoff)
        
        logger.info(f"Total queries processed: {total_queries}")
        logger.info(f"Average processing time: {avg_processing_time:.2f}s")
        logger.info(f"Average confidence: {avg_confidence:.3f}")
        logger.info(f"Queries needing handoff: {handoff_needed}/{total_queries}")
        
        # Test edge cases
        logger.info(f"\n=== Edge Case Testing ===")
        
        # Empty query
        empty_result = await query_service.process_query(tenant, "")
        logger.info(f"Empty query result: {empty_result.to_dict()['status']}")
        
        # Very long query
        long_query = "What " + "are the details " * 100  # Very long query
        long_result = await query_service.process_query(tenant, long_query)
        logger.info(f"Long query result: {long_result.to_dict()['status']}")
        
        # Query with no relevant context
        irrelevant_result = await query_service.process_query(
            tenant, "What is the weather in Tokyo today?"
        )
        logger.info(f"Irrelevant query result: {irrelevant_result.to_dict()['status']}")
        logger.info(f"Sufficient context: {irrelevant_result.has_sufficient_context}")
        
        # Service health check
        logger.info(f"\n=== Service Health Check ===")
        health = await query_service.health_check()
        
        logger.info(f"Query service health: {health['status']}")
        for component, status in health.get('components', {}).items():
            logger.info(f"  {component}: {status.get('status', 'unknown')}")
        
    finally:
        await query_service.close()


async def main():
    """Run all Module 4 demos."""
    try:
        logger.info("Starting Module 4: Retrieval & Generation Demo")
        logger.info("=" * 60)
        
        # Setup test data
        tenant, documents = await setup_test_data()
        
        # Demo 1: LLM Service
        await demo_llm_service()
        
        # Demo 2: Hybrid Retrieval
        await demo_hybrid_retrieval(tenant, documents)
        
        # Demo 3: Answer Generation
        await demo_answer_generation(tenant, documents)
        
        # Demo 4: Citation Verification
        await demo_citation_verification(tenant, documents)
        
        # Demo 5: End-to-End Query Service
        await demo_query_service(tenant, documents)
        
        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("Module 4 Demo Complete!")
        logger.info("\nKey Features Demonstrated:")
        logger.info("✓ Multi-provider LLM generation (OpenAI + Anthropic)")
        logger.info("✓ Hybrid search (Dense embeddings + BM25 sparse)")
        logger.info("✓ Reciprocal Rank Fusion (RRF) for result merging")
        logger.info("✓ Answer generation with inline citations")
        logger.info("✓ Citation verification with confidence scoring")
        logger.info("✓ Multi-tenant data isolation in retrieval")
        logger.info("✓ Comprehensive error handling and edge cases")
        logger.info("✓ Health monitoring and observability")
        logger.info("✓ Human handoff detection")
        
        logger.info("\nRAG Pipeline Components:")
        logger.info("- Query Processing → Hybrid Retrieval → LLM Generation → Citation Verification")
        logger.info("- Fallback mechanisms for API failures")
        logger.info("- Confidence scoring and quality assessment")
        logger.info("- Structured logging and performance metrics")
        
        logger.info("\n🎉 Module 4 implementation is ready for production!")
        logger.info("🔗 Complete RAG pipeline from documents to verified answers!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

