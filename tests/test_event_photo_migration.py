import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def _load_migration(filename: str):
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / filename
    )
    spec = importlib.util.spec_from_file_location(
        filename.replace(".py", ""), migration_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_event_media_type_migration_upgrade_and_downgrade():
    """Verify 20260816_event_media_type works on SQLite without syntax errors."""
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE event_photos ("
                "id INTEGER PRIMARY KEY, "
                "society_id INTEGER NOT NULL, "
                "event_id INTEGER NOT NULL, "
                "uploaded_by_user_id INTEGER NOT NULL, "
                "file_path VARCHAR(255) NOT NULL, "
                "filename VARCHAR(255) NOT NULL, "
                "status VARCHAR(20) NOT NULL DEFAULT 'PENDING'"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO event_photos "
                "(id, society_id, event_id, uploaded_by_user_id, file_path, filename) "
                "VALUES (1, 1, 1, 1, '/uploads/test.jpg', 'test.jpg')"
            )
        )

        migration = _load_migration("20260816_event_media_type.py")
        migration.op = Operations(MigrationContext.configure(conn))

        # Upgrade
        migration.upgrade()

        insp = inspect(conn)
        columns = {c["name"]: c for c in insp.get_columns("event_photos")}
        assert "media_type" in columns
        assert columns["media_type"]["nullable"] is False

        indexes = {i["name"] for i in insp.get_indexes("event_photos")}
        assert "ix_event_photos_media_type" in indexes

        rows = conn.execute(
            text("SELECT id, filename, media_type FROM event_photos")
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "PHOTO"

        # Downgrade
        migration.downgrade()
        insp = inspect(conn)
        columns = {c["name"] for c in insp.get_columns("event_photos")}
        assert "media_type" not in columns

        # Re-upgrade
        migration.upgrade()
        insp = inspect(conn)
        columns = {c["name"]: c for c in insp.get_columns("event_photos")}
        assert "media_type" in columns
