# alembic/versions/0003_add_user_role.py
"""Add role column to users table.

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01 00:00:02.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add role column to users table.

    The role column is a VARCHAR that can be either 'user' or 'admin'.
    Default value is 'user' for all existing and new users.

    Note: We use VARCHAR instead of native ENUM for better portability
    across database systems (PostgreSQL, SQLite for testing).
    """
    # Add role column with default value
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=10),
            nullable=False,
            server_default="user",
        ),
    )

    # Create index on role for efficient role-based queries
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)


def downgrade() -> None:
    """Remove role column from users table."""
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "role")

