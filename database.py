from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator
import asyncio
import logging
from dotenv import load_dotenv
import os
import streamlit as st

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL") or st.secrets.get("DATABASE_URL")

# Create async engine with proper connection pool settings
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    # Connection pool settings
    pool_size=10,                    # Number of connections to maintain in pool
    max_overflow=20,                 # Additional connections beyond pool_size
    pool_recycle=3600,              # Recycle connections after 1 hour
    pool_pre_ping=True,             # Test connections before use
    pool_timeout=30,                # Timeout when getting connection from pool
    # Additional asyncpg-specific settings
    connect_args={
        "server_settings": {
            "application_name": "preptab_backend",
        },
        "command_timeout": 60,       # Command timeout in seconds
        "statement_cache_size": 0,   # Disable statement cache to avoid issues
    }
)

# Create async session maker
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,                # Don't auto-flush to avoid unexpected queries
)

# Base class for models
Base = declarative_base()

# Dependency to get DB session with proper error handling
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session = None
    try:
        session = AsyncSessionLocal()
        yield session
    except Exception as e:
        if session:
            await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        if session:
            await session.close()

# Health check function
async def check_database_connection():
    """Check if database connection is healthy"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# Graceful engine disposal
async def close_db_connection():
    """Close database connections gracefully"""
    await engine.dispose()