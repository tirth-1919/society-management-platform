"""Temporary, read-only account audit CLI for the approved Render database."""

import csv
import io

import click
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.models import Society, User, db


# Pin the command to the Render database target confirmed for this audit.
EXPECTED_DB_HOST = "dpg-dbooe60u01pc73fua630-a.oregon-postgres.render.com"
EXPECTED_DB_NAME = "society_maintenance_o32j"


def register_account_audit_command(app):
    @app.cli.command("audit-accounts")
    def audit_accounts():
        """Print account metadata from the approved Render DB, read-only."""
        database_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        normalized_host = (database_url.host or "").lower().rstrip(".")
        configured_database = (database_url.database or "").lstrip("/")

        if (
            database_url.get_backend_name() != "postgresql"
            or normalized_host != EXPECTED_DB_HOST
            or configured_database != EXPECTED_DB_NAME
        ):
            raise click.ClickException(
                "Audit aborted: configured database is not the approved Render PostgreSQL target."
            )

        click.echo(
            f"Configured target: PostgreSQL host={EXPECTED_DB_HOST}, "
            f"database={EXPECTED_DB_NAME}"
        )

        engine = db.engine
        headers = (
            "id",
            "full_name",
            "username",
            "mobile",
            "email",
            "role",
            "society_name",
            "account_status",
            "password_hash_present",
        )
        statement = (
            select(
                User.id,
                User.full_name,
                User.username,
                User.mobile,
                User.email,
                User.role,
                Society.name.label("society_name"),
                User.account_status,
                (
                    User.password_hash.is_not(None)
                    & (func.length(func.trim(User.password_hash)) > 0)
                ).label("password_hash_present"),
            )
            .outerjoin(Society, User.society_id == Society.id)
            .order_by(User.id)
        )

        connection = engine.connect()
        transaction = None
        try:
            transaction = connection.begin()
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")

            actual_database = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()
            if actual_database != EXPECTED_DB_NAME:
                raise click.ClickException(
                    "Audit aborted: connected database name does not match the approved target."
                )

            rows = connection.execute(statement).mappings().all()
            output = io.StringIO()
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row[column] for column in headers])
            click.echo(output.getvalue(), nl=False)
            click.echo(f"Account count: {len(rows)}")
        except click.ClickException:
            raise
        except Exception:
            raise click.ClickException(
                "Audit failed; database error details were suppressed."
            ) from None
        finally:
            if transaction is not None and transaction.is_active:
                transaction.rollback()
            connection.close()
