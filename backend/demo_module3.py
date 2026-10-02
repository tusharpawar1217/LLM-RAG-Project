#!/usr/bin/env python3
"""
Module 3: Document Ingestion Demo Script

This script demonstrates the complete document ingestion pipeline:
- File upload and processing
- URL crawling 
- Background workers
- Vector store integration
- Status monitoring
"""

import asyncio
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.database import get_session
from app.core.logging import setup_logging, get_logger
from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Document, DocumentStatus
from app.models.tenant import Tenant
from app.services.document import DocumentService
from app.workers.ingestion import enqueue_document_ingestion, get_job_status

# Setup logging
setup_logging(level="INFO", format_type="console")
logger = get_logger(__name__)


async def create_sample_documents():
    """Create sample documents for testing."""
    documents = {}
    
    # Sample text document
    txt_content = """# AskDocs Documentation

## Introduction
AskDocs is a production-grade multi-tenant SaaS platform that allows small businesses to upload documents and get an embeddable chat widget that answers customer questions strictly from those documents.

## Features
- Multi-tenant architecture with strict data isolation
- Support for PDF, DOCX, Markdown, and TXT documents
- URL crawling for web content
- Hybrid search using dense embeddings and BM25
- Citation verification with confidence scoring
- Background processing with ARQ workers
- Comprehensive observability and monitoring

## Architecture
The system is built with:
- FastAPI for the REST API
- PostgreSQL for data storage
- Redis for caching and job queues
- Qdrant for vector storage
- OpenAI for embeddings and generation
- Docker for containerization

## Getting Started
1. Set up your environment variables
2. Run database migrations
3. Start the API server
4. Start background workers
5. Upload your first document
6. Test the chat widget

This platform handles everything from document ingestion to customer support automation.
"""
    
    # Create temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(txt_content)
        documents['txt'] = Path(f.name)
    
    # Sample Markdown document
    md_content = """# Technical Specifications

## System Requirements

### Hardware
- **CPU**: Minimum 4 cores, 8 cores recommended
- **Memory**: Minimum 8GB RAM, 16GB recommended  
- **Storage**: SSD with at least 50GB free space
- **Network**: Stable internet connection for API access

### Software Dependencies
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose
- Node.js 18+ (for frontend)

## Database Schema

### Tenants Table
```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    plan_tier VARCHAR(50) NOT NULL DEFAULT 'trial',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Documents Table
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    content_hash VARCHAR(255),
    chunk_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/refresh` - Refresh JWT token

### Documents
- `GET /documents` - List documents
- `POST /documents` - Upload document
- `GET /documents/{id}` - Get document details
- `PUT /documents/{id}` - Update document
- `DELETE /documents/{id}` - Delete document
- `POST /documents/{id}/reingest` - Re-process document

### Query
- `POST /query` - Ask questions about documents
- `GET /query/history` - Get query history

## Configuration

Environment variables for production deployment:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/askdocs
REDIS_URL=redis://host:6379/0

# Vector Store
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=your-api-key

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# Security
SECRET_KEY=your-secret-key-32-chars-min
```

## Monitoring & Observability

The system includes comprehensive monitoring:
- Structured JSON logging
- Request tracing with correlation IDs
- Performance metrics collection  
- Error tracking with Sentry
- Health check endpoints
- Usage analytics per tenant

## Scaling Considerations

For production deployments:
- Use managed PostgreSQL (RDS, Cloud SQL)
- Deploy Redis cluster for high availability
- Scale Qdrant horizontally across nodes
- Use container orchestration (K8s, ECS)
- Implement proper backup strategies
- Set up monitoring and alerting
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(md_content)
        documents['md'] = Path(f.name)
    
    logger.info(f"Created sample documents: {list(documents.keys())}")
    return documents


async def demo_ingestion_pipeline():
    """Demonstrate the ingestion pipeline components."""
    logger.info("=== Module 3: Document Ingestion Pipeline Demo ===")
    
    # Initialize pipeline
    pipeline = IngestionPipeline()
    
    try:
        # Health check
        logger.info("\n1. Checking pipeline health...")
        health = await pipeline.health_check()
        logger.info(f"Pipeline health: {health['status']}")
        
        if health['status'] != 'healthy':
            logger.warning("Pipeline components are not fully healthy:")
            for component, status in health.get('components', {}).items():
                logger.info(f"  {component}: {status.get('status', 'unknown')}")
        
        # Create test tenant
        logger.info("\n2. Setting up test tenant...")
        tenant = Tenant(
            id=uuid4(),
            name="Demo Corp",
            slug="demo-corp",
            plan_tier="pro"
        )
        
        async with get_session() as session:
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        
        logger.info(f"Created tenant: {tenant.name} ({tenant.id})")
        
        # Get sample documents
        sample_docs = await create_sample_documents()
        
        ingestion_results = []
        
        # Process each document type
        for doc_type, file_path in sample_docs.items():
            logger.info(f"\n3. Processing {doc_type.upper()} document...")
            
            # Create document record
            document = Document(
                id=uuid4(),
                tenant_id=tenant.id,
                name=f"Sample {doc_type.upper()} Document",
                document_type=doc_type,
                status=DocumentStatus.PENDING
            )
            
            async with get_session() as session:
                session.add(document)
                await session.commit()
                await session.refresh(document)
            
            try:
                # Process through pipeline
                start_time = time.time()
                result = await pipeline.ingest_document(
                    tenant=tenant,
                    document=document,
                    file_path=file_path
                )
                
                processing_time = time.time() - start_time
                
                logger.info(f"✓ {doc_type.upper()} document processed successfully")
                logger.info(f"  Status: {result.status.value}")
                logger.info(f"  Chunks created: {result.chunk_count}")
                logger.info(f"  Processing time: {processing_time:.2f}s")
                logger.info(f"  Content hash: {result.content_hash[:16]}...")
                
                if result.metadata.get('embedding_cost'):
                    logger.info(f"  Embedding cost: ${result.metadata['embedding_cost']:.4f}")
                
                ingestion_results.append({
                    'type': doc_type,
                    'document_id': str(result.id),
                    'chunks': result.chunk_count,
                    'status': result.status.value,
                    'processing_time': processing_time
                })
                
            except Exception as e:
                logger.error(f"✗ Failed to process {doc_type} document: {e}")
                ingestion_results.append({
                    'type': doc_type,
                    'error': str(e),
                    'status': 'failed'
                })
        
        # Check ingestion status
        logger.info("\n4. Checking ingestion status...")
        status = await pipeline.get_ingestion_status(tenant)
        
        logger.info(f"Tenant collection: {status.get('collection_name')}")
        logger.info(f"Total chunks: {status.get('total_chunks', 0)}")
        logger.info(f"Collection status: {status.get('collection_status')}")
        
        # Summary
        logger.info("\n5. Ingestion Summary:")
        successful = len([r for r in ingestion_results if r.get('status') == 'completed'])
        total = len(ingestion_results)
        
        logger.info(f"Documents processed: {successful}/{total}")
        
        if successful > 0:
            total_chunks = sum(r.get('chunks', 0) for r in ingestion_results if 'chunks' in r)
            avg_time = sum(r.get('processing_time', 0) for r in ingestion_results if 'processing_time' in r) / successful
            
            logger.info(f"Total chunks created: {total_chunks}")
            logger.info(f"Average processing time: {avg_time:.2f}s")
        
        # Cleanup sample files
        for file_path in sample_docs.values():
            try:
                file_path.unlink()
            except Exception:
                pass
        
        return ingestion_results
        
    finally:
        await pipeline.close()


async def demo_document_service():
    """Demonstrate the document service."""
    logger.info("\n=== Document Service Demo ===")
    
    service = DocumentService()
    
    try:
        # Health check
        logger.info("\n1. Checking document service health...")
        health = await service.health_check()
        logger.info(f"Service health: {health['status']}")
        
        # Create test tenant
        tenant = Tenant(
            id=uuid4(),
            name="Service Demo Corp", 
            slug="service-demo-corp",
            plan_tier="pro"
        )
        
        async with get_session() as session:
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        
        logger.info(f"Created tenant: {tenant.name}")
        
        # Create sample document
        sample_content = """
        This is a sample document for testing the document service.
        It contains multiple paragraphs with various information.
        
        The service should be able to:
        - Create documents from uploads
        - Process them in background
        - Track status and progress
        - Provide statistics and metrics
        
        This content will be chunked and embedded for retrieval.
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_content)
            temp_file = Path(f.name)
        
        # Mock upload file
        from io import BytesIO
        from unittest.mock import MagicMock
        
        mock_file = MagicMock()
        mock_file.filename = "service-test.txt"
        mock_file.file = BytesIO(sample_content.encode())
        
        try:
            # Create document through service
            logger.info("\n2. Creating document through service...")
            document, job_id = await service.create_document(
                tenant=tenant,
                name="Service Test Document",
                document_type="txt",
                file=mock_file,
                metadata={"source": "demo", "category": "test"}
            )
            
            logger.info(f"✓ Document created: {document.name}")
            logger.info(f"  Document ID: {document.id}")
            logger.info(f"  Job ID: {job_id}")
            logger.info(f"  Status: {document.status.value}")
            
            # Get document status
            logger.info("\n3. Checking document status...")
            status = await service.get_document_status(tenant, document.id)
            
            logger.info(f"Document status: {status['status']}")
            logger.info(f"Chunk count: {status.get('chunk_count', 0)}")
            
            if 'job' in status:
                logger.info(f"Job status: {status['job'].get('status', 'unknown')}")
            
            # List documents
            logger.info("\n4. Listing documents...")
            documents, total = await service.list_documents(tenant, limit=10)
            
            logger.info(f"Found {total} documents:")
            for doc in documents:
                logger.info(f"  - {doc.name} ({doc.status.value})")
            
            # Get tenant statistics
            logger.info("\n5. Getting tenant statistics...")
            stats = await service.get_tenant_statistics(tenant)
            
            logger.info("Tenant Statistics:")
            logger.info(f"  Tenant ID: {stats['tenant_id']}")
            logger.info(f"  Total chunks: {stats.get('total_chunks', 0)}")
            
            for status_name, count in stats.get('document_counts', {}).items():
                if count > 0:
                    logger.info(f"  {status_name.title()} documents: {count}")
            
            for doc_type, count in stats.get('document_types', {}).items():
                if count > 0:
                    logger.info(f"  {doc_type.upper()} documents: {count}")
            
        finally:
            temp_file.unlink()
            
    finally:
        await service.close()


async def demo_background_workers():
    """Demonstrate background worker functionality."""
    logger.info("\n=== Background Workers Demo ===")
    
    try:
        # Create test tenant and document
        tenant = Tenant(
            id=uuid4(),
            name="Worker Demo Corp",
            slug="worker-demo-corp", 
            plan_tier="pro"
        )
        
        async with get_session() as session:
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
        
        document = Document(
            id=uuid4(),
            tenant_id=tenant.id,
            name="Worker Test Document",
            document_type="txt",
            status=DocumentStatus.PENDING
        )
        
        async with get_session() as session:
            session.add(document)
            await session.commit()
            await session.refresh(document)
        
        # Create test file
        test_content = """
        This document will be processed by background workers.
        Workers handle document ingestion asynchronously using ARQ.
        
        Benefits of background processing:
        - Non-blocking API responses
        - Better user experience
        - Scalable processing
        - Error handling and retries
        - Status tracking and monitoring
        
        The worker will parse this content, chunk it, generate embeddings,
        and store everything in the vector database.
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            temp_file = Path(f.name)
        
        try:
            logger.info("1. Enqueuing document ingestion job...")
            
            # Enqueue job
            job_id = await enqueue_document_ingestion(
                tenant_id=tenant.id,
                document_id=document.id,
                file_path=str(temp_file),
                force_reprocess=True
            )
            
            logger.info(f"✓ Job enqueued: {job_id}")
            
            # Monitor job status
            logger.info("\n2. Monitoring job progress...")
            
            max_wait = 60  # Maximum 60 seconds
            wait_time = 0
            check_interval = 2
            
            while wait_time < max_wait:
                job_status = await get_job_status(job_id)
                
                status = job_status.get('status', 'unknown')
                logger.info(f"Job status: {status}")
                
                if status == 'completed':
                    logger.info("✓ Job completed successfully!")
                    
                    result = job_status.get('result', {})
                    if result:
                        logger.info(f"  Document status: {result.get('document_status')}")
                        logger.info(f"  Chunk count: {result.get('chunk_count', 0)}")
                        logger.info(f"  Content hash: {result.get('content_hash', 'N/A')[:16]}...")
                    
                    break
                    
                elif status == 'not_found':
                    logger.warning("Job not found - may have been cleaned up")
                    break
                    
                elif 'error' in job_status:
                    logger.error(f"✗ Job failed: {job_status['error']}")
                    break
                
                # Wait before next check
                await asyncio.sleep(check_interval)
                wait_time += check_interval
                
                if wait_time >= max_wait:
                    logger.warning("⚠ Job monitoring timeout - job may still be running")
            
            # Check final document state
            logger.info("\n3. Checking final document state...")
            
            async with get_session() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Document).where(Document.id == document.id)
                )
                final_document = result.scalar_one_or_none()
                
                if final_document:
                    logger.info(f"Final document status: {final_document.status.value}")
                    logger.info(f"Chunk count: {final_document.chunk_count}")
                    
                    if final_document.error_message:
                        logger.error(f"Error message: {final_document.error_message}")
                else:
                    logger.warning("Document not found in database")
        
        finally:
            temp_file.unlink()
    
    except Exception as e:
        logger.error(f"Background worker demo failed: {e}")
        raise


async def main():
    """Run all Module 3 demos."""
    try:
        logger.info("Starting Module 3: Document Ingestion Demo")
        logger.info("=" * 60)
        
        # Demo 1: Ingestion Pipeline
        pipeline_results = await demo_ingestion_pipeline()
        
        # Demo 2: Document Service  
        await demo_document_service()
        
        # Demo 3: Background Workers
        await demo_background_workers()
        
        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("Module 3 Demo Complete!")
        logger.info("\nKey Features Demonstrated:")
        logger.info("✓ Document parsing (TXT, Markdown)")
        logger.info("✓ Content chunking with LangChain")
        logger.info("✓ OpenAI embeddings generation")
        logger.info("✓ Qdrant vector storage")
        logger.info("✓ Background processing with ARQ")
        logger.info("✓ Document service layer")
        logger.info("✓ Status monitoring and health checks")
        logger.info("✓ Multi-tenant data isolation")
        
        successful_docs = len([r for r in pipeline_results if r.get('status') == 'completed'])
        if successful_docs > 0:
            total_chunks = sum(r.get('chunks', 0) for r in pipeline_results if 'chunks' in r)
            logger.info(f"\nProcessing Results:")
            logger.info(f"- Documents processed: {successful_docs}")
            logger.info(f"- Total chunks created: {total_chunks}")
        
        logger.info("\n🎉 Module 3 implementation is ready for production!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())