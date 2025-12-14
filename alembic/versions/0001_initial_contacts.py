# alembic/versions/0001_initial_contacts.py
"""Initial contacts table.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create contacts table."""
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("birthday", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contacts_birthday"), "contacts", ["birthday"], unique=False)
    op.create_index(
        "ix_contacts_birthday_month_day", "contacts", ["birthday"], unique=False
    )
    op.create_index(op.f("ix_contacts_email"), "contacts", ["email"], unique=True)
    op.create_index(
        op.f("ix_contacts_first_name"), "contacts", ["first_name"], unique=False
    )
    op.create_index(
        op.f("ix_contacts_last_name"), "contacts", ["last_name"], unique=False
    )
    op.create_index(op.f("ix_contacts_phone"), "contacts", ["phone"], unique=False)


def downgrade() -> None:
    """Drop contacts table."""
    op.drop_index(op.f("ix_contacts_phone"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_last_name"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_first_name"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_email"), table_name="contacts")
    op.drop_index("ix_contacts_birthday_month_day", table_name="contacts")
    op.drop_index(op.f("ix_contacts_birthday"), table_name="contacts")
    op.drop_table("contacts")

