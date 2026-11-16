"""Add user profile fields.

Revision ID: 0002_add_user_profile_fields
Revises: 0001_create_users
Create Date: 2026-11-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_user_profile_fields"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("phone", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
    )
    op.execute(
        "UPDATE users SET full_name = left(split_part(email, '@', 1), 100) "
        "WHERE full_name IS NULL"
    )
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=100),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "phone")
    op.drop_column("users", "full_name")
