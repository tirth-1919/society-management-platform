import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


def _load_notification_log_migration():
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20260811_notification_log_user_fields.py"
    )
    spec = importlib.util.spec_from_file_location(
        "notification_log_migration", migration_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_log_migration_preserves_legacy_rows_and_adds_user_id():
    """The SQLite migration must retain notifications that predate user ownership."""
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE notification_logs ("
                "id INTEGER PRIMARY KEY, society_id INTEGER, "
                "recipient_mobile_or_email VARCHAR(120) NOT NULL, channel VARCHAR(20) NOT NULL, "
                "subject VARCHAR(150), message TEXT NOT NULL, status VARCHAR(20), "
                "retry_count INTEGER, created_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notification_logs "
                "(id, society_id, recipient_mobile_or_email, channel, message, status, retry_count) "
                "VALUES (1, 7, '9000000000', 'SMS', 'legacy notification', 'Sent', 0)"
            )
        )

        migration = _load_notification_log_migration()
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()

        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(notification_logs)"))
        }
        legacy_row = connection.execute(
            text(
                "SELECT recipient_mobile_or_email, message, user_id "
                "FROM notification_logs WHERE id = 1"
            )
        ).one()

    assert {"user_id", "notification_type", "billing_month", "sent_at"} <= columns
    assert legacy_row == ("9000000000", "legacy notification", None)
