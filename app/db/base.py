"""Database base and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import settings

# Configure connection pooling for production
# pool_size: number of connections to keep open
# max_overflow: additional connections that can be created on demand
# pool_timeout: seconds to wait before giving up on getting a connection
# pool_recycle: seconds before recycling a connection (prevent stale connections)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.debug,
    pool_size=10,  # Base pool size
    max_overflow=20,  # Additional connections on demand
    pool_timeout=30,  # Wait up to 30s for a connection
    pool_recycle=3600,  # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


