"""
Pytest configuration and fixtures.
"""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base import Base, get_db
from app.db.models import Tenant
from app.main import app

# Test database URL
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/askdocs", "/askdocs_test")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,  # Don't use connection pooling in tests
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async with test_engine.connect() as connection:
        # Begin a transaction
        transaction = await connection.begin()
        
        # Create session bound to the connection
        Session = sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async with Session() as session:
            yield session
            
        # Rollback transaction
        await transaction.rollback()


@pytest.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    
    # Override get_db dependency
    async def get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = get_test_db
    
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
async def test_tenant(db_session) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant-" + str(uuid4())[:8],
        qdrant_collection_name=f"test_collection_{str(uuid4()).replace('-', '_')}",
        subscription_status="active",
        subscription_tier="pro",
    )
    
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    
    return tenant