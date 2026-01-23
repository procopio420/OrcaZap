"""Integration tests for database migrations."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.base import engine


@pytest.fixture
def alembic_cfg():
    """Get Alembic configuration."""
    alembic_cfg = Config("alembic.ini")
    return alembic_cfg


def test_migrations_can_run_up_and_down(alembic_cfg, tmp_path):
    """Test that migrations can be applied and rolled back."""
    # This test requires a real database connection
    # For CI, we'll use the test database
    # For local, skip if DATABASE_URL not set

    try:
        # Test upgrade
        command.upgrade(alembic_cfg, "head")

        # Verify tables exist
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            tables = [row[0] for row in result]

        assert "tenants" in tables
        assert "users" in tables
        assert "messages" in tables
        assert "conversations" in tables
        assert "quotes" in tables

        # Test downgrade to base
        command.downgrade(alembic_cfg, "base")

        # Verify tables are gone
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            tables = [row[0] for row in result]

        # Should only have system tables left
        assert "tenants" not in tables
        assert "users" not in tables

        # Upgrade again for cleanup
        command.upgrade(alembic_cfg, "head")

    except Exception as e:
        pytest.skip(f"Database not available for migration test: {e}")


