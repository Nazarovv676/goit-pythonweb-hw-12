# alembic/versions/0002_add_users_and_contact_owner.py
"""Add users table and contact owner relationship.

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add users table and user_id foreign key to contacts.

    Migration strategy for existing data:
    1. Create users table
    2. Add user_id column as nullable first
    3. Create a default user for any existing contacts (if any)
    4. Update existing contacts to reference the default user
    5. Make user_id non-nullable
    6. Add foreign key constraint
    """
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # Add user_id column to contacts as nullable first
    op.add_column(
        "contacts",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    # Check if there are existing contacts without a user
    # For fresh databases, this does nothing
    # For databases with existing contacts, we need to handle them
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT COUNT(*) FROM contacts WHERE user_id IS NULL"))
    orphan_count = result.scalar()

    if orphan_count and orphan_count > 0:
        # Create a migration user to own orphaned contacts
        # Using bcrypt hash of 'migration_password_change_me'
        migration_password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.S3NmTt.YMPYxZG"
        connection.execute(
            sa.text(
                "INSERT INTO users (email, hashed_password, full_name, is_active, is_verified) "
                "VALUES ('migration@system.local', :pwd, 'Migration User', true, true)"
            ),
            {"pwd": migration_password_hash},
        )

        # Get the migration user's ID
        result = connection.execute(
            sa.text("SELECT id FROM users WHERE email = 'migration@system.local'")
        )
        migration_user_id = result.scalar()

        # Update orphaned contacts
        connection.execute(
            sa.text("UPDATE contacts SET user_id = :uid WHERE user_id IS NULL"),
            {"uid": migration_user_id},
        )

    # Now make user_id non-nullable
    op.alter_column(
        "contacts",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Create index on user_id
    op.create_index(op.f("ix_contacts_user_id"), "contacts", ["user_id"], unique=False)

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_contacts_user_id_users",
        "contacts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove users table and user_id from contacts."""
    # Drop foreign key constraint
    op.drop_constraint("fk_contacts_user_id_users", "contacts", type_="foreignkey")

    # Drop index
    op.drop_index(op.f("ix_contacts_user_id"), table_name="contacts")

    # Drop user_id column
    op.drop_column("contacts", "user_id")

    # Drop users table
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

