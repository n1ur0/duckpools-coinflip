"""Database module for DuckPools bankroll management."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Numeric, BigInteger, DateTime, Boolean, Integer, Index, Text
from datetime import datetime
from decimal import Decimal

__all__ = ["Base", "engine", "AsyncSessionLocal", "get_db"]


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    
    pass


# Async engine configuration
engine = create_async_engine(
    "postgresql+asyncpg://user:password@localhost:5432/duckpools",
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=async_sessionmaker,
    expire_on_commit=False,
)


async def get_db():
    """Dependency injection for database sessions.
    
    Yields:
        AsyncSession: Database session for request handling.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
