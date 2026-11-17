"""Fix moderation foreign key ondelete and remove duplicate categories slug index

Revision ID: 20261117_04
Revises: 20261117_03
Create Date: 2026-11-17 19:25:00.000000

"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '20261117_04'
down_revision: Union[str, None] = '20261117_03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Remove duplicate unique index on categories.slug (kept uq_categories_slug)
    op.drop_index('ix_categories_slug', table_name='categories')

    # 2. Change posts.moderated_by foreign key from ON DELETE SET NULL to ON DELETE RESTRICT
    # This prevents deleting an admin who performed moderation, preserving audit trail integrity
    # and preventing conflict with ck_posts_moderation check constraint.
    op.drop_constraint('fk_posts_moderated_by', 'posts', type_='foreignkey')
    op.create_foreign_key(
        'fk_posts_moderated_by',
        'posts',
        'users',
        ['moderated_by'],
        ['id'],
        ondelete='RESTRICT'
    )


def downgrade() -> None:
    # 1. Revert posts.moderated_by foreign key to ON DELETE SET NULL
    op.drop_constraint('fk_posts_moderated_by', 'posts', type_='foreignkey')
    op.create_foreign_key(
        'fk_posts_moderated_by',
        'posts',
        'users',
        ['moderated_by'],
        ['id'],
        ondelete='SET NULL'
    )

    # 2. Re-create index on categories.slug
    op.create_index('ix_categories_slug', 'categories', ['slug'], unique=True)
