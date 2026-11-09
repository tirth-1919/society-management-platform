
"""Add registration requests and user fields.

Revision ID: c32a0ce0c443
Revises:
Create Date: 2026-08-11 12:42:19.896615
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c32a0ce0c443"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # This root revision also serves as the schema bootstrap for a brand-new
    # installation. checkfirst=True only creates missing tables; it never
    # drops, recreates, or alters existing tables (including the three
    # application-specific residents columns maintained outside the model).
    # Existing partial tables are handled by explicit revisions below or must
    # be reviewed manually before upgrade.
    from app.models import db

    db.metadata.create_all(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        raise RuntimeError(
            "Required table 'users' does not exist."
        )

    # Check whether username is already unique.
    unique_constraints = inspector.get_unique_constraints("users")
    unique_indexes = inspector.get_indexes("users")

    username_already_unique = any(
        item.get("column_names") == ["username"]
        for item in unique_constraints
    ) or any(
        item.get("unique")
        and item.get("column_names") == ["username"]
        for item in unique_indexes
    )

    # Avoid creating a duplicate PostgreSQL unique constraint.
    if username_already_unique:
        print(
            "[MIGRATION] Username uniqueness already exists. Skipping."
        )
        return

    duplicate_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT username FROM users WHERE username IS NOT NULL "
            "GROUP BY username HAVING COUNT(*) > 1"
            ") AS duplicates"
        )
    ).scalar_one()
    if duplicate_count:
        raise RuntimeError(
            f"Found {duplicate_count} duplicate username groups. "
            "Resolve them manually before applying the username constraint. "
            "No user records were changed."
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_users_username",
            ["username"],
        )


def downgrade():
    # The root revision may have bootstrapped the full schema or adopted an
    # existing schema. Dropping the username rule or any table is unsafe.
    pass
